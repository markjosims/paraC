"""
src/fst.py - Config-driven FST compilation for Tira morphological parser.

Functions for loading YAML configs, building inventory registries,
compiling pattern strings, phonological rules, and morphological markers
into pynini FSTs/FSAs.

This module is the foundational layer of the config-driven refactor.
All higher-level config-driven code will depend on it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, Literal
from loguru import logger
import pynini
from pynini import FstProperties
import yaml
import unicodedata
from graphlib import TopologicalSorter

from src.registry_utils import Registry

class ReservedSymbolMixin:
    """
    Mixin class for registries to define reserved symbols that cannot be used as
    inventory item values. This is to prevent collisions between user-defined
    inventory items and special symbols used in pattern/rule contexts.
    """
    bos = "[BOS]"
    eos = "[EOS]"
    phone = "<Phone>"
    flag = "<Flag>"
    epsilon = "<Empty>"

    affix_boundary = "-"
    clitic_boundary = "="

    affix_boundary_fsa_str = "[AFFIX]"
    clitic_boundary_fsa_str = "[CLITIC]"

    boundary2fsa_iput = {
        affix_boundary: affix_boundary_fsa_str,
        clitic_boundary: clitic_boundary_fsa_str,
    }

    star = '*'
    plus = '+'
    optional = '?'
    union = '|'
    left_paren = '('
    right_paren = ')'
    left_brace = '{'
    right_brace = '}'

    left_delimiters = (left_paren, left_brace)
    right_delimiters = (right_paren, right_brace)
    unary_operators = (star, plus, optional)
    pipe_operators = (union,)
    reserved_refs = (phone, flag, epsilon)
    reserved_flags = (bos, eos)
    boundary_symbols = (affix_boundary, clitic_boundary)
    boundary_fsa_symbols = (affix_boundary_fsa_str, clitic_boundary_fsa_str)

    reserved_symbols = left_delimiters + right_delimiters + \
        unary_operators + pipe_operators+ reserved_refs + \
        reserved_flags + boundary_symbols

class InventoryRegistry(Registry):
    """
    Registry for storing inventory items (phones, flags, classes).
    Default is to instantiate from InventoryRegistry.from_config_dir()
    which loads all YAML configs in the specified directory.
    Can also be instantiated directly with a pre-built data dict
    or list of configs.
    """

    def __init__(
            self,
            data: Optional[Dict[str, InventoryItem]] = None,
            config_lists: Optional[List[dict]] = None,
        ):
        super().__init__(kind="Inventory", data=data, config_list=config_lists)
        self._populate_sublists()

    def _populate_sublists(self):
        phones = []
        flags = []
        classes = []
        for item in self.data.values():
            if item.type == "phone":
                phones.append(item.value)
            elif item.type == "flag":
                flags.append(item.value)
            elif item.type == "class":
                classes.append(item.value)
        self.phones = phones
        self.flags = flags
        self.classes = classes

    @classmethod
    def from_config_dir(cls, config_dir: str) -> InventoryRegistry:
        registry = super().from_config_dir(kind="Inventory", config_dir=config_dir)
        registry.data = registry.load_all_configs()
        registry._populate_sublists()

        return registry
        
    def load_all_configs(self) -> Dict[str, InventoryItem]:
        config_items = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            # check for collisions
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate inventory item '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(
            self,
            config: dict,
        ) -> Dict[str, InventoryItem]:
        top_classes = config.get("data", [])
        if not top_classes:
            logger.error("No top-level inventory classes found in config")
            return {}
        
        # get flat list of items
        inventory_items = []
        for item_config in top_classes.values():
            item = InventoryItem.from_config(item_config)
            flat_item = item.flatten()
            inventory_items.extend(flat_item)
        
        # check for item collisions
        item_values = [item.value for item in inventory_items]
        if len(item_values) != len(set(item_values)):
            error = f"Collision found among item values: {item_values}"
            logger.error(error)
            raise ValueError(error)

        # make dict mapping ref to item
        config_items = {item.value: item for item in inventory_items}

        return config_items
    
    def _get_tokens_from_class(self, item: InventoryItem) -> List[str]:
        """Recursively collect all phone/flag tokens from an InventoryItem subtree."""
        tokens = []
        if item.type in ("phone", "flag"):
            tokens.append(item.value)
        for child in item.children:
            tokens.extend(self._get_tokens_from_class(child))
        return tokens

@dataclass
class Acceptor:
    """
    Wrapper for strings that represent acceptor patterns in rules.
    """
    value: str
    fsa: Optional[pynini.Fst] = None

    def __post_init__(self):
        self.acceptor_built = False

        if self.fsa is not None:
            raise ValueError("Acceptor should not be passed on init but constructed by an FstRegistry object.")

    def set_acceptor(self, fsa: pynini.Fst):
        if self.acceptor_built:
            raise ValueError("Acceptor cannot be overridden.")
        if not fsa.properties(pynini.ACCEPTOR, True):
            raise ValueError("Must be an fsa FST")
        self.fsa = fsa
        self.acceptor_built = True

@dataclass
class InventoryItem(Acceptor):
    """
    Represents an item in the inventory, which may be a phone,
    flag or class.
    Attributes:
        value: The string value of the item (e.g. "a", "[TBU]", "<V>").
        type: The type of the item, one of "phone", "flag", or "class".
        children: List of child InventoryItems (for nested structures).
        parent: Optional reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """
    value: str
    type: Literal["phone", "flag", "class"]
    children: List[InventoryItem] = field(default_factory=list)
    parent: Optional[InventoryItem] = None
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        if self.value in ReservedSymbolMixin.reserved_symbols:
            error = f"Inventory item value '{self.value}' is a reserved symbol and cannot be used."
            logger.error(error)
            raise ValueError(error)

        if self.type == "class" and self.children is None:
            raise ValueError("Class items must have children")
        if self.type in ("phone", "flag") and self.children:
            raise ValueError("Phone and flag items cannot have children")
        
        if (
            (self.type == "class") and
            (not self.value.startswith("<") or not self.value.endswith(">"))
        ):
            raise ValueError("Class items must have values that start with '<' and end with '>'")
        if (
            (self.type == "flag") and
            (not self.value.startswith("[") or not self.value.endswith("]"))
        ):
            raise ValueError("Flag items must have values that start with '[' and end with ']'")
        if (
            (self.type == "phone") and
            (self.value.startswith("<") or self.value.startswith("["))
        ):
            raise ValueError("Phone items cannot have values that start with '<' or '['")

    @classmethod
    def from_config(
            cls,
            item_dict: dict,
            parent: Optional[InventoryItem] = None,
    ) -> InventoryItem:
        """
        Builds an InventoryItem from a config dict
        If config has children (nested dicts), recursively
        build child InventoryItems and attach to parent
        """

        # get source filepath if specified
        source_path = item_dict.get('source', None)

        inventory_item = cls(
            value=item_dict["_ref"],
            type="class",
            children=[],
            parent=parent,
            source=source_path,
        )

        children = []
        for key, value in item_dict.items():
            if key == '_phones':
                for phone in value:
                    child = cls(value=phone, type="phone", parent=inventory_item)
                    children.append(child)
            elif key == '_flags':
                for flag in value:
                    child = cls(value=flag, type="flag", parent=inventory_item)
                    children.append(child)
            elif isinstance(value, dict):
                child = cls.from_config(value, parent=inventory_item)
                children.append(child)

        inventory_item.children = children
        return inventory_item
    
    def flatten(self) -> List[InventoryItem]:
        """Recursively InventoryItem into a list including itself and all children."""
        items = [self]
        for child in self.children:
            items.extend(child.flatten)
        return items

class PatternRegistry(Registry):
    """
    Registry for storing pattern definitions, also computes dependency graph
    to track import logic.

    Default is to instantiate from PatternRegistry.from_config_dir() which loads
    all YAML configs in the specified directory. Can also be instantiated directly
    with a pre-built data dict or list of configs.
    """

    def __init__(
            self,
            data: Optional[Dict[str, Pattern]] = None,
            config_lists: Optional[List[dict]] = None,
        ):
        super().__init__(kind="Patterns", data=data, config_list=config_lists)
        self.build_dependency_graph()

    @classmethod
    def from_config_dir(cls, config_dir: str) -> PatternRegistry:
        pattern_registry = super().from_config_dir(kind="Patterns", config_dir=config_dir)
        pattern_registry.data = pattern_registry.load_all_configs()
        pattern_registry.build_dependency_graph()
        return pattern_registry

    def load_all_configs(self):
        config_items = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            # check for collisions
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate pattern '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(
            self,
            config: dict,
        ) -> Dict[str, Pattern]:
        patterns = config.get("data", [])
        if not patterns:
            logger.error("No patterns found in config")
            return
        
        patterns_list = [Pattern.from_config(p) for p in patterns]

        # make dict mapping ref to item
        config_items = {item._ref: item for item in patterns_list}
        return config_items
    
    def build_dependency_graph(self):
        """
        Populates `uses` and `used_by` fields for all pattern objects
        based on which patterns reference which other patterns in their
        pattern strings. Stores dependency chains in `self.dependency_graph`,
        and a topologically sorted list of patterns in `self.patterns_sorted`.
        """
        dependency_graph = {}

        for pattern in self.data.values():
            # get list of patterns this pattern uses
            used_by = []
            uses = []
            dependency_graph[pattern._ref] = set()
            for other_pattern in self.data.values():
                if pattern._ref in other_pattern.value:
                    used_by.append(other_pattern._ref)

                if other_pattern._ref in pattern.value:
                    uses.append(other_pattern._ref)
                    dependency_graph[pattern._ref].add(other_pattern._ref)

            pattern.set_dependencies(used_by=used_by, uses=uses)

        self.dependency_graph = dependency_graph
        pattern_refs_sorted = list(TopologicalSorter(dependency_graph).static_order())
        patterns_sorted = [self.data[ref] for ref in pattern_refs_sorted]
        self.patterns_sorted = patterns_sorted

@dataclass
class Pattern(Acceptor):
    """
    Represents a pattern which is a shorthand FSA to be used for defining rules.

    Attributes:
        value: The string value of the pattern (e.g. `(<V>|<R>|<N>)`).
        _ref: The registry reference string for this pattern (e.g. `<VowelClass>`).
        source: Optional string indicating filepath pattern originates from.
        fsa: pynini.Fst accepting the pattern language.
    """
    value: str
    _ref: str
    used_by: List[Pattern] = field(default_factory=list)
    uses: List[Pattern] = field(default_factory=list)
    source: Optional[os.PathLike] = None
    fsa: Optional[pynini.Fst] = None


    def __post_init__(self):
        super().__post_init__()

        if (
            (self.value in ReservedSymbolMixin.reserved_symbols)
            or (self._ref in ReservedSymbolMixin.reserved_symbols)
        ):
            error = f"Pattern value and ref cannot be reserved symbols. Got value '{self.value}' and ref '{self._ref}'."
            logger.error(error)
            raise ValueError(error)

        # set attributes to track state
        self.dependencies_built = False

        if self.used_by:
            raise ValueError("Used_by should not be passed on init but constructed by an FstRegistry object.")
        if self.uses:
            raise ValueError("Uses should not be passed on init but constructed by an FstRegistry object.")
        
    def set_dependencies(self, used_by: List[Pattern], uses: List[Pattern]):
        self.used_by = used_by
        self.uses = uses
        self.dependencies_built = True

    @classmethod
    def from_config(
            cls,
            item_dict: dict,
    ) -> Pattern:
        """
        Builds a Pattern from a config dict.
        """

        # get source filepath if specified
        source_path = item_dict.get('source', None)

        pattern = cls(
            value=item_dict["pattern"],
            _ref=item_dict["_ref"],
            source=source_path,
        )
        return pattern
    
    def __str__(self):
        return f"Pattern(_ref={self._ref}, value={self.value})"
    
    def __eq__(self, other):
        if not isinstance(other, Pattern):
            return self.value == str(other)
        return self.value == other.value

class RuleRegistry(Registry, ReservedSymbolMixin):
    def __init__(
            self,
            data: Optional[Dict[str, Pattern]] = None,
            config_lists: Optional[List[dict]] = None,
        ):
        super().__init__(kind="Rules", data=data, config_list=config_lists)
        self.build_dependency_graph()

    @classmethod
    def from_config_dir(cls, config_dir: str) -> PatternRegistry:
        rule_registry = super().from_config_dir(kind="Rules", config_dir=config_dir)
        rule_registry.data = rule_registry.load_all_configs()
        rule_registry.build_dependency_graph()
        return rule_registry

    def load_all_configs(self):
        config_items = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            # check for collisions
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate rule '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(
            self,
            config: dict,
        ) -> Dict[str, Pattern]:
        patterns = config.get("data", [])
        if not patterns:
            logger.error("No rules found in config")
            return
        
        rule_list = [Rule.from_config(p) for p in patterns]

        # make dict mapping ref to item
        config_items = {item._ref: item for item in rule_list}
        return config_items
    
    def build_dependency_graph(self):
        """
        Populates `rule_sequence` and `used_by` fields for all rule objects
        based on which rules reference which other rules in their
        rule strings. Stores dependency chains in `self.dependency_graph`,
        and a topologically sorted list of rules in `self.rules_sorted`.
        """
        dependency_graph = {}

        for rule in self.data.values():
            # get list of rules using this rule in their rule_sequence
            used_by = []
            for other_rule in self.data.values():
                if rule._ref in other_rule.value:
                    used_by.append(other_rule._ref)

            if rule.kind == "chain_of_rules":
                rule_objs = []
                for sub_rule in rule.rule_sequence:
                    rule_name = sub_rule.removeprefix("$")
                    if rule_name in self.data:
                        rule_objs.append(self.data[rule_name])
                    else:
                        raise KeyError(
                            f"Rule '{rule_name}' referenced in rule sequence for "\
                            f"'{rule._ref}' not found in registry."
                        )
                rule.set_dependencies(
                    used_by=used_by,
                    rule_sequence=rule_objs,
                )
                dependency_graph[rule._ref] = set(rule_objs)
            else:
                rule.set_dependencies(used_by=used_by)

        self.dependency_graph = dependency_graph
        rule_refs_sorted = list(TopologicalSorter(dependency_graph).static_order())
        rules_sorted = [self.data[ref] for ref in rule_refs_sorted]
        self.rules_sorted = rules_sorted

@dataclass
class Rule:
    """
    Dataclass for phonological rules. Rules can be of three types:
    - Simple rules: defined by input and output patterns
    - String map rules: defined by a list of input-output string pairs
    - Chain of rules: defined by a sequence of other rules to apply in order

    Any rule can also have left and right context patterns that must be satisfied
    for the rule to apply.

    Since we expect a RuleRegistry to be built upon a PatternRegistry, we load
    pattern objects directly into the Rule dataclass and track references to patterns via
    the `uses` and `used_by` fields.
    
    Note that the actual FST construction logic for rules is not implemented here, but
    is handled by the `FstRegistry` class which compiles patterns and rules into FSTs.
    """

    kind: Literal["simple", "string_map", "chain_of_rules"]
    _ref: str

    # attributes for simple rules
    input_pattern: Acceptor = field(default_factory=Acceptor)
    output_pattern: Acceptor = field(default_factory=Acceptor)

    # attributes for string map rules
    string_map: List[Tuple[str, str]] = field(default_factory=list)

    # attributes for chain of rules
    rule_sequence: List[Rule] = field(default_factory=list)

    # attributes for all rule types
    left_context: Acceptor = field(default_factory=Acceptor)
    right_context: Acceptor = field(default_factory=Acceptor)
    
    # references to other objects
    used_by: List[Rule] = field(default_factory=list)

    # metadata
    source: Optional[os.PathLike] = None

    # initialized by FstRegistry
    transducer: Optional[pynini.Fst] = None

    def __post_init__(self):
        self.dependencies_built = False
        self.transducer_built = False

        if self._ref in ReservedSymbolMixin.reserved_symbols:
            error = f"Rule ref '{self._ref}' cannot be a reserved symbol."
            logger.error(error)
            raise ValueError(error)

        if self.transducer is not None:
            raise ValueError(
                "Transducer should not be passed on init but constructed by an FstRegistry object."
            )
        if self.used_by:
            raise ValueError(
                "Used_by should not be passed on init but constructed by a RuleRegistry object."
            )
        
        if self.kind == "simple":
            if not self.input_pattern or not self.output_pattern:
                raise ValueError("Simple rules must have input and output patterns")
            if self.string_map:
                raise ValueError("Simple rules cannot have a string map")
            if self.rule_sequence:
                raise ValueError("Simple rules cannot have a rule sequence")
            
        if self.kind == "chain_of_rules":
            if not self.rule_sequence:
                raise ValueError("Chain of rules must have a rule sequence")
            if self.input_pattern.value != "" or self.output_pattern.value != "":
                raise ValueError("Chain of rules cannot have input or output patterns")
            if self.string_map:
                raise ValueError("Chain of rules cannot have a string map")

    def set_dependencies(self, used_by: List[Rule], rule_sequence: Optional[List[Rule]] = None):
        self.used_by = used_by
        if rule_sequence is not None and self.kind != "chain_of_rules":
            raise ValueError("Only chain_of_rules can have a rule sequence")
        self.rule_sequence = rule_sequence
        self.dependencies_built = True


class FstRegistry(Registry):
    """
    Orchestrates the compilation of inventory items, patterns and rules into FSTs.
    """

    def __init__(
            self,
            inventory_registry: InventoryRegistry,
            pattern_registry: PatternRegistry,
            rule_registry: RuleRegistry,
        ):
        self.inventory_registry = inventory_registry
        self.pattern_registry = pattern_registry
        self.rule_registry = rule_registry

        self.inventory: Dict[str, InventoryItem] = inventory_registry.data
        self.phones: Dict[str, InventoryItem] = inventory_registry.phones
        self.flags: Dict[str, InventoryItem] = inventory_registry.flags
        self.classes: Dict[str, InventoryItem] = inventory_registry.classes
        self.patterns: Dict[str, Pattern] = pattern_registry.data
        self.patterns_sorted: Tuple[Pattern, ...] = pattern_registry.patterns_sorted
        self.rules: Dict[str, Rule] = rule_registry.data 
        self.rules_sorted: Tuple[Rule, ...] = rule_registry.rules_sorted       

        self._symbol_table_built = False
        self._inventory_acceptors_built = False
        self._pattern_acceptors_built = False
        self._rule_transducers_built = False
        self.initialized = False

        self._build_symbol_table()
        self._init_fsas()
        self.initialized = True
    
    @classmethod
    def from_config_dir(cls, config_dir: str) -> FstRegistry:
        inventory_registry = InventoryRegistry.from_config_dir(config_dir)
        pattern_registry = PatternRegistry.from_config_dir(config_dir)
        rule_registry = RuleRegistry.from_config_dir(config_dir)
        return cls(inventory_registry, pattern_registry, rule_registry)

    def _build_symbol_table(self):
        symbols = pynini.SymbolTable()
        for item in self.phones:
            symbols.add_symbol(item)
        for item in self.flags:
            symbols.add_symbol(item)
        self.symbols = symbols
        self._symbol_table_built = True

    def _token_acceptor(self, token_str: str) -> pynini.Fst:
        """
        Builds an acceptor for a single token.
        Checks that `token_str` is mapped to a symbol in `self.symbols`
        """
        if self.symbols.find(token_str) == -1:
            raise KeyError("Token not found in symbol table")
        return pynini.accep(token_str, token_type=self.symbols)

    def _build_token_map(self):
        # store tokens as a dict mapping token type to list of token values
        # acting as an incomplete Aho-Corasick trie for tokenization of pattern strings
        tokens = defaultdict(list)
        for l_delimiter in self.left_delimiters:
            tokens["left_delimiter"].append(Token(value=l_delimiter, type="left_delimiter"))
        for r_delimiter in self.right_delimiters:
            tokens["right_delimiter"].append(Token(value=r_delimiter, type="right_delimiter"))
        for op in self.unary_operators:
            tokens["unary_operator"].append(Token(value=op, type="unary_operator"))
        for op in self.pipe_operators:
            tokens["pipe_operator"].append(Token(value=op, type="pipe_operator"))
        for ref in self.reserved_refs:
            acceptor = self._token_acceptor(ref)
            tokens["ref"].append(Token(value=ref, type="special_ref", acceptor=acceptor))
        for flag in self.reserved_flags:
            acceptor = self._token_acceptor(flag)
            tokens["flag"].append(Token(value=flag, type="special_flag", acceptor=acceptor))
        for boundary in self.boundary_symbols:
            fsa_input = self.boundary2fsa_input[boundary]
            acceptor = self._token_acceptor(fsa_input)
            tokens["boundary"].append(Token(value=boundary, type="boundary", acceptor=acceptor))
        for phone, phone_obj in self.phones.items():
            tokens["phone"].append(Token(value=phone, type="phone", acceptor=phone_obj))
        for flag, flag_obj in self.flags.items():
            tokens["flag"].append(Token(value=flag, type="flag", acceptor=flag_obj))
        for class_ref, class_obj in self.classes.items():
            tokens["ref"].append(Token(value=class_ref, type="class_ref", acceptor=class_obj))
        for pattern_ref, pattern_obj in self.patterns.items():
            tokens["ref"].append(Token(value=pattern_ref, type="pattern_ref", acceptor=pattern_obj))


        # sort tokens by length in descending order so that longest matches
        # are found first during tokenization
        for token_type, token_list in tokens.items():
            token_list = sorted(token_list, key=lambda t: len(t),    reverse=True)
            tokens[token_type] = token_list
        self.tokens: Dict[str, List[Token]] = tokens

    def _infer_token_type(self, input_str: str) -> Optional[str]:
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
            return "phones"
        elif starting_char == "[":
            return "flag"
        elif starting_char == "<":
            return "ref"
        elif starting_char in self.operators:
            return "operator"
        elif starting_char in self.left_delimiters:
            return "left_delimiter"
        elif starting_char in self.right_delimiters:
            return "right_delimiter"
        # defaulting to "phone" will not cause any false positives
        # as the string will be checked against the phone registry later
        # since this function just tells `_tokenize_str` which token dictionary
        # to check the current substring against
        return "phone"

    def _tokenize_str(self, input_str: str) -> List[Token]:
        """
        Tokenize an input string into a list of Tokens.

        Uses the token lists built in `_build_token_list` to find the longest
        matching token at each position in the input string, and infers token
        type from the token string itself (e.g. flags start with '[', refs start with '<', etc.)
        """
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
                error = f"Unrecognized token starting at position {i} in string '{input_str}'"
                logger.error(error)
                raise ValueError(error)
            tokens.append(match)
            i += len(match)

        return tokens
    
    def _build_inventory_acceptors(self):
        """
        Before any patterns can be parsed, all InventoryItems must be compiled with acceptors.
        """
        for item in self.phones.values():
            acceptor = pynini.accep(item.value, token_type=self.symbols)
            item.set_acceptor(acceptor)
        for item in self.flags.values():
            acceptor = pynini.accep(item.value, token_type=self.symbols)
            item.set_acceptor(acceptor)
        for item in self.classes.values():
            children = item.flatten()
            child_values = [
                child.value for child in children
                if child.type != 'class'
            ]
            acceptor = pynini.union(*child_values)
            item.set_acceptor(acceptor)
        self._inventory_acceptors_built = True

    def _build_pattern_acceptors(self):
        """
        Parse patterns using recursive descent.
        """
        for pattern in self.patterns_sorted:
            tokens = self._tokenize_str(pattern.value)
            acceptor = self._parse_tokens(tokens)
            pattern.set_acceptor(acceptor)
        self._pattern_acceptors_built = True

    def _build_rule_transducer(self):
        """
        Parse rules...
        """
        # simple rule
        # string map
        # rule chain

    def _parse_tokens(self, tokens: List[Token]) -> pynini.Fst:
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
        acceptor, current_index = self._parse_expression(tokens, current_index=0)
        if current_index != len(tokens):
            raise ValueError(f"Tokens remaining after parsing expression for token array {tokens}")
        return acceptor

    def _parse_expression(
            self,
            tokens: List[Token],
            current_index: int,
        ) -> Tuple[pynini.Fst, int]:
        """
        Parses an expression in the token array starting at `current_index`, where
        an expression is a single term or any sequence of term | term | term ...
        """
        term, current_index = self._parse_term(tokens, current_index)
        terms = [term]
        current_type = tokens[current_index].type
        while current_type == "pipe_operator" and current_index < len(tokens):
            current_term, current_index = self._parse_term(tokens, current_index)
            terms.append(current_term)

            current_type = tokens[current_index].type
            if current_type == "right_delimiter":
                # let parent handle
                break
        
        acceptor = pynini.union(terms)
        return acceptor, current_index

    def _parse_term(
        self,
        tokens: List[Token],
        current_index: int,
    ) -> Tuple[pynini.Fst, int]:
        """
        Parses a term, i.e. a sequence of factors and unary operators of
        arbitrary length.
        """
        current_type = tokens[current_index].type
        if current_type in ("right_delimiter", "pipe_operator"):
            raise ValueError(
                f"Got unexpected token type {current_type} at start of term, tokens {tokens} current index {current_index}"
            )
        factors_w_operators = []
        while (
            (current_type not in ("right_delimiter", "pipe_operator")) and
            (current_index < len(tokens))
        ):
            factor, current_index = self._parse_factor(tokens, current_index)
            current_type = tokens[current_index].type
            if current_type == 'unary_operator':
                operator = tokens[current_type].value
                factor = self._interpret_unary_operator(factor, operator)
                current_index+=1
            factors_w_operators.append(factor)
        
        if not factors_w_operators:
            raise ValueError(f"Empty term detected in token sequence {tokens} current index {current_index}")
        if len(factors_w_operators) == 1:
            return factors_w_operators[0]
        output_factor = factors_w_operators[0]
        for factor in factors_w_operators[1:]:
            output_factor = pynini.concat(output_factor, factor)
        return output_factor

    def _parse_factor(
            self,
            tokens: List[Token],
            current_index: int,
            group_behavior: Literal['concatenation', 'union'] = 'concatenation'
        ) -> Tuple[pynini.Fst, int]:
        """
        Consume tokens starting at `current_index` and until the end of the
        current factor is reached. Then return an acceptor over the factor
        alongside the index of the first token after the current factor.

        By default assume all tokens within the factor are to be concatenated
        into a sequence. If `group_behavior='union'` is passed, compute a union
        over all tokens/sub-factors (e.g. for factors delimited by curly braces)
        """
        acceptors = []
        while current_index < len(tokens):
            token_acceptor = tokens[current_index].acceptor
            token_type = tokens[current_index].type
            if token_acceptor is not None and token_acceptor.acceptor_built:
                acceptors.append(token_acceptor)
                current_index += 1
            elif isinstance(token_acceptor, Pattern) and not token_acceptor.acceptor_built:
                token_val = tokens[current_index].value
                raise ValueError(
                    "Uninitialized pattern found while parsing with recursive descent. "
                    f"pattern ref {token_val} tokens {tokens} current index {current_index}. "
                    "Check topological sort for pattern objects."
                )
            elif isinstance(token_acceptor, InventoryItem) and not token_acceptor.acceptor_built:
                token_val = tokens[current_index].value
                raise ValueError(
                    "Uninitialized inventory item found while parsing with recursive descent. "
                    f"item ref {token_val} tokens {tokens} current index {current_index}. "
                )
            elif token_type == 'left_delimiter':
                acceptor, current_index = self._parse_delimited_factor(
                    tokens, current_index
                )
            elif token_type in ("pipe_operator", "unary_operator", "right_delimiter"):
                # let parent function handle
                break

        if not acceptors:
            raise ValueError(f"Empty factor detected in token sequence {tokens} current index {current_index}")
        elif len(acceptors) == 1:
            return acceptors[0]

        if group_behavior == 'concatenation':
            output_acceptor = acceptors[0]
            for acceptor in acceptors[1:]:
                output_acceptor = pynini.concat(output_acceptor, acceptor)
        else:
            output_acceptor = pynini.union(*acceptors)
        return output_acceptor
            
    def _parse_delimited_factor(
            self,
            tokens: List[Token],
            current_index: int,
    ) -> Tuple[pynini.Fst, int]:
        left_delimiter = tokens[current_index].value
        
        # curly braces indicate union of tokens
        if left_delimiter == r'{':
            group_behavior = 'union'
            expected_right_delimiter = r'}'
            inner_expression, current_index = self._parse_factor(
                tokens=tokens,
                group_behavior=group_behavior,
                current_index=current_index,
            )

        # parentheses indicate a single expression
        elif left_delimiter == r'(':
            expected_right_delimiter = r')'
            inner_expression, current_index = self._parse_expression(
                tokens=tokens,
                current_index=current_index,
            )
        
        else:
            raise ValueError(
                f"Unrecognized left delimiter {left_delimiter}, tokens {tokens} current index {current_index}"
            )

        current_token = tokens[current_index].value
        assert current_token == expected_right_delimiter
        current_index+=1
        return inner_expression, current_index


    def _interpret_unary_operator(term: pynini.Fst, operator: str) -> pynini.Fst:
        if operator == '?':
            return term.ques
        if operator == '+':
            return term.plus
        if operator == '*':
            return term.star
        raise ValueError(f"Unrecognized unary operator {operator}")
    
@dataclass
class Token:
    value: str
    type: Literal[
        "phone", "flag", "class_ref", "pattern_ref",
        "special_flag", "special_ref", "unary_operator",
        "pipe_operator", "boundary", "left_delimiter",
        "right_delimiter",
    ]
    acceptor: Optional[Acceptor] = None

    def __post_init__(self):
        """
        Check if Token has acceptor if it is of the appropriate type.
        'op', 'left_delimiter' and 'right_delimiter' should not have acceptors,
        all other types should have them.
        """
        if (
            (self.type in (
                'unary_operator', 'pipe_operator',
                'left_delimiter', 'right_delimiter',
            ))
            and (self.acceptor is not None)
        ):
                raise ValueError(
                    "Operators and delimiters should not have Acceptor objects passed. "
                    f"Token value: {self.value}, token type: {self.type}"
                )
        elif self.acceptor is None:
            raise ValueError(
                "All tokens except operators and delimiters should have Acceptor objects. "
                f"Token value: {self.value}, token type: {self.type}"
            )

    def __len__(self):
        return len(self.value)
        
# ---------------------------------------------------------------------------
# Section 1: Config Loading
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Section 2: Inventory Registry
# ---------------------------------------------------------------------------

# Special symbol strings used in pattern/rule contexts
_BOS_STR = "[BOS]"
_EOS_STR = "[EOS]"
_SIGMA_STR = "<Sigma>"
_EMPTY_STR = "<Empty>"


def _build_registry_from_node(node: dict, registry: Dict[str, pynini.Fst]) -> pynini.Fst:
    """
    Recursively walk an inventory data node.

    Returns an FSA that is the union of all phones/flags in this subtree,
    and registers any intermediate/top-level reprs encountered.
    """
    phones = node.get("_phones", [])
    flags = node.get("_flags", [])
    repr_str = node.get("_ref", None)

    # Build the FSA for all phones/flags at this node
    parts: List[pynini.Fst] = []
    for phone in phones:
        parts.append(fst(phone))
    for flag in flags:
        # flags may have bracket notation like "[TBU]" — encode them
        # TODO Validate flag string meets expected format
        parts.append(fst(flag))

    # Recurse into child nodes (skip  keys)
    skip_keys = {"_ref", "_phones", "_flags"}
    for key, value in node.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict):
            child_fsa = _build_registry_from_node(value, registry)
            parts.append(child_fsa)

    if not parts:
        node_fsa = fst("")
    elif len(parts) == 1:
        node_fsa = parts[0]
    else:
        node_fsa = pynini.union(*parts).optimize()

    if repr_str is not None:
        registry[repr_str] = node_fsa

    return node_fsa


def build_inventory_registry(config: dict) -> Dict[str, pynini.Fst]:
    """
    Build a registry mapping repr strings (e.g. '<V>', '<C>') to FSAs.

    Walks the nested data tree of an Inventory config, unions all
    phones/flags beneath each node with a 'repr' key.

    Also adds:
      - '[BOS]'    → pynini BOS acceptor
      - '[EOS]'    → pynini EOS acceptor
      - '<Sigma>'  → SIGMASTAR
      - '<Empty>'  → fst('')
      - '-'        → boundary symbol FSA
      - '<TBU>'    → tone-bearing unit FSA
      - '<FLOAT>'  → floating tone FSA
      - '<CL>'     → class placeholder FSA

    Arguments:
        config: Fully-resolved Inventory config dict.
    Returns:
        registry: dict mapping repr strings to FSAs.
    """
    registry: Dict[str, pynini.Fst] = {}

    data = config.get("data", {})
    for key, value in data.items():
        if isinstance(value, dict):
            _build_registry_from_node(value, registry)

    # Special symbols
    # [BOS] and [EOS] are pynini's byte-level anchoring tokens; use pynini.accep directly
    registry[_BOS_STR] = pynini.accep("[BOS]")
    registry[_EOS_STR] = pynini.accep("[EOS]")
    registry[_SIGMA_STR] = SIGMASTAR
    registry[_EMPTY_STR] = fst("")
    registry[BOUNDARY_STR] = fst(BOUNDARY_STR)
    registry[TONE_SLOT_STR] = fst(TONE_SLOT_STR)
    registry[TONE_PLACEHOLDER_STR] = fst(TONE_PLACEHOLDER_STR)
    registry[CLASS_PLACEHOLDER] = fst(CLASS_PLACEHOLDER)

    return registry


# ---------------------------------------------------------------------------
# Section 3: Pattern String Compiler
# ---------------------------------------------------------------------------

# Regex for tokenizing pattern strings.
# Order matters: longest matches first.
_TOKEN_RE = re.compile(
    r"""
    (?P<special>  \[BOS\] | \[EOS\]   )  |   # BOS/EOS special tokens TODO: add remaining special tokens
    (?P<ref>      <[^>]+>             )  |   # <X> registry references
    (?P<op>       [*+?|]              )  |   # operators
    (?P<paren>    [()]                )  |   # grouping
    (?P<literal>  .                   )      # any other character (Unicode)
    """,
    re.VERBOSE | re.DOTALL | re.UNICODE,
)
# TODO: check behavior of named groups with python.re so that `_PatternParser`
# can use the token types directly instead of hardcoding strings like "ref", "special", etc.

def _tokenize_pattern(pattern_str: str) -> List[Tuple[str, str]]:
    """
    Tokenize a pattern string into typed tokens.

    Returns a list of (token_type, token_value) pairs where token_type is
    one of: 'ref', 'special', 'op', 'paren', 'literal'.

    Multi-character IPA tokens (dental stops) are kept together because
    they are handled as single symbols by the fst() factory.
    """
    tokens = []
    i = 0
    text = pattern_str
    # Encode to find multichar tokens (handles dental bridges etc.)
    # We work on the raw string but use fst() for actual FSA construction.
    while i < len(text):
        # Try special multi-char symbols first
        matched = False
        # TODO doesn't re-use _TOKEN_RE, should this be fixed?
        for tok_type, tok_re in [
            ("special", re.compile(r"\[BOS\]|\[EOS\]")),
            ("ref", re.compile(r"<[^>]+>")),
        ]:  
            m = tok_re.match(text, i)
            if m:
                tokens.append((tok_type, m.group()))
                i = m.end()
                matched = True
                break

        if matched:
            continue

        ch = text[i]
        if ch in "*+?|":
            tokens.append(("operator", ch))
            i += 1
        elif ch in "()":
            tokens.append(("paren", ch))
            i += 1
        else:
            # Possibly a multi-byte Unicode character or dental bridge combo
            # Collect combining characters that follow
            j = i + 1
            while j < len(text) and unicodedata.combining(text[j]):
                j += 1
            literal = text[i:j]
            tokens.append(("literal", literal))
            i = j

    return tokens


class _PatternParser:
    """
    Recursive descent parser for pattern strings.

    Grammar:
        expr   ::= term ('|' term)*
        term   ::= factor+
        factor ::= atom ('*' | '+' | '?')?
        atom   ::= ref | special | literal | '(' expr ')'

    TODO: Current behavior is to construct a _PatternParser for a single string
    change so that we initialize a _PatternParser with the registry and
    then call parse_expr() for each pattern string
    so we can reuse the same parser instance.
    """

    def __init__(self, tokens: List[Tuple[str, str]], registry: Dict[str, pynini.Fst]):
        self._tokens = tokens
        self._pos = 0
        self._registry = registry

    def _peek(self) -> Optional[Tuple[str, str]]:
        """
        Return token at current position without advancing position
        """
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> Tuple[str, str]:
        """
        Return token at current position and advance position
        """
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def parse_expr(self) -> pynini.Fst:
        """expr ::= term ('|' term)*"""
        left = self._parse_term()
        while self._peek() == ("operator", "|"):
            self._consume()
            right = self._parse_term()
            left = pynini.union(left, right).optimize()
        return left

    def _parse_term(self) -> pynini.Fst:
        """term ::= factor+"""
        # A term must have at least one factor
        result = self._parse_factor()
        # Join factors until a right parenthesis or pipe operator is found
        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok == ("paren", ")"):
                break
            if tok == ("operator", "|"):
                break
            next_factor = self._parse_factor()
            result = pynini.concat(result, next_factor)
        return result

    def _parse_factor(self) -> pynini.Fst:
        """factor ::= atom ('*' | '+' | '?')?"""
        atom = self._parse_atom()
        tok = self._peek()
        if tok is not None and tok[0] == "operator" and tok[1] in "*+?":
            self._consume()
            if tok[1] == "*":
                atom = pynini.closure(atom).optimize()
            elif tok[1] == "+":
                atom = pynini.closure(atom, 1).optimize()
            elif tok[1] == "?":
                atom = pynini.union(fst(""), atom).optimize()
        return atom

    def _parse_atom(self) -> pynini.Fst:
        """atom ::= ref | special | literal | '(' expr ')'"""
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of pattern string")

        tok_type, tok_val = tok

        if tok_type == "paren" and tok_val == "(":
            self._consume()  # consume '('
            inner = self.parse_expr()
            closing = self._peek()
            if closing != ("paren", ")"):
                raise ValueError(f"Expected ')' but got {closing}")
            self._consume()  # consume ')'
            return inner

        elif tok_type == "ref":
            self._consume()
            if tok_val not in self._registry:
                raise KeyError(f"Pattern ref '{tok_val}' not found in registry")
            return self._registry[tok_val]

        elif tok_type == "special":
            self._consume()
            if tok_val == "[BOS]":
                # pynini byte-level BOS anchor
                return pynini.accep("[BOS]")
            elif tok_val == "[EOS]":
                # pynini byte-level EOS anchor
                return pynini.accep("[EOS]")
            else:
                raise ValueError(f"Unknown special token: {tok_val}")

        elif tok_type == "literal":
            self._consume()
            return fst(tok_val)

        else:
            raise ValueError(f"Unexpected token type: {tok}")


def compile_pattern_str(pattern_str: str, registry: Dict[str, pynini.Fst]) -> pynini.Fst:
    """
    Compile a pattern string (e.g. "(<V>|<R>|<N>)" or "<V>-?") to a pynini FSA.

    Arguments:
        pattern_str: Pattern string using registry refs and standard regex ops.
        registry:    Dict mapping repr strings to FSAs.
    Returns:
        FSA accepting the language described by pattern_str.
    """

    # base case: empty string
    if pattern_str == "":
        return fst("")
    tokens = _tokenize_pattern(pattern_str)
    parser = _PatternParser(tokens, registry)
    result = parser.parse_expr()
    if parser._pos != len(tokens):
        remaining = tokens[parser._pos:]
        raise ValueError(f"Unexpected tokens at end of pattern: {remaining}")
    return result.optimize()


def compile_patterns(config: dict, registry: Dict[str, pynini.Fst]) -> Dict[str, pynini.Fst]:
    """
    TODO: Since patterns can build off other patterns,
    we'll need to define an order of compilation based off which
    YAML files import which, or do a topological sort based on pattern references.

    Compile all patterns from a Patterns config into the registry.

    Iterates over the 'patterns' list, compiles each 'pattern' string
    using the current registry, and registers the result under its 'repr'.

    Arguments:
        config:   Fully-resolved Patterns config dict.
        registry: Existing registry (will be extended in-place and returned).
    Returns:
        Extended registry.
    """
    patterns_list = config.get("patterns", [])
    for entry in patterns_list:
        # Each entry is either {name: {pattern: ..., _ref: ...}} or flat
        # TODO: this is not true, the YAML structure requires pattern and repr
        # attributes for each pattern
        if isinstance(entry, dict):
            for _name, spec in entry.items():
                if not isinstance(spec, dict):
                    continue
                pattern_str = spec.get("pattern", "")
                repr_str = spec.get("_ref", None)
                if repr_str is None:
                    continue
                fsa = compile_pattern_str(pattern_str, registry)
                registry[repr_str] = fsa
    return registry


# ---------------------------------------------------------------------------
# Section 4: Rule Compiler
# ---------------------------------------------------------------------------


def _compile_simple_rule(
    rule_dict: dict,
    registry: Dict[str, pynini.Fst],
) -> pynini.Fst:
    """Compile a simple_rule (cdrewrite-based) to an FST."""
    input_pattern = rule_dict.get("input_pattern", "")
    output_pattern = rule_dict.get("output_pattern", "")
    left_context = rule_dict.get("left_context", "")
    right_context = rule_dict.get("right_context", "")
    # TODO: full words should be allowed in the YAML
    # i.e. 'left-to-right' or 'right-to-left' vs. 'ltr', 'rtl'
    direction = rule_dict.get("direction", "ltr")
    sigma_str = rule_dict.get("sigma_star", None)

    input_fsa = compile_pattern_str(input_pattern, registry)
    output_fsa = compile_pattern_str(output_pattern, registry)

    # Build transducer tau
    if input_pattern == "" and output_pattern != "":
        tau = insert_fst(output_fsa)
    elif input_pattern != "" and output_pattern == "":
        tau = delete_fst(input_fsa)
    else:
        tau = pynini.cross(input_fsa, output_fsa)

    l_fsa = compile_pattern_str(left_context, registry) if left_context else fst("")
    r_fsa = compile_pattern_str(right_context, registry) if right_context else fst("")

    if sigma_str:
        sigma = compile_pattern_str(sigma_str, registry)
        sigma = pynini.closure(sigma).optimize()
    else:
        sigma = SIGMASTAR

    result = pynini.cdrewrite(tau, l_fsa, r_fsa, sigma, direction=direction)
    return result.optimize()


def _compile_map_rule(
    rule_dict: dict,
    registry: Dict[str, pynini.Fst],
) -> pynini.Fst:
    """Compile a map_rule (union of string mappings, wrapped in cdrewrite)."""
    string_map = rule_dict.get("string_map", [])
    left_context = rule_dict.get("left_context", "")
    right_context = rule_dict.get("right_context", "")
    direction = rule_dict.get("direction", "ltr")

    if not string_map:
        raise ValueError("map_rule must have a non-empty string_map")

    tau_parts = []
    for pair in string_map:
        src, tgt = pair
        src_fsa = compile_pattern_str(str(src), registry)
        tgt_fsa = compile_pattern_str(str(tgt), registry)
        tau_parts.append(pynini.cross(src_fsa, tgt_fsa))

    tau = pynini.union(*tau_parts).optimize()

    l_fsa = compile_pattern_str(left_context, registry) if left_context else fst("")
    r_fsa = compile_pattern_str(right_context, registry) if right_context else fst("")

    result = pynini.cdrewrite(tau, l_fsa, r_fsa, SIGMASTAR, direction=direction)
    return result.optimize()


def compile_rule(
    name: str,
    rule_dict: dict,
    all_rules: dict,
    registry: Dict[str, pynini.Fst],
    compiled_cache: Optional[Dict[str, pynini.Fst]] = None,
) -> pynini.Fst:
    """
    Compile a single rule to an FST.

    Dispatches on rule type detected from keys present in rule_dict:
      - 'rule_sequence' → chain_of_rules (composition)
      - 'string_map'    → map_rule
      - otherwise       → simple_rule (cdrewrite)

    Arguments:
        name:           Rule name (for cycle detection and caching).
        rule_dict:      Raw rule specification dict.
        all_rules:      Dict of all rules in the config (for chain lookups).
        registry:       FSA registry for pattern compilation.
        compiled_cache: Optional mutable cache to avoid recompilation.
    Returns:
        Compiled FST for this rule.

    # TODO: validate rule dict contains keys 'input/output_pattern' XOR
    'string_map' XOR 'rule_sequence'
    """
    if compiled_cache is None:
        compiled_cache = {}

    if name in compiled_cache:
        return compiled_cache[name]

    if "rule_sequence" in rule_dict:
        # chain_of_rules: compose rules in sequence
        sequence = rule_dict["rule_sequence"]
        composed: Optional[pynini.Fst] = None
        for rule_name in sequence:
            if rule_name not in all_rules:
                raise KeyError(f"Rule '{rule_name}' not found in rules config")
            sub_rule = compile_rule(
                rule_name, all_rules[rule_name], all_rules, registry, compiled_cache
            )
            if composed is None:
                composed = sub_rule
            else:
                composed = pynini.compose(composed, sub_rule).optimize()
        result = composed if composed is not None else SIGMASTAR.copy()

    elif "string_map" in rule_dict:
        result = _compile_map_rule(rule_dict, registry)

    else:
        result = _compile_simple_rule(rule_dict, registry)

    compiled_cache[name] = result
    return result


def compile_rules(
    config: dict,
    registry: Dict[str, pynini.Fst],
) -> Dict[str, pynini.Fst]:
    """
    Compile all rules from a Rules config.

    Arguments:
        config:   Fully-resolved Rules config dict.
        registry: FSA registry for pattern compilation.
    Returns:
        Dict mapping rule name to compiled FST.
    """
    rules_spec = config.get("rules", {})
    compiled: Dict[str, pynini.Fst] = {}

    for name in rules_spec:
        compile_rule(name, rules_spec[name], rules_spec, registry, compiled)

    return compiled


# ---------------------------------------------------------------------------
# Section 5: Marker Compiler
# ---------------------------------------------------------------------------

# from src.forms.form_helpers import prefix as _prefix_fst, suffix as _suffix_fst


def compile_marker_dict(
    marker_dict: Optional[dict],
    registry: Dict[str, pynini.Fst],
    rules: Dict[str, pynini.Fst],
) -> pynini.Fst:
    """
    Compile a single marker dict (or None for zero-marking) to an FST.

    Supported keys:
      - null / None  → identity transducer (SIGMASTAR)
      - prefix       → prepend prefix string to stem
      - suffix       → append suffix string to stem
      - replace      → [src, tgt] cross-rewrite via cdrewrite
      - rule         → named rule from rules dict (or '$name' ref)
      - suppletion   → maps any stem to the suppletive form

    If multiple ops are present (except suppletion), they are composed.

    Arguments:
        marker_dict: Marker specification dict, or None for zero-marking.
        registry:    FSA registry (not currently used, for future extension).
        rules:       Compiled rules dict.
    Returns:
        FST implementing the marker operation.
    """
    if marker_dict is None:
        # Zero marking: identity transducer
        return SIGMASTAR.copy()

    parts: List[pynini.Fst] = []

    # Handle suppletion first (incompatible with other ops)
    if "suppletion" in marker_dict:
        suppletive_form = marker_dict["suppletion"]
        # TODO: test this code
        # I'd expect cross(SIGMASTAR, suppletive_form)
        # should be all that's needed

        # Maps any input to the suppletive form
        suppletive_fsa = fst(suppletive_form)
        result = pynini.compose(
            pynini.cross(SIGMASTAR, SIGMASTAR),
            fst("", suppletive_form)
        )
        # Simpler: accept anything, output suppletive form
        # This is: epsilon → suppletive_form composed with SIGMASTAR on input
        result = insert_fst(suppletive_fsa) @ SIGMASTAR
        return result.optimize()

    if "prefix" in marker_dict:
        prefix_str = marker_dict["prefix"]
        parts.append(_prefix_fst(prefix_str))

    if "suffix" in marker_dict:
        suffix_str = marker_dict["suffix"]
        parts.append(_suffix_fst(suffix_str))

    if "replace" in marker_dict:
        src, tgt = marker_dict["replace"]
        src_fsa = fst(str(src))
        tgt_fsa = fst(str(tgt))
        tau = pynini.cross(src_fsa, tgt_fsa)
        replace_rule = pynini.cdrewrite(tau, fst(""), fst(""), SIGMASTAR).optimize()
        parts.append(replace_rule)

    if "rule" in marker_dict:
        rule_ref = marker_dict["rule"]
        if rule_ref.startswith("$"):
            rule_ref = rule_ref[1:]
        if rule_ref not in rules:
            raise KeyError(f"Rule '{rule_ref}' not found in compiled rules dict")
        parts.append(rules[rule_ref])

    if not parts:
        # No operation specified, treat as identity
        return SIGMASTAR.copy()

    if len(parts) == 1:
        return parts[0].optimize()

    # Compose all parts in sequence
    result = parts[0]
    for part in parts[1:]:
        result = pynini.compose(result, part).optimize()
    return result


def compile_feature_markers(
    config: dict,
    registry: Dict[str, pynini.Fst],
    rules: Dict[str, pynini.Fst],
) -> Dict[str, List[pynini.Fst]]:
    """
    Compile a FeatureMarkers config into a dict of feature value → [FST, ...].

    Arguments:
        config:   Fully-resolved FeatureMarkers config dict.
        registry: FSA registry.
        rules:    Compiled rules dict.
    Returns:
        Dict mapping feature value string to list of compiled FSTs.

    TODO: validate feature values against Features config
    """
    global_attributes = config.get("global_attributes", {})
    markers_spec = config.get("markers", {})

    result: Dict[str, List[pynini.Fst]] = {}

    for feature_value, marker_val in markers_spec.items():
        # TODO: we need to remember marker order
        # instead of storing a list of FSTs, store a list
        # of Tuple(pynini.Fst, str), where the str is the
        # unique name for the ordering stage
        fsts: List[pynini.Fst] = []

        if marker_val is None:
            # Zero-marking
            fsts.append(compile_marker_dict(None, registry, rules))

        elif isinstance(marker_val, dict):
            # Merge global_attributes (individual marker wins on conflict)
            merged = {**global_attributes, **marker_val}
            fsts.append(compile_marker_dict(merged, registry, rules))

        elif isinstance(marker_val, list):
            # List of marker dicts applied in sequence
            for item in marker_val:
                if item is None:
                    fsts.append(compile_marker_dict(None, registry, rules))
                elif isinstance(item, dict):
                    merged = {**global_attributes, **item}
                    fsts.append(compile_marker_dict(merged, registry, rules))
                else:
                    raise ValueError(f"Unexpected marker item type: {type(item)}")
        else:
            raise ValueError(
                f"Unexpected marker value type for '{feature_value}': {type(marker_val)}"
            )

        result[str(feature_value)] = fsts

    return result


def compile_contingent_markers(
    config: dict,
    registry: Dict[str, pynini.Fst],
    rules: Dict[str, pynini.Fst],
) -> dict:
    """
    Compile a ContingentFeatureMarkers config into a nested dict.

    The nesting structure mirrors the 'markers' structure in the config:
    the outermost key is a feature name, the next level is feature values,
    and the leaves are dicts mapping the secondary feature values to FST lists.

    Arguments:
        config:   Fully-resolved ContingentFeatureMarkers config dict.
        registry: FSA registry.
        rules:    Compiled rules dict.
    Returns:
        Nested dict: {outer_feature: {outer_value: {inner_value: [FST, ...]}}}
    """
    markers_spec = config.get("markers", {})
    result = {}

    def _compile_nested(node: dict) -> dict:
        """Recursively compile nested marker specs."""
        out = {}
        for key, value in node.items():
            if isinstance(value, dict):
                # Check if this is a leaf marker dict (has marker keys)
                # TODO: instead of checking for marker keys, check whether the key
                # is a feature specified in config.features: List[str]
                # if not, THEN check intersection with marker keys
                # if the key is neither a listed feature nor a marker key,
                # throw a value error
                marker_keys = {"prefix", "suffix", "replace", "rule", "suppletion"}
                if marker_keys.intersection(value.keys()) or not value:
                    # Leaf: compile as marker dict
                    out[str(key)] = [compile_marker_dict(value or None, registry, rules)]
                else:
                    # Intermediate: recurse
                    out[str(key)] = _compile_nested(value)
            elif value is None:
                out[str(key)] = [compile_marker_dict(None, registry, rules)]
            elif isinstance(value, list):
                fsts = []
                for item in value:
                    fsts.append(compile_marker_dict(item if item else None, registry, rules))
                out[str(key)] = fsts
            else:
                out[str(key)] = value
        return out

    for feature_name, feature_spec in markers_spec.items():
        result[feature_name] = _compile_nested(feature_spec)

    return result


# ---------------------------------------------------------------------------
# Section 6: Decoding
# ---------------------------------------------------------------------------

# Symbols to strip from decoded strings
# _STRIP_SYMBOLS = {TONE_SLOT_STR, TONE_PLACEHOLDER_STR, CLASS_PLACEHOLDER, EOS_STR}


def decode_fst_string(encoded_str: str) -> str:
    """
    TODO: Handle string decoding logic later
    Fix config compilation first.

    Decode an FST output string to human-readable IPA.

    Reverses the encoding applied by encode_fst_string():
    - Collapses space-separated char encoding back to a string
    - Replaces tone symbols (<H>, <L>, <HL>, <LH>) with Unicode diacritics
    - Removes flag symbols (<TBU>, <FLOAT>, <CL>, <ENDOFSENTENCE>)
    - Replaces '|' word boundary with a space

    Arguments:
        encoded_str: Space-separated encoded FST output string.
    Returns:
        Human-readable IPA string.
    """
    # The encoded string uses spaces between characters and multichar tokens
    # in angle-brackets or special forms. We need to collapse it back.
    # Strategy: split on spaces, then join, then replace multichar symbols.

    # First handle if input is already decoded (no spaces)
    parts = encoded_str.split(" ")
    # Re-join parts: each part is either a single char or a multichar symbol
    raw = "".join(parts)

    # Replace tone symbols with diacritics
    for symbol, diac in SYMBOL2DIAC.items():
        raw = raw.replace(symbol, diac)

    # Replace word boundary with space
    raw = raw.replace(WORD_BOUNDARY_STR, " ")

    # Strip flag/placeholder symbols
    for sym in _STRIP_SYMBOLS:
        raw = raw.replace(sym, "")

    return raw
