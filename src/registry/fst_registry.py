"""
Implements following Registry classes:
- `InventoryRegistry`: stores inventory items including phones, flags
    and classes
- `PatternRegistry`: stores patterns and tracks dependencies across them
- `RuleRegistry`: stores rules and tracks dependencies across them
- `FstRegistry`: orchestrates the above three registries and provides
    logic for building pattern acceptors and rule transducers

Registries are supported by the following classes, each representing
a single item from the relevant config.
- `InventoryItem` (inventory config)
- `Pattern` (pattern config)
- `Rule` (rule config)

In addition, the `Acceptor` class defines a general FSA, allowing
for association between the human-specified config string and the
FST object, and the `Token` is used by `FstRegistry` to represent
a single token, which may be a phone, flag, class or special symbol,
and (with the exception of delimiters and operators) maps to an FSA.

"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional, Tuple, Literal, Union
import unicodedata
from loguru import logger
import pynini
from pynini.lib import rewrite
from pynini import FstProperties
from graphlib import TopologicalSorter
from src.constants import EXAMPLE_CONFIG_DIR

from src.fst_utils import Acceptor, TransducerList, Prefix, Suffix
from src.registry.registry_utils import Registry, ReservedSymbolMixin

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
        self._populate_subdicts()

    def _populate_subdicts(self):
        phones = {}
        flags = {}
        classes = {}
        for item in self.data.values():
            if item.type == "phone":
                phones[item.value] = item
            elif item.type == "flag":
                flags[item.value] = item
            elif item.type == "class":
                classes[item.value] = item
        self.phones = phones
        self.flags = flags
        self.classes = classes

    @classmethod
    def from_config_dir(cls, config_dir: str) -> InventoryRegistry:
        registry = super().from_config_dir(config_dir=config_dir)
        registry.data = registry.load_all_configs()
        registry._populate_subdicts()

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
            duplicate_items = set([x for x in item_values if item_values.count(x) > 1])
            error = f"Collision found among item values: {item_values} " +\
                    f"Duplicate items: {duplicate_items}"
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
    value: str = ''
    type: Literal["phone", "flag", "class"] = 'phone'
    children: List[InventoryItem] = field(default_factory=list)
    parent: Optional[InventoryItem] = None
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        super().__post_init__()

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
            items.extend(child.flatten())
        return items

    def __str__(self):
        return f"InventoryItem(value='{self.value}')"
    
    def __repr__(self):
        return self.__str__()

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
        pattern_registry = super().from_config_dir(config_dir=config_dir)
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
        patterns = config.get("patterns", [])
        if not patterns:
            logger.error(f"No patterns found in config: {config}")
            return
        # each pattern is stored as a dict {'Pattern_name': {**data}}
        # since the _ref key in the pattern data is used as a unique
        # identifier internally, we ignore the user-specified pattern name
        patterns = [p.popitem()[1] for p in patterns]
        
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
                    used_by.append(other_pattern)

                if other_pattern._ref in pattern.value:
                    uses.append(other_pattern)
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
    value: Union[str, List[str]] = ''
    _ref: str = ''
    used_by: List[Pattern] = field(default_factory=list)
    uses: List[Pattern] = field(default_factory=list)
    source: Optional[os.PathLike] = None
    test_includes: List[str] = field(default_factory=list)
    test_excludes: List[str] = field(default_factory=list)


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
    
    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(self._ref)
    
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
        rule_registry = super().from_config_dir(config_dir=config_dir)
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
        rules = config.get("rules", [])
        if not rules:
            logger.error("No rules found in config")
            return

        rule_list = [
            Rule.from_config(rule_name, rule_data)
            for rule_name, rule_data in rules.items()
        ]

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
            dependency_graph[rule._ref] = set()
            # get list of rules using this rule in their rule_sequence
            used_by = []
            for other_rule in self.data.values():
                if (
                    (other_rule.rule_sequence) and
                    (rule._ref in other_rule.rule_sequence)
                ):
                    used_by.append(other_rule)

            if rule.type == "rule_sequence":
                sub_rules = []
                sub_rule_refs = [
                    ref.removeprefix("$")
                    for ref in rule.rule_sequence
                ]
                for sub_rule in sub_rule_refs:
                    if sub_rule in self.data:
                        sub_rules.append(self.data[sub_rule])
                    else:
                        raise KeyError(
                            f"Rule '{sub_rule}' referenced in rule sequence for "\
                            f"'{rule._ref}' not found in registry."
                        )
                rule.set_dependencies(
                    used_by=used_by,
                    rule_sequence=sub_rules,
                )
                dependency_graph[rule._ref] = set(sub_rule_refs)
            else:
                rule.set_dependencies(used_by=used_by)

        self.dependency_graph = dependency_graph
        rule_refs_sorted = list(TopologicalSorter(dependency_graph).static_order())
        rules_sorted = [self.data[ref] for ref in rule_refs_sorted]
        self.rules_sorted = rules_sorted

@dataclass
class Rule(TransducerList):
    """
    Dataclass for phonological rules. Rules can be of three types:
    - Simple rules: defined by input and output patterns
    - String map rules: defined by a list of input-output string pairs
    - Rule sequence: defined by a sequence of other rules to apply in order

    Any rule can also have left and right context patterns that must be satisfied
    for the rule to apply.

    Since we expect a RuleRegistry to be built upon a PatternRegistry, we load
    pattern objects directly into the Rule dataclass and track references to patterns via
    the `uses` and `used_by` fields.
    
    Note that the actual FST construction logic for rules is not implemented here, but
    is handled by the `FstRegistry` class which compiles patterns and rules into FSTs.
    """

    type: Literal["simple_rule", "string_map", "rule_sequence"] = "simple_rule"
    _ref: str = ""

    # attributes for simple rules
    input_pattern: Acceptor = field(default_factory=Acceptor)
    output_pattern: Acceptor = field(default_factory=Acceptor)

    # attributes for string map rules
    string_map: List[Tuple[Acceptor, Acceptor]] = field(default_factory=list)

    # attributes for chain of rules
    rule_sequence: List[Rule] = field(default_factory=list)

    # attributes for simple and string map rules with contexts
    left_context: Acceptor = field(default_factory=Acceptor)
    right_context: Acceptor = field(default_factory=Acceptor)

    # attributes for all rules
    direction: Literal['ltr', 'rtl', 'sim'] = 'ltr'   

    # references to other objects
    used_by: List[Rule] = field(default_factory=list)

    # metadata
    source: Optional[os.PathLike] = None
    description: Optional[str] = None
    test_mappings: List[Tuple[str, str]] = field(default_factory=list)


    def __post_init__(self):
        super().__post_init__()

        self.dependencies_built = False

        if not self._ref:
            raise ValueError("_ref key must have a non-empty string.")

        if self._ref in ReservedSymbolMixin.reserved_symbols:
            error = f"Rule ref '{self._ref}' cannot be a reserved symbol."
            logger.error(error)
            raise ValueError(error)

        if self.used_by:
            raise ValueError(
                "used_by should not be passed on init but constructed by a RuleRegistry object."
            )
        
        if self.type == "simple_rule":
            if (not self.input_pattern) or (not self.output_pattern):
                raise ValueError("Simple rules must have input and output patterns")
            if self.string_map:
                raise ValueError("Simple rules cannot have a string map")
            if self.rule_sequence:
                raise ValueError("Simple rules cannot have a rule sequence")
            
        if self.type == "rule_sequence":
            if not self.rule_sequence:
                raise ValueError("Rule sequence must have a rule sequence")
            if self.input_pattern.value or self.output_pattern.value:
                raise ValueError("Rule sequence cannot have input or output patterns")
            if self.string_map:
                raise ValueError("Rule sequence cannot have a string map")
            if self.left_context.value or self.right_context.value:
                raise ValueError("Rule sequence cannot have left or right context")
        
        if self.type == "string_map":
            if not self.string_map:
                raise ValueError("String map rules must have a string map")
            if self.input_pattern.value or self.output_pattern.value:
                raise ValueError("String map rules cannot have input or output patterns")
            if self.rule_sequence:
                raise ValueError("String map rules cannot have a rule sequence")

    def set_dependencies(self, used_by: List[Rule], rule_sequence: Optional[List[Rule]] = None):
        self.used_by = used_by
        if rule_sequence is not None and self.type != "rule_sequence":
            raise ValueError(
                f"if `rule_sequence` is passed expect type='rule_sequence' but got type={self.type}"
            )
        self.rule_sequence = rule_sequence
        self.dependencies_built = True
        

    def __str__(self):
        return f"Rule(_ref='{self._ref}', type='{self.type}')"
    
    def __repr__(self):
        return self.__str__()

    @classmethod
    def from_config(
            cls,
            rule_name: str,
            config: dict,
    ) -> Rule:
        """
        Builds an Rule from a config dict, inferring the type
        from the attributes contained
        """
        config['_ref'] = rule_name


        # infer rule type from attrs
        # and set pattern strings to Acceptors
        if ('input_pattern' in config) and ('output_pattern' in config):
            rule_type = 'simple_rule'
            config['input_pattern'] = Acceptor(config['input_pattern'])
            config['output_pattern'] = Acceptor(config['output_pattern'])
        elif 'string_map' in config:
            rule_type = 'string_map'
            string_map = []
            for input_str, output_str in config['string_map']:
                string_map.append(
                    (Acceptor(input_str), Acceptor(output_str))
                )
            config['string_map'] = string_map
        elif 'rule_sequence' in config:
            rule_type = 'rule_sequence'
            # no transformation done here: handled by RuleRegistry instead
        else:
            raise ValueError(
                f"Unrecognized rule type for rule {config}, check format"
            )
        
        config['type'] = rule_type

        # set secondary attrs to Acceptor (if applicable)
        for attr_name in ('left_context', 'right_context'):
            if attr_name in config:
                config[attr_name] = Acceptor(config[attr_name])

        # cast test input, output string arrays to tuples
        if 'test_mappings' in config:
            config['test_mappings'] = [tuple(mapping) for mapping in config['test_mappings']]

        rule = cls(**config)
        return rule

    def __str__(self):
        return f"Rule(_ref={self._ref}, type={self.type})"
    
class AnonymousRule(Rule):
    """
    A subclass of Rule to represent rules that are generated internally by the FstRegistry
    and not specified directly by the user in a config file. These rules do not have a _ref
    string since they are not referenced directly by the user, but instead are used as helper
    rules for implementing replace or suppletion markers.
    """

    def __post_init__(self):
        if self._ref:
            raise ValueError("AnonymousRule should not have a _ref string since it is not directly referenced by the user.")
        
        # set generic ref string to avoid ValueError
        # on Rule __post_init__
        self._ref = f"anonymous_rule_{id(self)}"
        super().__post_init__()

class FstRegistry(Registry, ReservedSymbolMixin):
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

        self._symbol_table_built = False
        self._inventory_acceptors_built = False
        self._sigmas_built = False
        self._pattern_acceptors_built = False
        self._rule_transducers_built = False
        self.is_initialized = False

        if not inventory_registry:
            return

        self.inventory: Dict[str, InventoryItem] = inventory_registry.data
        self.phones: Dict[str, InventoryItem] = inventory_registry.phones # TODO change this from list to dict!
        self.flags: Dict[str, InventoryItem] = inventory_registry.flags
        self.classes: Dict[str, InventoryItem] = inventory_registry.classes
        self.patterns: Dict[str, Pattern] = pattern_registry.data
        self.patterns_sorted: Tuple[Pattern, ...] = pattern_registry.patterns_sorted
        self.rules: Dict[str, Rule] = rule_registry.data 
        self.rules_sorted: Tuple[Rule, ...] = rule_registry.rules_sorted       

        if not self.inventory:
            # don't try to initialize if inventory is empty
            # instead leave the registry in an uninitialized state
            return

        self.initialize()
        if not self.is_initialized:
            raise ValueError("Error occurred while initializing FstRegistry, check logs.")
    
    @classmethod
    def from_config_dir(
        cls,
        config_dir: str,
    ) -> FstRegistry:
        logger.info("Loading child registries for FstRegistry...")

        inventory_registry = None
        pattern_registry = None
        rule_registry = None

        try:
            inventory_registry = InventoryRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading inventory registry: {e}")

        try:
            pattern_registry = PatternRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading pattern registry: {e}")

        try:
            rule_registry = RuleRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading rule registry: {e}")

        if (inventory_registry is None) or (not inventory_registry.data):
            logger.warning(
                "InventoryRegistry was found empty after construction. "
                "FstRegistry will not be initialized until inventory_registry "
                "is provided and `initialize()` is called."
            )
            return cls(inventory_registry, pattern_registry, rule_registry)

        return cls(inventory_registry, pattern_registry, rule_registry)

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
        self._build_symbol_table()
        self._build_boundary_acceptors()
        self._build_inventory_acceptors()
        self._build_sigmas()
        self._build_token_map()
        self._build_pattern_acceptors()
        self._build_rule_transducers()
        self.is_initialized = True

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
        self.boundary_fsa = pynini.union(
            self.affix_boundary_fsa,
            self.clitic_boundary_fsa,
        )

        self.bow_fsa = pynini.accep(
            self.bow,
            token_type=self.symbols
        )
        self.eow_fsa = pynini.accep(
            self.eow,
            token_type=self.symbols
        )
        self.word_edge_fsa = pynini.union(self.bow_fsa, self.eow_fsa)

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
                pynini.accep(child.value, token_type=self.symbols)
                for child in children
                if child.type != 'class'
            ]
            acceptor = pynini.union(*child_values)
            item.set_acceptor(acceptor)
        self._inventory_acceptors_built = True

    def _build_sigmas(self):
        if not self._inventory_acceptors_built:
            raise ValueError(
                "Cannot build sigma acceptors if inventory acceptors are not initialized."
            )
        if not self.phones:
            raise ValueError(
                "Cannot build FstRegistry without any phones in inventory, "
                "but no phones found. Check inventory config files."
            )
        phone_fsa = pynini.union(*[
            phone.fsa for phone in self.phones.values()
        ])

        # unlike phones, an inventory may have zero flags
        # in which case the flag_fsa is just the empty language
        if self.flags:
            flag_fsa = pynini.union(*[
                flag.fsa for flag in self.flags.values()
            ])
        else:
            flag_fsa = pynini.accep("")

        sigma = pynini.union(
            phone_fsa, flag_fsa, self.boundary_fsa, self.word_edge_fsa
        )

        self.phone_fsa = phone_fsa
        self.flag_fsa = flag_fsa
        self.sigma = sigma

        self.phone_star = phone_fsa.star
        self.flag_star = flag_fsa.star
        self.sigma_star = sigma.star
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

        if token_str == self.phone_ref:
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
        for l_delimiter in self.left_delimiters:
            tokens["left_delimiter"].append(Token(value=l_delimiter, type="left_delimiter"))
        for r_delimiter in self.right_delimiters:
            tokens["right_delimiter"].append(Token(value=r_delimiter, type="right_delimiter"))
        for op in self.unary_operators:
            tokens["unary_operator"].append(Token(value=op, type="unary_operator"))
        for op in self.pipe_operator:
            tokens["pipe_operator"].append(Token(value=op, type="pipe_operator"))
        for op in self.caret_operator:
            tokens["caret_operator"].append(Token(value=op, type="caret_operator"))
        for ref in self.reserved_refs:
            acceptor = self._token_acceptor(ref)
            tokens["ref"].append(Token(value=ref, type="special_ref", acceptor=acceptor))
        for flag in self.bow_eow_flags:
            acceptor = self._token_acceptor(flag)
            tokens["flag"].append(Token(value=flag, type="bow_eow", acceptor=acceptor))
        for boundary in self.boundary_symbols:
            acceptor = self._token_acceptor(boundary)
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
        elif starting_char in self.unary_operators:
            return "unary_operator"
        elif starting_char  == self.pipe_operator:
            return "pipe_operator"
        elif starting_char == self.caret_operator:
            return "caret_operator"
        elif starting_char in self.left_delimiters:
            return "left_delimiter"
        elif starting_char in self.right_delimiters:
            return "right_delimiter"
        elif starting_char in self.boundary_symbols:
            return "boundary"
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
            acceptor = self.parse_pattern(pattern.value)
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

    def _parse_rule(self, rule: Rule) -> Union[pynini.Fst, List[pynini.Fst]]:
        """
        Constructs all acceptors and transducers needed for a context-sensitive
        rule and returns the rule transducer or list of transducers (for a rule
        sequence)
        """
        if rule.type == "rule_sequence":
            return [sub_rule.fst for sub_rule in rule.rule_sequence]
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
        if rule.type == 'simple_rule':
            input_pattern = rule.input_pattern
            if not input_pattern.acceptor_built:
                input_pattern.set_acceptor(
                    self.parse_pattern(input_pattern.value)
                )
            output_pattern = rule.output_pattern
            if not output_pattern.acceptor_built:
                output_pattern.set_acceptor(
                    self.parse_pattern(output_pattern.value)
                )
            tau = pynini.cross(
                input_pattern.fsa,
                output_pattern.fsa
            )
        elif rule.type == 'string_map':
            transducers = []
            for input_acceptor, output_acceptor in rule.string_map:
                input_acceptor.set_acceptor(
                    self.parse_pattern(input_acceptor.value)
                )
                output_acceptor.set_acceptor(
                    self.parse_pattern(output_acceptor.value)
                )
                transducer = pynini.cross(
                    input_acceptor.fsa,
                    output_acceptor.fsa,
                )
                transducers.append(transducer)
            tau = pynini.union(*transducers)
        else:
            raise ValueError(f"Cannot interpret tau for rule type {rule.type}")
        return tau
    
    def _parse_rule_context(self, rule: Rule) -> Tuple[pynini.Fst, pynini.Fst]:
        left_context_fsa = self.parse_pattern(rule.left_context)

        # special case: if right context is just '#' (word edge)
        # interpret as [EOS] (otherwise _parse_pattern will 
        # default to [BOS] since it's at the beginning of the string)
        if rule.right_context.value == self.word_edge:
            rule.right_context.set_acceptor(
                self._token_acceptor(self.eow_flag)
            )
            right_context_fsa = rule.right_context.fsa
        else:
            right_context_fsa = self.parse_pattern(rule.right_context)
        if isinstance(rule.left_context, Acceptor):
            rule.left_context.set_acceptor(left_context_fsa)
        if isinstance(rule.right_context, Acceptor):
            rule.right_context.set_acceptor(right_context_fsa)
        return left_context_fsa, right_context_fsa
        
    def parse_pattern(
            self,
            pattern_input: Union[str, Acceptor, List[str], None]
        ) -> pynini.Fst:
        """
        Interprets a pattern string as an FSA.
        """
        if isinstance(pattern_input, Acceptor):
            if pattern_input.acceptor_built:
                logger.info(f"Redundant call on pattern {pattern_input._ref} with existing acceptor")
                return pattern_input.fsa
            pattern_input = pattern_input.value
        if not pattern_input:
            return pynini.accep('', token_type=self.symbols)
        elif isinstance(pattern_input, list):
            acceptors = []
            for sub_pattern in pattern_input:
                sub_acceptor = self.parse_pattern(sub_pattern)
                acceptors.append(sub_acceptor)
            return pynini.union(*acceptors)
        try:
            tokens = self._tokenize_str(pattern_input)
            acceptor = self._parse_tokens(tokens)
        except Exception as e:
            raise Exception(
                f"Error occurred while parsing pattern {pattern_input} ",
                e
            )
        return acceptor

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

    def _tokenize_str(self, input_str: str) -> List[Token]:
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
        acceptor, current_index = self._parse_expression(tokens, initial_index=0)
        if current_index != len(tokens):
            raise ValueError(f"Tokens remaining after parsing expression for token array {tokens}")
        return acceptor

    def _parse_expression(
            self,
            tokens: List[Token],
            initial_index: int,
        ) -> Tuple[pynini.Fst, int]:
        """
        Parses an expression in the token array starting at `current_index`, where
        an expression is a single term or any sequence of term | term | term ...
        """
        current_index = initial_index
        term, current_index = self._parse_term(tokens, current_index)
        terms = [term]
        while (
            (current_index < len(tokens))
            and tokens[current_index].type == 'pipe_operator'
        ):
            current_index+=1
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
        tokens: List[Token],
        initial_index: int,
    ) -> Tuple[pynini.Fst, int]:
        """
        Parses a term, i.e. a sequence of factors and unary operators of
        arbitrary length, OR a delimited expression in parentheses or curly braces.
        """
        current_index = initial_index
        current_type = tokens[current_index].type
        if current_type in ("right_delimiter", "pipe_operator"):
            raise ValueError(
                f"Got unexpected token type {current_type} at start of term, tokens {tokens} current index {current_index}"
            )

        factors_w_operators = []
        while (
            (current_index < len(tokens)) and
            (current_type not in ("right_delimiter", "pipe_operator"))
        ):
            factor_list, current_index = self._parse_factor_sequence(tokens, current_index)
            # check if `_parse_factor_sequence` stopped before a unary operator
            # and if so apply the operator to the last factor
            if current_index < len(tokens):
                current_type = tokens[current_index].type
                if current_type == 'unary_operator':
                    operator = tokens[current_index].value
                    last_factor = factor_list[-1]
                    last_factor = self._interpret_unary_operator(last_factor, operator)
                    factor_list[-1] = last_factor
                    current_index+=1
            factors_w_operators.extend(factor_list)
        
        if not factors_w_operators:
            raise ValueError(f"Empty term detected in token sequence {tokens} current index {current_index}")
        if len(factors_w_operators) == 1:
            return factors_w_operators[0], current_index
        output_factor = factors_w_operators[0]
        for factor in factors_w_operators[1:]:
            output_factor = pynini.concat(output_factor, factor)
        return output_factor, current_index

    def _parse_factor_sequence(
            self,
            tokens: List[Token],
            initial_index: int,
        ) -> Tuple[List[pynini.Fst], int]:
        """
        Consume tokens starting at `current_index` and until the end of the
        current factor is reached. Then return a list of acceptors for each
        token,alongside the index of the first token after the current
        factor sequence.
        """
        acceptors = []
        current_index = initial_index
        while current_index < len(tokens):
            token_acceptor = tokens[current_index].acceptor
            token_type = tokens[current_index].type
            if token_acceptor is not None and token_acceptor.acceptor_built:
                acceptors.append(token_acceptor.fsa)
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
                acceptors.append(acceptor)
            elif token_type in ("pipe_operator", "unary_operator", "right_delimiter"):
                # let parent function handle
                break
            else:
                raise ValueError(
                    f"Cannot parse token of type {token_type} at index {current_index} tokens {tokens}"
                )

        if not acceptors:
            raise ValueError(f"Empty factor detected in token sequence {tokens} current index {current_index}")
        return acceptors, current_index
            
    def _parse_delimited_factor(
            self,
            tokens: List[Token],
            initial_index: int,
    ) -> Tuple[pynini.Fst, int]:
        current_index = initial_index
        left_delimiter = tokens[current_index].value
        current_index+=1
        
        # curly braces indicate union of tokens
        if left_delimiter == r'{':
            # check if group begins with caret operator, which indicates negation of the union
            is_negated = False
            if tokens[current_index].type == 'caret_operator':
                is_negated = True
                current_index+=1
            expected_right_delimiter = r'}'
            factor_list, current_index = self._parse_factor_sequence(
                tokens=tokens,
                initial_index=current_index,
            )
            if not is_negated:
                inner_expression = pynini.union(*factor_list)
            else:
                inner_expression = pynini.difference(self.sigma, pynini.union(*factor_list))

        # parentheses indicate a single expression
        elif left_delimiter == r'(':
            expected_right_delimiter = r')'
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
        current_index+=1
        return inner_expression, current_index


    def _interpret_unary_operator(self, term: pynini.Fst, operator: str) -> pynini.Fst:
        if operator == '?':
            return term.ques
        if operator == '+':
            return term.plus
        if operator == '*':
            return term.star
        raise ValueError(f"Unrecognized unary operator {operator}")
    
    def fsa(self, fsa_input: str) -> pynini.Fst:
        """
        Constructs FSA for input string.
        Wraps `self.parse_pattern` but only takes a string,
        not an `Acceptor`.
        """
        if not isinstance(fsa_input, str):
            raise ValueError(f"Input to `fsa` must be a string, got {type(fsa_input)}")

        return self.parse_pattern(fsa_input)
    
    def word_fsa(self, word_str: str) -> pynini.Fst:
        """
        Constructs an FSA for a word, i.e. a string with [BOS] and [EOS] markers at the beginning and end.
        """
        if not isinstance(word_str, str):
            raise ValueError(f"Input to `word_fsa` must be a string, got {type(word_str)}")
        word_str = self.bow + word_str + self.eow
        return self.parse_pattern(word_str)
    
    def acceptor(
            self,
            fsa_input: str,
            acceptor_class: Acceptor = Acceptor
        ) -> Acceptor:
        """
        Given a pattern string and an uninitialized `Acceptor` class,
        return an initialized the `Acceptor` with a built FSA
        """
        fsa = self.fsa(fsa_input)
        acceptor: Acceptor = acceptor_class(fsa_input)
        acceptor.set_acceptor(fsa)
        return acceptor
    
    def prefix(self, prefix_str: str) -> Prefix:
        """
        Returns a `Prefix` object with an initialized FST
        """
        prefix = Prefix(prefix_str, stem=self.sigma_star)
        prefix_fsa = self.fsa(prefix_str)
        prefix.set_transducer(prefix_fsa)
        return prefix
    
    def suffix(self, suffix_str: str) -> Suffix:
        """
        Returns a `Suffix` object with an initialized FST
        """
        suffix = Suffix(suffix_str, stem=self.sigma_star)
        suffix_fsa = self.fsa(suffix_str)
        suffix.set_transducer(suffix_fsa)
        return suffix
    
    def replace_transducer(
            self,
            input_pattern: str,
            output_pattern: str
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
            string_map: List[List[str]],
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
            string_map=string_map_acceptors,
        )
        rule_fst = self._parse_rule(string_map_rule)
        string_map_rule.set_transducer(rule_fst)
        return string_map_rule
    
    def apply_rule(
            self,
            rule_input: Union[str, pynini.Fst],
            rule_ref: str
        ) -> pynini.Fst:
        """
        Applies the rule specified by `rule_ref` to the input string or FST
        and returns the output FST.
        """
        if rule_ref not in self.rules:
            raise KeyError(f"Rule ref '{rule_ref}' not found in registry.")
        rule = self.rules[rule_ref]

        if not rule.transducer_built:
            raise ValueError(f"Rule '{rule_ref}' has uninitialized transducer, check logs for details.")
        
        if isinstance(rule_input, str):
            input_fsa = self.word_fsa(rule_input)
        elif isinstance(rule_input, pynini.Fst):
            input_fsa = rule_input
        else:
            raise ValueError(f"rule_input must be a string or FST, got {type(rule_input)}")

        if isinstance(rule.fst, list):
            output_fsa = input_fsa
            for subrule_fst in rule.fst:
                output_fsa = rewrite.rewrite_lattice(
                    string=output_fsa,
                    rule=subrule_fst,
                    token_type=self.symbols,
                )
            return output_fsa
        return rewrite.rewrite_lattice(
            string=input_fsa,
            rule=rule.fst,
            token_type=self.symbols,
        )
    
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
        test_includes: List[str],
        test_excludes: List[str],
    ) -> dict:
        """
        Test explicit include/exclude strings against the compiled FSA for a
        single pattern.

        Returns a dict with per-string results and an overall ``all_pass`` flag::

            {"ref": "<V>", "results": [...], "all_pass": True}

        Raises ``KeyError`` if *pattern_ref* is not in the registry.
        """
        if pattern_ref not in self.patterns:
            raise KeyError(
                f"Pattern ref '{pattern_ref}' not found in registry."
            )
        pattern = self.patterns[pattern_ref]

        results: List[dict] = []
        all_pass = True

        for test_str in test_includes:
            try:
                input_fsa = self.word_fsa(test_str)
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
        test_mappings: List[List[str]],
    ) -> dict:
        """
        Test explicit input→output mappings against the compiled FST for a
        single rule.

        Returns a dict with per-mapping results and an overall ``all_pass`` flag::

            {"ref": "diphthongization", "results": [...], "all_pass": True}

        Raises ``KeyError`` if *rule_ref* is not in the registry.
        """
        if rule_ref not in self.rules:
            raise KeyError(
                f"Rule ref '{rule_ref}' not found in registry."
            )

        results: List[dict] = []
        all_pass = True

        for input_str, expected_output_str in test_mappings:
            try:
                output_fsa = self.apply_rule(input_str, rule_ref)
                output_fsa = pynini.project(output_fsa, project_type='output')
                expected_output_fsa = self.word_fsa(expected_output_str)
                intersection = pynini.intersect(output_fsa, expected_output_fsa)
                passed = intersection.start() != pynini.NO_STATE_ID
            except Exception:
                passed = False
            results.append({
                "input": input_str,
                "output": expected_output_str,
                "type": "mapping",
                "pass": passed,
            })
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
                output_fsa = pynini.project(output_fsa, project_type='output')
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
            project: Literal['input', 'output'] = 'output',
            nshortest: int = None
    ) -> List[Tuple[str, float]]:

        decoded_outputs = []
        fsa = pynini.project(fst, project_type=project)
        if nshortest is not None:
            fsa = rewrite.lattice_to_nshortest(fsa, nshortest=nshortest)

        path_iter = fsa.paths()
        while not path_iter.done():
            label_iter = path_iter.olabels()
            word = self._decode_labels(label_iter)
            weight = float(path_iter.weight())
            if word not in  decoded_outputs:
                decoded_outputs.append((word, weight))
            path_iter.next()

        decoded_outputs.sort(key=lambda t:t[-1])
        return decoded_outputs

    def fsm_strings(
            self,
            fst: pynini.Fst,
            project: Literal['input', 'output'] = 'output',
            nshortest: int = None,
    ) -> List[Tuple[str, float]]:
        """
        Return all (or nshortest) strings for an input FSM.
        Wraps `self.fsm_strings_and_weights` but only passes string.
        """
        strs_and_weights = self.fsm_strings_and_weights(
            fst=fst,
            project=project,
            nshortest=nshortest
        )
        string_list = [string for string, _ in strs_and_weights]
        return string_list

    def fsm_string(
            self,
            fst: pynini.Fst,
            project: Literal['input', 'output'] = 'output',
    ) -> str:
        """
        Wraps `self.fsm_strings` with `nshortest=1` and returns
        single string instead of list of strings.
        """
        string_list = self.fsm_strings(fst, project, nshortest=1)
        if len(string_list) != 1:
            raise ValueError(
                f"Expected single string, got {string_list}"
            )
        return string_list[0]
        
    def _decode_labels(self, label_iter, strip_word_edge_symbols=True) -> str:
        """
        Arguments:
            label_iter:     An iterator over FST labels
        Returns:
            word:           Decoded string from the labels

        Decodes a string from the given `label_iter`.
        """
        word = ''
        for label in label_iter:
            if label == 0:
                    # epsilon, skip
                continue
            symbol = self.symbols.find(label)
            word += symbol
        if strip_word_edge_symbols:
            word = word.strip(''.join(self.bow_eow_flags))

        return word

@dataclass
class Token:
    value: str
    type: Literal[
        "phone", "flag", "class_ref", "pattern_ref",
        "bow_eow", "special_ref", "unary_operator",
        "pipe_operator", "caret_operator", "boundary",
        "left_delimiter", "right_delimiter",
    ]
    acceptor: Optional[Acceptor] = None

    def __post_init__(self):
        """
        Check if Token has acceptor if it is of the appropriate type.
        operators and delimiters should not have acceptors,
        all other types should have them.
        """
        if (
            self.type.endswith("operator") or self.type.endswith("delimiter")
        ):
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

if __name__ == '__main__':
    # test initializing each config
    inventory_reg = InventoryRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    pattern_reg = PatternRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    rule_reg = RuleRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    fst_reg = FstRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)