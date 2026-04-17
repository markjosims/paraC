"""
Implements the `FstOrchestrator`, which orchestrates
the `InventoryRegistry`, `PatternRegistry` and `RuleRegistry`
classes. The FstOrchestrator's primary role is to compile FSAs
and FSTs based on user-defined inventory, patterns and rules,
and provides functions for other classes like `FeatureMarkers`
or `Paradigm` to compile FSTs as well.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from copy import deepcopy
from typing import Literal
import unicodedata
from loguru import logger
import pynini
from pynini.lib import rewrite
from src.constants import EXAMPLE_CONFIG_DIR

from src.fst_utils import Acceptor, Prefix, ReservedSymbolMixin, Suffix, FsaLike
from src.grammar.classes import Orchestrator
from src.grammar.registry.inventory_registry import InventoryItem, InventoryRegistry
from src.grammar.registry.pattern_registry import Pattern, PatternRegistry
from src.grammar.registry.rule_registry import Rule, RuleRegistry, AnonymousRule
from src.grammar.orchestrator.feature_orchestrator import (
    stringify_features,
    FeatureOrchestrator,
)


class FstOrchestrator(Orchestrator, ReservedSymbolMixin):
    """
    Orchestrates the compilation of inventory items, patterns and rules into FSTs.
    Constructs the `InventoryRegistry`, `PatternRegistry` and `RuleRegistry` objects
    from YAML data.

    Takes an optional (pre-initialized) `FeatureValuesRegistry` class as well. If passed,
    adds symbols for every feature and value to the inventory (see below).

    The FST registry is initialized in the following stages:
    1. `self._init`: Construct all three registry classes
        from YAML data.
    2. `self._add_feature_flags` (Optional): If a `FeatureValuesRegistry` is provided,
        add flags for all feature values to `InventoryRegistry.flags` before
        compiling any FSMs.
    3. `self._build_symbol_table()`: Build a `pynini.symbol_table` object with
        every phone and flag in the inventory, also including all reserved symbols.
    4. `self._build_boundary_acceptors()`: Build FSAs for boundary symbols
        (viz. `-` for affix boundaries, `=` for clitic boundaries and `_` for periphrasis)
        as well as the BOW/EOW tokens
    5. `self._build_inventory_acceptors()`: Build FSAs for all inventory items, including
        classes, such that classes map to a union over all child nodes.
    6. `self._build_special_acceptors()`: Build the FSAs self.phone (accepting any phone),
        self.flag (accepting any flag) and self.sigma (accepting any symbol), as well as
        closures for each of these (accepting 0-inf repetitions)
    7. `self._build_token_map()`: Build a nested dictionary of tokens used internally to
        parse pattern strings.
    8. `self._build_pattern_acceptors()`: Parse every pattern string in the `PatternRegistry`
        using the Recursive Descent Parser implemented in `self._parse_pattern()`
    9. `self._build_rule_transducers()`: Parse every rule in the `RuleRegistry` using
        `self._parse_rule()`
    """

    def __init__(
        self,
        inventory_configs: dict[str, dict],
        pattern_configs: dict[str, dict],
        rule_configs: dict[str, dict],
        feature_orchestrator: FeatureOrchestrator,
    ):
        self.inventory_registry = InventoryRegistry(config_objects=inventory_configs)
        self.pattern_registry = PatternRegistry(config_objects=pattern_configs)
        self.rule_registry = RuleRegistry(config_objects=rule_configs)
        self.feature_orchestrator = feature_orchestrator

        self._symbol_table_built = False
        self._inventory_acceptors_built = False
        self._sigmas_built = False
        self._pattern_acceptors_built = False
        self._rule_transducers_built = False
        self.is_initialized = False

        if not self.inventory_registry.data:
            logger.warning(
                "Cannot compile any acceptors without an inventory, returning..."
            )
            return

        self.inventory: dict[str, InventoryItem] = self.inventory_registry.data
        self.phones: dict[str, InventoryItem] = self.inventory_registry.phones
        self.flags: dict[str, InventoryItem] = self.inventory_registry.flags
        self.classes: dict[str, InventoryItem] = self.inventory_registry.classes
        self.patterns: dict[str, Pattern] = self.pattern_registry.data
        self.patterns_sorted: tuple[Pattern, ...] = (
            self.pattern_registry.patterns_sorted
        )

        if not self.rule_registry:
            return

        self.rules: dict[str, Rule] = self.rule_registry.data
        self.rules_sorted: tuple[Rule, ...] = self.rule_registry.rules_sorted

        self.initialize()
        if not self.is_initialized:
            raise ValueError(
                "Error occurred while initializing FstRegistry, check logs."
            )

    def initialize(self):
        """
        Initializes all data in the registry, in the following order:
        - Symbol table (mapping strings to token indices used by FSMs)
        - Inventory acceptors (FSAs for each inventory item or class over items)
        - 'Sigmas' (sigma, the acceptor over all symbols, as well as phone_fsa
            and flag_fsa, acceptors over all phones and flags respectively, and
            their repsective closures.)
        - Tokens (phones, classes, special symbols to encode strings into)
        - Pattern acceptors (FSAs for each pattern config)
        - Rule transducers (FSTs for each rule config)
        """
        if self.is_initialized:
            logger.warning("FstRegistry already initialized, returning...")
            return
        self._add_feature_flags()
        self._build_symbol_table()
        self._build_boundary_acceptors()
        self._build_inventory_acceptors()
        self._build_special_acceptors()
        self._build_token_map()
        self._build_pattern_acceptors()
        self._build_rule_transducers()
        self.is_initialized = True

    def _add_feature_flags(self):
        """
        Checks if `self.feature_orchestrator` is present and, if so, adds
        feature flags to flag inventory.
        """
        if self.feature_orchestrator is None:
            return

        if self._inventory_acceptors_built:
            raise ValueError(
                "Cannot add feature flags if inventory acceptors have already been built."
            )

        for feature in self.feature_orchestrator.features.values():
            for feature_value in feature.values:
                feature_str = f"[{feature.name}={feature_value}]"
                flag = InventoryItem(feature_str, type="flag", source=feature.source)
                self.flags[feature_str] = flag

    def _build_symbol_table(self):
        """
        Creates a symbol table with a token for each phone and flag
        in the inventory, as well as special symbols.
        """
        symbols = pynini.SymbolTable()
        symbols.add_symbol(self.epsilon_ref)
        for item in self.phones.values():
            symbols.add_symbol(item.value)
        for item in self.flags.values():
            symbols.add_symbol(item.value)
        for item in self.boundary_symbols:
            symbols.add_symbol(item)
        for item in self.edit_flags:
            symbols.add_symbol(item)
        for item in self.bow_eow_flags:
            symbols.add_symbol(item)

        self.symbols = symbols
        self._symbol_table_built = True

    def _build_boundary_acceptors(self):
        """
        Build acceptors for the affix boundary token '-' and clitic boundary
        token '='
        """
        self.affix_boundary_fsa = pynini.accep(
            self.affix_boundary,
            token_type=self.symbols,
        )
        self.clitic_boundary_fsa = pynini.accep(
            self.clitic_boundary,
            token_type=self.symbols,
        )
        self.periphrasis_break_fsa = pynini.accep(
            self.periphrasis_break,
            token_type=self.symbols,
        )
        self.boundary_fsa = pynini.union(
            self.affix_boundary_fsa,
            self.clitic_boundary_fsa,
            self.periphrasis_break_fsa,
        )

        self.bow_fsa = pynini.accep(self.bow, token_type=self.symbols)
        self.eow_fsa = pynini.accep(self.eow, token_type=self.symbols)
        self.word_edge_fsa = pynini.union(self.bow_fsa, self.eow_fsa)

    def _build_inventory_acceptors(self):
        """
        Before any patterns can be parsed, all InventoryItems must be compiled with acceptors.
        """
        for item in self.phones.values():
            acceptor = pynini.accep(item.value, token_type=self.symbols)
            acceptor.optimize()
            item.set_acceptor(acceptor)
        for item in self.flags.values():
            acceptor = pynini.accep(item.value, token_type=self.symbols)
            acceptor.optimize()
            item.set_acceptor(acceptor)
        for item in self.classes.values():
            children = item.flatten()
            child_values = [
                pynini.accep(child.value, token_type=self.symbols)
                for child in children
                if isinstance(child, InventoryItem)
            ]
            acceptor = pynini.union(*child_values)
            acceptor.optimize()
            item.set_acceptor(acceptor)
        self._inventory_acceptors_built = True

    def update_flags(self, flags: list[InventoryItem]):
        logger.info(f"Adding {len(flags)} flags to inventory...")
        self._inventory_acceptors_built = False
        self._sigmas_built = False

        for flag in flags:
            self._add_flag(flag)
        self._inventory_acceptors_built = True

        logger.info("Flags added successfully.")

    def _add_flag(self, flag: InventoryItem) -> int:
        if flag.value in self.flags:
            error = f"{flag.value} already found in self.flags"
            raise KeyError(error)
        self.flags[flag.value] = flag

        symbol_index: int = self.symbols.add_symbol(flag.value)
        fsa = pynini.accep(flag.value, token_type=self.symbols)
        fsa.optimize()
        flag.set_acceptor(fsa)
        return symbol_index

    def _build_special_acceptors(self):
        if not self._inventory_acceptors_built:
            raise ValueError(
                "Cannot build special acceptors if inventory acceptors are not initialized."
            )
        if not self.phones:
            raise ValueError(
                "Cannot build FstRegistry without any phones in inventory, "
                "but no phones found. Check inventory config files."
            )
        phone_fsa = pynini.union(*[phone.fsa for phone in self.phones.values()])
        phone_fsa.optimize()

        # unlike phones, an inventory may have zero flags
        # in which case the flag_fsa is just the empty language
        if self.flags:
            flag_fsa = pynini.union(*[flag.fsa for flag in self.flags.values()])
        else:
            flag_fsa = pynini.accep("")
        flag_fsa.optimize()

        sigma = pynini.union(phone_fsa, flag_fsa, self.boundary_fsa, self.word_edge_fsa)
        sigma.optimize()

        self.phone_fsa = phone_fsa
        self.flag_fsa = flag_fsa
        self.sigma = sigma

        self.phone_star = phone_fsa.star.optimize()
        self.flag_star = flag_fsa.star.optimize()
        self.sigma_star = sigma.star.optimize()
        self._sigmas_built = True

    def _token_acceptor(self, token_str: str) -> Acceptor:
        """
        Builds an acceptor for a single token.
        """
        if not self._sigmas_built:
            raise ValueError(
                "Cannot call `_token_acceptor` until universal FSAs "
                "('sigmas') are built using `self._build_sigmas()`"
            )

        if token_str == self.dot:
            fsa = self.sigma
        elif token_str == self.phone_ref:
            fsa = self.phone_fsa
        elif token_str == self.flag_ref:
            fsa = self.flag_fsa
        elif token_str == self.sigma_ref:
            fsa = self.sigma
        elif token_str == self.affix_boundary:
            fsa = self.affix_boundary_fsa
        elif token_str == self.clitic_boundary:
            fsa = self.clitic_boundary_fsa
        elif token_str == self.boundary_ref:
            fsa = self.boundary_fsa
        elif token_str == self.bow:
            fsa = self.bow_fsa
        elif token_str == self.eow:
            fsa = self.eow_fsa
        elif token_str == self.word_edge:
            fsa = self.word_edge_fsa
        elif self.symbols.find(token_str) == -1:
            raise KeyError("Token not found in symbol table")
        else:
            fsa = pynini.accep(token_str, token_type=self.symbols)
        acceptor = Acceptor(value=token_str)
        acceptor.set_acceptor(fsa)
        return acceptor

    def _build_token_map(self):
        # store tokens as a dict mapping token type to list of token values
        # acting as an incomplete Aho-Corasick trie for tokenization of pattern strings
        tokens = defaultdict(list)

        dot_acceptor = self._token_acceptor(self.dot)
        tokens["dot"].append(
            Token(value=self.dot, type="special_ref", acceptor=dot_acceptor)
        )
        for l_delimiter in self.left_delimiters:
            tokens["left_delimiter"].append(
                Token(value=l_delimiter, type="left_delimiter")
            )
        for r_delimiter in self.right_delimiters:
            tokens["right_delimiter"].append(
                Token(value=r_delimiter, type="right_delimiter")
            )
        for op in self.unary_operators:
            tokens["unary_operator"].append(Token(value=op, type="unary_operator"))
        for op in self.pipe_operator:
            tokens["pipe_operator"].append(Token(value=op, type="pipe_operator"))
        for op in self.caret_operator:
            tokens["caret_operator"].append(Token(value=op, type="caret_operator"))
        for ref in self.reserved_refs:
            acceptor = self._token_acceptor(ref)
            tokens["ref"].append(
                Token(value=ref, type="special_ref", acceptor=acceptor)
            )
        for flag in self.bow_eow_flags:
            acceptor = self._token_acceptor(flag)
            tokens["flag"].append(Token(value=flag, type="bow_eow", acceptor=acceptor))
        for flag in self.edit_flags:
            acceptor = self._token_acceptor(flag)
            tokens["flag"].append(
                Token(value=flag, type="edit_flag", acceptor=acceptor)
            )
        for boundary in self.boundary_symbols:
            acceptor = self._token_acceptor(boundary)
            tokens["boundary"].append(
                Token(value=boundary, type="boundary", acceptor=acceptor)
            )
        for phone, phone_obj in self.phones.items():
            tokens["phone"].append(Token(value=phone, type="phone", acceptor=phone_obj))
        for flag, flag_obj in self.flags.items():
            tokens["flag"].append(Token(value=flag, type="flag", acceptor=flag_obj))
        for class_ref, class_obj in self.classes.items():
            tokens["ref"].append(
                Token(value=class_ref, type="class_ref", acceptor=class_obj)
            )
        for pattern_ref, pattern_obj in self.patterns.items():
            tokens["ref"].append(
                Token(value=pattern_ref, type="pattern_ref", acceptor=pattern_obj)
            )

        # sort tokens by length in descending order so that longest matches
        # are found first during tokenization
        for token_type, token_list in tokens.items():
            token_list = sorted(token_list, key=lambda t: len(t), reverse=True)
            tokens[token_type] = token_list
        self.tokens: dict[str, list[Token]] = tokens

    def _infer_token_type(self, input_str: str) -> str | None:
        """
        Token type can be inferred from the first character of the token string:
        - '[' -> flag
        - '<' -> ref
        - operators and delimiters are single characters that can be looked up in a set
        """
        if not input_str:
            raise ValueError("Cannot infer token type from empty string")

        starting_char = input_str[0]
        # greedily use hashmap to find phone from starting char
        # some phones will be multiple characters though, which is
        # why we return 'phone' as default at the end
        if self.phones.get(starting_char):
            return "phone"
        elif starting_char == "[":
            return "flag"
        elif starting_char == "<":
            return "ref"
        elif starting_char in self.unary_operators:
            return "unary_operator"
        elif starting_char == self.pipe_operator:
            return "pipe_operator"
        elif starting_char == self.caret_operator:
            return "caret_operator"
        elif starting_char in self.left_delimiters:
            return "left_delimiter"
        elif starting_char in self.right_delimiters:
            return "right_delimiter"
        elif starting_char in self.boundary_symbols:
            return "boundary"
        elif starting_char == self.dot:
            return "dot"
        # defaulting to "phone" will not cause any false positives
        # as the string will be checked against the phone registry later
        # since this function just tells `_tokenize_str` which token dictionary
        # to check the current substring against
        return "phone"

    def _build_pattern_acceptors(self):
        """
        Parse patterns using recursive descent.
        """
        for pattern in self.patterns_sorted:
            acceptor = self._parse_pattern(pattern.value)
            pattern.set_acceptor(acceptor)
        self._pattern_acceptors_built = True

    def _build_rule_transducers(self):
        """
        Parse each rule in `self.rules_sorted`
        """
        for rule in self.rules_sorted:
            rule_transducer = self._parse_rule(rule)
            rule.set_transducer(rule_transducer)
        self._rule_transducers_built = True

    def _parse_rule(
        self, rule: Rule, lexical_features: dict[str, str] = None
    ) -> pynini.Fst | list[pynini.Fst]:
        """
        Constructs all acceptors and transducers needed for a context-sensitive
        rule and returns the rule transducer or list of transducers (for a rule
        sequence)
        """
        left_context = None
        if lexical_features:
            left_context = self.lexical_feature_left_context(lexical_features)
        if rule.type == "rule_sequence":
            # return list of FSTs
            # sub-rules may themselves be rule sequences, so need to flatten
            rules_flat = []
            for subrule in rule.rule_sequence:
                if not subrule.rule_sequence:
                    rules_flat.append(subrule)
                else:
                    rules_flat.extend(subrule.rule_sequence)

            if left_context:
                # need to re-parse each rule using the new left context
                rule_fsts_flat = []
                for subrule in rules_flat:
                    subrule = deepcopy(subrule)
                    if subrule.left_context:
                        subrule_left_context = self.concatenate_acceptors(
                            left_context, subrule.left_context
                        )
                    else:
                        subrule_left_context = left_context
                    subrule.left_context = left_context
                    new_rule = self._parse_rule(subrule)
                    if not isinstance(new_rule, pynini.Fst):
                        raise ValueError(
                            f"Expected subrule to return a single FST on compilation, got {type(subrule)}"
                        )
                    rule_fsts_flat.append(new_rule)
            else:
                rule_fsts_flat = [subrule.fst for subrule in rules_flat]

            return rule_fsts_flat
        # tau = main transducer, the rational relation effected by the rule
        tau = self._parse_rule_tau(rule)
        left_context, right_context = self._parse_rule_context(rule)
        direction = rule.direction
        sigma_star = self.sigma_star
        rule_fst = pynini.cdrewrite(
            tau=tau,
            l=left_context,
            r=right_context,
            direction=direction,
            sigma_star=sigma_star,
        )
        return rule_fst

    def _parse_rule_tau(self, rule: Rule) -> pynini.Fst:
        if rule.type == "simple_rule":
            input_pattern = rule.input_pattern
            if not input_pattern.acceptor_built:
                input_pattern.set_acceptor(self._parse_pattern(input_pattern.value))
            output_pattern = rule.output_pattern
            if not output_pattern.acceptor_built:
                output_pattern.set_acceptor(self._parse_pattern(output_pattern.value))
            tau = pynini.cross(input_pattern.fsa, output_pattern.fsa)
        elif rule.type == "string_map":
            transducers = []
            for input_acceptor, output_acceptor in rule.string_map:
                input_acceptor.set_acceptor(self._parse_pattern(input_acceptor.value))
                output_acceptor.set_acceptor(self._parse_pattern(output_acceptor.value))
                transducer = pynini.cross(
                    input_acceptor.fsa,
                    output_acceptor.fsa,
                )
                transducers.append(transducer)
            tau = pynini.union(*transducers)
        else:
            raise ValueError(f"Cannot interpret tau for rule type {rule.type}")

        tau.optimize()

        return tau

    def _parse_rule_context(self, rule: Rule) -> tuple[pynini.Fst, pynini.Fst]:
        left_context_fsa = self._parse_pattern(rule.left_context)

        # special case: if right context is just '#' (word edge)
        # interpret as [EOS] (otherwise _parse_pattern will
        # default to [BOS] since it's at the beginning of the string)
        if rule.right_context.value == self.word_edge:
            right_context_fsa = self.eow_fsa
        else:
            right_context_fsa = self._parse_pattern(rule.right_context)

        if (
            isinstance(rule.left_context, Acceptor)
            and not rule.left_context.acceptor_built
        ):
            rule.left_context.set_acceptor(left_context_fsa)
        if (
            isinstance(rule.right_context, Acceptor)
            and not rule.right_context.acceptor_built
        ):
            rule.right_context.set_acceptor(right_context_fsa)
        return left_context_fsa, right_context_fsa

    def _parse_pattern(
        self, pattern_input: str | Acceptor | list[str] | None
    ) -> pynini.Fst:
        """
        Interprets a pattern string as an FSA.
        """
        if isinstance(pattern_input, Acceptor):
            if pattern_input.acceptor_built:
                logger.info(
                    f"Redundant call on pattern {pattern_input._ref} with existing acceptor"
                )
                return pattern_input.fsa
            pattern_input = pattern_input.value
        if not pattern_input:
            return pynini.accep("", token_type=self.symbols)
        elif isinstance(pattern_input, list):
            acceptors = []
            for sub_pattern in pattern_input:
                sub_acceptor = self._parse_pattern(sub_pattern)
                acceptors.append(sub_acceptor)
            return pynini.union(*acceptors)
        try:
            tokens = self._tokenize_str(pattern_input)
            fsa = self._parse_tokens(tokens)
        except Exception as e:
            raise Exception(f"Error occurred while parsing pattern {pattern_input} ", e)

        fsa.optimize()

        return fsa

    def _preprocess_str(self, input_str: str) -> str:
        """
        Performs following normalizations:
        - Strip whitespace
        - Unicode NFKD normalization (e.g. decomposing accented characters into base character + diacritic)
        - Replace beginning '#' with [BOS] and ending '#' with [EOS]
        """
        input_str = input_str.strip()
        input_str = unicodedata.normalize("NFKD", input_str)
        if input_str.startswith(self.word_edge):
            input_str = self.bow + input_str[1:]
        if input_str.endswith(self.word_edge):
            input_str = input_str[:-1] + self.eow
        return input_str

    def _tokenize_str(self, input_str: str) -> list[Token]:
        """
        Tokenize an input string into a list of Tokens.

        Uses the token lists built in `_build_token_list` to find the longest
        matching token at each position in the input string, and infers token
        type from the token string itself (e.g. flags start with '[', refs start with '<', etc.)
        """
        input_str = self._preprocess_str(input_str)

        tokens = []
        i = 0
        while i < len(input_str):
            current_token_type = self._infer_token_type(input_str[i:])
            # Find the longest matching token
            match = None
            for token in self.tokens[current_token_type]:
                if input_str.startswith(token.value, i):
                    match = token
                    break
            if not match:
                breakpoint()
                error = f"Unrecognized token '{input_str[i:]}' starting at position {i} in string '{input_str}'"
                logger.error(error)
                raise ValueError(error)
            tokens.append(match)
            i += len(match)

        return tokens

    def _parse_tokens(self, tokens: list[Token]) -> pynini.Fst:
        """
        Parse a list of tokens into an FST.

        Uses recursive descent parsing to handle grouping and operator precedence,
        and looks up refs in the registry.

        Build acceptor as a list of FST objects, then concatenate at end.

        Recursive descent logic:
        - Expression -> Term Expression*
        - Expression* -> Factor Term*
        - Term* -> | Factor Expression*
        - Factor -> (Expression) | Ref | Atom
        - Atom -> Phone | Flag | Class | Pattern
        """
        logger.debug(f"Parsing tokens {tokens}")
        acceptor, current_index = self._parse_expression(tokens, initial_index=0)
        if current_index != len(tokens):
            raise ValueError(
                f"Tokens remaining after parsing expression for token array {tokens}"
            )
        return acceptor

    def _parse_expression(
        self,
        tokens: list[Token],
        initial_index: int,
    ) -> tuple[pynini.Fst, int]:
        """
        Parses an expression in the token array starting at `current_index`, where
        an expression is a single term or any sequence of term | term | term ...
        """
        logger.debug(
            f"Parsing expression starting at index {initial_index}, tokens {tokens}"
        )

        current_index = initial_index
        term, current_index = self._parse_term(tokens, current_index)
        terms = [term]
        while (current_index < len(tokens)) and tokens[
            current_index
        ].type == "pipe_operator":
            logger.debug(
                f"Found pipe operator at index {current_index}, tokens {tokens}, parsing next term in expression..."
            )
            current_index += 1
            current_term, current_index = self._parse_term(tokens, current_index)
            terms.append(current_term)

            if current_index == len(tokens):
                break

            current_type = tokens[current_index].type
            if current_type == "right_delimiter":
                # let parent handle
                break

        acceptor = pynini.union(*terms)
        return acceptor, current_index

    def _parse_term(
        self,
        tokens: list[Token],
        initial_index: int,
    ) -> tuple[pynini.Fst, int]:
        """
        Parses a term, i.e. a sequence of factors and unary operators of
        arbitrary length, OR a delimited expression in parentheses or curly braces.
        """
        logger.debug(f"Parsing term starting at index {initial_index}, tokens {tokens}")

        current_index = initial_index
        current_type = tokens[current_index].type
        if current_type in ("right_delimiter", "pipe_operator"):
            raise ValueError(
                f"Got unexpected token type {current_type} at start of term, tokens {tokens} current index {current_index}"
            )

        factors_w_operators = []
        while (current_index < len(tokens)) and (
            current_type not in ("right_delimiter", "pipe_operator")
        ):
            logger.debug(
                f"Parsing factor sequence starting at index {current_index}, tokens {tokens}"
            )
            factor_list, current_index = self._parse_factor_sequence(
                tokens, current_index
            )
            # check if `_parse_factor_sequence` stopped before a unary operator
            # and if so apply the operator to the last factor
            if current_index < len(tokens):
                current_type = tokens[current_index].type
                if current_type == "unary_operator":
                    logger.debug(
                        f"Found unary operator at index {current_index}, tokens {tokens}, applying to last factor in factor sequence..."
                    )
                    operator = tokens[current_index].value
                    last_factor = factor_list[-1]
                    last_factor = self._interpret_unary_operator(last_factor, operator)
                    factor_list[-1] = last_factor
                    current_index += 1
            factors_w_operators.extend(factor_list)

        if not factors_w_operators:
            raise ValueError(
                f"Empty term detected in token sequence {tokens} current index {current_index}"
            )
        if len(factors_w_operators) == 1:
            return factors_w_operators[0], current_index
        output_factor = factors_w_operators[0]
        for factor in factors_w_operators[1:]:
            output_factor = pynini.concat(output_factor, factor)
        return output_factor, current_index

    def _parse_factor_sequence(
        self,
        tokens: list[Token],
        initial_index: int,
    ) -> tuple[list[pynini.Fst], int]:
        """
        Consume tokens starting at `current_index` and until the end of the
        current factor is reached. Then return a list of acceptors for each
        token,alongside the index of the first token after the current
        factor sequence.
        """
        logger.debug(
            f"Parsing factor sequence starting at index {initial_index}, tokens {tokens}"
        )

        acceptors = []
        current_index = initial_index
        while current_index < len(tokens):
            logger.debug(
                f"Parsing factor starting at index {current_index}, tokens {tokens}"
            )
            token_acceptor = tokens[current_index].acceptor
            token_type = tokens[current_index].type
            if token_acceptor is not None and token_acceptor.acceptor_built:
                acceptors.append(token_acceptor.fsa)
                current_index += 1
            elif (
                isinstance(token_acceptor, Pattern)
                and not token_acceptor.acceptor_built
            ):
                token_val = tokens[current_index].value
                raise ValueError(
                    "Uninitialized pattern found while parsing with recursive descent. "
                    f"pattern ref {token_val} tokens {tokens} current index {current_index}. "
                    "Check topological sort for pattern objects."
                )
            elif (
                isinstance(token_acceptor, InventoryItem)
                and not token_acceptor.acceptor_built
            ):
                token_val = tokens[current_index].value
                raise ValueError(
                    "Uninitialized inventory item found while parsing with recursive descent. "
                    f"item ref {token_val} tokens {tokens} current index {current_index}. "
                )
            elif token_type == "left_delimiter":
                logger.debug(
                    f"While parsing factor sequence found left delimiter at index {current_index}, tokens {tokens}, parsing delimited factor..."
                )
                acceptor, current_index = self._parse_delimited_factor(
                    tokens, current_index
                )
                acceptors.append(acceptor)
            elif token_type in ("pipe_operator", "unary_operator", "right_delimiter"):
                # let parent function handle
                break
            else:
                raise ValueError(
                    f"Cannot parse token of type {token_type} at index {current_index} tokens {tokens}"
                )

        return acceptors, current_index

    def _parse_delimited_factor(
        self,
        tokens: list[Token],
        initial_index: int,
    ) -> tuple[pynini.Fst, int]:
        logger.debug(
            f"Parsing delimited factor starting at index {initial_index}, tokens {tokens}"
        )

        current_index = initial_index
        left_delimiter = tokens[current_index].value
        current_index += 1

        # curly braces indicate union of tokens
        if left_delimiter == r"{":
            # check if group begins with caret operator, which indicates negation of the union
            is_negated = False
            if tokens[current_index].type == "caret_operator":
                is_negated = True
                current_index += 1
            expected_right_delimiter = r"}"
            factor_list, current_index = self._parse_factor_sequence(
                tokens=tokens,
                initial_index=current_index,
            )
            if not is_negated:
                inner_expression = pynini.union(*factor_list)
            else:
                inner_expression = pynini.difference(
                    self.sigma, pynini.union(*factor_list)
                )

        # parentheses indicate a single expression
        elif left_delimiter == r"(":
            expected_right_delimiter = r")"
            inner_expression, current_index = self._parse_expression(
                tokens=tokens,
                initial_index=current_index,
            )

        else:
            raise ValueError(
                f"Unrecognized left delimiter {left_delimiter}, tokens {tokens} current index {current_index}"
            )

        current_token = tokens[current_index].value
        assert current_token == expected_right_delimiter
        current_index += 1
        return inner_expression, current_index

    def _interpret_unary_operator(self, term: pynini.Fst, operator: str) -> pynini.Fst:
        if operator == "?":
            return term.ques
        if operator == "+":
            return term.plus
        if operator == "*":
            return term.star
        raise ValueError(f"Unrecognized unary operator {operator}")

    def _cast_fsalike_to_fsa(
        self, fsa_input: FsaLike, is_word: bool = True
    ) -> pynini.Fst:
        if isinstance(fsa_input, Acceptor):
            fsa = fsa_input.fsa
        elif isinstance(fsa_input, str):
            fsa_constructor: callable[[str], pynini.Fst]
            if is_word:
                fsa_constructor = self.word_fsa
            else:
                fsa_constructor = self.fsa
            fsa = fsa_constructor(fsa_input)
        elif isinstance(fsa_input, pynini.Fst):
            fsa = fsa_input
        elif hasattr(fsa_input, "iter"):
            fsa_list = [
                self._cast_fsalike_to_fsa(input_item, is_word)
                for input_item in fsa_input
            ]
            fsa = pynini.union(*fsa_list)
        else:
            error = (
                f"Unknown type for input strs {type(fsa_input)} "
                + "Expected one of str, pynini.Fst, or Acceptor"
            )
            logger.error(error)
            raise TypeError(error)
        fsa.optimize()
        return fsa

    def fsa(self, fsa_input: str) -> pynini.Fst:
        """
        Constructs FSA for input string.
        Wraps `self.parse_pattern` but only takes a string,
        not an `Acceptor`.
        """
        if not isinstance(fsa_input, str):
            raise ValueError(f"Input to `fsa` must be a string, got {type(fsa_input)}")

        return self._parse_pattern(fsa_input)

    def wfsa(self, fsa_input: str, weight: float) -> pynini.Fst:
        """
        Wraps `self.fsa` and assigns a weight value.
        """
        fsa = self.fsa(fsa_input)
        wfsa = fsa + pynini.accep("", weight=weight)
        wfsa.optimize()
        return wfsa

    def word_fsa(self, word_str: str, prefix: str | None = None) -> pynini.Fst:
        """
        Constructs an FSA for a word, i.e. a string with [BOW] and [EOW]
        markers at the beginning and end. If a `prefix` is specified, it
        is prepended to the word **before** the [BOW] marker. This is
        typically used for lexical features that other rules may reference.
        """
        if not isinstance(word_str, str):
            raise ValueError(
                f"Input to `word_fsa` must be a string, got {type(word_str)}"
            )

        word_str = self.bow + word_str + self.eow

        if prefix and not isinstance(prefix, str):
            raise ValueError(f"`prefix` must be a string, got {type(word_str)}")
        elif prefix:
            word_str = prefix + word_str

        return self._parse_pattern(word_str)

    def wordlist_fsa(self, words: list[str]) -> pynini.Fst:
        """
        Wraps FSA constructor for list of words.
        """
        if not isinstance(words, list):
            raise ValueError("wordlist_fsa expects a list of strs.")
        word_fsas = [self.word_fsa(word) for word in words]
        wordlist_fsa = pynini.union(*word_fsas)
        wordlist_fsa.optimize()
        return wordlist_fsa

    def acceptor(
        self,
        fsa_input: str,
    ) -> Acceptor:
        """
        Given a pattern string and an uninitialized `Acceptor` class,
        return an initialized the `Acceptor` with a built FSA
        """
        fsa = self.fsa(fsa_input)
        acceptor = Acceptor(fsa_input)
        acceptor.set_acceptor(fsa)
        return acceptor

    def concatenate_acceptors(self, *acceptor_list: Acceptor) -> Acceptor:
        concat_value = ""
        concat_fsa = pynini.accep("")
        for acceptor in acceptor_list:
            if not acceptor.acceptor_built:
                raise ValueError("Cannot concatenate uninitialized Acceptor objects")
            concat_value += acceptor.value or ""
            concat_fsa += self.fsa(acceptor.fsa or "")

        concat_acceptor = Acceptor(value=concat_value)
        concat_acceptor.set_acceptor(concat_fsa)

        return concat_acceptor

    def lexical_feature_left_context(
        self, lexical_features: dict[str, str]
    ) -> Acceptor:
        """
        Creates an FSA accepting any left context where the features specified by `lexical_features`
        are present preceding the [BOW] flag.
        """
        lexical_feature_str = stringify_features(lexical_features)

        feature_sequence_acceptor_str = ""
        for feature_str in re.findall(r"(\[[^\]]\])", lexical_feature_str):
            feature_sequence_acceptor_str += feature_str

        left_context_str = (
            f"{self.bow}{self.sigma_ref}{self.star}{feature_sequence_acceptor_str}"
        )
        try:
            left_context = self.acceptor(left_context_str)
        except Exception as e:
            raise Exception(
                f"Error when parsing acceptor for {left_context_str}, check if paradigm successfully added lexical features to symbol table. "
                f"Original exception: {e}"
            )

        return left_context

    def prefix(
        self, prefix_str: str, lexical_features: dict[str, str] | None = None
    ) -> Prefix:
        """
        Returns a `Prefix` object with an initialized FST

        If lexical_features passed, pass to `left_context` kwarg
        for `Prefix.set_transducer`.
        """
        prefix = Prefix(prefix_str, stem=self.sigma_star)
        prefix_fsa = self.fsa(prefix_str)

        kwargs = {}
        if lexical_features:
            left_context = self.lexical_feature_left_context(lexical_features)
            kwargs["left_context"] = left_context
        prefix.set_transducer(prefix_fsa, self.bow_fsa, **kwargs)
        return prefix

    def suffix(
        self, suffix_str: str, lexical_features: dict[str, str] | None = None
    ) -> Suffix:
        """
        Returns a `Suffix` object with an initialized FST

        If lexical_features passed, pass to `left_context` kwarg
        for `Suffix.set_transducer`.
        """
        suffix = Suffix(suffix_str, stem=self.sigma_star)
        suffix_fsa = self.fsa(suffix_str)
        kwargs = {}
        if lexical_features:
            left_context = self.lexical_feature_left_context(lexical_features)
            kwargs["left_context"] = left_context
        suffix.set_transducer(suffix_fsa, self.eow_fsa)
        return suffix

    def replace_transducer(
        self, input_pattern: str, output_pattern: str
    ) -> AnonymousRule:
        """
        Returns a context-free anonymous Rule that replaces
        the input pattern with the output.
        """
        input_acceptor = self.acceptor(input_pattern)
        output_acceptor = self.acceptor(output_pattern)
        replace_rule = AnonymousRule(
            input_pattern=input_acceptor,
            output_pattern=output_acceptor,
        )
        rule_fst = self._parse_rule(replace_rule)
        replace_rule.set_transducer(rule_fst)
        return replace_rule

    def string_map_transducer(
        self,
        string_map: list[list[str]],
    ) -> AnonymousRule:
        """
        Returns a context-free anonymous Rule that maps each input pattern in the string map
        to its corresponding output pattern.
        """
        string_map_acceptors = []
        for input_pattern, output_pattern in string_map:
            input_acceptor = self.acceptor(input_pattern)
            output_acceptor = self.acceptor(output_pattern)
            string_map_acceptors.append((input_acceptor, output_acceptor))
        string_map_rule = AnonymousRule(
            type="string_map",
            string_map=string_map_acceptors,
        )
        rule_fst = self._parse_rule(string_map_rule)
        string_map_rule.set_transducer(rule_fst)
        return string_map_rule

    def apply_rule(self, rule_input: FsaLike, rule_ref: str) -> pynini.Fst:
        """
        Applies the rule specified by `rule_ref` to the input string or FST
        and returns the output FST.
        """
        if rule_ref not in self.rules:
            raise KeyError(f"Rule ref '{rule_ref}' not found in registry.")
        rule = self.rules[rule_ref]

        if not rule.transducer_built:
            raise ValueError(
                f"Rule '{rule_ref}' has uninitialized transducer, check logs for details."
            )

        input_fsa = self._cast_fsalike_to_fsa(rule_input, is_word=True)

        if isinstance(rule.fst, list):
            output_fst = input_fsa
            for subrule_fst in rule.fst:
                output_fst = rewrite.rewrite_lattice(
                    string=output_fst,
                    rule=subrule_fst,
                    token_type=self.symbols,
                )
                output_fst.optimize()
            return output_fst
        output_fst = rewrite.rewrite_lattice(
            string=input_fsa,
            rule=rule.fst,
            token_type=self.symbols,
        )
        output_fst.optimize()
        return output_fst

    def filter_strings_by_pattern(
        self,
        input_strs: FsaLike,
        pattern: FsaLike,
    ) -> list[str]:

        input_fsa = self._cast_fsalike_to_fsa(input_strs)
        pattern = self._cast_fsalike_to_fsa(pattern, is_word=False)

        # compute intersection of input and pattern, then get stringlist
        intersection = pynini.intersect(input_fsa, pattern)
        intersection.optimize()
        output_strs = self.fsm_strings(intersection)

        return output_strs

    def test_pattern_includes(self):
        """
        For each pattern in the registry, test that all strings in its `includes` field
        are accepted by the pattern's FSA.
        """
        for pattern in self.patterns.values():
            for test_str in pattern.test_includes:
                fsa = self.word_fsa(test_str)
                intersection = pynini.intersect(pattern.fsa, fsa)
                if intersection.start() == pynini.NO_STATE_ID:
                    raise ValueError(
                        f"Pattern '{pattern._ref}' failed includes test for string '{test_str}'. "
                        "Check that the pattern is correctly specified and that the test string is correct."
                    )

    def test_pattern_excludes(self):
        """
        For each pattern in the registry, test that all strings in its `excludes` field
        are not accepted by the pattern's FSA.
        """
        for pattern in self.patterns.values():
            for test_str in pattern.test_excludes:
                fsa = self.word_fsa(test_str)
                intersection = pynini.intersect(pattern.fsa, fsa)
                if intersection.start() != pynini.NO_STATE_ID:
                    raise ValueError(
                        f"Pattern '{pattern._ref}' failed excludes test for string '{test_str}'. "
                        "Check that the pattern is correctly specified and that the test string is correct."
                    )

    def test_pattern(
        self,
        pattern_ref: str,
        test_includes: list[str],
        test_excludes: list[str],
    ) -> dict:
        """
        Test explicit include/exclude strings against the compiled FSA for a
        single pattern.

        Returns a dict with per-string results and an overall ``all_pass`` flag::

            {"ref": "<V>", "results": [...], "all_pass": True}

        Raises ``KeyError`` if *pattern_ref* is not in the registry.
        """
        if pattern_ref not in self.patterns:
            raise KeyError(f"Pattern ref '{pattern_ref}' not found in registry.")
        pattern = self.patterns[pattern_ref]

        results: list[dict] = []
        all_pass = True

        for test_str in test_includes:
            try:
                input_fsa = self.fsa(test_str)
                intersection = pynini.intersect(pattern.fsa, input_fsa)
                passed = intersection.start() != pynini.NO_STATE_ID
            except Exception:
                passed = False
            results.append({"string": test_str, "type": "include", "pass": passed})
            if not passed:
                all_pass = False

        for test_str in test_excludes:
            try:
                input_fsa = self.word_fsa(test_str)
                intersection = pynini.intersect(pattern.fsa, input_fsa)
                passed = intersection.start() == pynini.NO_STATE_ID
            except Exception:
                passed = False
            results.append({"string": test_str, "type": "exclude", "pass": passed})
            if not passed:
                all_pass = False

        return {"ref": pattern_ref, "results": results, "all_pass": all_pass}

    def test_rule(
        self,
        rule_ref: str,
        test_mappings: list[list[str]],
    ) -> dict:
        """
        Test explicit input→output mappings against the compiled FST for a
        single rule.

        Returns a dict with per-mapping results and an overall ``all_pass`` flag::

            {"ref": "diphthongization", "results": [...], "all_pass": True}

        Raises ``KeyError`` if *rule_ref* is not in the registry.
        """
        if rule_ref not in self.rules:
            raise KeyError(f"Rule ref '{rule_ref}' not found in registry.")

        results: list[dict] = []
        all_pass = True

        for input_str, expected_output_str in test_mappings:
            output_strs = None
            try:
                output_fsa = self.apply_rule(input_str, rule_ref)
                output_fsa = pynini.project(output_fsa, project_type="output")
                expected_output_fsa = self.word_fsa(expected_output_str)
                intersection = pynini.intersect(output_fsa, expected_output_fsa)
                passed = intersection.start() != pynini.NO_STATE_ID

                output_strs = self.fsm_strings(output_fsa)
            except Exception:
                passed = False
            results.append(
                {
                    "input": input_str,
                    "output": output_strs,
                    "expected_output": expected_output_str,
                    "type": "mapping",
                    "pass": passed,
                }
            )
            if not passed:
                all_pass = False

        return {"ref": rule_ref, "results": results, "all_pass": all_pass}

    def test_rule_mappings(self):
        """
        For each rule in the registry, test that all input-output string pairs in its `test_mappings` field
        are correctly mapped by the rule's FST.
        """
        for rule in self.rules.values():
            for input_str, expected_output_str in rule.test_mappings:
                output_fsa = self.apply_rule(input_str, rule._ref)
                output_fsa = pynini.project(output_fsa, project_type="output")
                expected_output_fsa = self.word_fsa(expected_output_str)
                intersection = pynini.intersect(output_fsa, expected_output_fsa)
                if intersection.start() == pynini.NO_STATE_ID:
                    raise ValueError(
                        f"Rule '{rule._ref}' failed test mapping for input '{input_str}' and expected output '{expected_output_str}'. "
                        "Check that the rule is correctly specified and that the test mapping is correct."
                    )

    def fsm_strings_and_weights(
        self,
        fst: pynini.Fst,
        project: Literal["input", "output"] = "output",
        nshortest: int = None,
        strip_word_edge_symbols: bool = True,
        strip_all_flags: bool = False,
    ) -> list[tuple[str, float]]:

        decoded_outputs = []
        fsa = pynini.project(fst, project_type=project)
        if nshortest is not None:
            fsa = rewrite.lattice_to_nshortest(fsa, nshortest=nshortest)

        path_iter = fsa.paths()
        while not path_iter.done():
            label_iter = path_iter.olabels()
            word = self._decode_labels(
                label_iter,
                strip_word_edge_symbols=strip_word_edge_symbols,
                strip_all_flags=strip_all_flags,
            )
            weight = float(path_iter.weight())
            if word not in decoded_outputs:
                decoded_outputs.append((word, weight))
            path_iter.next()

        decoded_outputs.sort(key=lambda t: t[-1])
        return decoded_outputs

    def fsm_strings(
        self,
        fst: pynini.Fst,
        project: Literal["input", "output"] = "output",
        nshortest: int = None,
        strip_word_edge_symbols: bool = True,
        strip_all_flags: bool = False,
    ) -> list[str]:
        """
        Return all (or nshortest) strings for an input FSM.
        Wraps `self.fsm_strings_and_weights` but only passes string.
        """
        strs_and_weights = self.fsm_strings_and_weights(
            fst=fst,
            project=project,
            nshortest=nshortest,
            strip_word_edge_symbols=strip_word_edge_symbols,
            strip_all_flags=strip_all_flags,
        )
        string_list = [string for string, _ in strs_and_weights]
        return string_list

    def fsm_string(
        self,
        fst: pynini.Fst,
        project: Literal["input", "output"] = "output",
        strip_word_edge_symbols: bool = True,
        strip_all_flags: bool = False,
    ) -> str:
        """
        Wraps `self.fsm_strings` with `nshortest=1` and returns
        single string instead of list of strings.
        """
        string_list = self.fsm_strings(
            fst,
            project,
            nshortest=1,
            strip_word_edge_symbols=strip_word_edge_symbols,
            strip_all_flags=strip_all_flags,
        )
        if len(string_list) != 1:
            raise ValueError(f"Expected single string, got {string_list}")
        return string_list[0]

    def _decode_labels(
        self,
        label_iter,
        strip_word_edge_symbols: bool = True,
        strip_all_flags: bool = False,
    ) -> str:
        """
        Arguments:
            label_iter:     An iterator over FST labels
        Returns:
            word:           Decoded string from the labels

        Decodes a string from the given `label_iter`.
        """
        word = ""
        for label in label_iter:
            if label == 0:
                # epsilon, skip
                continue
            symbol = self.symbols.find(label)
            if strip_all_flags and symbol[0] == "[":
                continue
            elif strip_word_edge_symbols and symbol in self.bow_eow_flags:
                continue
            word += symbol

        return word


@dataclass
class Token:
    value: str
    type: Literal[
        "phone",
        "flag",
        "class_ref",
        "pattern_ref",
        "bow_eow",
        "edit_flag",
        "special_ref",
        "unary_operator",
        "pipe_operator",
        "caret_operator",
        "boundary",
        "left_delimiter",
        "right_delimiter",
    ]
    acceptor: Acceptor | None = None

    def __post_init__(self):
        """
        Check if Token has acceptor if it is of the appropriate type.
        operators and delimiters should not have acceptors,
        all other types should have them.
        """
        if self.type.endswith("operator") or self.type.endswith("delimiter"):
            if self.acceptor is not None:
                raise ValueError(
                    "Operators and delimiters tokens should not have Acceptor objects passed. "
                    f"Token value: {self.value}, token type: {self.type}"
                )
        elif self.acceptor is None:
            raise ValueError(
                "All tokens except operators and delimiters should have Acceptor objects. "
                f"Token value: {self.value}, token type: {self.type}"
            )

    def __len__(self):
        return len(self.value)

    def __eq__(self, other):
        other_str = other
        if type(other) is Token:
            other_str = other.value
        return self.value == other_str

    def __str__(self):
        return f"Token(value='{self.value}')"

    def __repr__(self):
        return self.__str__()


if __name__ == "__main__":
    # test initializing each config
    inventory_reg = InventoryRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    pattern_reg = PatternRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    rule_reg = RuleRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    fst_reg = FstOrchestrator.from_config_dir(EXAMPLE_CONFIG_DIR)
