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
- FeatureQueryMixin: feature string <-> dict conversion and lookup
- FeatureValueCombinations: tracks licit feature-value combinations
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple, Union, Literal, Any
from dataclasses import dataclass, field

from loguru import logger

from src.fst_utils import TransducerList, Prefix, Suffix
from src.registry.fst_registry import FstRegistry
from src.registry.registry_utils import Registry

from src.constants import EXAMPLE_CONFIG_DIR

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
        value: String to be interpreted as formative
        order: Stage name controlling application order within a paradigm
    """
    type: Literal["prefix", "suffix", "replace", "suppletion", "rule"]
    order: Optional[str] = None
    comment: Optional[str] = None

    @classmethod
    def from_config(
        cls,
        config: Optional[Dict[str, Any]] = None,
        global_order: Optional[str] = None,
    ) -> Optional[Marker]:
        """
        Build a Marker from a YAML marker dict. Returns None for null (zero-marking).
        """
        order = config.get('order', global_order)
        value = config['value']
        marker_type = config['type']

        # Convert list-form replace to tuple
        if marker_type == "replace" and isinstance(value, list):
            value = tuple(value)

        return Marker(value=value, type=marker_type, order=order)

    @classmethod
    def list_from_config(
        cls,
        config,
        global_order: Optional[str] = None,
        global_markers: List[Marker] = list(),
    ) -> List[Marker]:
        """
        Build a list of Markers from a YAML value that may be:
        - None (zero-marking) -> empty list
        - A dict (single marker) -> one-element list
        - A list of dicts (ordered multi-step markers) -> list of Markers

        This should be the default `Marker` constructor, as we generally expect
        that Marker definitions in the config may be a list, singleton, or null.
        """
        if config is None:
            config = []
        elif isinstance(config, dict):
            config = [config]    

        markers = []
        for item in config:
            marker = cls.from_config(item, global_order=global_order)
            if marker is not None:
                markers.append(marker)
        markers.extend(global_markers)
        return markers

    def __str__(self):
        return f"Marker(type={self.type}, value={self.value})"

    def __repr__(self):
        return self.__str__()


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
    feature: str = ''
    data: Dict[str, List[Marker]] = field(default_factory=dict)
    global_order: Optional[str] = None
    global_markers: List[Marker] = field(default_factory=list)
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        # Set dynamic attributes so ParadigmMarkers can use
        # getattr(marker_map, feature_value) for lookup
        for key, value in self.data.items():
            setattr(self, key, value)

    @classmethod
    def from_config(cls, config: dict) -> FeatureMarkers:
        """Build a FeatureMarkers from a full YAML config dict."""
        feature = config.get('feature', '')
        source = config.get('source_path')
        global_order = config.get('global_order', None)
        global_markers = config.get('global_markers', [])
        markers_config = config.get('markers', {})

        data = {}
        for value_name, marker_config in markers_config.items():
            data[value_name] = Marker.list_from_config(
                marker_config,
                global_markers=global_markers,
                global_order=global_order,
            )

        return cls(
            feature=feature,
            data=data,
            global_order=global_order,
            global_markers=global_markers,
            source=source,
        )

    def __str__(self):
        return f"FeatureMarkers(feature='{self.feature}', values={list(self.data.keys())})"

    def __repr__(self):
        return self.__str__()

# ---------------------------------------------------------------------------
## FeatureQueryMixin
# ---------------------------------------------------------------------------

class FeatureQueryMixin:
    """
    Mixin providing methods for querying markers based on feature dictionaries.
    Converts between 'feature=value feature=value' strings and dicts, with
    consistent alphabetical ordering of features.
    """

    def _feature_str_to_dict(self, feature_str: str) -> Dict[str, str]:
        """Convert 'feature=value feature=value' string to a dict."""
        feature_dict = {}
        for feature_value in feature_str.split(' '):
            feature, value = feature_value.split('=')
            feature_dict[feature] = value
        return feature_dict

    def _stringify_feature_dict(self, feature_dict: Dict[str, str]) -> str:
        """Convert a feature dict to a sorted 'feature=value feature=value' string."""
        return ' '.join(
            f"{feature}={value}"
            for feature, value in sorted(feature_dict.items())
        )

    def get_marker(self, **feature_dict: str) -> List[Marker]:
        """Retrieve markers for a given set of feature values."""
        key = self._stringify_feature_dict(feature_dict)
        data = getattr(self, 'data', None)
        if data is None:
            raise ValueError("No data attribute found.")
        if key not in data:
            raise KeyError(f"No marker found for feature combination: {key}")
        return data[key]


# ---------------------------------------------------------------------------
# ContingentMarkers dataclass
# ---------------------------------------------------------------------------

@dataclass
class ContingentMarkers(FeatureQueryMixin):
    """
    Maps combinations of multiple feature values to Marker lists.
    Corresponds to a ``kind: ContingentFeatureMarkers`` YAML config.

    Keys in ``data`` are sorted 'feature=value feature=value' strings,
    enabling O(1) lookup via :meth:`get_marker`.

    Attributes:
        features: List of feature names this config covers
        data: Dict mapping stringified feature combos to Marker lists
        global_attributes: Attributes applied to every marker
        source: Filepath this config was loaded from
    """
    features: List[str] = field(default_factory=list)
    data: Dict[str, List[Marker]] = field(default_factory=dict)
    global_attributes: dict = field(default_factory=dict)
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        self.feature_names = list(sorted(self.features))

    @classmethod
    def from_config(cls, config: dict) -> ContingentMarkers:
        """Build a ContingentMarkers from a full YAML config dict."""
        features = config.get('features', [])
        source = config.get('source_path')
        global_attrs = config.get('global_attributes', {})
        markers_config = config.get('markers', {})

        data = _flatten_contingent_markers(
            node=markers_config,
            all_features=features,
            assigned={},
            global_attrs=global_attrs,
        )

        return cls(
            features=features,
            data=data,
            global_attributes=global_attrs,
            source=source,
        )

    def __str__(self):
        return (
            f"ContingentMarkers(features={self.features}, "
            f"combos={len(self.data)})"
        )

    def __repr__(self):
        return self.__str__()


def _flatten_contingent_markers(
    node: dict,
    all_features: List[str],
    assigned: Dict[str, str],
    global_attrs: dict,
) -> Dict[str, List[Marker]]:
    """
    Recursively flatten a nested contingent-marker YAML structure into a flat
    dict keyed by sorted 'feature=value feature=value' strings.

    Handles both explicit feature-name nesting (key matches a feature name)
    and implicit value nesting (key is a value for the next unassigned feature).
    """
    result: Dict[str, List[Marker]] = {}

    # On first call, no features have been assigned
    # Accumulate assign features during recursion
    unassigned = [f for f in all_features if f not in assigned]

    if not unassigned:
        # All features assigned — node is a marker config (base case)
        # Build Marker objects
        markers = Marker.list_from_config(node, global_attrs)
        key = ' '.join(f"{f}={v}" for f, v in sorted(assigned.items()))
        result[key] = markers
        return result

    node_keys = set(node.keys()) - {'inherits'}

    if node_keys & set(unassigned):
        # Keys are feature names — explicit feature-name level
        for feat_name in node_keys:
            if feat_name not in unassigned:
                raise ValueError(
                    f"Unexpected key '{feat_name}' in contingent markers. "
                    f"Expected one of {unassigned}."
                )
            for feat_val, sub_node in node[feat_name].items():
                new_assigned = {**assigned, feat_name: feat_val}
                result.update(_flatten_contingent_markers(
                    sub_node, all_features, new_assigned, global_attrs,
                ))
    else:
        # Keys are values for the next unassigned feature (implicit)
        next_feat = unassigned[0]
        for feat_val, sub_node in node.items():
            if feat_val == 'inherits':
                continue
            new_assigned = {**assigned, next_feat: feat_val}
            result.update(_flatten_contingent_markers(
                sub_node, all_features, new_assigned, global_attrs,
            ))

    return result

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
        fst_registry: Optional[FstRegistry] = None,
    ):
        super().__init__(
            kind="FeatureMarkers", data=data, config_list=config_lists
        )
        self.fst_registry = fst_registry

    @classmethod
    def from_config_dir(cls, config_dir: str) -> FeatureMarkersRegistry:
        registry = super().from_config_dir(config_dir=config_dir)
        registry.data = registry.load_all_configs()
        fst_registry = FstRegistry.from_config_dir(config_dir)
        registry.fst_registry = fst_registry
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
    Orchestrates FeatureMarkersRegistry, ContingentMarkersRegistry
    and FstRegistry. Uses the lattermost to compile FSTs for markers
    contained in the former two classes.
    """

    def __init__(
        self,
        feature_markers_registry: FeatureMarkersRegistry,
        contingent_markers_registry: ContingentMarkersRegistry,
        fst_registry: FstRegistry,
    ):
        self.feature_markers_registry = feature_markers_registry
        self.contingent_markers_registry = contingent_markers_registry

        self.feature_markers: Dict[str, FeatureMarkers] = (
            feature_markers_registry.data
        )
        self.contingent_markers: Dict[str, ContingentMarkers] = (
            contingent_markers_registry.data
        )
        self.fst_registry = fst_registry

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
        fst_registry = FstRegistry.from_config_dir(
            config_dir
        )
        return cls(
            feature_markers_registry,
            contingent_markers_registry,
            fst_registry,
        )
    
    def initialize(self):
        self._build_all_marker_transducers()
        self.is_initialized = True

    def _build_all_marker_transducers(self):
        for marker_list in self.feature_markers.values():
            for marker in marker_list:
                self._build_marker_transducer(marker)
        for marker_list in self.contingent_markers.values():
            for marker in marker_list:
                self._build_marker_transducer(marker)

    def _build_marker_transducer(self, marker: Marker):
        if marker.type == 'rule':
            marker_rule = self.fst_registry.rules[marker.value]
        elif marker.type == 'prefix':
            marker_rule = self.fst_registry.prefix(marker.value)
        elif marker.type == 'suffix':
            marker_rule = self.fst_registry.suffix(marker.value)
        elif marker.type == 'replace':
            marker_rule = self.fst_registry.replace_transducer(
                marker.value[0], marker.value[1]
            )
        elif marker.type == 'suppletion':
            sigma_star = '<Sigma>*'
            marker_rule = self.fst_registry.replace_transducer(
                sigma_star, marker.value
            )
        marker.set_transducer(marker_rule.fst)

    def get(self, name: str) -> Union[FeatureMarkers, ContingentMarkers]:
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