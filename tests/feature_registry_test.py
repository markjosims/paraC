import os

import pytest

from src.grammar.registry.feature_values_registry import (
    Feature,
    FeatureValuesRegistry,
)
from src.grammar.registry.feature_combination_registry import (
    FeatureCombinationsRegistry,
    FeatureValueCombinations,
)
from src.constants import EXAMPLE_CONFIG_DIR
from src.config_utils.config_walker import ConfigWalker


def test_feature_from_config_builds_feature():
    config_path = os.path.join(EXAMPLE_CONFIG_DIR, "features", "verb_and_adjective.yaml")
    feature = Feature.from_config(
        name="tam",
        values=["imperfective", "perfective", "imperative"],
        source=config_path,
    )

    assert isinstance(feature, Feature)
    assert feature.name == "tam"
    assert feature.values == ["imperfective", "perfective", "imperative", "unmarked"]
    assert feature.source == config_path


def test_feature_rejects_empty_name_or_values_or_duplicate_values():
    with pytest.raises(ValueError, match="Feature name cannot be empty"):
        Feature(name="", values=["x"])

    with pytest.raises(ValueError, match="must define at least one value"):
        Feature(name="tam", values=[])

    with pytest.raises(ValueError, match="contains duplicate values"):
        Feature(name="tam", values=["imperative", "imperative"])


def test_feature_values_registry_load_data_from_config_builds_feature_objects():
    registry = FeatureValuesRegistry()
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
    assert data["person"].values == ["1sg", "2sg", "3sg", "unmarked"]
    assert data["person"].source == "config/features/sample.yaml"


def test_feature_values_registry_rejects_duplicate_features_across_configs():
    with pytest.raises(ValueError, match="Duplicate feature 'person'"):
        registry = FeatureValuesRegistry(
            config_objects={
                "a.yaml": {"features": {"person": ["1sg", "2sg"]}, "source_path": "a.yaml"},
                "b.yaml": {"features": {"person": ["3sg"]}, "source_path": "b.yaml"},
            }
        )


def test_feature_value_combinations_expands_wildcards_and_defaults_missing_query_values():
    features = [
        Feature(name="tam", values=["imperative", "infinitive"]),
        Feature(name="deixis", values=["itive", "ventive"]),
    ]
    combinations = FeatureValueCombinations(
        combinations=[
            {"tam": "imperative", "deixis": "*"},
            {"tam": "infinitive", "deixis": "unmarked"},
        ],
        features=features,
    )

    assert combinations.feature_names == ["tam", "deixis"]
    assert combinations.is_licit_combination(tam="imperative", deixis="itive")
    assert combinations.is_licit_combination(tam="imperative", deixis="ventive")
    assert combinations.is_licit_combination(tam="infinitive")
    assert not combinations.is_licit_combination(tam="imperative")

    all_combos = combinations.get_all_combinations()
    assert len(all_combos) == 3
    assert {"tam": "imperative", "deixis": "itive"} in all_combos
    assert {"tam": "imperative", "deixis": "ventive"} in all_combos
    assert {"tam": "infinitive", "deixis": "unmarked"} in all_combos


def test_feature_value_combinations_rejects_unknown_feature_in_query():
    features = [
        Feature(name="tam", values=["imperative"]),
        Feature(name="deixis", values=["itive"]),
    ]
    combinations = FeatureValueCombinations(
        combinations=[{"tam": "imperative", "deixis": "itive"}],
        features=features,
    )

    with pytest.raises(ValueError, match="Unexpected feature 'subject'"):
        combinations.is_licit_combination(tam="imperative", deixis="itive", subject="1sg")


def test_feature_combinations_registry_load_data_from_config_normalizes_unmarked_values():
    feature_values_registry = FeatureValuesRegistry(
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
    feature_values_registry = FeatureValuesRegistry(
        data={"tam": Feature(name="tam", values=["imperative"])}
    )
    registry = FeatureCombinationsRegistry(feature_values_registry=feature_values_registry)

    with pytest.raises(KeyError, match="No feature found with name 'deixis'"):
        registry.load_data_from_config(
            {
                "features": ["tam", "deixis"],
                "combinations": [{"tam": "imperative", "deixis": "itive"}],
                "source_path": "config/features/bad.yaml",
            }
        )


def test_feature_and_combination_registries_load_real_project_configs():
    walker = ConfigWalker(EXAMPLE_CONFIG_DIR)
    feature_configs = walker.config_data["feature_definition_configs"]
    feature_values_registry = FeatureValuesRegistry(config_objects=feature_configs)
    
    combo_configs = walker.config_data["feature_combination_configs"]
    combinations_registry = FeatureCombinationsRegistry(
        feature_values_registry=feature_values_registry,
        config_objects=combo_configs
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
        "unmarked",
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


def test_features_registry_orchestrates_feature_and_combination_lookup():
    walker = ConfigWalker(EXAMPLE_CONFIG_DIR)
    feature_configs = walker.config_data["feature_definition_configs"]
    registry = FeatureValuesRegistry(config_objects=feature_configs)

    tam = registry.get_feature("tam")
    assert isinstance(tam, Feature)
    assert tam.name == "tam"


def test_features_registry_getters_raise_for_unknown_names():
    walker = ConfigWalker(EXAMPLE_CONFIG_DIR)
    feature_configs = walker.config_data["feature_definition_configs"]
    registry = FeatureValuesRegistry(config_objects=feature_configs)

    with pytest.raises(KeyError, match="No feature found"):
        registry.get_feature("does_not_exist")
