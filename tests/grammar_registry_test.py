from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.constants import EXAMPLE_CONFIG_DIR
from src.registry.feature_values_registry import FeatureValueCombinations, FeatureValuesRegistry
from src.registry.marker_registry import ContingentMarkers, FeatureMarkers, Marker, MarkerRegistry
from src.registry.grammar_registry import ParadigmMarkers


PARADIGM_CONFIG = Path(EXAMPLE_CONFIG_DIR) / "paradigms" / "ipfv_it.yaml"



def _load_ipfv_it_config():
    with PARADIGM_CONFIG.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _build_ipfv_feature_combinations():
    features_registry = FeatureValuesRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    feature_values = deepcopy(
        features_registry.feature_values_registry.features_to_values
    )
    for values in feature_values.values():
        if "unmarked" not in values:
            values.append("unmarked")

    return FeatureValueCombinations(
        combinations=[
            {
                "class_marker": "l",
                "deixis": "itive",
                "object": "1sg",
                "subject": "1sg",
                "tam": "imperfective",
            },
            {
                "class_marker": "l",
                "deixis": "itive",
                "object": "3sg",
                "subject": "1sg",
                "tam": "imperfective",
            },
        ],
        features_to_values=feature_values,
    )


def _build_ipfv_marker_objects():
    marker_registry = MarkerRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)
    class_prefixes = marker_registry.get_config("class_prefixes")
    object_markers = marker_registry.get_config("ipfv_obj_markers")

    return {
        "class_marker": FeatureMarkers(
            feature="class_marker",
            data={"l": class_prefixes.data["l"]},
        ),
        "deixis": FeatureMarkers(feature="deixis", data={"itive": []}),
        "object": FeatureMarkers(
            feature="object",
            data={"1sg": object_markers.data["1sg"]},
        ),
        "subject": FeatureMarkers(
            feature="subject",
            data={
                "1sg": [],
            },
        ),
        "tam": FeatureMarkers(feature="tam", data={"imperfective": []}),
    }


def test_paradigm_markers_combine_global_standard_and_contingent_markers_for_ipfv_slots():
    ipfv_it = _load_ipfv_it_config()
    contingent = MarkerRegistry.from_config_dir(EXAMPLE_CONFIG_DIR).get_config("ipfv_3person_obj_markers")

    paradigm = ParadigmMarkers(
        feature_value_combinations=_build_ipfv_feature_combinations(),
        marker_objects=_build_ipfv_marker_objects(),
        contingent_marker_objects=[contingent],
        global_markers=Marker.list_from_config(ipfv_it["global_markers"]),
        marker_order=ipfv_it["order"],
    )

    plain_slot = paradigm.get_marker(
        class_marker="l",
        deixis="itive",
        object="1sg",
        subject="1sg",
        tam="imperfective",
    )
    third_object_slot = paradigm.get_marker(
        class_marker="l",
        deixis="itive",
        object="3sg",
        subject="1sg",
        tam="imperfective",
    )

    assert paradigm.feature_names == [
        "class_marker",
        "deixis",
        "object",
        "subject",
        "tam",
    ]
    assert set(paradigm.data) == {
        "class_marker=l deixis=itive object=1sg subject=1sg tam=imperfective",
        "class_marker=l deixis=itive object=3sg subject=1sg tam=imperfective",
    }

    assert [marker.order for marker in plain_slot] == [
        "root_tone",
        "final_vowel",
        "argument_marker",
        "class_prefix",
        "resolve_hiatus",
        "vowel_harmony",
        "tone_processes",
    ]
    assert plain_slot[0].rule == "$hl_star_tone"
    assert plain_slot[1].rule == "$final_vowel_A"
    assert plain_slot[2].suffix == "-ŋɛ̂"
    assert plain_slot[3].replace == ("[CL]", "l")
    assert plain_slot[4].rule == "$resolve_hiatus"
    assert plain_slot[5].rule == "$vowel_harmony"
    assert plain_slot[6].rule == "$float_tones"

    assert [marker.order for marker in third_object_slot] == [
        "root_tone",
        "final_vowel",
        "argument_marker",
        "class_prefix",
        "resolve_hiatus",
        "vowel_harmony",
        "tone_processes",
    ]
    assert third_object_slot[2].prefix == "[CL]-"
    assert third_object_slot[2].suffix == "-ɛ́"
    assert not any(marker.suffix == "-ŋɛ̂" for marker in third_object_slot)


