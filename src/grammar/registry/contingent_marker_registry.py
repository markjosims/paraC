from src.grammar.classes import Registry
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.registry.feature_marker_registry import MarkerList
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from dataclasses import dataclass, field
import os
from loguru import logger


@dataclass
class ContingentMarkers:
    """
    Maps arbitrary feature vectors to Marker lists.
    Corresponds to a ``kind: ContingentFeatureMarkers`` YAML config.

    Attributes:
        feature_mappings: Dict mapping feature vector (frozenset of items) to MarkerList
        global_order: Order applied to every marker
        global_markers: Markers applied to all feature values
        source: Filepath this config was loaded from
    """

    features: list[Feature]
    feature_mappings: dict[frozenset[tuple[str, str]], MarkerList] = field(
        default_factory=dict
    )
    global_order: str | None = None
    global_markers: MarkerList = field(default_factory=MarkerList)
    source: os.PathLike | None = None

    @classmethod
    def from_config(
        cls, config: dict, feature_orchestrator: FeatureOrchestrator
    ) -> "ContingentMarkers":
        """Build a ContingentMarkers from a full YAML config dict."""
        source = config.get("source_path")
        global_order = config.get("global_order", None)
        global_markers_config = config.get("global_markers", [])
        markers_config = config.get("markers", [])

        global_markers = MarkerList.from_config(
            global_markers_config, global_order=global_order
        )

        feature_list = config.get("features", [])
        feature_list = [
            feature_orchestrator.get_feature(feature_name)
            for feature_name in feature_list
        ]

        feature_mappings: dict[frozenset[tuple[str, str]], MarkerList] = {}
        for entry in markers_config:
            features_dict = entry.get("features", {})
            realization_config = entry.get("realization", [])

            # Validate features
            for f_name, f_val in features_dict.items():
                feature = feature_orchestrator.get_feature(f_name)
                if f_val not in feature.values:
                    raise ValueError(
                        f"Invalid value '{f_val}' for feature '{f_name}' in {source}"
                    )

            vector = frozenset(features_dict.items())
            realization = MarkerList.from_config(
                realization_config, global_order=global_order
            )
            feature_mappings[vector] = realization

        return cls(
            features=feature_list,
            feature_mappings=feature_mappings,
            global_order=global_order,
            global_markers=global_markers,
            source=source,
        )

    def to_dict(self) -> dict:
        """Serialize to ContingentFeatureMarkers YAML format."""
        doc = {
            "kind": "ContingentFeatureMarkers",
        }
        if self.global_order:
            doc["global_order"] = self.global_order

        global_markers = self.global_markers.to_dict()
        if global_markers:
            doc["global_markers"] = global_markers

        feature_names = [feature.name for feature in self.features]
        doc["features"] = feature_names

        markers_list = []
        for vector, m_list in self.feature_mappings.items():
            entry = {
                "features": dict(vector),
                "realization": m_list.to_dict(),
            }
            markers_list.append(entry)
        doc["markers"] = markers_list
        return doc

    def get_marker(self, **feature_dict: str) -> MarkerList:
        """Retrieve markers matching the feature vector."""
        for vector, markers in self.feature_mappings.items():
            if vector.issubset(feature_dict.items()):
                return markers

        raise KeyError(
            f"No matching feature vector in {self.source} for {feature_dict}"
        )

    def __str__(self):
        return (
            f"ContingentMarkers(source='{self.source}', "
            f"vectors={len(self.feature_mappings)})"
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
        feature_orchestrator: FeatureOrchestrator,
        data: dict[str, ContingentMarkers | None] = None,
        config_objects: dict[str, dict | None] = None,
    ):
        self.feature_orchestrator = feature_orchestrator
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
            config, self.feature_orchestrator
        )
        return {name: contingent_markers}
