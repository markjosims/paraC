"""
Registries and dataclasses for morphological markers.

Registry classes (inherit Registry from src.registry_utils):
- FeatureMarkersRegistry: loads/manages FeatureMarkers configs
- ContingentMarkersRegistry: loads/manages ContingentFeatureMarkers configs
- MarkerRegistry: orchestrates both registries, provides unified lookup

Unlike `FstRegistry` classes, where each pattern and rule contained
must be unique, there is no unique feature vector <---> marker relation.
Rather, an arbitrary number of different `FeatureMarkers` or
`ContingentMarkers` may exist for a single feature value/combination.
The `MarkerRegistry` class, along with its `FeatureMarkersRegistry`
and `ContingentMarkersRegistry` children, allow for querying of entire
(Contingent)Marker *files*.

Dataclasses:
- Marker: single morphological formative (inherits Transducer)
- FeatureMarkers: maps values of one feature to Markers
- ContingentMarkers: maps combinations of multiple feature values to Markers

Utilities:
- FeatureValueCombinations: tracks licit feature-value combinations
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple, Union, Literal, Any
from dataclasses import dataclass, field
from collections import UserList

from loguru import logger

from src.fst_utils import TransducerList
from src.registry.feature_registry import FeatureRegistry
from src.registry.registry_utils import Registry

from src.constants import EXAMPLE_CONFIG_DIR
from graphlib import TopologicalSorter

# ---------------------------------------------------------------------------
# Marker dataclass
# ---------------------------------------------------------------------------

@dataclass
class Marker(TransducerList):
    """
    Single morphological formative (affix, replacement, rule, or suppletion).
    Inherits `value` and `fst` from TransducerList; the FST is built later by a
    compilation step (not at config-load time).

    Attributes:
        type: Type of formative represented, including:
        - prefix: String to prepend to stem
        - suffix: String to append to stem
        - replace: (input, output) pair for substring replacement
        - suppletion: Full replacement form (incompatible with other operations)
        - rule: Name(s) of phonological rule(s) to apply ($ reference)
        - principal_part: Selects a principal part for the feature value
        value: String to be interpreted as formative
        order: Stage name controlling application order within a paradigm
    """
    value: Union[str, Tuple[str, str]] = ""
    type: Literal["prefix", "suffix", "replace", "suppletion", "rule", "principal_part"] = "suffix"
    order: Optional[str] = None
    comment: Optional[str] = None

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
        
        elif self.type not in ("prefix", "suffix", "suppletion", "rule", "principal_part"):
            raise ValueError(f"Unrecognized marker type {self.type}")
        


    @classmethod
    def from_config(
        cls,
        config: Optional[Dict[str, Any]] = None,
        global_order: Optional[str] = None,
    ) -> Optional[Marker]:
        """
        Build a Marker from a YAML marker dict. Returns None for null (zero-marking).
        """
        if type(global_order) is not str and global_order is not None:
            raise ValueError(f"Expected global_order to be a string or None, but got {type(global_order)}")

        order = config.get('order', global_order)
        value = config['value']
        marker_type = config['type']

        # Convert list-form replace to tuple
        if marker_type == "replace" and isinstance(value, list):
            value = tuple(value)

        return Marker(value=value, type=marker_type, order=order)

    def __str__(self):
        return f"Marker(type={self.type}, value={self.value})"

    def __repr__(self):
        return self.__str__()
    
class MarkerList(UserList):
    """
    List of `Marker` objects. Enforces that all items are Markers,
    and that at most one 'principal_part' marker is present (if any).
    Allows principal_part marker to be set via a dedicated method,
    which ensures it is always the first marker in the list.
    """

    def __post_init__(self):
        for item in self:
            if not isinstance(item, Marker):
                raise ValueError(f"All items in a MarkerList must be Markers, but got {type(item)}")
            
        # check no more than one 'principal_part' marker, if any
        self.principal_part = None
        principal_parts = [m for m in self if m.type == 'principal_part']
        if len(principal_parts) > 1:
            raise ValueError(f"MarkerList may contain at most one 'principal_part' marker, but got {len(principal_parts)}")
        elif principal_parts:
            # If a principal_part marker is present, it must be the first marker in the list
            if self[0].type != 'principal_part':
                raise ValueError("If a 'principal_part' marker is present, it must be the first marker in the list")
            self.principal_part = principal_parts[0].value

    @classmethod
    def from_config(
        cls,
        config,
        global_order: Optional[str] = None,
        global_markers: Union[MarkerList, List[dict], None] = None,
    ) -> MarkerList:
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
            marker = Marker.from_config(item, global_order=global_order)
            if marker is None:
                continue
            if marker.type == 'principal_part':
                if principal_part_marker is not None:
                    raise ValueError("Multiple 'principal_part' markers found in config. Only one is allowed.")
                principal_part_marker = marker
            else:
                markers.append(marker)

        # merge in global markers, ensuring no more than one 'principal_part' marker total
        if global_markers is not None:
            if not isinstance(global_markers, MarkerList):
                global_markers = MarkerList.from_config(global_markers, global_order=global_order)
            for marker in global_markers:
                if marker.type == 'principal_part':
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
    
    def set_principal_part(self, marker: Union[Marker, str], override=True):
        if isinstance(marker, str):
            marker = Marker(type='principal_part', value=marker)
        if marker.type != 'principal_part':
            raise ValueError(f"Can only set principal part marker, but got marker of type {marker.type}")
        if self.principal_part is not None and not override:
            logger.info("MarkerList already has a 'principal_part' marker, and override is set to False")
            return
        if self.principal_part is not None and override:
            # remove existing principal part marker
            self.data = [m for m in self.data if m.type != 'principal_part']
        self.data.insert(0, marker)
        self.principal_part = marker.value

    def merge_list(self, other: MarkerList, global_order: Optional[str] = None):
        """
        Merge another MarkerList into this one, ensuring principal_part constraints are maintained.
        If both lists have a principal_part marker, the one from `other` will override this one's.
        """
        if other.principal_part is not None:
            other_principal_part = [m for m in other if m.type == 'principal_part'][0]
            self.set_principal_part(other_principal_part, override=True)
        
        for marker in other:
            if marker.type != 'principal_part':
                self.append(marker)

        for marker in self:
            if marker.order is None and global_order is not None:
                marker.order = global_order

    # basic list operations with type checks and principal_part constraints

    def __setitem__(self, i, item):
        if not isinstance(item, Marker):
            raise ValueError(f"All items in a MarkerList must be Markers, but got {type(item)}")
        return super().__setitem__(i, item)
    
    def append(self, item):
        if not isinstance(item, Marker):
            raise ValueError(f"All items in a MarkerList must be Markers, but got {type(item)}")
        if item.type == 'principal_part':
            if self.principal_part is not None:
                raise ValueError("MarkerList may contain at most one 'principal_part' marker, but already has one")
            if len(self) > 0 and self[0].type != 'principal_part':
                raise ValueError("If a 'principal_part' marker is present, it must be the first marker in the list")
            self.principal_part = item.value
        return super().append(item)

    def extend(self, other):
        for item in other:
            if not isinstance(item, Marker):
                raise ValueError(f"All items in a MarkerList must be Markers, but got {type(item)}")
            if item.type == 'principal_part':
                self.set_principal_part(item, override=False)
        return super().extend(other)
    
    def insert(self, i, item):
        if not isinstance(item, Marker):
            raise ValueError(f"All items in a MarkerList must be Markers, but got {type(item)}")
        if item.type == 'principal_part':
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
    feature: str
    inherits: Optional[str] = None

    data: Dict[str, MarkerList] = field(default_factory=dict)
    global_order: Optional[str] = None
    global_markers: MarkerList = field(default_factory=MarkerList)
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        if not self.feature:
            raise ValueError("FeatureMarkers must have a feature name.")

        self.parent_data_loaded = False

    @classmethod
    def from_config(cls, config: dict) -> FeatureMarkers:
        """Build a FeatureMarkers from a full YAML config dict."""
        feature = config.get('feature', '')
        source = config.get('source_path')
        global_order = config.get('global_order', None)
        global_markers = config.get('global_markers', [])
        markers_config = config.get('markers', {})
        inherits = config.get('inherits', None)

        data = {}

        for value_name, marker_config in markers_config.items():
            data[value_name] = MarkerList.from_config(
                marker_config,
                global_markers=global_markers,
                global_order=global_order,
            )
        global_markers = MarkerList.from_config(
            global_markers, global_order=global_order
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
            raise KeyError(f"No markers found for feature value '{feature_value}' in feature '{self.feature}'")
        return self.data[feature_value]
    
    def update_from_parent(self, parent_config: FeatureMarkers):
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
        

    def _merge_global_markers(self, parent_config: FeatureMarkers):
        # eagerly check if child and parent config both have
        # 'principal_part' global marker
        parent_global_markers = parent_config.global_markers or MarkerList()

        

        if self.global_markers.principal_part is None and parent_global_markers.principal_part is not None:
            # if only parent has a principal_part marker, child inherits it
            self.global_markers.set_principal_part(
                parent_global_markers.principal_part,
                override=False,
            )
            self.principal_part = parent_global_markers.principal_part

        parent_global_markers = [
            m for m in parent_global_markers if m.type != 'principal_part'
        ]

        self.global_markers.extend(parent_global_markers)  

    def get_order_values(self) -> List[str]:
        order_values = set()
        for marker_list in self.data.values():
            for marker in marker_list:
                if marker.order is not None:
                    order_values.add(marker.order)
        return list(order_values)
    
    def __str__(self):
        return f"FeatureMarkers(feature='{self.feature}', values={list(self.data.keys())})"

    def __repr__(self):
        return self.__str__()

# ---------------------------------------------------------------------------
# ContingentMarkers dataclass
# ---------------------------------------------------------------------------

@dataclass
class ContingentMarkers:
    """
    Maps combinations of exactly two feature values to Marker lists.
    Corresponds to a ``kind: ContingentFeatureMarkers`` YAML config.

    The outer feature partitions the markers into groups, each stored as
    a :class:`FeatureMarkers` keyed on the inner feature.  Lookup is
    two-step: outer value → FeatureMarkers → inner value → MarkerList.

    Attributes:
        outer_feature: Name of the feature that partitions the marker groups
        inner_feature: Name of the feature whose values are marked within each group
        inner_maps: Dict mapping outer feature values to FeatureMarkers objects
        global_order: Order applied to every marker
        global_markers: Markers applied to all feature values
        source: Filepath this config was loaded from
    """
    outer_feature: str = ""
    inner_feature: str = ""
    inner_maps: Dict[str, FeatureMarkers] = field(default_factory=dict)
    global_order: Optional[str] = None
    global_markers: MarkerList = field(default_factory=MarkerList)
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        if not self.outer_feature:
            raise ValueError("ContingentMarkers must have an outer_feature.")
        if not self.inner_feature:
            raise ValueError("ContingentMarkers must have an inner_feature.")

    @classmethod
    def from_config(cls, config: dict) -> ContingentMarkers:
        """Build a ContingentMarkers from a full YAML config dict."""
        outer_feature = config.get('outer_feature', '')
        inner_feature = config.get('inner_feature', '')
        source = config.get('source_path')
        global_order = config.get('global_order', None)
        global_markers_config = config.get('global_markers', [])
        markers_config = config.get('markers', [])

        global_markers = MarkerList.from_config(
            global_markers_config, global_order=global_order
        )

        inner_maps: Dict[str, FeatureMarkers] = {}
        for entry in markers_config:
            outer_value = entry['outer_feature_value']
            inner_feature_values = entry.get('inner_feature_values', {})

            # Build a FeatureMarkers config dict and delegate
            fm_config = {
                'feature': inner_feature,
                'markers': inner_feature_values,
                'global_order': global_order,
                'global_markers': global_markers_config,
            }
            inner_maps[outer_value] = FeatureMarkers.from_config(fm_config)

        return cls(
            outer_feature=outer_feature,
            inner_feature=inner_feature,
            inner_maps=inner_maps,
            global_order=global_order,
            global_markers=global_markers,
            source=source,
        )

    def get_marker(self, **feature_dict: str) -> MarkerList:
        """Retrieve markers for a given outer/inner feature value pair."""
        outer_val = feature_dict.get(self.outer_feature)
        inner_val = feature_dict.get(self.inner_feature)
        if outer_val is None:
            raise KeyError(
                f"Missing outer feature '{self.outer_feature}' in query. "
                f"Got: {feature_dict}"
            )
        if inner_val is None:
            raise KeyError(
                f"Missing inner feature '{self.inner_feature}' in query. "
                f"Got: {feature_dict}"
            )
        if outer_val not in self.inner_maps:
            raise KeyError(
                f"No markers for outer feature value '{outer_val}' "
                f"(outer_feature='{self.outer_feature}')"
            )
        fm = self.inner_maps[outer_val]
        if inner_val not in fm.data:
            raise KeyError(
                f"No markers for inner feature value '{inner_val}' "
                f"(inner_feature='{self.inner_feature}') "
                f"under outer value '{outer_val}'"
            )
        return fm.data[inner_val]

    def __str__(self):
        return (
            f"ContingentMarkers(outer='{self.outer_feature}', "
            f"inner='{self.inner_feature}', "
            f"outer_values={list(self.inner_maps.keys())})"
        )

    def __repr__(self):
        return self.__str__()

# ---------------------------------------------------------------------------
# Registry classes
# ---------------------------------------------------------------------------


class FeatureMarkersRegistry(Registry):
    """
    Registry for ``kind: FeatureMarkers`` configs.
    ``data`` maps config filename stems to FeatureMarkers objects.
    """

    def __init__(
        self,
        data: Optional[Dict[str, FeatureMarkers]] = None,
        config_lists: Optional[List[dict]] = None,
    ):
        super().__init__(
            kind="FeatureMarkers", data=data, config_list=config_lists
        )
        self.dependency_graph = None
        self.sorted_configs = None

        self.build_dependency_graph()

    def initialize(self):
        self.build_dependency_graph()
        if self.dependency_graph is not None:
            self.update_from_parents()
        
    @classmethod
    def from_config_dir(cls, config_dir: str) -> FeatureMarkersRegistry:
        registry = super().from_config_dir(config_dir=config_dir)
        registry.data = registry.load_all_configs()
        registry.build_dependency_graph()
        return registry

    def load_all_configs(self) -> Dict[str, FeatureMarkers]:
        config_items: Dict[str, FeatureMarkers] = {}
        for config in self.config_list:
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

    def load_data_from_config(
        self, config: dict
    ) -> Dict[str, FeatureMarkers]:
        source_path = config.get('source_path', '')
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get('feature', '')
        )
        feature_markers = FeatureMarkers.from_config(config)
        return {name: feature_markers}
    
    def build_dependency_graph(self):
        graph = {}
        for name, config in self.data.items():
            parent = config.inherits
            if parent:
                if parent not in self.data:
                    raise ValueError(f"Config '{name}' inherits from '{parent}', but no config named '{parent}' was found.")
                graph[name] = parent
        if not graph:
            logger.info("No inheritance relationships found among FeatureMarkers configs.")
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

class ContingentMarkersRegistry(Registry):
    """
    Registry for ``kind: ContingentFeatureMarkers`` configs.
    ``data`` maps config filename stems to ContingentMarkers objects.
    """

    def __init__(
        self,
        data: Optional[Dict[str, ContingentMarkers]] = None,
        config_lists: Optional[List[dict]] = None,
    ):
        super().__init__(
            kind="ContingentFeatureMarkers",
            data=data,
            config_list=config_lists,
        )

    @classmethod
    def from_config_dir(cls, config_dir: str) -> ContingentMarkersRegistry:
        registry = super().from_config_dir(config_dir=config_dir)
        registry.data = registry.load_all_configs()
        return registry

    def load_all_configs(self) -> Dict[str, ContingentMarkers]:
        config_items: Dict[str, ContingentMarkers] = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate ContingentMarkers '{key}' found in "
                        f"multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(
        self, config: dict
    ) -> Dict[str, ContingentMarkers]:
        source_path = config.get('source_path', '')
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else ''
        )
        contingent_markers = ContingentMarkers.from_config(config)
        return {name: contingent_markers}


class MarkerRegistry:
    """
    Orchestrates FeatureMarkersRegistry, ContingentMarkersRegistry,
    and FeatureRegistry. Uses FeatureRegistry to validate all feature
    combintions and values listed.
    """

    def __init__(
        self,
        feature_markers_registry: FeatureMarkersRegistry,
        contingent_markers_registry: ContingentMarkersRegistry,
        feature_registry: FeatureRegistry,
    ):
        self.feature_markers_registry = feature_markers_registry
        self.contingent_markers_registry = contingent_markers_registry

        self.feature_markers: Dict[str, FeatureMarkers] = (
            feature_markers_registry.data
        )
        self.contingent_markers: Dict[str, ContingentMarkers] = (
            contingent_markers_registry.data
        )
        self.feature_registry = feature_registry
        self.features = feature_registry.features
        self.feature_combinations = feature_registry.feature_combinations

        self.is_initialized = False
        self.initialize()
        if not self.is_initialized:
            raise ValueError("Error occurred while initializing MarkerRegistry, check logs.")

    @classmethod
    def from_config_dir(cls, config_dir: str) -> MarkerRegistry:
        feature_markers_registry = FeatureMarkersRegistry.from_config_dir(
            config_dir
        )
        contingent_markers_registry = ContingentMarkersRegistry.from_config_dir(
            config_dir
        )
        feature_registry = FeatureRegistry.from_config_dir(
            config_dir
        )
        return cls(
            feature_markers_registry,
            contingent_markers_registry,
            feature_registry
        )
    
    def _validate_feature_values(self):
        """
        Iterate through every `FeatureMarkers` object and check its features
        are supported by `self.feature_registry`
        """
        for markers_name, markers in self.feature_markers.items():
            feature_name = markers.feature
            if feature_name not in self.features:
                raise KeyError(f"{markers_name} has unsupported feature {feature_name}")
            feature = self.features[feature_name]
            for feature_val in markers.data:
                if feature_val not in feature.values:
                    raise KeyError(
                        f"Unsupported value {feature_val} for feature {feature_name} "
                        f"in marker set {markers_name}. Expected values are {feature.values}"
                    )
    
    def _validate_contingent_features(self):
        """
        Iterate through every `ContingentMarkers` object and check its features
        are supported by `self.feature_registry`
        """
        for markers_name, markers in self.contingent_markers.items():
            for feature_name in (markers.outer_feature, markers.inner_feature):
                if feature_name not in self.features:
                    raise KeyError(f"{markers_name} has unsupported feature {feature_name}")

            outer_feature = self.features[markers.outer_feature]
            for outer_val, inner_fm in markers.inner_maps.items():
                if outer_val not in outer_feature.values:
                    raise KeyError(
                        f"Unsupported value {outer_val} for feature {markers.outer_feature} "
                        f"in marker set {markers_name}. Expected values are {outer_feature.values}"
                    )
                inner_feature = self.features[markers.inner_feature]
                for inner_val in inner_fm.data:
                    if inner_val not in inner_feature.values:
                        raise KeyError(
                            f"Unsupported value {inner_val} for feature {markers.inner_feature} "
                            f"in marker set {markers_name}. Expected values are {inner_feature.values}"
                        )
    
    def initialize(self):
        self._validate_feature_values()
        self._validate_contingent_features()
        self.is_initialized = True

    def get_config(self, name: str) -> Union[FeatureMarkers, ContingentMarkers]:
        """Look up a marker config by filename stem."""
        if name in self.feature_markers:
            return self.feature_markers[name]
        if name in self.contingent_markers:
            return self.contingent_markers[name]
        raise KeyError(f"No marker config found with name '{name}'.")

if __name__ == '__main__':
    # test initializing each config
    feature_reg = FeatureMarkersRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    conting_marker_reg = ContingentMarkersRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    marker_reg = MarkerRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    breakpoint()