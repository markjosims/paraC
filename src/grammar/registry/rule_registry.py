"""
Implements the `Rule` and `RuleRegistry` classes. `Rule`
is a `TransducerList` object representing a user-defined
context-sensitive rule, and `RuleRegistry` aggregates rules
from a list of configs, builds a dependency graph (since rules
may be sequences of other rules) and maps rule names to `Rule`
objects.
"""

from src.grammar.classes import Registry
from src.fst_utils import Acceptor, ReservedSymbolMixin, TransducerList
from typing import Literal
from dataclasses import dataclass, field
import os
from loguru import logger
from graphlib import TopologicalSorter

@dataclass
class Rule(TransducerList):
    """
    Dataclass for phonological rules. Rules can be of three types:
    - Simple rules: defined by input and output patterns
    - String map rules: defined by a list of input-output string pairs
    - Rule sequence: defined by a sequence of other rules to apply in order

    Any rule can also have left and right context patterns that must be satisfied
    for the rule to apply.

    Note that the actual FST construction logic for rules is not implemented here, but
    is handled by the `FstRegistry` class which compiles patterns and rules into FSTs.

    TODO: handle PDT-based rules conditioned on flags
    """

    type: Literal["simple_rule", "string_map", "rule_sequence"] = "simple_rule"
    _ref: str = ""

    # attributes for simple rules
    input_pattern: Acceptor = field(default_factory=Acceptor)
    output_pattern: Acceptor = field(default_factory=Acceptor)

    # attributes for string map rules
    string_map: list[tuple[Acceptor, Acceptor]] = field(default_factory=list)

    # attributes for chain of rules
    rule_sequence: list['Rule'] = field(default_factory=list)

    # attributes for simple and string map rules with contexts
    left_context: Acceptor = field(default_factory=Acceptor)
    right_context: Acceptor = field(default_factory=Acceptor)

    # attributes for all rules
    direction: Literal["ltr", "rtl", "sim"] = "ltr"

    # references to other objects
    used_by: list['Rule'] = field(default_factory=list)

    # metadata
    source: os.PathLike | None = None
    description: str | None = None
    test_mappings: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()

        # duplicate `self._ref` to value so parent functions can access
        # name when logging errors
        self.value = self._ref

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
            if self.rule_sequence is None:
                raise ValueError("Rule sequence must have a rule sequence")
            elif not self.rule_sequence:
                logger.warning(f"Found empty rule sequence: {self._ref}")

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
                raise ValueError(
                    "String map rules cannot have input or output patterns"
                )
            if self.rule_sequence:
                raise ValueError("String map rules cannot have a rule sequence")

    def set_dependencies(
        self, used_by: list['Rule'], rule_sequence: list['Rule'] | None = None
    ):
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
    ) -> 'Rule':
        """
        Builds an Rule from a config dict, inferring the type
        from the attributes contained
        """
        config["_ref"] = rule_name

        # infer rule type from attrs
        # and set pattern strings to Acceptors
        if ("input_pattern" in config) and ("output_pattern" in config):
            rule_type = "simple_rule"
            config["input_pattern"] = Acceptor(config["input_pattern"])
            config["output_pattern"] = Acceptor(config["output_pattern"])
        elif "string_map" in config:
            rule_type = "string_map"
            string_map = []
            for input_str, output_str in config["string_map"]:
                string_map.append((Acceptor(input_str), Acceptor(output_str)))
            config["string_map"] = string_map
        elif "rule_sequence" in config:
            rule_type = "rule_sequence"
            # no transformation done here: handled by RuleRegistry instead
        else:
            raise ValueError(f"Unrecognized rule type for rule {config}, check format")

        config["type"] = rule_type

        # set secondary attrs to Acceptor (if applicable)
        for attr_name in ("left_context", "right_context"):
            if attr_name in config:
                config[attr_name] = Acceptor(config[attr_name])

        # cast test input, output string arrays to tuples
        if "test_mappings" in config:
            config["test_mappings"] = [
                tuple(mapping) for mapping in config["test_mappings"]
            ]

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
            raise ValueError(
                "AnonymousRule should not have a _ref string since it is not directly referenced by the user."
            )

        # set generic ref string to avoid ValueError
        # on Rule __post_init__
        self._ref = f"anonymous_rule_{id(self)}"
        super().__post_init__()

class RuleRegistry(Registry, ReservedSymbolMixin):
    """
    Initialized either with a `data` dict mapping rule names to `Rule` objects
    or a `config_objects` dict mapping filenames for YAML objects.
    """
    def __init__(
        self,
        data: dict[str, Rule] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        super().__init__(kind="Rules", data=data, config_objects=config_objects)
        self.build_dependency_graph()

    def load_all_configs(self):
        config_items = {}
        for config in self.config_objects.values():
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
    ) -> dict[str, Rule]:
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
                if (other_rule.rule_sequence) and (
                    rule._ref in other_rule.rule_sequence
                ):
                    used_by.append(other_rule)

            if rule.type == "rule_sequence":
                sub_rules = []
                sub_rule_refs = [ref.removeprefix("$") for ref in rule.rule_sequence]
                for sub_rule in sub_rule_refs:
                    if sub_rule in self.data:
                        sub_rules.append(self.data[sub_rule])
                    else:
                        raise KeyError(
                            f"Rule '{sub_rule}' referenced in rule sequence for "
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

