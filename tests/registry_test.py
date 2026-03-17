import pytest

from src.fst_registry import (
    InventoryRegistry, InventoryItem,
    Pattern, PatternRegistry,
    Rule, RuleRegistry,
    FstRegistry,
)

def test_inventory_registry():
    reg = InventoryRegistry.from_config_dir('config/')

    assert hasattr(reg, 'data')
    data = reg.data
    assert isinstance(data, dict)
    for key, value in data.items():
        assert type(key) is str
        assert isinstance(value, InventoryItem)
    
    # test sample inventory items
    assert '<N>' in data
    assert data['<N>'].type == 'class'
    expected_nasal_phones = ['m', 'n', 'ɲ', 'ŋ']

    for item in data['<N>'].children:
        assert item.type == 'phone'
        assert item.value in expected_nasal_phones

    assert '<V>' in data
    assert data['<V>'].type == 'class'
    expected_vowel_subclasses = ["<V_High>", "<V_Mid>", "<V_Low>"]

    for item in data['<V>'].children:
        assert item.type == 'class'
        assert item.value in expected_vowel_subclasses

    assert '<T>' in data
    assert data['<T>'].type == 'class'
    expected_tones = {
        "<HL>": "\u0302",
        "<H>": "\u0301",
        "<L>": "\u0300",
        "<LH>": "\u030C",
    }

    for item in data['<T>'].children:
        assert item.type == 'class'
        assert item.value in expected_tones
        for subitem in item.children:
            assert subitem.type == 'phone'
            assert subitem.value == expected_tones[item.value]

    assert "<TONE_SLOT>" in data
    assert data["<TONE_SLOT>"].type == 'class'
    expected_flags = ["[TBU]", "[FLOAT]"]

    for item in data["<TONE_SLOT>"].children:
        assert item.type == 'flag'
        assert item.value in expected_flags

