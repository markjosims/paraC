"""
Implements the `Pattern` and `PatternRegistry` classes.
`Pattern` is a subclass of `Acceptor` representing a user-defined
pattern, and `PatternRegistry` aggregaters patterns from a list of,
builds a dependency graph (since patterns may use other patterns)
and maps `Pattern` objects to their string representation.
"""

from src.fst_utils import Acceptor, ReservedSymbolMixin
from src.grammar.classes import Registry
from dataclasses import dataclass, field
from loguru import logger
import os
from graphlib import TopologicalSorter
from uuid import uuid4

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

    name: str = ""
    value: str = ""
    _ref: str = ""
    used_by: list['Pattern'] = field(default_factory=list)
    uses: list['Pattern'] = field(default_factory=list)
    source: os.PathLike | None = None
    test_includes: list[str] = field(default_factory=list)
    test_excludes: list[str] = field(default_factory=list)
    uuid: str = field(default_factory=lambda: str(uuid4()), init=False)

    def __post_init__(self):
        super().__post_init__()

        if (self.value in ReservedSymbolMixin.reserved_symbols) or (
            self._ref in ReservedSymbolMixin.reserved_symbols
        ):
            error = f"Pattern value and ref cannot be reserved symbols. Got value '{self.value}' and ref '{self._ref}'."
            logger.error(error)
            raise ValueError(error)

        # set attributes to track state
        self.dependencies_built = False

        if self.used_by:
            raise ValueError(
                "Used_by should not be passed on init but constructed by an FstRegistry object."
            )
        if self.uses:
            raise ValueError(
                "Uses should not be passed on init but constructed by an FstRegistry object."
            )

    def set_dependencies(self, used_by: list['Pattern'], uses: list['Pattern']):
        self.used_by = used_by
        self.uses = uses
        self.dependencies_built = True

    @classmethod
    def from_config(
        cls,
        item_dict: dict,
    ) -> 'Pattern':
        """
        Builds a Pattern from a config dict.
        """

        pattern = cls(
            name=item_dict.get("name", ""),
            value=item_dict["pattern"],
            _ref=item_dict["_ref"],
            source=item_dict.get("source", None),
            test_includes=item_dict.get("test_includes", []),
            test_excludes=item_dict.get("test_excludes", []),
        )
        return pattern

    def to_dict(self) -> dict:
        d: dict = {"_ref": self._ref, "name": self.name, "pattern": self.value}
        if self.test_includes:
            d["test_includes"] = self.test_includes
        if self.test_excludes:
            d["test_excludes"] = self.test_excludes
        return d

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


class PatternRegistry(Registry):
    """
    Registry for storing pattern definitions, also computes dependency graph
    to track import logic. Instantiated with a pre-built `data` dict mapping
    pattern names to `Pattern` objects, or a `config_objects` dict mapping
    filenames to YAML objects.
    """

    def __init__(
        self,
        data: dict[str, Pattern] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        super().__init__(kind="Patterns", data=data, config_objects=config_objects)
        self.build_dependency_graph()

    def load_all_configs(self):
        config_items = {}
        for config in self.config_objects.values():
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
    ) -> dict[str, Pattern]:
        patterns = config.get("patterns", [])
        if not patterns:
            logger.error(f"No patterns found in config: {config}")
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
                    used_by.append(other_pattern)

                if other_pattern._ref in pattern.value:
                    uses.append(other_pattern)
                    dependency_graph[pattern._ref].add(other_pattern._ref)

            pattern.set_dependencies(used_by=used_by, uses=uses)

        self.dependency_graph = dependency_graph
        pattern_refs_sorted = list(TopologicalSorter(dependency_graph).static_order())
        patterns_sorted = [self.data[ref] for ref in pattern_refs_sorted]
        self.patterns_sorted = patterns_sorted
