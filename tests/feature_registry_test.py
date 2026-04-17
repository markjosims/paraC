import os

import pytest

from src.registry.feature_values_registry import (
    Feature,
    FeatureCombinationsRegistry,
    FeatureValuesRegisry,
    FeatureValueCombinations,
    FeatureValuesRegistry,
)
from src.constants import EXAMPLE_CONFIG_DIR


def test_feature_from_config_builds_feature():
    config_path = os.path.join(EXAMPLE_CONFIG_DIR, "features", "verb_and_adjective.yaml")
    feature = Feature.from_config(
        name="tam",
        values=["imperfective", "perfective", "imperative"],
        source=config_path,
    )

    assert isinstance(feature, Feature)
    assert feature.name == "tam"
    assert feature.values == ["imperfective", "perfective", "imperative"]
    assert feature.source == config_path


def test_feature_rejects_empty_name_or_values_or_duplicate_values():
    with pytest.raises(ValueError, match="Feature name cannot be empty"):
        Feature(name="", values=["x"])

    with pytest.raises(ValueError, match="must define at least one value"):
        Feature(name="tam", values=[])

    with pytest.raises(ValueError, match="contains duplicate values"):
        Feature(name="tam", values=["imperative", "imperative"])


def test_feature_values_registry_load_data_from_config_builds_feature_objects():
    registry = FeatureValuesRegisry()
    config = {
        "features": {
            "person": ["1sg", "2sg", "3sg"],
            "tense": ["present", "past"],
        },
        "source_path": "config/features/sample.yaml",
    }

    data = registry.load_data_from_config(config)

    assert set(data) == {"person", "tense"}
    assert isinstance(data["person"], Feature)
    assert data["person"].values == ["1sg", "2sg", "3sg"]
    assert data["person"].source == "config/features/sample.yaml"


def test_feature_values_registry_rejects_duplicate_features_across_configs():
    with pytest.raises(ValueError, match="Duplicate feature 'person'"):
        registry = FeatureValuesRegisry(
            config_lists=[
                {"features": {"person": ["1sg", "2sg"]}, "source_path": "a.yaml"},
                {"features": {"person": ["3sg"]}, "source_path": "b.yaml"},
            ]
        )


def test_feature_value_combinations_expands_wildcards_and_defaults_missing_query_values():
    combinations = FeatureValueCombinations(
        combinations=[
            {"tam": "imperative", "deixis": "*"},
            {"tam": "infinitive", "deixis": "unmarked"},
        ],
        features_to_values={
            "tam": ["imperative", "infinitive", "unmarked"],
            "deixis": ["itive", "ventive", "unmarked"],
        },
    )

    assert combinations.feature_names == ["deixis", "tam"]
    assert combinations.is_licit_combination(tam="imperative", deixis="itive")
    assert combinations.is_licit_combination(tam="imperative", deixis="ventive")
    assert combinations.is_licit_combination(tam="infinitive")
    assert not combinations.is_licit_combination(tam="imperative")

    assert combinations.get_all_combinations() == [
        {"tam": "imperative", "deixis": "itive"},
        {"tam": "imperative", "deixis": "ventive"},
        {"tam": "infinitive", "deixis": "unmarked"},
    ]


def test_feature_value_combinations_rejects_unknown_feature_in_query():
    combinations = FeatureValueCombinations(
        combinations=[{"tam": "imperative", "deixis": "itive"}],
        features_to_values={
            "tam": ["imperative"],
            "deixis": ["itive"],
        },
    )

    with pytest.raises(ValueError, match="Unexpected feature 'subject'"):
        combinations.is_licit_combination(tam="imperative", deixis="itive", subject="1sg")


