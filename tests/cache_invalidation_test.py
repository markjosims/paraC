from src.yaml_utils.models import (
    Marker,
    Rule,
    SimpleRule,
    StringMapRule,
    RuleSequence,
    SingleStringMarker,
    StringTupleMarker,
    UnorderedMarker,
    PrincipalPartMarker,
    OperationTypeStringTuple,
    OperationTypeSingleString,
    UnorderedOperation,
)
from src.grammar.transducer_compilation import compile_marker
from src.grammar.acceptor_compilation import (
    fsa,
    word_fsa,
    fsm_strings,
    filter_strings_by_pattern,
)
from src.grammar.marker_resolution import get_markers_for_paradigm
from src.lexicon import get_roots_with_gloss
import pynini

import yaml
from copy import deepcopy
import pytest

from src.yaml_utils.yaml_server import get_yaml_data_safe, get_yaml_path
from src.grammar.paradigm_compilation import inflect, parse, search, _get_or_build

from src.grammar.transducer_compilation import get_rule_fst

from src.constants import PROJECT_ROOT
import os

yaml_dir = os.path.join(PROJECT_ROOT, "yaml", "spanish-example")
os.environ["YAML_DIR"] = yaml_dir


@pytest.fixture
def restore_diphthongization_rule():
    yaml_basename = "vowel_alternations"
    yaml_data = get_yaml_data_safe("Rules", yaml_basename)
    yaml_path = get_yaml_path("Rules", yaml_basename)

    yield

    # ensure original YAML data restored at test completion
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)


def test_rule_invalidation_from_rule_file(restore_diphthongization_rule):
    rule_input = word_fsa("pod")
    orig_rule_fst = get_rule_fst("diphthongization")
    orig_result = rule_input @ orig_rule_fst
    orig_result = fsm_strings(orig_result, strip_all_tags=True)

    assert orig_result == ["pued"]

    # first test: touching file triggers recompilation
    # and rule results are the same before and after

    yaml_basename = "vowel_alternations"
    yaml_data = get_yaml_data_safe("Rules", yaml_basename)
    yaml_path = get_yaml_path("Rules", yaml_basename)

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input @ new_rule_fst
    new_result = fsm_strings(new_result)

    # second test: edit the yaml data so rule output changes

    diphthongization_rule_index = [
        i
        for i, rule in enumerate(yaml_data["rules"])
        if rule["name"] == "diphthongization"
    ][0]

    yaml_data["rules"][diphthongization_rule_index]["string_map"] = [
        ["e", "eee"],
        ["o", "ooo"],
    ]

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input @ new_rule_fst
    new_result = fsm_strings(new_result, strip_all_tags=True)

    assert new_result == ["poood"]
