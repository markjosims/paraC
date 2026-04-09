from src.grammar.classes import Registry
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.registry.feature_marker_registry import MarkerList, FeatureMarkers
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from dataclasses import dataclass, field
import os
from loguru import logger


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

    outer_feature: Feature
    inner_feature: Feature
    inner_maps: dict[str, FeatureMarkers] = field(default_factory=dict)
    global_order: str | None = None
    global_markers: MarkerList = field(default_factory=MarkerList)
    source: os.PathLike | None = None

    def __post_init__(self):
        if not self.outer_feature:
            raise ValueError("ContingentMarkers must have an outer_feature.")
        if not self.inner_feature:
            raise ValueError("ContingentMarkers must have an inner_feature.")

    @classmethod
    def from_config(
        cls, config: dict, feature_values_registry: FeatureOrchestrator
    ) -> "ContingentMarkers":
        """Build a ContingentMarkers from a full YAML config dict."""
        outer_feature_name = config.get("outer_feature", "")
        inner_feature_name = config.get("inner_feature", "")
        outer_feature = feature_values_registry.get_feature(outer_feature_name)
        inner_feature = feature_values_registry.get_feature(inner_feature_name)
        source = config.get("source_path")
        global_order = config.get("global_order", None)
        global_markers_config = config.get("global_markers", [])
        markers_config = config.get("markers", [])

        global_markers = MarkerList.from_config(
            global_markers_config, global_order=global_order
        )

        inner_maps: dict[str, FeatureMarkers] = {}
        for entry in markers_config:
            outer_value = entry["outer_feature_value"]
            inner_feature_values = entry.get("inner_feature_values", {})

            # Build a FeatureMarkers config dict and delegate
            fm_config = {
                "feature": inner_feature.name,
                "markers": inner_feature_values,
                "global_order": global_order,
                "global_markers": global_markers_config,
            }
            inner_maps[outer_value] = FeatureMarkers.from_config(
                fm_config,
                feature_values_registry=feature_values_registry,
            )

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
        outer_val = feature_dict.get(self.outer_feature.name)
        inner_val = feature_dict.get(self.inner_feature.name)
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


class ContingentMarkersRegistry(Registry):
    """
    Registry for ``kind: ContingentFeatureMarkers`` configs.
    ``data`` maps config filename stems to ContingentMarkers objects.
    """

    def __init__(
        self,
        data: dict[str, ContingentMarkers | None] = None,
        config_objects: dict[str, dict | None] = None,
        feature_orchestrator: FeatureOrchestrator | None = None,
    ):
        self.feature_values_registry = feature_orchestrator
        super().__init__(
            kind="ContingentFeatureMarkers",
            data=data,
            config_objects=config_objects,
        )

    def load_all_configs(self) -> dict[str, ContingentMarkers]:
        config_items: dict[str, ContingentMarkers] = {}
        for config in self.config_objects.values():
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

    def load_data_from_config(self, config: dict) -> dict[str, ContingentMarkers]:
        source_path = config.get("source_path", "")
        name = os.path.splitext(os.path.basename(source_path))[0] if source_path else ""
        contingent_markers = ContingentMarkers.from_config(
            config, self.feature_values_registry
        )
        return {name: contingent_markers}
