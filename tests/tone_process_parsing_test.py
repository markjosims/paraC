from src.parser import (
    add_tone_process_to_parser,
    append_eos_to_input, apply_rule_to_input, shift_feature_value,
    prune_redundant_paths,
)
from src.lexicon import *
from src.constants import EOS_STR
from src.lexicon.phonology import FINAL_LOWERING_RULE, LEFT_H_RULE
from src.fst_helpers import get_lattice_strs, fst


"""
## Tone process application tests
"""

parser_input_strs = [
    "kə̀pɔ́",
    "ká pɛ̀",
]
parser_output_strs = [
    "p[class=g][tam=perfective][deixis=ventive][final_lowering=unmarked][left_h=unmarked]",
    "p[class=g][tam=perfective][deixis=itive][final_lowering=unmarked][left_h=unmarked]",
]
parser_output_strs_shifted_features = [
    "p[class=g][tam=perfective][deixis=ventive][final_lowering=true][left_h=true]",
    "p[class=g][tam=perfective][deixis=itive][final_lowering=true][left_h=true]",
]
non_redundant_path_idcs = [0]

parser = pynini.union(*[
    fst(in_str, out_str)
    for in_str, out_str in zip(parser_input_strs, parser_output_strs)
])

parser_input_strs_eos = [
    in_str + EOS_STR for in_str in parser_input_strs
]

parser_eos = pynini.union(*[
    fst(in_str, out_str)
    for in_str, out_str in zip(parser_input_strs_eos, parser_output_strs)
])

rules = [FINAL_LOWERING_RULE, LEFT_H_RULE]
feature_map = {
    'final_lowering': ('unmarked', 'true'),
    'left_h': ('unmarked', 'true'),
}

parser_inputs_w_rule = [*map(fst, parser_input_strs_eos)]
for rule in rules:
    for i, f in enumerate(parser_inputs_w_rule):
        parser_inputs_w_rule[i] = f @ rule

parser_input_strs_w_rule = get_lattice_strs(
    pynini.union(*parser_inputs_w_rule),
    strip_eos=False,
)

parser_non_redundant_strs_w_rule = get_lattice_strs(
    pynini.union(*[
        f for i, f in enumerate(parser_inputs_w_rule)
        if i in non_redundant_path_idcs
    ]),
    strip_eos=False,
)

non_redundant_parses_w_rule = [
    output_str for i, output_str in enumerate(parser_output_strs_shifted_features)
    if i in non_redundant_path_idcs
]

def test_append_eos_to_input():

    result_fst = append_eos_to_input(parser)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    assert set(parser_input_strs_eos) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(parser_output_strs) == set(result_output_strs)

def test_append_eos_to_input_optional():

    result_fst = append_eos_to_input(parser, optional=True)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    assert set(parser_input_strs_eos+parser_input_strs) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(parser_output_strs) == set(result_output_strs)
def test_apply_rule_to_input():
    result_fst = apply_rule_to_input(parser_eos, rules)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input'
    )
    assert set(parser_input_strs_w_rule) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output'
    )
    assert set(parser_output_strs) == set(result_output_strs)

def test_shift_feature_value():
    """
    Note: this test assumes that `append_eos_to_input` works as intended.
    """
    result_fst = shift_feature_value(parser, feature_map)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )
    assert set(parser_input_strs) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )
    assert set(parser_output_strs_shifted_features) == set(result_output_strs)

def test_prune_redundant_paths():
    """
    Note: This test assumes that `append_eos_to_input`, `apply_rule_to_input`
    and `shift_feature_value` work as intended.
    """

    parser_w_rule = apply_rule_to_input(parser_eos, rules)
    parser_w_rule = shift_feature_value(parser_w_rule, feature_map)
    result_fst = prune_redundant_paths(parser_eos, parser_w_rule)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )
    assert set(parser_non_redundant_strs_w_rule) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )
    assert set(non_redundant_parses_w_rule) == set(result_output_strs)

def test_add_tone_process_to_parser():
    result_fst = add_tone_process_to_parser(parser_eos, rules, feature_map=feature_map)
    result_input_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='input',
    )
    assert set(parser_non_redundant_strs_w_rule) == set(result_input_strs)

    result_output_strs = get_lattice_strs(
        result_fst,
        strip_eos=False,
        project_type='output',
    )
    assert set(non_redundant_parses_w_rule) == set(result_output_strs)