def test_paradigm_markers_contingent_markers_take_priority_over_standard_markers():
    feature_combinations = FeatureValueCombinations(
        combinations=[
            {"object": "3sg", "subject": "1sg"},
        ],
        features_to_values={
            "object": ["3sg", "unmarked"],
            "subject": ["1sg", "unmarked"],
        },
    )
    marker_objects = {
        "object": FeatureMarkers(
            feature="object",
            data={"3sg": [Marker(suffix="-obj", order="argument_marker")]},
        ),
        "subject": FeatureMarkers(feature="subject", data={"1sg": []}),
    }
    contingent_markers = [
        ContingentMarkers(
            features=["subject", "object"],
            data={
                "object=3sg subject=1sg": [
                    Marker(prefix="[CL]-", suffix="-agr", order="argument_marker")
                ]
            },
        )
    ]

    paradigm = ParadigmMarkers(
        feature_value_combinations=feature_combinations,
        marker_objects=marker_objects,
        contingent_marker_objects=contingent_markers,
        global_markers=[],
        marker_order=["argument_marker"],
    )

    markers = paradigm.get_marker(subject="1sg", object="3sg")

    assert markers == [Marker(prefix="[CL]-", suffix="-agr", order="argument_marker")]


def test_paradigm_markers_require_feature_names_to_match_feature_combinations():
    feature_combinations = FeatureValueCombinations(
        combinations=[{"subject": "1sg", "object": "1sg"}],
        features_to_values={
            "subject": ["1sg", "unmarked"],
            "object": ["1sg", "unmarked"],
        },
    )

    with pytest.raises(ValueError, match="Feature names in feature_value_combinations do not match"):
        ParadigmMarkers(
            feature_value_combinations=feature_combinations,
            marker_objects={
                "subject": FeatureMarkers(feature="subject", data={"1sg": []}),
            },
            contingent_marker_objects=[],
            global_markers=[],
            marker_order=["argument_marker"],
        )


def test_paradigm_markers_reject_overlapping_contingent_feature_sets():
    feature_combinations = FeatureValueCombinations(
        combinations=[{"object": "3sg", "subject": "1sg", "class_marker": "l"}],
        features_to_values={
            "class_marker": ["l", "unmarked"],
            "object": ["3sg", "unmarked"],
            "subject": ["1sg", "unmarked"],
        },
    )

    contingent_a = ContingentMarkers(
        features=["subject", "object"],
        data={"object=3sg subject=1sg": [Marker(prefix="[CL]-")]},
    )
    contingent_b = ContingentMarkers(
        features=["object", "class_marker"],
        data={"class_marker=l object=3sg": [Marker(suffix="-x")]},
    )

    with pytest.raises(ValueError, match="Overlapping feature 'object'"):
        ParadigmMarkers(
            feature_value_combinations=feature_combinations,
            marker_objects={},
            contingent_marker_objects=[contingent_a, contingent_b],
            global_markers=[],
            marker_order=["argument_marker", "class_prefix"],
        )


def test_paradigm_markers_reject_unknown_order_stage_from_any_marker():
    feature_combinations = FeatureValueCombinations(
        combinations=[{"object": "1sg"}],
        features_to_values={"object": ["1sg", "unmarked"]},
    )

    with pytest.raises(ValueError, match="Marker order 'bad_stage' not recognized"):
        ParadigmMarkers(
            feature_value_combinations=feature_combinations,
            marker_objects={
                "object": FeatureMarkers(
                    feature="object",
                    data={"1sg": [Marker(suffix="-ŋɛ̂", order="bad_stage")]},
                ),
            },
            contingent_marker_objects=[],
            global_markers=[],
            marker_order=["argument_marker"],
        )


def test_paradigm_markers_place_unordered_markers_after_all_ordered_stages():
    feature_combinations = FeatureValueCombinations(
        combinations=[{"class_marker": "l", "object": "1sg"}],
        features_to_values={
            "class_marker": ["l", "unmarked"],
            "object": ["1sg", "unmarked"],
        },
    )

    paradigm = ParadigmMarkers(
        feature_value_combinations=feature_combinations,
        marker_objects={
            "class_marker": FeatureMarkers(
                feature="class_marker",
                data={"l": [Marker(replace=("[CL]", "l"), order="class_prefix")]},
            ),
            "object": FeatureMarkers(
                feature="object",
                data={"1sg": [Marker(suffix="-ŋɛ̂")]},
            ),
        },
        contingent_marker_objects=[],
        global_markers=[Marker(rule="$hl_star_tone", order="root_tone")],
        marker_order=["root_tone", "class_prefix"],
    )

    markers = paradigm.get_marker(class_marker="l", object="1sg")

    assert markers[0].rule == "$hl_star_tone"
    assert markers[1].replace == ("[CL]", "l")
    assert markers[2].suffix == "-ŋɛ̂"
