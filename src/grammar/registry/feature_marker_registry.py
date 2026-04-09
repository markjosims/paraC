from dataclasses import dataclass, field
from src.fst_utils import TransducerList
from src.grammar.classes import Registry
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from typing import Literal
from collections import UserList
from loguru import logger
from graphlib import TopologicalSorter
import os


@dataclass
class Marker(TransducerList):
    """
    Single morphological formative (affix, replacement, rule, or suppletion).
    Inherits `value` and `fst` from TransducerList; the FST is built later by a
    compilation step (not at config-load time).

    The 'order' and `lexical_features` are flags for the `Paradigm` object
    to control the application of the marker, where `order` is a named stage
    the rule applies in, and `lexical_features` is a mapping of feature names
    to values, where the rule only applies if the specified configuration of
    features is found.

    Attributes:
        type: Type of formative represented, including:
        - prefix: prepends value to stem
        - suffix: appends value to stem
        - replace: (input, output) pair for substring replacement
        - suppletion: Full replacement form (incompatible with other operations)
        - rule: Name(s) of phonological rule(s) to apply ($ reference)
        - principal_part: Selects a principal part for the feature value
        value: String to be interpreted as formative
        - if self.type == replace, type(self.value) is tuple[str, str]
        - else type(self.value) is str
        order: Stage name controlling application order within a paradigm
        lexical_features: Dict indicating feature:value pairs this marker relies on
    """

    value: str | tuple[str, str] = ""
    feature_value: str | None = None
    type: Literal[
        "prefix", "suffix", "replace", "suppletion", "rule", "principal_part"
    ] = "suffix"
    order: str | None = None
    comment: str | None = None
    lexical_features: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()

        if not self.value:
            raise ValueError("Marker must have value")

        if self.type == "replace":
            if type(self.value) is not tuple:
                raise ValueError(
                    "Markers of type 'replace' must have a tuple of length 2 "
                    f"but got {type(self.value)}"
                )
            if len(self.value) != 2:
                raise ValueError(
                    "Markers of type 'replace' must have a tuple of length 2 "
                    f"but got {len(self.value)}"
                )

        elif type(self.value) is tuple:
            raise ValueError(
                "Only 'replace' markers may have a tuple value "
                f"but got tuple for marker type {self.type}"
            )

        elif self.type not in (
            "prefix",
            "suffix",
            "suppletion",
            "rule",
            "principal_part",
        ):
            raise ValueError(f"Unrecognized marker type {self.type}")

    @classmethod
    def from_config(
        cls,
        config: dict | None = None,
        global_order: str | None = None,
        feature_value: str | None = None,
    ) -> "Marker" | None:
        """
        Build a Marker from a YAML marker dict. Returns None for null (zero-marking).
        """
        if type(global_order) is not str and global_order is not None:
            raise ValueError(
                f"Expected global_order to be a string or None, but got {type(global_order)}"
            )

        order = config.get("order", global_order)
        value = config["value"]
        marker_type = config["type"]

        # Convert list-form replace to tuple
        if marker_type == "replace" and isinstance(value, list):
            value = tuple(value)

        return Marker(
            value=value, type=marker_type, order=order, feature_value=feature_value
        )

    def __str__(self):
        return f"Marker(type={self.type}, value={self.value})"

    def __repr__(self):
        return self.__str__()


