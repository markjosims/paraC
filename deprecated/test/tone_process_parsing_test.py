from src.parser import (
    add_process_to_parser,
    append_eos_to_input, apply_rule_to_input, shift_feature_value,
)
from src.lexicon import *
from src.constants import EOS_STR, TEST_CASE_DIR
from src.lexicon.phonology import (
    FINAL_LOWERING_RULE, LEFT_H_RULE,
    FINAL_LOWERING_RULE_NONVACUOUS, LEFT_H_RULE_NONVACUOUS,
)
from src.fst_helpers import get_lattice_strs, fst
import yaml
import pytest
import os
from recursivenamespace import rns

"""
## Load test data
"""

tone_process_data_path = os.path.join(TEST_CASE_DIR, 'parser_processes.yaml')
with open(tone_process_data_path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
data = rns(**data)

parser = pynini.union(*[
    fst(in_str, out_str)
    for in_str, out_str in zip(data.input_strings.base, data.output_strings.base)
])

parser_eos = pynini.union(*[
    fst(in_str, out_str)
    for in_str, out_str in zip(data.input_strings.eos, data.output_strings.base)
])

parser_optional_eos = parser | parser_eos

rule_map = {
    'final_lowering': FINAL_LOWERING_RULE,
    'left_h': LEFT_H_RULE,
    'final_lowering_left_h': [FINAL_LOWERING_RULE, LEFT_H_RULE],
}
nonvacuous_rule_map = {
    'final_lowering': FINAL_LOWERING_RULE_NONVACUOUS,
    'left_h': LEFT_H_RULE_NONVACUOUS,
    'final_lowering_left_h': [
        FINAL_LOWERING_RULE_NONVACUOUS,
        LEFT_H_RULE_NONVACUOUS,
    ],
}

"""
## Tone process application tests
"""

def test_append_eos_to_input():

    result_fst = append_eos_to_input(parser)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    assert set(data.input_strings.eos) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(data.output_strings.base) == set(result_output_strs)

def test_append_eos_to_input_optional():

    result_fst = append_eos_to_input(parser, optional=True)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    assert set(data.input_strings.eos+data.input_strings.base) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(data.output_strings.base) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
    'final_lowering_left_h',
])
def test_apply_rule_to_input(rule_set: str):
    result_fst = apply_rule_to_input(
        parser_eos,
        rule_map[rule_set],
    )
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    expected_input = getattr(data.input_strings, rule_set)
    assert set(expected_input) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(data.output_strings.base) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
])
def test_apply_rule_to_input_optional_eos(rule_set: str):
    result_fst = apply_rule_to_input(
        parser_optional_eos,
        rule_map[rule_set],
    )
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    expected_input = getattr(data.input_strings, rule_set)
    if 'left_h' in rule_set:
        expected_input_no_eos = [x.removesuffix(EOS_STR) for x in expected_input]
        expected_input += expected_input_no_eos
    else:
        expected_input += data.input_strings.base
    assert set(expected_input) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(data.output_strings.base) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
    'final_lowering_left_h',
])
def test_shift_feature_value(rule_set: str):
    feature_map = getattr(data.feature_maps, rule_set)
    result_fst = shift_feature_value(parser, feature_map)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )
    assert set(data.input_strings.base) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )
    expected_output = getattr(data.output_strings, rule_set)
    assert set(expected_output) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
    'final_lowering_left_h',
])
def test_apply_rule_to_input_nonvacuous(rule_set: str):
    result_fst = apply_rule_to_input(
        parser_eos,
        nonvacuous_rule_map[rule_set],
    )
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )

    expected_input = getattr(data.input_strings, rule_set)
    expected_input = [
        x for i, x in enumerate(expected_input)
        if i in data.non_redundant_path_indices
    ]

    assert set(expected_input) == set(result_input_strs)


    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )

    expected_output = data.output_strings.base
    expected_output = [
        x for i, x in enumerate(expected_output)
        if i in data.non_redundant_path_indices
    ]

    assert set(expected_output) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
    'final_lowering_left_h',
])
def test_apply_rule_to_input_nonvacuous_optional_eos(rule_set: str):
    result_fst = apply_rule_to_input(
        parser_optional_eos,
        nonvacuous_rule_map[rule_set],
    )
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )

    expected_input = getattr(data.input_strings, rule_set)
    expected_input = [
        x for i, x in enumerate(expected_input)
        if i in data.non_redundant_path_indices
    ]
    if 'final_lowering' not in rule_set:
        expected_input_no_eos = [x.removesuffix(EOS_STR) for x in expected_input]
        expected_input += expected_input_no_eos

    assert set(expected_input) == set(result_input_strs)


    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )

    expected_output = data.output_strings.base
    expected_output = [
        x for i, x in enumerate(expected_output)
        if i in data.non_redundant_path_indices
    ]

    assert set(expected_output) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
    'final_lowering_left_h',
])
def test_add_tone_process_to_parser(rule_set: str):
    rule = nonvacuous_rule_map[rule_set]
    feature_map = getattr(data.feature_maps, rule_set)

    result_fst = add_process_to_parser(parser_eos, rule, feature_map=feature_map)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )
    expected_input = getattr(data.input_strings, rule_set)
    expected_input = [
        x for i, x in enumerate(expected_input)
        if i in data.non_redundant_path_indices
    ]
    assert set(expected_input) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )
    expected_output = getattr(data.output_strings, rule_set)
    expected_output = [
        x for i, x in enumerate(expected_output)
        if i in data.non_redundant_path_indices
    ]
    assert set(expected_output) == set(result_output_strs)

@pytest.mark.parametrize("rule_set", [
    'final_lowering',
    'left_h',
    'final_lowering_left_h',
])
def test_add_tone_process_to_parser_optional_eos(rule_set: str):
    rule = nonvacuous_rule_map[rule_set]
    feature_map = getattr(data.feature_maps, rule_set)

    result_fst = add_process_to_parser(parser_optional_eos, rule, feature_map=feature_map)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )
    expected_input = getattr(data.input_strings, rule_set)
    expected_input = [
        x for i, x in enumerate(expected_input)
        if i in data.non_redundant_path_indices
    ]
    if 'final_lowering' not in rule_set:
        expected_input_no_eos = [x.removesuffix(EOS_STR) for x in expected_input]
        expected_input += expected_input_no_eos
    assert set(expected_input) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )
    expected_output = getattr(data.output_strings, rule_set)
    expected_output = [
        x for i, x in enumerate(expected_output)
        if i in data.non_redundant_path_indices
    ]
    assert set(expected_output) == set(result_output_strs)