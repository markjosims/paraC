import os

import pytest

from src.registry.feature_registry import FeatureValueCombinations
from src.registry.marker_registry import (
    ContingentMarkers,
    ContingentMarkersRegistry,
    FeatureMarkers,
    FeatureMarkersRegistry,
    Marker,
    MarkerRegistry,
)
from src.constants import EXAMPLE_CONFIG_DIR


def test_marker_from_config_merges_global_attributes_and_normalizes_replace():
    marker_list = Marker.list_from_config(
        [
            {"type": "suffix", "value": "-te"},
            {"type": "replace", "value": ["dt", "tt"]},
        ],
        global_order="suffixation",
        global_markers=[{"type": "prefix", "value": "ke-"}]
    )

    assert isinstance(marker_list, list)
    for marker in marker_list:
        assert isinstance(marker, Marker)
        if marker.type == "prefix":
            assert marker.value == "ke-"
        elif marker.type == "suffix":
            assert marker.value == "-te"
        elif marker.type == "replace":
            assert marker.value == ("dt", "tt")
        assert marker.order == "suffixation"


def test_marker_list_from_config_handles_none_single_and_multiple_markers():
    assert Marker.list_from_config(
        [None, None], global_order="x"
    ) == []

    single = Marker.list_from_config([{"suffix": "-ap"}], global_order="outer")
    assert len(single) == 1
    assert single[0].suffix == "-ap"
    assert single[0].order == "outer"

    multiple = Marker.list_from_config(
        [{"suffix": "-te"}, {"replace": ["dt", "tt"]}],
        global_order="shared"
    )
    assert len(multiple) == 2
    assert multiple[0].type == "suffix"
    assert multiple[0].value == "-te"
    assert multiple[0].order == "shared"
    assert multiple[1].type == "replace"
    assert multiple[1].value == ("dt", "tt")
    assert multiple[1].order == "shared"


def test_marker_rejects_unsupported_type():
    with pytest.raises(ValueError, match="Unrecognized marker type"):
        Marker.from_config({"type": "foo", "value": "bar"})


def test_feature_markers_from_config_builds_dynamic_attributes_and_global_marker():
    config_path = os.path.join(EXAMPLE_CONFIG_DIR, "markers", "person_markers.yaml")
    config = {
        "feature": "person",
        "global_order": "outer_suffixation",
        "global_markers": [{"type": "prefix", "value": "pre-"}],
        "markers": {
            "1sg": {"type": "suffix", "value": "-o"},
            "2sg": [
                {"type": "suffix", "value": "-te", "order": "suffixation"},
                {"type": "replace", "value": ["dt", "tt"], "order": "assimilation"},
            ], #STOPPEDHERE
            "3sg": None,
        },
        "source_path": config_path,
    }

    markers = FeatureMarkers.from_config(config)

    assert markers.feature == "person"
    assert markers.source == config_path
    assert markers.global_attributes == {"order": "outer_suffixation"}
    assert len(markers.global_marker) == 1
    assert markers.global_marker[0].prefix == "pre-"

    assert len(markers.data["1sg"]) == 1
    assert markers.data["1sg"][0].suffix == "-o"
    assert markers.data["1sg"][0].order == "outer_suffixation"
    assert markers.data["2sg"][0].suffix == "-te"
    assert markers.data["2sg"][0].order == "suffixation"
    assert markers.data["2sg"][1].replace == ("dt", "tt")
    assert markers.data["2sg"][1].order == "assimilation"
    assert markers.data["3sg"] == []

    assert markers.__dict__["1sg"] == markers.data["1sg"]
    assert markers.__dict__["2sg"] == markers.data["2sg"]


def test_contingent_markers_from_config_flattens_explicit_nesting_and_supports_lookup():
    config_path = os.path.join(EXAMPLE_CONFIG_DIR, "markers", "contingent_markers.yaml")
    config = {
        "features": ["subject", "object"],
        "global_attributes": {"order": "argument_marker"},
        "markers": {
            "object": {
                "3sg": {
                    "subject": {
                        "1sg": {"prefix": "[CL]-", "suffix": "-e"},
                        "2sg": {"prefix": "[CL]-", "suffix": "-a"},
                    }
                }
            }
        },
        "source_path": config_path,
    }

    markers = ContingentMarkers.from_config(config)

    assert markers.features == ["subject", "object"]
    assert markers.feature_names == ["object", "subject"]
    assert set(markers.data.keys()) == {
        "object=3sg subject=1sg",
        "object=3sg subject=2sg",
    }

    subject_1sg = markers.get_marker(subject="1sg", object="3sg")
    assert len(subject_1sg) == 1
    assert subject_1sg[0].prefix == "[CL]-"
    assert subject_1sg[0].suffix == "-e"
    assert subject_1sg[0].order == "argument_marker"