@dataclass
class MarkerList(UserList):
    """
    List of `Marker` objects. Enforces that all items are Markers,
    and that at most one 'principal_part' marker is present (if any).
    Allows principal_part marker to be set via a dedicated method,
    which ensures it is always the first marker in the list.
    """

    def __init__(self, data: list[Marker] | None = None):
        super().__init__(data)
        for item in self:
            if not isinstance(item, Marker):
                raise ValueError(
                    f"All items in a MarkerList must be Markers, but got {type(item)}"
                )

        # check no more than one 'principal_part' marker, if any
        self.principal_part = None
        principal_parts = [m for m in self if m.type == "principal_part"]
        if len(principal_parts) > 1:
            raise ValueError(
                f"MarkerList may contain at most one 'principal_part' marker, but got {len(principal_parts)}"
            )
        elif principal_parts:
            # If a principal_part marker is present, it must be the first marker in the list
            if self[0].type != "principal_part":
                raise ValueError(
                    "If a 'principal_part' marker is present, it must be the first marker in the list"
                )
            self.principal_part = principal_parts[0].value

    @classmethod
    def from_config(
        cls,
        config,
        global_order: str | None = None,
        global_markers: "MarkerList" | list[dict] | None = None,
        feature_value: str | None = None,
    ) -> "MarkerList":
        """
        Build a list of Markers from a YAML value that may be:
        - None (zero-marking) -> empty list
        - A dict (single marker) -> one-element list
        - A list of dicts (ordered multi-step markers) -> list of Markers

        This should be the default `Marker` constructor, as we generally expect
        that Marker definitions in the config may be a list, singleton, or null.
        """

        # coerce config to list for unified processing
        if config is None:
            config = []
        elif isinstance(config, dict):
            config = [config]

        markers = []

        # track principal part separately
        principal_part_marker = None

        for item in config:
            if item is None:
                continue
            marker = Marker.from_config(
                item, global_order=global_order, feature_value=feature_value
            )
            if marker is None:
                continue
            if marker.type == "principal_part":
                if principal_part_marker is not None:
                    raise ValueError(
                        "Multiple 'principal_part' markers found in config. Only one is allowed."
                    )
                principal_part_marker = marker
            else:
                markers.append(marker)

        # merge in global markers, ensuring no more than one 'principal_part' marker total
        if global_markers is not None:
            if not isinstance(global_markers, MarkerList):
                global_markers = MarkerList.from_config(
                    global_markers, global_order=global_order, feature_value="<global>"
                )
            for marker in global_markers:
                if marker.type == "principal_part":
                    if principal_part_marker is None:
                        principal_part_marker = marker
                    else:
                        logger.info(
                            "Child config already has a 'principal_part' marker, "
                            "and global_markers contains another. The global 'principal_part' "
                            "marker will be ignored since child configs take precedence."
                        )
                else:
                    markers.append(marker)

        # prepend principal_part marker if specified at all
        if principal_part_marker is not None:
            markers.insert(0, principal_part_marker)
        return cls(markers)

    def set_principal_part(self, marker: Marker | str, override=True):
        if isinstance(marker, str):
            marker = Marker(type="principal_part", value=marker)
        if marker.type != "principal_part":
            raise ValueError(
                f"Can only set principal part marker, but got marker of type {marker.type}"
            )
        if self.principal_part is not None and not override:
            logger.info(
                "MarkerList already has a 'principal_part' marker, and override is set to False"
            )
            return
        if self.principal_part is not None and override:
            # remove existing principal part marker
            self.data = [m for m in self.data if m.type != "principal_part"]
        self.data.insert(0, marker)
        self.principal_part = marker.value

    def merge_list(self, other: "MarkerList", global_order: str | None = None):
        """
        Merge another MarkerList into this one, ensuring principal_part constraints are maintained.
        If both lists have a principal_part marker, the one from `other` will override this one's.
        """
        if other.principal_part is not None:
            other_principal_part = [m for m in other if m.type == "principal_part"][0]
            self.set_principal_part(other_principal_part, override=True)

        for marker in other:
            if marker.type != "principal_part":
                self.append(marker)

        for marker in self:
            if marker.order is None and global_order is not None:
                marker.order = global_order

    def __str__(self):
        return str(self.data)

    def __repr__(self):
        return self.data.__repr__()

    # basic list operations with type checks and principal_part constraints

    def __setitem__(self, i, item):
        if not isinstance(item, Marker):
            raise ValueError(
                f"All items in a MarkerList must be Markers, but got {type(item)}"
            )
        return super().__setitem__(i, item)

    def append(self, item):
        if not isinstance(item, Marker):
            raise ValueError(
                f"All items in a MarkerList must be Markers, but got {type(item)}"
            )
        if item.type == "principal_part":
            if self.principal_part is not None:
                raise ValueError(
                    "MarkerList may contain at most one 'principal_part' marker, but already has one"
                )
            if len(self) > 0 and self[0].type != "principal_part":
                raise ValueError(
                    "If a 'principal_part' marker is present, it must be the first marker in the list"
                )
            self.principal_part = item.value
        return super().append(item)

    def extend(self, other):
        for item in other:
            if not isinstance(item, Marker):
                raise ValueError(
                    f"All items in a MarkerList must be Markers, but got {type(item)}"
                )
            if item.type == "principal_part":
                self.set_principal_part(item, override=False)
        return super().extend(other)

    def insert(self, i, item):
        if not isinstance(item, Marker):
            raise ValueError(
                f"All items in a MarkerList must be Markers, but got {type(item)}"
            )
        if item.type == "principal_part":
            self.set_principal_part(item, override=False)
        return super().insert(i, item)


# ---------------------------------------------------------------------------
# FeatureMarkers dataclass
# ---------------------------------------------------------------------------