def test_pattern_list():
    pattern_list = PatternRegistry.from_config_dir('config/')
    
    assert hasattr(pattern_list, 'data')

    # test sample members

    nonhigh_v = '<V_NonHigh>'
    assert nonhigh_v in pattern_list.data
    nonhigh_v_pattern = pattern_list.data[nonhigh_v]
    assert isinstance(nonhigh_v_pattern, Pattern)
    assert nonhigh_v_pattern.value == "(<V_Mid>|<V_Low>)"

    coronal_obstruent = '<CorObs>'
    assert coronal_obstruent in pattern_list.data
    coronal_obs_pattern = pattern_list.data[coronal_obstruent]
    assert isinstance(coronal_obs_pattern, Pattern)
    assert coronal_obs_pattern.value == "(t|d|s|t̪|d̪)"

    velar_stop = '<VelStop>'
    assert velar_stop in pattern_list.data
    velar_stop_pattern = pattern_list.data[velar_stop]
    assert isinstance(velar_stop_pattern, Pattern)
    assert velar_stop_pattern.value == "(k|g)"

    coronal_sequence = '<CorSeq>'
    assert coronal_sequence in pattern_list.data
    coronal_seq_pattern = pattern_list.data[coronal_sequence]
    assert isinstance(coronal_seq_pattern, Pattern)
    assert coronal_seq_pattern.value == "<CorObs><CorObs>+"

    ng_cluster = '<Ng>'
    assert ng_cluster in pattern_list.data
    ng_pattern = pattern_list.data[ng_cluster]
    assert isinstance(ng_pattern, Pattern)
    assert ng_pattern.value == "ŋ<VelStop>"

    velar_coronal_cluster = '<VelCor>'
    assert velar_coronal_cluster in pattern_list.data
    velcor_pattern = pattern_list.data[velar_coronal_cluster]
    assert isinstance(velcor_pattern, Pattern)
    assert velcor_pattern.value == "<VelStop><CorObs>"

    # test linkages

    assert hasattr(nonhigh_v_pattern, 'used_by')
    assert hasattr(nonhigh_v_pattern, 'uses')
    assert set(nonhigh_v_pattern.used_by) == set()
    assert set(nonhigh_v_pattern.uses) == set()

    assert hasattr(coronal_obs_pattern, 'used_by')
    assert hasattr(coronal_obs_pattern, 'uses')
    assert set(coronal_obs_pattern.used_by) == {coronal_seq_pattern, velcor_pattern}
    assert set(coronal_obs_pattern.uses) == set()

    assert hasattr(velar_stop_pattern, 'used_by')
    assert hasattr(velar_stop_pattern, 'uses')
    assert set(velar_stop_pattern.used_by) == {velcor_pattern, ng_pattern}
    assert set(velar_stop_pattern.uses) == set()
    
    assert hasattr(coronal_seq_pattern, 'used_by')
    assert hasattr(coronal_seq_pattern, 'uses')
    assert set(coronal_seq_pattern.used_by) == set()
    assert set(coronal_seq_pattern.uses) == {coronal_obs_pattern}

    assert hasattr(ng_pattern, 'used_by')
    assert hasattr(ng_pattern, 'uses')
    assert set(ng_pattern.used_by) == set()
    assert set(ng_pattern.uses) == {velar_stop_pattern}

    assert hasattr(velcor_pattern, 'used_by')
    
    assert hasattr(velcor_pattern, 'uses')
    assert set(velcor_pattern.used_by) == set()
    assert set(velcor_pattern.uses) == {velar_stop_pattern, coronal_obs_pattern}

    # test topological sort

    sorted_patterns = pattern_list.patterns_sorted

    # pairwise orderings matter more than absolute order
    # (i.e., if pattern A is before pattern B in the sorted list, then A must be used by B)
    for pattern in sorted_patterns:
        for child_pattern in pattern.uses:
            assert sorted_patterns.index(child_pattern) < sorted_patterns.index(pattern),\
                f"Pattern {child_pattern} should be before {pattern} in topological sort"
            
        for parent_pattern in pattern.used_by:
            assert sorted_patterns.index(pattern) < sorted_patterns.index(parent_pattern),\
                f"Pattern {pattern} should be before {parent_pattern} in topological sort"

    # test that all patterns are present in the sorted list
    assert set(sorted_patterns) == set(pattern_list.data.values())

    # cannot test fst composition as that requires an InventoryRegistry
    # see test_fst_registry for tests of FST construction and composition


def test_rule_list():
    rule_list = RuleRegistry.from_config_dir('config/')
    assert hasattr(rule_list, 'data')

    # test sample members
    assert 'coalesce_before_i' in rule_list.data
    coalesce_rule = rule_list.data['coalesce_before_i']
    assert isinstance(coalesce_rule, Rule)
    assert coalesce_rule.type == 'simple_rule'
    assert coalesce_rule.input_pattern.value == "<V_NonHigh>-?i"
    assert coalesce_rule.output_pattern.value == "ɛ"
    assert coalesce_rule.left_context.value is None
    assert coalesce_rule.right_context.value is None
    assert not coalesce_rule.rule_sequence

    assert 'delete_vowel_in_hiatus' in rule_list.data
    delete_rule = rule_list.data['delete_vowel_in_hiatus']
    assert isinstance(delete_rule, Rule)
    assert delete_rule.type == 'simple_rule'
    assert delete_rule.input_pattern.value == "<V>-?"
    assert delete_rule.output_pattern.value is None # deletion
    assert delete_rule.left_context.value is None
    assert delete_rule.right_context.value == "<V>"
    assert not delete_rule.rule_sequence

    assert 'resolve_hiatus' in rule_list.data
    resolve_rule = rule_list.data['resolve_hiatus']
    assert isinstance(resolve_rule, Rule)
    assert resolve_rule.type == 'rule_sequence'
    assert resolve_rule.input_pattern.value is None
    assert resolve_rule.output_pattern.value is None
    assert resolve_rule.left_context.value is None
    assert resolve_rule.right_context.value is None
    assert resolve_rule.rule_sequence == [coalesce_rule, delete_rule]

    # check topological sort
    sorted_rules = rule_list.rules_sorted
    assert sorted_rules.index(delete_rule) < sorted_rules.index(resolve_rule)
    assert sorted_rules.index(coalesce_rule) < sorted_rules.index(resolve_rule)