def test_contingent_markers_supports_implicit_nesting():
    config = {
        "features": ["tense", "person"],
        "markers": {
            "present": {
                "1sg": {"suffix": "-o"},
                "2sg": {"suffix": "-as"},
            },
            "past": {
                "1sg": {"suffix": "-e"},
            },
        },
    }

    markers = ContingentMarkers.from_config(config)

    assert set(markers.data.keys()) == {
        "person=1sg tense=present",
        "person=2sg tense=present",
        "person=1sg tense=past",
    }
    assert markers.get_marker(person="2sg", tense="present")[0].suffix == "-as"


def test_contingent_markers_get_marker_raises_for_unknown_combination():
    markers = ContingentMarkers(
        features=["subject", "object"],
        data={"object=3sg subject=1sg": [Marker(prefix="[CL]-")]},
    )

    with pytest.raises(KeyError, match="No marker found"):
        markers.get_marker(subject="2sg", object="3sg")


def test_feature_value_combinations_expands_wildcards_and_unmarked_defaults():
    combinations = FeatureValueCombinations(
        combinations=[
            {"subject": ["1sg", "2sg"], "object": "*"},
            {"subject": "unmarked", "object": "3sg"},
        ],
        features_to_values={
            "subject": ["1sg", "2sg", "unmarked"],
            "object": ["3sg", "3pl", "unmarked"],
        },
    )

    assert combinations.is_licit_combination(subject="1sg", object="3sg")
    assert combinations.is_licit_combination(subject="2sg", object="3pl")
    assert combinations.is_licit_combination(object="3sg")
    assert not combinations.is_licit_combination(subject="unmarked", object="3pl")

    assert combinations.get_all_combinations() == [
        {"subject": "1sg", "object": "3sg"},
        {"subject": "1sg", "object": "3pl"},
        {"subject": "2sg", "object": "3sg"},
        {"subject": "2sg", "object": "3pl"},
        {"subject": "unmarked", "object": "3sg"},
    ]


def test_feature_value_combinations_rejects_inconsistent_feature_sets():
    with pytest.raises(ValueError, match="All combination dictionaries must have the same feature names"):
        FeatureValueCombinations(
            combinations=[
                {"subject": "1sg", "object": "3sg"},
                {"subject": "2sg"},
            ],
            features_to_values={"subject": ["1sg", "2sg"], "object": ["3sg"]},
        )


def test_marker_registries_load_real_project_configs():
    feature_registry = FeatureMarkersRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    contingent_registry = ContingentMarkersRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    marker_registry = MarkerRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)

    assert set(feature_registry.data) >= {
        "class_prefixes",
        "ipfv_obj_markers",
        "ipfv_subj_markers",
    }
    assert set(contingent_registry.data) >= {"ipfv_3person_obj_markers"}

    subj_markers = marker_registry.get("ipfv_subj_markers")
    assert isinstance(subj_markers, FeatureMarkers)
    assert subj_markers.feature == "subject"
    assert subj_markers.data["1sg"][0].prefix == "íŋ-<CL>-"
    assert subj_markers.data["1sg"][0].order == "argument_marker"

    class_prefixes = marker_registry.get("class_prefixes")
    assert isinstance(class_prefixes, FeatureMarkers)
    assert class_prefixes.data["l"][0].replace == ("[CL]", "l")
    assert class_prefixes.data["l"][0].order == "class_prefix"

    obj_3sg = marker_registry.get("ipfv_3person_obj_markers")
    assert isinstance(obj_3sg, ContingentMarkers)
    markers = obj_3sg.get_marker(subject="1sg", object="3sg")
    assert len(markers) == 1
    assert markers[0].prefix == "[CL]-"
    assert markers[0].suffix == "-ɛ́"
    assert markers[0].order == "argument_marker"


def test_marker_registry_get_raises_for_unknown_name():
    marker_registry = MarkerRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)

    with pytest.raises(KeyError, match="No marker config found"):
        marker_registry.get("does_not_exist")
