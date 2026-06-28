"""
Implements FeatureOrchestrator, which manages following registries:
- FeatureValuesRegistry: loads/manages FeatureDefinitions configs
- FeatureCombinationsRegistry: loads/manages FeatureCombinations configs
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import pandas as pd

from src.grammar.registry.feature_combination_registry import (
    FeatureValueCombinations,
    FeatureCombinationsRegistry,
)
from src.grammar.registry.feature_values_registry import Feature, FeatureValuesRegistry
from src.grammar.classes import Orchestrator


class FeatureOrchestrator(Orchestrator):
    """
    Orchestrates FeatureValuesRegistry and FeatureCombinationsRegistry.
    """

    feature_regex = re.compile(r"\[([^=]+)=([^=]+)\]")

    def __init__(
        self,
        feature_configs: dict[str, dict],
        feature_combination_configs: dict[str, dict] | None = None,
    ):
        self.feature_values_registry = FeatureValuesRegistry(
            config_objects=feature_configs
        )

        self.features: dict[str, Feature] = self.feature_values_registry.data
        self.get_feature = self.feature_values_registry.get_feature

        # TODO: FeatureCombinations is buggy so it is commented out for now
        # self.feature_combinations_registry = FeatureCombinationsRegistry(
        #     config_objects=feature_combination_configs,
        #     feature_values_registry=self.feature_values_registry,
        # )
        # self.feature_combinations: dict[str, FeatureValueCombinations] = (
        #     self.feature_combinations_registry.data
        # )

    # def get_feature_combinations(self, name: str) -> FeatureValueCombinations:
    #     name = name.removeprefix("$")
    #     if name not in self.feature_combinations:
    #         raise KeyError(f"No feature-combinations config found with name '{name}'.")
    #     return self.feature_combinations[name]


def stringify_features(
    features: dict[str, str] | pd.Series | frozenset[tuple[str, str]],
) -> str:
    if len(features) == 0:
        return ""
    if isinstance(features, dict) or isinstance(features, pd.Series):
        feature_iterator = features.items()
    else:
        # check features is frozenset of tuples, then iterate directly
        assert type(features) is frozenset, type(features)
        feature_iterator = tuple(features)
        assert len(feature_iterator[0]) == 2, feature_iterator[0]
    feature_strings = [
        f"[{feature_name}={feature_value or 'unmarked'}]"
        for feature_name, feature_value in feature_iterator
    ]
    feature_strings.sort()
    result_str = "".join(feature_strings)
    return result_str


def serialize_feature_str(feature_str: str) -> dict[str, str]:
    feature_tuples = FeatureOrchestrator.feature_regex.findall(feature_str)
    feature_dict = {}
    for feature_name, feature_value in feature_tuples:
        feature_dict[feature_name] = feature_value
    return feature_dict
