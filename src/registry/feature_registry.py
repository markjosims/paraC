"""
Registries and dataclasses for morphological features.

Registry classes (inherit Registry from src.registry_utils):
- FeatureValuesRegistry: loads/manages FeatureDefinitions configs
- FeatureCombinationsRegistry: loads/manages FeatureCombinations configs
- FeatureRegistry: orchestrates both registries

Dataclasses:
- Feature: a single feature category and its possible values

Utilities:
- FeatureValueCombinations: expands and queries licit feature-value combinations
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, List, Optional, Union

import pandas as pd
from loguru import logger

from src.registry.registry_utils import Registry


@dataclass
class Feature:
    """
    Represents a single morphological feature and its possible values.

    Attributes:
        name: Feature name (e.g. ``subject`` or ``tam``)
        values: Enumerated values for the feature
        source: Filepath this feature definition was loaded from
    """

    name: str
    values: List[str]
    source: Optional[os.PathLike] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Feature name cannot be empty.")
        if not self.values:
            raise ValueError(f"Feature '{self.name}' must define at least one value.")
        if len(self.values) != len(set(self.values)):
            raise ValueError(
                f"Feature '{self.name}' contains duplicate values: {self.values}"
            )

    @classmethod
    def from_config(
        cls,
        name: str,
        values: List[str],
        source: Optional[os.PathLike] = None,
    ) -> Feature:
        return cls(name=name, values=list(values), source=source)

    def __str__(self):
        return f"Feature(name='{self.name}', values={self.values})"

    def __repr__(self):
        return self.__str__()


class FeatureValuesRegisry(Registry):
    """
    Registry for ``kind: FeatureDefinitions`` configs.
    ``data`` maps feature names to Feature objects.
    """

    def __init__(
        self,
        data: Optional[Dict[str, Feature]] = None,
        config_lists: Optional[List[dict]] = None,
    ):
        super().__init__(kind="FeatureDefinitions", data=data, config_list=config_lists)
        self._populate_features_to_values()

    def _populate_features_to_values(self):
        self.features_to_values = {
            feature.name: feature.values for feature in self.data.values()
        }

    @classmethod
    def from_config_dir(cls, config_dir: str) -> FeatureValuesRegisry:
        registry = super().from_config_dir(config_dir=config_dir)
        registry.data = registry.load_all_configs()
        registry._populate_features_to_values()
        return registry

    def load_all_configs(self) -> Dict[str, Feature]:
        config_items: Dict[str, Feature] = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate feature '{key}' found in multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> Dict[str, Feature]:
        features = config.get("features", {})
        source_path = config.get("source_path")
        if not features:
            error = "No features found in config."
            logger.error(error)
            raise ValueError(error)

        return {
            feature_name: Feature.from_config(
                name=feature_name,
                values=feature_values,
                source=source_path,
            )
            for feature_name, feature_values in features.items()
        }


class FeatureValueCombinations:
    """
    Tracks licit combinations of feature values.

    Each combination dict maps feature names to:
    - A single value string
    - A list of values
    - '*' (wildcard, expanded from ``features_to_values``)

    Features omitted in queries are treated as ``unmarked``.
    """

    def __init__(
        self,
        combinations: List[Dict[str, Union[str, List[str]]]],
        features_to_values: Dict[str, List[str]],
        source: Optional[os.PathLike] = None,
    ):
        if not combinations:
            raise ValueError("FeatureValueCombinations requires at least one combination.")

        self.features_to_values = features_to_values
        self.source = source

        first_combination = combinations[0]
        expected_features = set(first_combination.keys())
        self.feature_names = list(sorted(expected_features))

        all_combinations = pd.DataFrame()
        for combination in combinations:
            combination_features = set(combination.keys())
            if combination_features != expected_features:
                raise ValueError(
                    f"All combination dictionaries must have the same feature names. "
                    f"Expected {expected_features}, got {combination_features}."
                )
            expanded_df = self._expand_combination_dict(combination)
            all_combinations = pd.concat(
                [all_combinations, expanded_df], ignore_index=True
            )
        self.valid_combinations = (
            all_combinations.drop_duplicates().reset_index(drop=True)
        )
        self.feature_masks = self._cache_feature_masks()

    def combination_is_valid(self, combination: Dict[str, str]) -> bool:
        """Check if a given combination of feature values is licit."""
        for expected_feature in self.feature_names:
            if expected_feature not in combination:
                combination[expected_feature] = "unmarked"

        for provided_feature in combination.keys():
            if provided_feature not in self.feature_names:
                raise ValueError(
                    f"Unexpected feature '{provided_feature}' provided. "
                    f"Expected features: {self.feature_names}."
                )

        feature_mask = pd.Series([True] * len(self.valid_combinations))
        for feature, value in combination.items():
            feature_mask &= self.feature_masks.get((feature, value))
        return bool(feature_mask.any())
    
    def _cache_feature_masks(self):
        """Precompute boolean masks for each feature-value pair to speed up validity checks."""
        feature_value_masks = {}
        for feature in self.feature_names:
            for value in self.features_to_values.get(feature, []):
                mask = self.valid_combinations[feature] == value
                feature_value_masks[(feature, value)] = mask
            unmarked_mask = self.valid_combinations[feature] == "unmarked"
            feature_value_masks[(feature, "unmarked")] = unmarked_mask
        return feature_value_masks

    def _expand_combination_dict(
        self,
        combination: Dict[str, Union[List[str], str]],
    ) -> pd.DataFrame:
        """Expand one combination dict into concrete combinations."""
        row = {}
        for feature, values in combination.items():
            if values == "*":
                if feature not in self.features_to_values:
                    raise KeyError(
                        f"Feature '{feature}' not found in features_to_values."
                    )
                values = self.features_to_values[feature]

                # wildcard should not match 'unmarked'
                values = [v for v in values if v != "unmarked"]
            row[feature] = values
        df = pd.DataFrame([row])
        for feature in combination.keys():
            df = df.explode(feature).reset_index(drop=True)
        return df

    def is_licit_combination(self, **feature_values: str) -> bool:
        """Check if a given combination of feature values is licit."""
        for expected_feature in self.feature_names:
            if expected_feature not in feature_values:
                feature_values[expected_feature] = "unmarked"

        for provided_feature in feature_values.keys():
            if provided_feature not in self.feature_names:
                raise ValueError(
                    f"Unexpected feature '{provided_feature}' provided. "
                    f"Expected features: {self.feature_names}."
                )

        feature_mask = pd.Series([True] * len(self.valid_combinations))
        for feature, value in feature_values.items():
            feature_mask &= self.valid_combinations[feature] == value
        return bool(feature_mask.any())

    def get_all_combinations(self) -> List[Dict[str, str]]:
        return self.valid_combinations.to_dict(orient="records")  # type: ignore

    def __str__(self):
        return (
            f"FeatureValueCombinations(features={self.feature_names}, "
            f"combos={len(self.valid_combinations)})"
        )

    def __repr__(self):
        return self.__str__()


class FeatureCombinationsRegistry(Registry):
    """
    Registry for ``kind: FeatureCombinations`` configs.
    ``data`` maps config filename stems to FeatureValueCombinations objects.
    """

    def __init__(
        self,
        feature_registry: Optional[FeatureValuesRegisry] = None,
        data: Optional[Dict[str, FeatureValueCombinations]] = None,
        config_lists: Optional[List[dict]] = None,
    ):
        self.feature_registry = (
            feature_registry if feature_registry is not None else FeatureValuesRegisry()
        )
        super().__init__(kind="FeatureCombinations", data=data, config_list=config_lists)

    @classmethod
    def from_config_dir(
        cls,
        config_dir: str,
        feature_registry: Optional[FeatureValuesRegisry] = None,
    ) -> FeatureCombinationsRegistry:
        if feature_registry is None:
            feature_registry = FeatureValuesRegisry.from_config_dir(config_dir)
        registry = cls(feature_registry=feature_registry)
        registry.config_dir = registry.feature_registry.config_dir
        registry.config_list = registry.load_config_files()
        registry.data = registry.load_all_configs()
        return registry

    def load_all_configs(self) -> Dict[str, FeatureValueCombinations]:
        config_items: Dict[str, FeatureValueCombinations] = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        "Duplicate FeatureCombinations "
                        f"'{key}' found in multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> Dict[str, FeatureValueCombinations]:
        source_path = config.get("source_path", "")
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else ""
        )

        config_features = config.get("features", [])
        features_to_values = {}
        for feature_name in config_features:
            if feature_name not in self.feature_registry.features_to_values:
                raise KeyError(
                    f"Feature '{feature_name}' referenced in FeatureCombinations "
                    "but not defined in FeatureRegistry."
                )
            features_to_values[feature_name] = (
                self.feature_registry.features_to_values[feature_name] + ["unmarked"]
            )

        combinations = config.get("combinations", [])
        normalized_combinations = []
        for combination in combinations:
            normalized = {}
            for feature_name in config_features:
                normalized[feature_name] = combination.get(feature_name, "unmarked")
            normalized_combinations.append(normalized)

        feature_combinations = FeatureValueCombinations(
            combinations=normalized_combinations,
            features_to_values=features_to_values,
            source=source_path,
        )
        return {name: feature_combinations}


class FeatureRegistry:
    """
    Orchestrates FeatureValuesRegistry and FeatureCombinationsRegistry.
    """

    def __init__(
        self,
        feature_registry: FeatureValuesRegisry,
        feature_combinations_registry: FeatureCombinationsRegistry,
    ):
        self.feature_registry = feature_registry
        self.feature_combinations_registry = feature_combinations_registry

        self.features: Dict[str, Feature] = feature_registry.data
        self.feature_combinations: Dict[str, FeatureValueCombinations] = (
            feature_combinations_registry.data
        )

    @classmethod
    def from_config_dir(cls, config_dir: str) -> FeatureRegistry:
        feature_registry = FeatureValuesRegisry.from_config_dir(config_dir)
        feature_combinations_registry = FeatureCombinationsRegistry.from_config_dir(
            config_dir, feature_registry=feature_registry
        )
        return cls(feature_registry, feature_combinations_registry)

    def get_feature(self, name: str) -> Feature:
        if name not in self.features:
            raise KeyError(f"No feature found with name '{name}'.")
        return self.features[name]

    def get_feature_combinations(self, name: str) -> FeatureValueCombinations:
        if name not in self.feature_combinations:
            raise KeyError(f"No feature-combinations config found with name '{name}'.")
        return self.feature_combinations[name]

