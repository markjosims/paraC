from src.fst_registry import (
    InventoryRegistry, InventoryItem,
    Pattern, PatternList
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
    expected_flags = ["<TBU>", "<FLOAT>"]

    for item in data["<TONE_SLOT>"].children:
        assert item.type == 'flag'
        assert item.value in expected_flags

def test_inventory_registry_symbols():
    reg = InventoryRegistry.from_config_dir('config/')

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

    expected_flags = ["<TBU>", "<FLOAT>"]

    assert hasattr(reg, 'sigma')
    assert hasattr(reg, 'sigma_star')

    assert hasattr(reg, 'phone_acceptor')
    assert hasattr(reg, 'phone_star')    

    assert hasattr(reg, 'flag_acceptor')
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
            reg.fsa(phone)@reg.phone_acceptor
        ) == phone
        assert reg.fsm_string(
            reg.fsa(phone+phone)@reg.phone_star
        ) == phone+phone

        # test flag acceptor rejects phone
        assert reg.fsm_string(
            reg.fsa(phone)@reg.flag_acceptor
        ) == ''
        assert reg.fsm_string(
            reg.fsa(phone+phone)@reg.flag_star
        ) == ''

    for flag in expected_flags:
        # test sigma and flag acceptors recognize flag
        assert reg.fsm_string(
            reg.fsa(flag)@reg.sigma
        ) == flag
        assert reg.fsm_string(
            reg.fsa(flag+flag)@reg.sigma_star
        ) == flag+flag

        assert reg.fsm_string(
            reg.fsa(flag)@reg.flag_acceptor
        ) == flag
        assert reg.fsm_string(
            reg.fsa(flag+flag)@reg.flag_star
        ) == flag+flag

        # test flag acceptor rejects flag
        assert reg.fsm_string(
            reg.fsa(flag)@reg.phone_acceptor
        ) == ''
        assert reg.fsm_string(
            reg.fsa(flag+flag)@reg.phone_star
        ) == ''

def test_pattern_list():
    pattern_list = PatternList.from_config_dir('config/')
    
    assert hasattr(pattern_list, 'data')

    # test sample members

    nonhigh_v = '<V_NonHigh>'
    assert nonhigh_v in pattern_list.data
    nonhigh_v_pattern = pattern_list.data[nonhigh_v]
    assert isinstance(nonhigh_v_pattern, Pattern)
    assert Pattern.value == "(<V_Mid>|<V_Low>)"

    coronal_obstruent = '<CorObs>'
    assert coronal_obstruent in pattern_list.data
    coronal_obs_pattern = pattern_list.data[coronal_obstruent]
    assert isinstance(coronal_obs_pattern, Pattern)
    assert Pattern.value == "(t|d|s|t̪|d̪)"

    velar_stop = '<VelStop>'
    assert velar_stop in pattern_list.data
    velar_stop_pattern = pattern_list.data[velar_stop]
    assert isinstance(velar_stop_pattern, Pattern)
    assert Pattern.value == "(k|g)"

    # test linkages


def test_rule_list():
    expected_nonhigh_vowels = ['e', 'ɛ', 'ə', 'ɜ', 'o', 'ɔ', 'a']
    