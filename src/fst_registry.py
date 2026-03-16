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
    string_map: List[Tuple[Acceptor, Acceptor]] = field(default_factory=list)

    # attributes for chain of rules
    rule_sequence: List[Rule] = field(default_factory=list)

    # attributes for all rule types
    left_context: Acceptor = field(default_factory=Acceptor)
    right_context: Acceptor = field(default_factory=Acceptor)
    direction: Literal['ltr', 'rtl', 'sim'] = 'ltr'    


    # references to other objects
    used_by: List[Rule] = field(default_factory=list)

    # metadata
    source: Optional[os.PathLike] = None

    # initialized by FstRegistry
    fst: Optional[pynini.Fst] = None

    def __post_init__(self):
        self.dependencies_built = False
        self.transducer_built = False

        if self._ref in ReservedSymbolMixin.reserved_symbols:
            error = f"Rule ref '{self._ref}' cannot be a reserved symbol."
            logger.error(error)
            raise ValueError(error)

        if self.fst is not None:
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

    def set_transducer(self, fst: pynini.Fst):
        if self.transducer_built:
            raise ValueError("Transducer cannot be overridden.")
        if not fst.properties(pynini.ACCEPTOR, False):
            raise ValueError("Must be a non-vacuous FST")
        self.fst = fst
        self.acceptor_built = True

    @classmethod
    def from_config(
            cls,
            item_dict: dict,
    ) -> Rule:
        """
        Builds an InventoryItem from a config dict
        If config has children (nested dicts), recursively
        build child InventoryItems and attach to parent
        """

        # infer rule type from attrs
        # and set pattern strings to Acceptors
        if ('input_pattern' in item_dict) and ('output_pattern' in item_dict):
            rule_type = 'simple_rule'
            item_dict['input_pattern'] = Acceptor(item_dict['input_pattern'])
            item_dict['output_pattern'] = Acceptor(item_dict['output_pattern'])
        elif 'string_map' in item_dict:
            rule_type = 'string_map'
            string_map = []
            for input_str, output_str in string_map:
                string_map.append(
                    (Acceptor(input_str), Acceptor(output_str))
                )
            item_dict['string_map'] = string_map
        elif 'rule_sequence' in item_dict:
            rule_type = 'chain_of_rules'
            # no transformation done here: handled by RuleRegistry instead
        
        item_dict['kind'] = rule_type

        # set secondary attrs to Acceptor (if applicable)
        for attr_name in ('left_context', 'right_context'):
            if attr_name in item_dict:
                item_dict[attr_name] = Acceptor(item_dict[attr_name])

        rule = cls(**item_dict)
        return rule


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
        self._sigmas_built = False
        self._pattern_acceptors_built = False
        self._rule_transducers_built = False
        self.initialized = False

        self.initialize()
        if not self.initialized:
            raise ValueError("Error occurred while initializing FstRegistry, check logs.")
    
    @classmethod
    def from_config_dir(cls, config_dir: str) -> FstRegistry:
        inventory_registry = InventoryRegistry.from_config_dir(config_dir)
        pattern_registry = PatternRegistry.from_config_dir(config_dir)
        rule_registry = RuleRegistry.from_config_dir(config_dir)
        return cls(inventory_registry, pattern_registry, rule_registry)

    def initialize(self):
        if self.initialized:
            logger.warning("FstRegistry already initialized, returning...")
            return
        self._build_symbol_table()
        self._build_inventory_acceptors()
        self._build_sigmas()
        self._build_pattern_acceptors()
        self._build_rule_transducers()
        self.initialized = True()

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
            return "phone"
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

    def _build_sigmas(self):
        if not self._inventory_acceptors_built:
            raise ValueError(
                "Cannot build sigma acceptors if inventory accepts are not initialized."
            )
        phone_acceptor = pynini.union(
            phone.acceptor for phone in self.phones.values()
        )
        flag_acceptor = pynini.union(
            flag.acceptor for flag in self.flags.values()
        )
        sigma = pynini.union(phone_acceptor, flag_acceptor)

        self.phone_fsa = phone_acceptor
        self.flag_fsa = flag_acceptor
        self.sigma = sigma

        self.phone_star = phone_acceptor.star
        self.flag_star = flag_acceptor.star
        self.sigma_star = sigma.star
        self._sigmas_built = True


    def _build_pattern_acceptors(self):
        """
        Parse patterns using recursive descent.
        """
        for pattern in self.patterns_sorted:
            tokens = self._tokenize_str(pattern.value)
            acceptor = self.parse_pattern(tokens)
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

    def _parse_rule(self, rule: Rule) -> pynini.Fst:
        """
        Constructs all acceptors and transducers
        """
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
            sigma_star=sigma_star
        )
        return rule_fst

    def _parse_rule_tau(self, rule: Rule) -> pynini.Fst:
        if rule.kind == 'simple':
            input_pattern = rule.input_pattern
            output_pattern = rule.output_pattern
            input_pattern.set_acceptor(
                self.parse_pattern(input_pattern.value)
            )
            output_pattern.set_acceptor(
                self.parse_pattern(output_pattern.value)
            )
            tau = pynini.cross(
                input_pattern.fsa,
                output_pattern.fsa
            )
        elif rule.kind == 'string_map':
            transducers = []
            for input_fsa, output_fsa in rule.string_map:
                input_fsa.set_acceptor(
                    self.parse_pattern(input_fsa.value)
                )
                output_fsa.set_acceptor(
                    self.parse_pattern(output_fsa.value)
                )
                transducer = pynini.cross(input_fsa, output_fsa)
                transducers.append(transducer)
            tau = pynini.union(*transducers)
        elif rule.kind == 'chain_of_rules':
            tau = self.sigmar_star
            for subrule in rule.rule_sequence:
                if not subrule.transducer_built:
                    raise ValueError(
                        f"Uninitialized rule {subrule._ref} found in rule sequence {rule._ref}, "
                        "check RuleRegistry topological sort."
                    )
                tau@=subrule.fst
        else:
            raise ValueError(f"Unknown rule type {rule.kind}")
        return tau
    
    def _parse_rule_context(self, rule: Rule) -> Tuple[pynini.Fst, pynini.Fst]:
        left_context_fsa = self.parse_pattern(rule.left_context)
        right_context_fsa = self.parse_pattern(rule.right_context)
        if isinstance(rule.left_context, Acceptor):
            rule.left_context.set_acceptor(left_context_fsa)
        if isinstance(rule.right_context, Acceptor):
            rule.right_context.set_acceptor(right_context_fsa)
        return left_context_fsa, right_context_fsa
        
    def parse_pattern(self, input_str: Optional[str]) -> pynini.Fst:
        """
        Interprets a pattern string as an FSA.
        """
        if not input_str:
            return pynini.accep('', token_type=self.symbols)
        tokens = self._tokenize_str(input_str)
        acceptor = self._parse_tokens(tokens)
        return acceptor

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
    
    def __eq__(self, other):
        other_str = other
        if type(other) is Token:
            other_str = other.value
        return self.value == other_str