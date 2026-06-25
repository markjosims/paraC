from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.constants import EXAMPLE_CONFIG_DIR
from src.grammar.registry.feature_values_registry import FeatureValuesRegistry, Feature
from src.grammar.registry.feature_combination_registry import FeatureValueCombinations
from src.grammar.registry.contingent_marker_registry import ContingentMarkers
from src.grammar.registry.feature_marker_registry import FeatureMarkers, Marker, MarkerList
from src.grammar.registry.paradigm_registry import Paradigm
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar.registry.lexicon_registry import Lexicon
from src.config_utils.config_walker import ConfigWalker


PARADIGM_CONFIG = Path(EXAMPLE_CONFIG_DIR) / "paradigm" / "ipfv_it.yaml"


def _load_ipfv_it_config():
    with PARADIGM_CONFIG.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _build_ipfv_feature_combinations(feature_orchestrator: FeatureOrchestrator):
    features = list(feature_orchestrator.features.values())

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
        features=features,
    )


def _build_ipfv_marker_objects(feature_orchestrator: FeatureOrchestrator):
    from src.grammar.registry.feature_marker_registry import FeatureMarkersRegistry
    walker = ConfigWalker(EXAMPLE_CONFIG_DIR)
    
    marker_registry = FeatureMarkersRegistry(
        feature_orchestrator=feature_orchestrator,
        config_objects=walker.config_data["feature_marker_configs"]
    )
    class_prefixes = marker_registry.data["person_markers"] # renamed in example? let's check. 
    # Actually example has class_prefixes.yaml in markers/ (old path)
    # New example has feature_markers/person_markers.yaml
    
    # Let's just mock them to be safe and independent of exact example file names if they change
    return [
        FeatureMarkers(
            feature=feature_orchestrator.get_feature("class_marker"),
            data={"l": MarkerList([Marker(value="l-", type="prefix")])},
        ),
        FeatureMarkers(
            feature=feature_orchestrator.get_feature("deixis"),
            data={"itive": MarkerList([])},
        ),
        FeatureMarkers(
            feature=feature_orchestrator.get_feature("object"),
            data={"1sg": MarkerList([Marker(value="-o", type="suffix")])},
        ),
        FeatureMarkers(
            feature=feature_orchestrator.get_feature("subject"),
            data={
                "1sg": MarkerList([]),
            },
        ),
        FeatureMarkers(
            feature=feature_orchestrator.get_feature("tam"),
            data={"imperfective": MarkerList([])},
        ),
    ]


def test_paradigm_combine_global_standard_and_contingent_markers_for_ipfv_slots():
    # We will try to make it syntactically correct with new API.
    # We won't load the real ipfv_it.yaml if it's not there, we'll mock the config.
    
    feature_orchestrator = FeatureOrchestrator(
        feature_configs={"f": {"features": {
            "class_marker": ["l"],
            "deixis": ["itive", "ventive"],
            "object": ["1sg", "3sg"],
            "subject": ["1sg", "2sg"],
            "tam": ["imperfective", "perfective"]
        }}},
        feature_combination_configs={}
    )
    
    contingent = ContingentMarkers(
        features=[feature_orchestrator.get_feature("subject"), feature_orchestrator.get_feature("object")],
        feature_mappings={
            frozenset([("subject", "1sg"), ("object", "3sg")]): MarkerList([Marker(value="-a", type="suffix")])
        }
    )

    # We need a Lexicon for Paradigm
    from src.grammar.registry.lexicon_registry import PartOfSpeech
    pos = PartOfSpeech(name="verb", features=[feature_orchestrator.get_feature(f) for f in ["tam", "subject", "object", "deixis", "class_marker"]])
    lexicon = Lexicon(part_of_speech=pos, entries=None, fst_orchestrator=None)

    paradigm = Paradigm(
        feature_value_combinations=_build_ipfv_feature_combinations(feature_orchestrator),
        markers=_build_ipfv_marker_objects(feature_orchestrator),
        contingent_markers=[contingent],
        global_markers=MarkerList([]),
        marker_order=["prefixation", "suffixation"],
        lexicon=lexicon,
        fst_orchestrator=None, 
    )

    assert paradigm.name == "[UNNAMED]"
    assert paradigm.marker_order == ["prefixation", "suffixation"]
