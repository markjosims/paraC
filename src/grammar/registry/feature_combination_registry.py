import os
import pandas as pd
from loguru import logger
from copy import deepcopy
from src.grammar.classes import Registry
from src.grammar.registry.feature_values_registry import FeatureValuesRegistry, Feature
from dataclasses import dataclass, field


@dataclass
class Combination:
    """
    A single combination from a FeatureValueCombinations file,
    stored as a dataframe with each column being a feature
    and each row being a valid set of feature values.
    Track original data as well for later YAML serialization
    (since the seed data -> interpreted data transformation
    is lossy).
    """

    combination_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    seed_data: frozenset[tuple[str, str | tuple[str, ...]]] = field(
        default_factory=frozenset
    )

    @classmethod
    def from_config(
        cls,
        config: dict,
        name2feature: dict[str, Feature],
    ) -> "Combination":
        """Expand one combination dict into concrete combinations."""
        row = {}
        for feature_name, values in config.items():
            if values == "*":
                if feature_name not in name2feature:
                    raise KeyError(
                        f"Feature '{feature_name}' not found in provided features {name2feature.values()}."
                    )
                values = name2feature[feature_name].values

                # wildcard should not match 'unmarked'
                values = [v for v in values if v != "unmarked"]
            row[feature_name] = values

        for feature_name in name2feature.keys():
            if feature_name not in row:
                row[feature_name] = "unmarked"

        df = pd.DataFrame([row])
        for feature_name in config.keys():
            df = df.explode(feature_name).reset_index(drop=True)

        # prepare config data for freezing
        seed_data = config.copy()
        for k, v in config.items():
            # cast list[str] to tuple[str] for hashing
            if type(v) is list:
                seed_data[k] = tuple(v)

        seed_data = frozenset(seed_data.items())

        return cls(combination_data=df, seed_data=seed_data)

    def to_dict(self) -> dict:
        """
        Unfreeze seed data and convert tuples to lists for YAML serialization.
        """
        unfrozen = dict(self.seed_data)
        for k, v in self.seed_data:
            if type(v) is tuple:
                unfrozen[k] = list(v)

        return unfrozen


class FeatureValueCombinations:
    """
    Tracks licit combinations of feature values.

    Each combination dict maps feature names to:
    - A single value string
    - A list of values
    - '*' (wildcard, expanded from ``feature.values``)

    Features omitted in queries are treated as ``unmarked``.
    """

    def __init__(
        self,
        combinations: list[dict[str, str | list[str]]],
        features: list[Feature],
        source: os.PathLike | None = None,
    ):

        self.features = features
        self.feature_names = [feature.name for feature in self.features]

        if not combinations:
            raise ValueError(
                "FeatureValueCombinations requires at least one combination."
            )

        self.source = source

        name2feature = {feature.name: feature for feature in features}
        combination_objs: list[Combination] = [
            Combination.from_config(config=combo, name2feature=name2feature)
            for combo in combinations
        ]
        combination_df = pd.concat(
            [combo.combination_data for combo in combination_objs]
        )

        self.combinations = combination_objs
        self.valid_combinations = combination_df.drop_duplicates().reset_index(
            drop=True
        )
        self.feature_masks = self._cache_feature_masks()

    @classmethod
    def from_config(
        cls, config: dict, feature_values_registry: FeatureValuesRegistry
    ) -> "FeatureValueCombinations":
        feature_names = config["features"]
        features = [
            feature_values_registry.get_feature(feature_name)
            for feature_name in feature_names
        ]
        combinations = config.get("combinations", [])
        source = config.get("source", None)
        return cls(combinations=combinations, features=features, source=source)

    def combination_is_valid(self, combination: dict[str, str]) -> bool:
        """Check if a given combination of feature values is licit."""
        combination = deepcopy(combination)
        for expected_feature in self.features:
            if expected_feature.name not in combination:
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
        for feature in self.features:
            for value in feature.values:
                mask = self.valid_combinations[feature.name] == value
                feature_value_masks[(feature.name, value)] = mask
            unmarked_mask = self.valid_combinations[feature.name] == "unmarked"
            feature_value_masks[(feature.name, "unmarked")] = unmarked_mask
        return feature_value_masks

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
        for feature_name, value in feature_values.items():
            feature_mask &= self.valid_combinations[feature_name] == value
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

    def to_dict(self) -> dict:
        """Serialize to FeatureCombinations YAML format."""
        return {
            "kind": "FeatureCombinations",
            "features": [feature.name for feature in self.features],
            "combinations": [combo.to_dict() for combo in self.combinations],
        }

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

        feature_names = config.get("features", [])
        features = [
            self.feature_values_registry.get_feature(feature_name)
            for feature_name in feature_names
        ]

        combinations = config.get("combinations", [])

        feature_combinations = FeatureValueCombinations(
            combinations=combinations,
            features=features,
            source=source_path,
        )
        return {name: feature_combinations}