@dataclass
class FeatureMarkers:
    """
    Maps values of a single feature to lists of Marker objects.
    Corresponds to a ``kind: FeatureMarkers`` YAML config.

    Attributes:
        feature: Name of the feature being marked (e.g. 'subject', 'class')
        data: Dict mapping feature values to lists of Markers
        global_order: Optional default order for all markers in config
        global_markers: Optional markers applied to all feature values
        source: Filepath this config was loaded from
    """

    feature: Feature
    inherits: str | None = None

    data: dict[str, MarkerList] = field(default_factory=dict)
    global_order: str | None = None
    global_markers: MarkerList = field(default_factory=MarkerList)
    source: os.PathLike | None = None

    def __post_init__(self):
        if not self.feature or not isinstance(self.feature, Feature):
            raise ValueError("FeatureMarkers must have a valid feature.")

        self.parent_data_loaded = False

    @classmethod
    def from_config(
        cls,
        config: dict,
        feature_values_registry: FeatureOrchestrator,
    ) -> "FeatureMarkers":
        """Build a FeatureMarkers from a full YAML config dict."""
        feature_name = config.get("feature", "")
        feature = feature_values_registry.get_feature(feature_name)

        source = config.get("source_path")
        global_order = config.get("global_order", None)
        global_markers = config.get("global_markers", [])
        markers_config = config.get("markers", {})
        inherits = config.get("inherits", None)

        data = {}

        global_markers = MarkerList.from_config(
            global_markers,
            global_order=global_order,
            feature_value=f"<{feature_name}_global>",
        )

        for value_name, marker_config in markers_config.items():
            data[value_name] = MarkerList.from_config(
                marker_config,
                global_markers=global_markers,
                global_order=global_order,
                feature_value=f"[{feature_name}={value_name}]",
            )

        markers = cls(
            feature=feature,
            data=data,
            global_order=global_order,
            global_markers=global_markers,
            source=source,
            inherits=inherits,
        )
        return markers

    def get_marker(self, feature_value: str) -> MarkerList:
        """Retrieve the list of Markers associated with a given feature value."""
        if feature_value not in self.data:
            raise KeyError(
                f"No markers found for feature value '{feature_value}' in feature '{self.feature}'"
            )
        return self.data[feature_value]

    def update_from_parent(self, parent_config: "FeatureMarkers"):
        # apply any inherited global order and markers from parent config
        global_markers = self._merge_global_markers(parent_config)
        if self.global_order is None and parent_config.global_order is not None:
            self.global_order = parent_config.global_order

        for marker_list in self.data.values():
            marker_list.merge_list(global_markers, global_order=self.global_order)

        # insert parent marker values if not present in child config
        for value_name, parent_marker_list in parent_config.data.items():
            if value_name not in self.data:
                self.data[value_name] = parent_marker_list

        self.parent_data_loaded = True

    def _merge_global_markers(self, parent_config: "FeatureMarkers"):
        # eagerly check if child and parent config both have
        # 'principal_part' global marker
        parent_global_markers = parent_config.global_markers or MarkerList()

        if (
            self.global_markers.principal_part is None
            and parent_global_markers.principal_part is not None
        ):
            # if only parent has a principal_part marker, child inherits it
            self.global_markers.set_principal_part(
                parent_global_markers.principal_part,
                override=False,
            )
            self.principal_part = parent_global_markers.principal_part

        parent_global_markers = [
            m for m in parent_global_markers if m.type != "principal_part"
        ]

        self.global_markers.extend(parent_global_markers)

    def get_order_values(self) -> list[str]:
        order_values = set()
        for marker_list in self.data.values():
            for marker in marker_list:
                if marker.order is not None:
                    order_values.add(marker.order)
        return list(order_values)

    def __str__(self):
        return (
            f"FeatureMarkers(feature='{self.feature}', values={list(self.data.keys())})"
        )

    def __repr__(self):
        return self.__str__()


class FeatureMarkersRegistry(Registry):
    """
    Registry for ``kind: FeatureMarkers`` configs.
    ``data`` maps config filename stems to FeatureMarkers objects.
    """

    def __init__(
        self,
        data: dict[str, FeatureMarkers] | None = None,
        config_objects: dict[str, dict] | None = None,
        feature_values_registry: FeatureOrchestrator | None = None,
    ):
        self.feature_values_registry = feature_values_registry
        super().__init__(
            kind="FeatureMarkers", data=data, config_objects=config_objects
        )
        self.dependency_graph = None
        self.sorted_configs = None

        self.build_dependency_graph()

    def initialize(self):
        self.build_dependency_graph()
        if self.dependency_graph is not None:
            self.update_from_parents()

    def load_all_configs(self) -> dict[str, FeatureMarkers]:
        config_items: dict[str, FeatureMarkers] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate FeatureMarkers '{key}' found in "
                        f"multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, FeatureMarkers]:
        source_path = config.get("source_path", "")
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get("feature", "")
        )
        feature_markers = FeatureMarkers.from_config(config, self.feature_values_registry)
        return {name: feature_markers}

    def build_dependency_graph(self):
        graph = {}
        for name, config in self.data.items():
            parent = config.inherits
            if parent:
                if parent not in self.data:
                    raise ValueError(
                        f"Config '{name}' inherits from '{parent}', but no config named '{parent}' was found."
                    )
                graph[name] = parent
        if not graph:
            logger.info(
                "No inheritance relationships found among FeatureMarkers configs."
            )
            return
        self.dependency_graph = graph
        sorted_config_names = TopologicalSorter(graph).static_order()
        self.sorted_configs = [self.data[name] for name in sorted_config_names]

    def update_from_parents(self):
        if self.dependency_graph is None:
            logger.info("No dependency graph found, skipping parent updates.")
            return
        for config in self.sorted_configs:
            if config.inherits:
                parent_config = self.data[config.inherits]
                config.update_from_parent(parent_config)
