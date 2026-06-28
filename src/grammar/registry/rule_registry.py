"""
Implements the `Rule` and `RuleRegistry` classes. `Rule`
is a `TransducerList` object representing a user-defined
context-sensitive rule, and `RuleRegistry` aggregates rules
from a list of configs, builds a dependency graph (since rules
may be sequences of other rules) and maps rule names to `Rule`
objects.
"""

from src.grammar.classes import Registry
from src.fst_utils import Acceptor, AcceptorLike, ReservedSymbolMixin, TransducerList
from typing import Literal, Protocol, runtime_checkable
from dataclasses import dataclass, field
import os
from loguru import logger
from graphlib import TopologicalSorter
from uuid import uuid4


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

    kind: Literal["simple_rule", "string_map", "rule_sequence"] = "simple_rule"
    name: str = ""

    # attributes for simple rules
    input_pattern: Acceptor = field(default_factory=Acceptor)
    output_pattern: Acceptor = field(default_factory=Acceptor)

    # attributes for string map rules
    string_map: list[tuple[Acceptor, Acceptor]] = field(default_factory=list)

    # attributes for chain of rules
    rule_sequence: list["Rule"] = field(default_factory=list)

    # attributes for simple and string map rules with contexts
    left_context: Acceptor = field(default_factory=Acceptor)
    right_context: Acceptor = field(default_factory=Acceptor)

    # attributes for all rules
    direction: Literal["ltr", "rtl", "sim"] = "ltr"

    # references to other objects
    used_by: list["Rule"] = field(default_factory=list)

    # metadata
    source: os.PathLike | None = None
    description: str | None = None
    test_mappings: list[tuple[str, str]] = field(default_factory=list)

    uuid: str = field(default_factory=lambda: str(uuid4()), init=False)

    def __post_init__(self):
        super().__post_init__()

        # duplicate `self.name` to value so parent functions can access
        # name when logging errors
        self.value = self.name

        self.dependencies_built = False

        if not self.name:
            raise ValueError("name key must have a non-empty string.")

        if self.name in ReservedSymbolMixin.reserved_symbols:
            error = f"Rule name '{self.name}' cannot be a reserved symbol."
            logger.error(error)
            raise ValueError(error)

        if self.used_by:
            raise ValueError(
                "used_by should not be passed on init but constructed by a RuleRegistry object."
            )

        if self.kind == "simple_rule":
            if (not self.input_pattern) or (not self.output_pattern):
                raise ValueError("Simple rules must have input and output patterns")
            if self.string_map:
                raise ValueError("Simple rules cannot have a string map")
            if self.rule_sequence:
                raise ValueError("Simple rules cannot have a rule sequence")

        if self.kind == "rule_sequence":
            if self.rule_sequence is None:
                raise ValueError("Rule sequence must have a rule sequence")
            elif not self.rule_sequence:
                logger.warning(f"Found empty rule sequence: {self.name}")

            if self.input_pattern.value or self.output_pattern.value:
                raise ValueError("Rule sequence cannot have input or output patterns")
            if self.string_map:
                raise ValueError("Rule sequence cannot have a string map")
            if self.left_context.value or self.right_context.value:
                raise ValueError("Rule sequence cannot have left or right context")

        if self.kind == "string_map":
            if not self.string_map:
                raise ValueError("String map rules must have a string map")
            if self.input_pattern.value or self.output_pattern.value:
                raise ValueError(
                    "String map rules cannot have input or output patterns"
                )
            if self.rule_sequence:
                raise ValueError("String map rules cannot have a rule sequence")

    def set_dependencies(
        self, used_by: list["Rule"], rule_sequence: list["Rule"] | None = None
    ):
        self.used_by = used_by
        if rule_sequence is not None and self.kind != "rule_sequence":
            raise ValueError(
                f"if `rule_sequence` is passed expect kind='rule_sequence' but got kind={self.kind}"
            )
        self.rule_sequence = rule_sequence
        self.dependencies_built = True

    def __str__(self):
        return f"Rule(name='{self.name}', kind='{self.kind}')"

    def __repr__(self):
        return self.__str__()

    @classmethod
    def from_config(
        cls,
        config: dict,
    ) -> "Rule":
        """
        Builds a Rule from a config dict, inferring the type
        from the attributes contained. This method is non-destructive
        and safely handles both raw string and already-initialized
        Acceptor inputs.
        """
        # infer rule type from attrs
        if ("input_pattern" in config) and ("output_pattern" in config):
            rule_kind = "simple_rule"
        elif "string_map" in config:
            rule_kind = "string_map"
        elif "rule_sequence" in config:
            rule_kind = "rule_sequence"
        else:
            raise ValueError(f"Unrecognized rule type for rule {config}, check format")

        # Build construction kwargs explicitly to avoid mutating input dict
        kwargs = {
            "kind": rule_kind,
            "name": config.get("name", ""),
            "description": config.get("description"),
            "source": config.get("source_path"),
            "direction": config.get("direction", "ltr"),
        }

        if rule_kind == "simple_rule":
            kwargs["input_pattern"] = cls._to_acceptor(config["input_pattern"])
            kwargs["output_pattern"] = cls._to_acceptor(config["output_pattern"])
        elif rule_kind == "string_map":
            kwargs["string_map"] = [
                (cls._to_acceptor(inp), cls._to_acceptor(out))
                for inp, out in config["string_map"]
            ]
        elif rule_kind == "rule_sequence":
            # Registry handles resolving these refs to Rule objects later
            kwargs["rule_sequence"] = config.get("rule_sequence", [])

        # Set secondary attrs
        kwargs["left_context"] = cls._to_acceptor(config.get("left_context", ""))
        kwargs["right_context"] = cls._to_acceptor(config.get("right_context", ""))

        # Cast test mappings to tuples
        if "test_mappings" in config:
            kwargs["test_mappings"] = [
                tuple(mapping) for mapping in config["test_mappings"]
            ]

        return cls(**kwargs)

    @staticmethod
    def _to_acceptor(val: str | AcceptorLike) -> AcceptorLike:
        """Helper to safely wrap string in Acceptor or return existing Acceptor."""
        if isinstance(val, AcceptorLike):
            return val
        return Acceptor(val)

    def __str__(self):
        return f"Rule(name={self.name}, kind={self.kind})"

    def to_dict(self) -> dict:
        """Serialize a Rule to a YAML-serializable dict (config format)."""
        d: dict = {"name": self.name}

        if self.description:
            d["description"] = self.description

        if self.kind == "simple_rule":
            d["input_pattern"] = self.input_pattern.value or ""
            d["output_pattern"] = self.output_pattern.value or ""
            if self.left_context.value:
                d["left_context"] = self.left_context.value
            if self.right_context.value:
                d["right_context"] = self.right_context.value
            if self.direction != "ltr":
                d["direction"] = self.direction

        elif self.kind == "string_map":
            d["string_map"] = [
                [inp.value or "", out.value or ""] for inp, out in self.string_map
            ]
            if self.left_context.value:
                d["left_context"] = self.left_context.value
            if self.right_context.value:
                d["right_context"] = self.right_context.value
            if self.direction != "ltr":
                d["direction"] = self.direction

        elif self.kind == "rule_sequence":
            # self.rule_sequence can be list[Rule] (resolved) or list[str] (unresolved)
            d["rule_sequence"] = [
                validate_file_reference_str(r.name if hasattr(r, "name") else r)
                for r in self.rule_sequence
            ]

        if self.test_mappings:
            d["test_mappings"] = [list(pair) for pair in self.test_mappings]

        return d


