"""
Registries and dataclasses for morphological markers.

Registry classes (inherit Registry from src.registry_utils):
- FeatureMarkersRegistry: loads/manages FeatureMarkers configs
- ContingentMarkersRegistry: loads/manages ContingentFeatureMarkers configs
- MarkerRegistry: orchestrates both registries, provides unified lookup

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
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from loguru import logger

from src.fst_utils import Transducer
from src.registry_utils import Registry

from src.constants import CONFIG_DIR


# ---------------------------------------------------------------------------
# Marker dataclass
# ---------------------------------------------------------------------------

MARKER_FIELDS = {'prefix', 'suffix', 'replace', 'suppletion', 'rule', 'order'}


@dataclass
class Marker(Transducer):
    """
    Single morphological formative (affix, replacement, rule, or suppletion).
    Inherits `value` and `fst` from Transducer; the FST is built later by a
    compilation step (not at config-load time).

    Attributes:
        prefix: String to prepend to stem
        suffix: String to append to stem
        replace: (input, output) pair for substring replacement
        suppletion: Full replacement form (incompatible with other operations)
        rule: Name(s) of phonological rule(s) to apply ($ reference)
        order: Stage name controlling application order within a paradigm
    """
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    replace: Optional[Tuple[str, str]] = None
    suppletion: Optional[str] = None
    rule: Optional[Union[str, List[str]]] = None
    order: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        if self.suppletion is not None:
            if any([self.prefix, self.suffix, self.replace, self.rule]):
                raise ValueError(
                    "Suppletion cannot be combined with other marker attributes."
                )

    @classmethod
    def from_config(
        cls,
        config: Optional[dict],
        global_attrs: Optional[dict] = None,
    ) -> Optional[Marker]:
        """Build a Marker from a YAML marker dict. Returns None for null (zero-marking)."""
        if config is None:
            return None
        merged = {}
        if global_attrs:
            merged.update(global_attrs)
        merged.update(config)
        # Only pass recognized Marker fields to the constructor
        filtered = {k: v for k, v in merged.items() if k in MARKER_FIELDS}
        # Convert list-form replace to tuple
        if 'replace' in filtered and isinstance(filtered['replace'], list):
            filtered['replace'] = tuple(filtered['replace'])
        return cls(**filtered)

    @classmethod
    def list_from_config(
        cls,
        config,
        global_attrs: Optional[dict] = None,
    ) -> List[Marker]:
        """
        Build a list of Markers from a YAML value that may be:
        - None (zero-marking) -> empty list
        - A dict (single marker) -> one-element list
        - A list of dicts (ordered multi-step markers) -> list of Markers
        """
        if config is None:
            return []
        if isinstance(config, dict):
            marker = cls.from_config(config, global_attrs)
            return [marker] if marker is not None else []
        if isinstance(config, list):
            markers = []
            for item in config:
                marker = cls.from_config(item, global_attrs)
                if marker is not None:
                    markers.append(marker)
            return markers
        raise ValueError(f"Unexpected marker config type: {type(config)}")

    def __str__(self):
        parts = []
        if self.prefix:
            parts.append(f"prefix={self.prefix}")
        if self.suffix:
            parts.append(f"suffix={self.suffix}")
        if self.replace:
            parts.append(f"replace={self.replace}")
        if self.suppletion:
            parts.append(f"suppletion={self.suppletion}")
        if self.rule:
            parts.append(f"rule={self.rule}")
        if self.order:
            parts.append(f"order={self.order}")
        return f"Marker({', '.join(parts)})"

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
        global_attributes: Attributes applied to every marker in this config
        global_marker: Optional markers applied to ALL feature values
        source: Filepath this config was loaded from
    """
    feature: str = ''
    data: Dict[str, List[Marker]] = field(default_factory=dict)
    global_attributes: dict = field(default_factory=dict)
    global_marker: Optional[List[Marker]] = None
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
        global_attrs = config.get('global_attributes', {})
        markers_config = config.get('markers', {})

        data = {}
        global_marker = None

        for value_name, marker_config in markers_config.items():
            if value_name == 'global_marker':
                global_marker = Marker.list_from_config(marker_config, global_attrs)
                continue
            data[value_name] = Marker.list_from_config(marker_config, global_attrs)

        return cls(
            feature=feature,
            data=data,
            global_attributes=global_attrs,
            global_marker=global_marker,
            source=source,
        )

    def __str__(self):
        return f"FeatureMarkers(feature='{self.feature}', values={list(self.data.keys())})"

    def __repr__(self):
        return self.__str__()


# ---------------------------------------------------------------------------
# FeatureQueryMixin
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
    unassigned = [f for f in all_features if f not in assigned]

    if not unassigned:
        # All features assigned — node is a marker config
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
    ):
        super().__init__(
            kind="FeatureMarkers", data=data, config_list=config_lists
        )

    @classmethod
    def from_config_dir(cls, config_dir: str) -> FeatureMarkersRegistry:
        registry = super().from_config_dir(config_dir=config_dir)
        registry.data = registry.load_all_configs()
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
    Orchestrates FeatureMarkersRegistry and ContingentMarkersRegistry.
    Analogous to FstRegistry orchestrating Inventory/Pattern/Rule registries.
    """

    def __init__(
        self,
        feature_markers_registry: FeatureMarkersRegistry,
        contingent_markers_registry: ContingentMarkersRegistry,
    ):
        self.feature_markers_registry = feature_markers_registry
        self.contingent_markers_registry = contingent_markers_registry

        self.feature_markers: Dict[str, FeatureMarkers] = (
            feature_markers_registry.data
        )
        self.contingent_markers: Dict[str, ContingentMarkers] = (
            contingent_markers_registry.data
        )

    @classmethod
    def from_config_dir(cls, config_dir: str) -> MarkerRegistry:
        feature_markers_registry = FeatureMarkersRegistry.from_config_dir(
            config_dir
        )
        contingent_markers_registry = (
            ContingentMarkersRegistry.from_config_dir(config_dir)
        )
        return cls(feature_markers_registry, contingent_markers_registry)

    def get(self, name: str) -> Union[FeatureMarkers, ContingentMarkers]:
        """Look up a marker config by filename stem."""
        if name in self.feature_markers:
            return self.feature_markers[name]
        if name in self.contingent_markers:
            return self.contingent_markers[name]
        raise KeyError(f"No marker config found with name '{name}'.")

if __name__ == '__main__':
    # test initializing each config
    feature_reg = FeatureMarkersRegistry.from_config_dir(CONFIG_DIR)
    conting_marker_reg = ContingentMarkersRegistry.from_config_dir(CONFIG_DIR)
    marker_reg = MarkerRegistry.from_config_dir(CONFIG_DIR)
    breakpoint()