"""
Implements `MarkerOrchestrator` which manages following registries:
- FeatureMarkersRegistry: loads/manages FeatureMarkers configs
- ContingentMarkersRegistry: loads/manages ContingentFeatureMarkers configs
- MarkerRegistry: orchestrates both registries, provides unified lookup
"""

from __future__ import annotations
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar.registry.feature_marker_registry import FeatureMarkersRegistry
from src.grammar.registry.contingent_marker_registry import (
    ContingentMarkers,
    ContingentMarkersRegistry,
)
from src.grammar.registry.feature_marker_registry import (
    FeatureMarkers,
    FeatureMarkersRegistry,
)

from loguru import logger


class MarkerOrchestrator:
    """
    Orchestrates FeatureMarkersRegistry, ContingentMarkersRegistry,
    and FeatureOrchestrator. Uses FeatureOrchestrator to validate all feature
    combintions and values listed.
    """

    def __init__(
        self,
        feature_marker_configs: list[dict],
        contingent_marker_configs: list[dict],
        feature_orchestrator: FeatureOrchestrator | None = None,
    ):
        self.is_initialized = False
        self.feature_orchestrator = feature_orchestrator
        if not feature_orchestrator:
            logger.warning(
                "MarkerRegistry requres at minumum a feature registry to initialize. "
                "Returning an uninitialized MarkerRegistry. "
                "Provide a feature registry to load configs and initialize MarkerRegistry."
            )
            return
        self.features = feature_orchestrator.features
        self.feature_combinations = feature_orchestrator.feature_combinations

        self.feature_markers_registry = FeatureMarkersRegistry(
            config_objects=feature_marker_configs,
            feature_orchestrator=self.feature_orchestrator
        )
        self.feature_markers = self.feature_markers_registry.data

        self.contingent_markers_registry = ContingentMarkersRegistry(
            config_objects=contingent_marker_configs
        )
        self.contingent_markers: dict[str, ContingentMarkers] = (
            self.contingent_markers_registry.data
        )

        self.initialize()
        if not self.is_initialized:
            raise ValueError(
                "Error occurred while initializing MarkerRegistry, check logs."
            )

    def _validate_feature_values(self):
        """
        Iterate through every `FeatureMarkers` object and check its features
        are supported by `self.feature_orchestrator`
        """
        for markers_name, markers in self.feature_markers.items():
            feature = markers.feature
            if feature.name not in self.features:
                raise KeyError(
                    f"{markers_name} has unsupported feature {feature.name} "
                    f"expected one of {list(self.features.keys())}"
                )
            feature = self.features[feature.name]
            for feature_val in markers.data:
                if feature_val not in feature.values:
                    raise KeyError(
                        f"Unsupported value {feature_val} for feature {feature.name} "
                        f"in marker set {markers_name}. Expected values are {feature.values}"
                    )

    def _validate_contingent_features(self):
        """
        Iterate through every `ContingentMarkers` object and check its features
        are supported by `self.feature_orchestrator`
        """
        for markers_name, markers in self.contingent_markers.items():
            for feature in (markers.outer_feature, markers.inner_feature):
                if feature.name not in self.features:
                    raise KeyError(
                        f"{markers_name} has unsupported feature {feature.name} "
                        f"expected one of {list(self.features.keys())}"
                    )

            outer_feature = self.features[markers.outer_feature.name]
            for outer_val, inner_fm in markers.inner_maps.items():
                if outer_val not in outer_feature.values:
                    raise KeyError(
                        f"Unsupported value {outer_val} for feature {markers.outer_feature} "
                        f"in marker set {markers_name}. Expected values are {outer_feature.values}"
                    )
                inner_feature = self.features[markers.inner_feature.name]
                for inner_val in inner_fm.data:
                    if inner_val not in inner_feature.values:
                        raise KeyError(
                            f"Unsupported value {inner_val} for feature {markers.inner_feature} "
                            f"in marker set {markers_name}. Expected values are {inner_feature.values}"
                        )

    def initialize(self):
        if self.feature_markers_registry:
            self._validate_feature_values()
        if self.contingent_markers_registry:
            self._validate_contingent_features()
        self.is_initialized = True

    def get_config(self, name: str) -> FeatureMarkers | ContingentMarkers:
        """Look up a marker config by filename stem."""
        if name in self.feature_markers:
            return self.feature_markers[name]
        if name in self.contingent_markers:
            return self.contingent_markers[name]
        raise KeyError(f"No marker config found with name '{name}'.")


if __name__ == "__main__":
    from src.constants import EXAMPLE_CONFIG_DIR

    # test initializing each config
    # TODO: update since
    # feature_reg = FeatureMarkersRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    # conting_marker_reg = ContingentMarkersRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    # marker_reg = MarkerRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    breakpoint()