class AnonymousRule(Rule):
    """
    A subclass of Rule to represent rules that are generated internally by the FstRegistry
    and not specified directly by the user in a config file. These rules do not have a name
    string since they are not referenced directly by the user, but instead are used as helper
    rules for implementing replace or suppletion markers.
    """

    def __post_init__(self):
        if self.name:
            raise ValueError(
                "AnonymousRule should not have a name string since it is not directly referenced by the user."
            )

        # set generic name string to avoid ValueError
        # on Rule __post_init__
        self.name = f"anonymous_rule_{id(self)}"
        super().__post_init__()


@runtime_checkable
class RuleLike(Protocol):
    """
    Structural protocol for Rule class.
    """

    kind: str
    name: str

    # attributes for simple rules
    input_pattern: object
    output_pattern: object

    # attributes for string map rules
    string_map: tuple

    # attributes for chain of rules
    rule_sequence: list

    # attributes for simple and string map rules with contexts
    left_context: object
    right_context: object

    # attributes for all rules
    direction: Literal["ltr", "rtl", "sim"]

    # references to other objects
    used_by: list

    # metadata
    source: os.PathLike | None
    description: str | None
    test_mappings: list[tuple[str, str]]

    uuid: str


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

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "rules": [rule.to_dict() for rule in self.data.values()],
        }

    def load_data_from_config(
        self,
        config: dict,
    ) -> dict[str, Rule]:
        rules = config.get("rules", [])
        if not rules:
            logger.error("No rules found in config")
            return

        rule_list = [Rule.from_config(rule_data) for rule_data in rules]

        # make dict mapping name to item
        config_items = {item.name: item for item in rule_list}
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
            dependency_graph[rule.name] = set()
            # get list of rules using this rule in their rule_sequence
            used_by = []
            for other_rule in self.data.values():
                if (other_rule.rule_sequence) and (
                    rule.name in other_rule.rule_sequence
                ):
                    used_by.append(other_rule)

            if rule.kind == "rule_sequence":
                # rule_sequence items may be Rule objects or strings indicating rule refs
                if not rule.rule_sequence:
                    continue
                elif isinstance(rule.rule_sequence[0], RuleLike):
                    sub_rules = rule.rule_sequence
                    sub_rule_refs = [sub_rule.name for sub_rule in sub_rules]
                else:
                    sub_rules = [self.get_rule(name) for name in rule.rule_sequence]
                    sub_rule_refs = rule.rule_sequence
                rule.set_dependencies(
                    used_by=used_by,
                    rule_sequence=sub_rules,
                )
                dependency_graph[rule.name] = set(sub_rule_refs)
            else:
                rule.set_dependencies(used_by=used_by)

        self.dependency_graph = dependency_graph
        rule_refs_sorted = list(TopologicalSorter(dependency_graph).static_order())
        rules_sorted = [self.get_rule(name) for name in rule_refs_sorted]
        self.rules_sorted = rules_sorted

    def get_rule(self, name: str) -> Rule:
        name = name.removeprefix("$")
        if name not in self.data:
            raise KeyError(f"Rule '{name}' not found in registry.")
        return self.data[name]