def test_fst_registry_acceptors():
    reg = FstRegistry.from_config_dir('config/')

    expected_phones = [
        'b', 'd̪', 'd', 'ɟ', 'g',
        'p', 't̪', 't', 'c', 'k', 'ʔ',
        'm', 'n', 'ɲ', 'ŋ',
        'f', 'v', 'ð', 's', 'ʃ', 'h',
        'l', 'r', 'ɾ', 'ɽ',
        'j', 'w',
        'i', 'ɪ', 'u', 'ʊ',
        'e', 'ɛ', 'ə', 'ɜ', 'o', 'ɔ',
        'a',
        '\u0300', '\u0301', '\u0302', '\u030C',
    ]

    expected_flags = ["[TBU]", "[FLOAT]"]

    assert hasattr(reg, 'sigma')
    assert hasattr(reg, 'sigma_star')

    assert hasattr(reg, 'phone_fsa')
    assert hasattr(reg, 'phone_star')    

    assert hasattr(reg, 'flag_fsa')
    assert hasattr(reg, 'flag_star')

    for phone in expected_phones:
        # test sigma and phone acceptors recognize phone
        assert reg.fsm_string(
            reg.fsa(phone)@reg.sigma
        ) == phone
        assert reg.fsm_string(
            reg.fsa(phone+phone)@reg.sigma_star
        ) == phone+phone

        assert reg.fsm_string(
            reg.fsa(phone)@reg.phone_fsa
        ) == phone
        assert reg.fsm_string(
            reg.fsa(phone+phone)@reg.phone_star
        ) == phone+phone

        # test flag acceptor rejects phone
        assert reg.fsm_strings(
            reg.fsa(phone)@reg.flag_fsa
        ) == []
        assert reg.fsm_strings(
            reg.fsa(phone+phone)@reg.flag_star
        ) == []

    for flag in expected_flags:
        # test sigma and flag acceptors recognize flag
        assert reg.fsm_string(
            reg.fsa(flag)@reg.sigma
        ) == flag
        assert reg.fsm_string(
            reg.fsa(flag+flag)@reg.sigma_star
        ) == flag+flag

        assert reg.fsm_string(
            reg.fsa(flag)@reg.flag_fsa
        ) == flag
        assert reg.fsm_string(
            reg.fsa(flag+flag)@reg.flag_star
        ) == flag+flag

        # test flag acceptor rejects flag
        predicted_output = reg.fsm_strings(
            reg.fsa(flag)@reg.phone_fsa
        )
        assert predicted_output == []
        predicted_output = reg.fsm_strings(
            reg.fsa(flag+flag)@reg.phone_star
        )
        assert predicted_output == []


@pytest.mark.parametrize(
    ("pattern_ref", "input_string"),
    [
        ("<V_NonHigh>", "e"),
        ("<V_NonHigh>", "ɛ"),
        ("<V_NonHigh>", "ə"),
        ("<V_NonHigh>", "ɜ"),
        ("<V_NonHigh>", "o"),
        ("<V_NonHigh>", "ɔ"),
        ("<V_NonHigh>", "a"),
        ("<CorObs>", "t"),
        ("<CorObs>", "d"),
        ("<CorObs>", "s"),
        ("<CorObs>", "t̪"),
        ("<CorObs>", "d̪"),
        ("<VelStop>", "k"),
        ("<VelStop>", "g"),
        ("<Ng>", "ŋk"),
        ("<Ng>", "ŋg"),
        ("<CorSeq>", "tt"),
        ("<CorSeq>", "td"),
        ("<CorSeq>", "tdd"),
        ("<CorSeq>", "ts"),
        ("<CorSeq>", "tss"),
        ("<CorSeq>", "d̪t"),
        ("<VelCor>", "kt"),
        ("<VelCor>", "gd̪"),
    ],
)
def test_fst_registry_patterns_accept_expected_strings(pattern_ref, input_string):
    reg = FstRegistry.from_config_dir('config/')

    predicted_output = reg.fsm_string(
        reg.fsa(input_string) @ reg.patterns[pattern_ref].fsa
    )

    assert predicted_output == input_string


