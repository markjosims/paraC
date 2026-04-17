import os
import pandas as pd
from loguru import logger
from copy import deepcopy
from src.grammar.classes import Registry
from src.grammar.registry.feature_values_registry import FeatureValuesRegistry


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
        combinations: list[dict[str, str | list[str]]],
        features_to_values: dict[str, list[str]],
        source: os.PathLike | None = None,
    ):
        if not combinations:
            raise ValueError(
                "FeatureValueCombinations requires at least one combination."
            )

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
        self.valid_combinations = all_combinations.drop_duplicates().reset_index(
            drop=True
        )
        self.feature_masks = self._cache_feature_masks()

    def combination_is_valid(self, combination: dict[str, str]) -> bool:
        """Check if a given combination of feature values is licit."""
        combination = deepcopy(combination)
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
        combination: dict[str, list[str] | str],
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

    def get_all_combinations(
        self,
        fixed_features: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:

        valid_combinations = self.valid_combinations
        if fixed_features:
            valid_combination_mask = pd.Series([True] * len(valid_combinations))
            for feature, value in fixed_features.items():
                if feature not in self.feature_names:
                    raise ValueError(
                        f"Unexpected feature '{feature}' provided. "
                        f"Expected features: {self.feature_names}."
                    )
                valid_combination_mask &= self.feature_masks.get(
                    (feature, value), pd.Series([False] * len(valid_combinations))
                )
            valid_combinations = valid_combinations[valid_combination_mask]

        return valid_combinations.to_dict(orient="records")

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
        feature_values_registry: FeatureValuesRegistry,
        data: dict[str, FeatureValueCombinations] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.feature_values_registry = feature_values_registry
        super().__init__(
            kind="FeatureCombinations", data=data, config_objects=config_objects
        )

    def load_all_configs(self) -> dict[str, FeatureValueCombinations]:
        config_items: dict[str, FeatureValueCombinations] = {}
        for config in self.config_objects.values():
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

    def load_data_from_config(
        self, config: dict
    ) -> dict[str, FeatureValueCombinations]:
        source_path = config.get("source_path", "")
        name = os.path.splitext(os.path.basename(source_path))[0] if source_path else ""

        config_features = config.get("features", [])
        features_to_values = {}
        for feature_name in config_features:
            if feature_name not in self.feature_values_registry.features_to_values:
                raise KeyError(
                    f"Feature '{feature_name}' referenced in FeatureCombinations "
                    "but not defined in FeatureValuesRegistry."
                )
            features_to_values[feature_name] = (
                # self.feature_values_registry.features_to_values[feature_name] + ["unmarked"]
                # "unmarked" now added directly within `Feature` class
                self.feature_values_registry.features_to_values[feature_name]
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
