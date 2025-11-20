import pytest
from src.lexicon.phonology import *
from src.fst_helpers import *
from pynini.lib import rewrite

@pytest.mark.parametrize("fst_input,fst_output", [
    ("àpɾí",                "námàl"),
    ("àpɾí", ["námàl",      "nàpɾí"]),
    (["àpɾí", "ðɔ̀mɔ̀cɔ̀"],    ["námàl", "nàpɾí"]),
    (["àpɾí", "ðɔ̀mɔ̀cɔ̀"],    "námàl"),
    (["àpɾí", "ðɔ̀mɔ̀cɔ̀"],    None),
    ("ðɔ̀mɔ̀cɔ̀",              None),
])
def test_fst_wrapper(fst_input, fst_output):
    f = fst(fst_input, fst_output)
    input_strings = get_lattice_strs(f, 'input')
    if type(fst_input) is str:
        assert len(input_strings) == 1
        assert input_strings[0] == fst_input
    else:
        assert set(input_strings) == set(fst_input)

    if fst_output is None:
        return

    output_strings = get_lattice_strs(f, 'output')
    if type(fst_output) is str:
        assert len(output_strings) == 1
        assert output_strings[0] == fst_output
    else:
        assert set(output_strings) == set(fst_output)

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "ŕn"),
    ("tutɔ", "tútɔ́"),
    ("kaŋt̪ɛt̪iŋi", "káŋt̪ɛ́t̪íŋí"),
    ("kr", "kŕ")
])
def test_all_high_tone(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(fst(atonal_str), ALL_HIGH_TONE_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==tone_added_str

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "r̀n"),
    ("tutɔ", "tùtɔ̀"),
    ("kaŋt̪ɛt̪iŋi", "kàŋt̪ɛ̀t̪ìŋì"),
    ("kr", "kr̀")
])
def test_all_low_tone(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(fst(atonal_str), ALL_LOW_TONE_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==tone_added_str

@pytest.mark.parametrize("atonal_str,tone_added_str", [
    ("rn", "ŕn"),
    ("tutɔ", "tútɔ̀"),
    ("kaŋt̪ɛt̪iŋi", "káŋt̪ɛ̀t̪ìŋì"),
    ("kr", "kŕ")
])
def test_hlstar(atonal_str, tone_added_str):
    lattice=rewrite.rewrite_lattice(fst(atonal_str), HLSTAR_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==tone_added_str

@pytest.mark.parametrize("unround_str,round_str", [
    ("ɜ̀d", "ɔ̀d"),
    ("kât̪", "kɔ̂t̪"),
    ("pɛ̌c", "pɔ̌c"),
    ("r̀lɛ̀ɲ", "r̀lɔ̀ɲ"),
    ("îɾcɛ́cɛ̀c", "îɾcɔ́cɔ̀c"),
    ("ɜ̌dɛ̀ŋnàt̪", "ɔ̌dɔ̀ŋnɔ̀t̪"),
    ("vɛ̀ð-ɛ̀t̪", "vɔ̀ð-ɔ̀t̪"),
    ("vɛ̀ð-ìt̪", "vɛ̀ð-ìt̪"), # /i/ blocks harmony
    ("kə̀-mɛ̀ð-ìt̪", "kə̀-mɛ̀ð-ìt̪"), # /i/ blocks harmony
])
def test_rounding_harmony(unround_str,round_str):
    lattice=rewrite.rewrite_lattice(fst(unround_str), ROUNDING_HARMONY)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==round_str

@pytest.mark.parametrize("uncoalesced,coalesced", [
    ("káɔ̀", "kɔ̀"),
    ("là-ípɛ̀", "l-ɛ́pɛ̀"),
    ("l-ɔ̀-ípɛ̀", "l-ɛ́pɛ̀"),
    ("ŋgɔ́-ìð", "ŋg-ɛ̀ð"),
    ("m-ɔ́-èɲà", "m-èɲà"),
])
def test_vowel_coalescence(uncoalesced,coalesced):
    lattice=rewrite.rewrite_lattice(fst(uncoalesced), VOWEL_COALESCENCE_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==coalesced

@pytest.mark.parametrize("pre_hts,w_hts", [
    ("àpɾí jìcə̀lò", "àpɾí jícə̀lò"),
    ("kə̀və̀lɛ̀ðɔ́ ðàŋàlà", "kə̀və̀lɛ̀ðɔ́ ðáŋàlà"),
    ("jǎ ŋɔ̀mɔ̀", "jǎ ŋɔ́mɔ̀"),
])
def test_h_spread(pre_hts, w_hts):
    lattice=rewrite.rewrite_lattice(fst(pre_hts), H_SPREAD_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==w_hts

@pytest.mark.parametrize("fall_tone_str,blocked_h_str", [
    ("kápɾî jícə̀lò", "kápɾî jìcə̀lò"),
    ("ŋg-éɲâ və́lɛ̀ð-ɛ̀", "ŋg-éɲâ və̀lɛ̀ð-ɛ̀"),
    ("j-à-ŋâ mɛ́ð-ɛ̀", "j-à-ŋâ mɛ̀ð-ɛ̀"),
])
def test_fall_blocks_h(fall_tone_str, blocked_h_str):
    lattice=rewrite.rewrite_lattice(fst(fall_tone_str), FALL_BLOCKS_H_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==blocked_h_str

@pytest.mark.parametrize("unround_str,round_str,do_round", [
    ("tɔ̀t-át̪", "tɔ̀t-ɔ́t̪", True),
    ("tɔ̀t-áp", "tɔ̀t-ɔ́p", False),
    ("kɔ́t̪-àt̪", "kɔ́t̪-ɔ̀t̪", True),
    ("ɔ̀d-ɛ́t̪", "ɔ̀d-ɔ́t̪", False),
    ("pát̪-át̪", "pát̪-ɔ́t̪", False),
])
def test_locative_rounding(unround_str,round_str,do_round):
    lattice=rewrite.rewrite_lattice(fst(unround_str), LOCATIVE_ROUNDING_RULE)
    strings = get_lattice_strs(lattice)
    if do_round:
        assert len(strings)==2
        assert round_str in strings
        assert unround_str in strings
    else:
        assert len(strings)==1
        assert strings[0]==unround_str

@pytest.mark.parametrize("orig_str,lefth_str", [
    ("àpɾí", "ápɾí"),
    ("ùnɛ́-ɾɛ́", "únɛ́-ɾɛ́"),
    ("k-á-və̀lɛ̀ð-ɔ́", "k-á-və̀lɛ̀ð-ɔ́"),
    ("p-ɔ̌", "p-ɔ́"),
])
def test_lefth_rule(orig_str,lefth_str):
    lattice=rewrite.rewrite_lattice(fst(orig_str), LEFT_H_RULE)
    strings = get_lattice_strs(lattice)
    assert len(strings)==1
    assert strings[0]==lefth_str

@pytest.mark.parametrize("orig_str,fl_str", [
    ("àpɾí", "àpɾì"),
    ("ùnɛ́-ɾɛ́", "ùnɛ̀-ɾɛ̀"),
    ("k-á-və̀lɛ̀ð-ɔ́", "k-á-və̀lɛ̀ð-ɔ̀"),
    ("p-ɔ̌", "p-ɔ̀"),
    ("p-ɛ́", "p-ɛ̂"),
])
def test_final_lowering(orig_str,fl_str):
    lattice_nonfinal=rewrite.rewrite_lattice(fst(orig_str), FINAL_LOWERING_RULE)
    strings_nonfinal = get_lattice_strs(lattice_nonfinal, strip_eos=False)
    assert len(strings_nonfinal)==1
    assert strings_nonfinal[0]==orig_str

    lattice_final =rewrite.rewrite_lattice(fst(orig_str+EOS_STR), FINAL_LOWERING_RULE)
    strings_final = get_lattice_strs(lattice_final, strip_eos=False)
    assert len(strings_final)==1
    assert strings_final[0]==fl_str+EOS_STR

@pytest.mark.parametrize("orig_str,expected_str", [
    ("àpɾí", "ápɾì"),
    ("ùnɛ́-ɾɛ́", "únɛ̀-ɾɛ̀"),
    ("k-á-və̀lɛ̀ð-ɔ́", "k-á-və̀lɛ̀ð-ɔ̀"),
    ("p-ɔ̌", "p-ɔ̂"),
    ("p-ɛ́", "p-ɛ̂"),
])
def test_final_lowering_and_lefth(orig_str, expected_str):
    lattice=rewrite.rewrite_lattice(fst(orig_str+EOS_STR), FINAL_LOWERING_RULE@LEFT_H_RULE)
    strings = get_lattice_strs(lattice, strip_eos=False)
    assert len(strings)==1
    assert strings[0]==expected_str+EOS_STR