@pytest.mark.parametrize(
    ("pattern_ref", "input_string"),
    [
        ("<V_NonHigh>", "i"),
        ("<V_NonHigh>", "u"),
        ("<V_NonHigh>", "m"),
        ("<V_NonHigh>", "ei"),
        ("<CorObs>", "k"),
        ("<CorObs>", "n"),
        ("<CorObs>", "ts"),
        ("<VelStop>", "t"),
        ("<VelStop>", "ŋ"),
        ("<VelStop>", "kg"),
        ("<Ng>", "ŋ"),
        ("<Ng>", "ŋt"),
        ("<Ng>", "kg"),
        ("<CorSeq>", "t"),
        ("<CorSeq>", "ktt"),
        ("<CorSeq>", "tn"),
        ("<VelCor>", "ŋk"),
        ("<VelCor>", "kk"),
        ("<VelCor>", "tk"),
    ],
)
def test_fst_registry_patterns_reject_unexpected_strings(pattern_ref, input_string):
    reg = FstRegistry.from_config_dir('config/')

    predicted_output = reg.fsm_strings(
        reg.fsa(input_string) @ reg.patterns[pattern_ref].fsa
    )

    assert predicted_output == []


@pytest.mark.parametrize(
    ("rule_ref", "input_string", "expected_output"),
    [
        ("coalesce_before_i", "a-i", "ɛ"),
        ("coalesce_before_i", "ai", "ɛ"),
        ("coalesce_before_i", "oi", "ɛ"),
        ("delete_vowel_in_hiatus", "a-i", "i"),
        ("delete_vowel_in_hiatus", "ai", "i"),
        ("delete_vowel_in_hiatus", "ua", "a"),
        ("resolve_hiatus", "au", "u"),
        ("resolve_hiatus", "a-i", "ɛ"),
        ("resolve_hiatus", "oi", "ɛ"),
        ("add_tbus", "a", "a[TBU]"),
        ("add_tbus", "m", "m[TBU]"),
        ("add_tbus", "ma", "m[TBU]a[TBU]"),
        ("remove_tbus_from_onset_c", "m[TBU]a[TBU]", "ma[TBU]"),
        ("remove_tbus_from_onset_c", "r[TBU]i[TBU]", "ri[TBU]"),
        ("remove_tbus_from_coda_c", "a[TBU]m[TBU]", "a[TBU]m"),
        ("remove_tbus_from_coda_c", "i[TBU]n[TBU]", "i[TBU]n"),
    ],
)
def test_rule_application(rule_ref, input_string, expected_output):
    reg = FstRegistry.from_config_dir('config/')

    predicted_output = reg.apply_rule(input_string, rule_ref)
    predicted_output = reg.fsm_string(predicted_output)
    assert predicted_output == expected_output


@pytest.mark.parametrize(
    ("rule_ref", "input_string"),
    [
        ("coalesce_before_i", "ui"),
        ("coalesce_before_i", "ab"),
        ("delete_vowel_in_hiatus", "at"),
        ("delete_vowel_in_hiatus", "m"),
        ("resolve_hiatus", "at"),
        ("resolve_hiatus", "mi"),
        ("add_tbus", "t"),
        ("add_tbus", "[TBU]"),
        ("remove_tbus_from_onset_c", "a[TBU]m[TBU]"),
        ("remove_tbus_from_onset_c", "a[TBU]"),
        ("remove_tbus_from_coda_c", "m[TBU]a[TBU]"),
        ("remove_tbus_from_coda_c", "a[TBU]m[TBU]a[TBU]"),
    ],
)
def test_rule_nonapplication(rule_ref, input_string):
    reg = FstRegistry.from_config_dir('config/')

    predicted_output = reg.apply_rule(input_string, rule_ref)
    predicted_output = reg.fsm_string(predicted_output)
    assert predicted_output == input_string