def test_feature_combinations_registry_load_data_from_config_normalizes_unmarked_values():
    feature_values_registry = FeatureValuesRegisry(
        data={
            "tam": Feature(name="tam", values=["imperative", "infinitive"]),
            "deixis": Feature(name="deixis", values=["itive", "ventive"]),
            "class_marker": Feature(name="class_marker", values=["ð"]),
            "subject": Feature(name="subject", values=["1sg"]),
            "object": Feature(name="object", values=["3sg"]),
        }
    )
    registry = FeatureCombinationsRegistry(feature_values_registry=feature_values_registry)

    config_path = os.path.join(EXAMPLE_CONFIG_DIR, "features", "verb_feature_combinations.yaml")
    data = registry.load_data_from_config(
        {
            "features": ["tam", "deixis", "class_marker", "subject", "object"],
            "combinations": [
                {"tam": "infinitive", "class_marker": "ð"},
                {"tam": "imperative", "deixis": ["itive", "ventive"]},
            ],
            "source_path": config_path,
        }
    )

    assert set(data) == {"verb_feature_combinations"}
    combos = data["verb_feature_combinations"]
    assert isinstance(combos, FeatureValueCombinations)
    assert combos.source == config_path
    assert combos.is_licit_combination(
        tam="infinitive",
        deixis="unmarked",
        class_marker="ð",
        subject="unmarked",
        object="unmarked",
    )
    assert combos.is_licit_combination(
        tam="imperative",
        deixis="ventive",
        class_marker="unmarked",
        subject="unmarked",
        object="unmarked",
    )
    assert not combos.is_licit_combination(
        tam="imperative",
        deixis="ventive",
        class_marker="ð",
        subject="unmarked",
        object="unmarked",
    )


def test_feature_combinations_registry_rejects_undefined_features():
    feature_values_registry = FeatureValuesRegisry(
        data={"tam": Feature(name="tam", values=["imperative"])}
    )
    registry = FeatureCombinationsRegistry(feature_values_registry=feature_values_registry)

    with pytest.raises(KeyError, match="Feature 'deixis' referenced in FeatureCombinations"):
        registry.load_data_from_config(
            {
                "features": ["tam", "deixis"],
                "combinations": [{"tam": "imperative", "deixis": "itive"}],
                "source_path": "config/features/bad.yaml",
            }
        )


def test_feature_and_combination_registries_load_real_project_configs():
    feature_values_registry = FeatureValuesRegisry.from_config_dir(EXAMPLE_CONFIG_DIR)
    combinations_registry = FeatureCombinationsRegistry.from_config_dir(
        EXAMPLE_CONFIG_DIR,
        feature_values_registry=feature_values_registry,
    )

    assert set(feature_values_registry.data) >= {
        "class_marker",
        "deixis",
        "object",
        "subject",
        "tam",
    }
    assert set(combinations_registry.data) >= {"verb_feature_combinations"}

    tam = feature_values_registry.data["tam"]
    assert isinstance(tam, Feature)
    assert tam.values == [
        "imperfective",
        "perfective",
        "dependent",
        "imperative",
        "infinitive",
    ]

    combos = combinations_registry.data["verb_feature_combinations"]
    assert combos.is_licit_combination(
        tam="infinitive",
        deixis="unmarked",
        class_marker="ð",
        subject="unmarked",
        object="unmarked",
    )
    assert combos.is_licit_combination(
        tam="imperative",
        deixis="itive",
        class_marker="unmarked",
        subject="unmarked",
        object="unmarked",
    )
    assert combos.get_all_combinations() == [
        {
            "tam": "infinitive",
            "deixis": "unmarked",
            "class_marker": "ð",
            "subject": "unmarked",
            "object": "unmarked",
        },
        {
            "tam": "imperative",
            "deixis": "itive",
            "class_marker": "unmarked",
            "subject": "unmarked",
            "object": "unmarked",
        },
        {
            "tam": "imperative",
            "deixis": "ventive",
            "class_marker": "unmarked",
            "subject": "unmarked",
            "object": "unmarked",
        },
    ]


def test_features_registry_orchestrates_feature_and_combination_lookup():
    registry = FeatureValuesRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)

    tam = registry.get_feature("tam")
    combos = registry.get_feature_combinations("verb_feature_combinations")

    assert isinstance(tam, Feature)
    assert tam.name == "tam"
    assert combos.is_licit_combination(
        tam="imperative",
        deixis="ventive",
        class_marker="unmarked",
        subject="unmarked",
        object="unmarked",
    )


def test_features_registry_getters_raise_for_unknown_names():
    registry = FeatureValuesRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)

    with pytest.raises(KeyError, match="No feature found"):
        registry.get_feature("does_not_exist")

    with pytest.raises(KeyError, match="No feature-combinations config found"):
        registry.get_feature_combinations("does_not_exist")
