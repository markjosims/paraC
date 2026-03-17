import pytest
from src.fst_helpers import *
from src.fst_registry import (
    load_config,
    build_inventory_registry,
    compile_pattern_str,
    compile_patterns,
    compile_rules,
    compile_marker_dict,
    compile_feature_markers,
    decode_fst_string,
)
from src.fst_helpers import fst, get_lattice_strs
from src.lexicon.phonology import SIGMASTAR
import pynini
from pynini.lib import rewrite


def _accepts(fsa: pynini.Fst, string: str) -> bool:
    """Return True if the FSA (built with TIRA_SYMBOL_TABLE) accepts string."""
    try:
        src_fsa = fst(string)
        lattice = pynini.compose(src_fsa, fsa)
        return lattice.num_states() > 0
    except Exception:
        return False


def _transduces(fst_: pynini.Fst, src: str, tgt: str) -> bool:
    """Return True if fst_ maps src to tgt (both decoded as IPA strings)."""
    try:
        src_fsa = fst(src)
        lattice = pynini.compose(src_fsa, fst_)
        outputs = get_lattice_strs(lattice)
        return tgt in outputs
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Section 1: Config loading
# ---------------------------------------------------------------------------

def test_load_config_inventory():
    config = load_config("config/inventory/segments.yaml")
    assert config["kind"] == "Inventory"
    assert "data" in config


def test_load_config_rules():
    config = load_config("config/rules/tone_association.yaml")
    assert config["kind"] == "Rules"
    assert "add_tbus" in config["rules"]


def test_load_config_markers():
    config = load_config("config/markers/class_prefixes.yaml")
    assert config["kind"] == "FeatureMarkers"
    assert config["feature"] == "class"


# ---------------------------------------------------------------------------
# Section 2: Inventory registry
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def segments_registry():
    config = load_config("config/inventory/segments.yaml")
    return build_inventory_registry(config)


@pytest.fixture(scope="module")
def full_registry():
    seg_config = load_config("config/inventory/segments.yaml")
    registry = build_inventory_registry(seg_config)
    tone_config = load_config("config/inventory/tones.yaml")
    registry.update(build_inventory_registry(tone_config))
    return registry


def test_registry_has_vowel_class(segments_registry):
    assert "<V>" in segments_registry


def test_registry_has_consonant_class(segments_registry):
    assert "<C>" in segments_registry


def test_registry_has_mid_vowels(segments_registry):
    assert "<V_MID>" in segments_registry


def test_registry_vowels_accept_vowels(segments_registry):
    vowel_fsa = segments_registry["<V>"]
    for v in ["i", "a", "ɛ", "u", "o"]:
        assert _accepts(vowel_fsa, v), f"<V> should accept '{v}'"


def test_registry_vowels_reject_consonants(segments_registry):
    vowel_fsa = segments_registry["<V>"]
    for c in ["p", "t", "k", "n"]:
        assert not _accepts(vowel_fsa, c), f"<V> should not accept '{c}'"


def test_registry_consonant_accepts_consonants(segments_registry):
    cons_fsa = segments_registry["<C>"]
    for c in ["p", "t", "k", "n", "l", "r"]:
        assert _accepts(cons_fsa, c), f"<C> should accept '{c}'"


def test_registry_mid_vowels(segments_registry):
    mid_fsa = segments_registry["<V_MID>"]
    for v in ["e", "ɛ", "o", "ɔ", "ə", "ɜ"]:
        assert _accepts(mid_fsa, v), f"<V_MID> should accept '{v}'"
    # High vowels not in mid
    assert not _accepts(mid_fsa, "i")
    assert not _accepts(mid_fsa, "u")


def test_registry_special_symbols(segments_registry):
    assert "[BOS]" in segments_registry
    assert "[EOS]" in segments_registry
    assert "<Sigma>" in segments_registry
    assert "<Empty>" in segments_registry
    assert "-" in segments_registry


def test_registry_tbu_from_tones():
    tone_config = load_config("config/inventory/tones.yaml")
    registry = build_inventory_registry(tone_config)
    assert "<T>" in registry
    assert "<H>" in registry
    assert "<L>" in registry


# ---------------------------------------------------------------------------
# Section 3: Pattern string compiler
# ---------------------------------------------------------------------------

def test_compile_simple_vowel_ref(segments_registry):
    fsa = compile_pattern_str("<V>", segments_registry)
    assert _accepts(fsa, "a")
    assert not _accepts(fsa, "p")


def test_compile_alternation(segments_registry):
    fsa = compile_pattern_str("(<V>|<R>|<N>)", segments_registry)
    # vowels
    assert _accepts(fsa, "a")
    # resonants (<R>: l, r, ɾ, ɽ, j, w)
    assert _accepts(fsa, "l")
    assert _accepts(fsa, "r")
    # nasals
    assert _accepts(fsa, "n")
    assert _accepts(fsa, "m")
    # stops should not match
    assert not _accepts(fsa, "p")
    assert not _accepts(fsa, "k")


def test_compile_optional(segments_registry):
    fsa = compile_pattern_str("<V>-?", segments_registry)
    assert _accepts(fsa, "a")
    assert _accepts(fsa, "a-")
    assert not _accepts(fsa, "-")


def test_compile_kleene_star(segments_registry):
    fsa = compile_pattern_str("<V>*", segments_registry)
    assert _accepts(fsa, "")
    assert _accepts(fsa, "a")
    assert _accepts(fsa, "ai")


def test_compile_kleene_plus(segments_registry):
    fsa = compile_pattern_str("<V>+", segments_registry)
    assert not _accepts(fsa, "")
    assert _accepts(fsa, "a")
    assert _accepts(fsa, "ai")


def test_compile_literal(segments_registry):
    fsa = compile_pattern_str("a", segments_registry)
    assert _accepts(fsa, "a")
    assert not _accepts(fsa, "b")


def test_compile_concatenation(segments_registry):
    fsa = compile_pattern_str("<C><V>", segments_registry)
    assert _accepts(fsa, "pa")
    assert _accepts(fsa, "la")
    assert not _accepts(fsa, "aa")
    assert not _accepts(fsa, "pp")


def test_compile_empty_pattern(segments_registry):
    fsa = compile_pattern_str("", segments_registry)
    assert _accepts(fsa, "")
    assert not _accepts(fsa, "a")


# ---------------------------------------------------------------------------
# Section 4: Rule compiler
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vowel_coalescence_rules(full_registry):
    config = load_config("config/rules/vowel_coalescence.yaml")
    return compile_rules(config, full_registry)


@pytest.fixture(scope="module")
def tone_association_rules(full_registry):
    config = load_config("config/rules/tone_association.yaml")
    return compile_rules(config, full_registry)


def test_rules_compiled(vowel_coalescence_rules):
    assert "coalesce_before_i" in vowel_coalescence_rules
    assert "delete_vowel_in_hiatus" in vowel_coalescence_rules
    assert "resolve_hiatus" in vowel_coalescence_rules


def test_coalesce_before_i(vowel_coalescence_rules):
    rule = vowel_coalescence_rules["coalesce_before_i"]
    # mid vowel + i -> ɛ
    assert _transduces(rule, "a-i", "ɛ"), "a-i should coalesce to ɛ"
    assert _transduces(rule, "ɛ-i", "ɛ"), "ɛ-i should coalesce to ɛ"


def test_delete_vowel_in_hiatus(vowel_coalescence_rules):
    rule = vowel_coalescence_rules["delete_vowel_in_hiatus"]
    # vowel before another vowel is deleted
    assert _transduces(rule, "a-a", "a"), "a-a should delete first vowel to give a"


def test_chain_rule_resolve_hiatus(vowel_coalescence_rules):
    rule = vowel_coalescence_rules["resolve_hiatus"]
    # a-i -> ɛ (coalesce) takes priority over delete (because delete runs first
    # but coalesce refines)
    # delete_vowel_in_hiatus: a-a -> a
    assert _transduces(rule, "a-a", "a"), "resolve_hiatus: a-a -> a"


def test_tone_association_rules_compiled(tone_association_rules):
    assert "add_tbus" in tone_association_rules
    assert "remove_tbus_from_onset_c" in tone_association_rules
    assert "remove_tbus_from_coda_c" in tone_association_rules


def test_add_tbus_inserts_tbu_after_vowel(tone_association_rules):
    from src.constants import TONE_SLOT_STR
    rule = tone_association_rules["add_tbus"]
    src_fsa = fst("a")
    lattice = pynini.compose(src_fsa, rule)
    outputs = get_lattice_strs(lattice)
    # get_lattice_strs returns [TBU] as a literal string (not decoded to empty)
    assert "a" + TONE_SLOT_STR in outputs, \
        f"Expected 'a[TBU]' in outputs, got: {outputs}"


# ---------------------------------------------------------------------------
# Section 5: Marker compiler
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def class_prefix_fsts(full_registry):
    config = load_config("config/markers/class_prefixes.yaml")
    return compile_feature_markers(config, full_registry, rules={})


def test_class_prefix_markers_compiled(class_prefix_fsts):
    assert "l" in class_prefix_fsts
    assert "g" in class_prefix_fsts
    assert "r" in class_prefix_fsts


def test_class_prefix_l_replaces_cl(class_prefix_fsts):
    from src.constants import CLASS_PLACEHOLDER
    fsts_l = class_prefix_fsts["l"]
    assert len(fsts_l) >= 1
    rule = fsts_l[0]
    # Replace <CL> with l
    assert _transduces(rule, CLASS_PLACEHOLDER, "l"), \
        f"l class prefix should replace <CL> with 'l'"


def test_class_prefix_n_replaces_cl(class_prefix_fsts):
    from src.constants import CLASS_PLACEHOLDER
    fsts_n = class_prefix_fsts["n"]
    rule = fsts_n[0]
    assert _transduces(rule, CLASS_PLACEHOLDER, "n"), \
        f"n class prefix should replace <CL> with 'n'"


def test_null_marker_is_identity():
    identity = compile_marker_dict(None, {}, {})
    # Identity passes through any string
    assert _transduces(identity, "ap", "ap")
    assert _transduces(identity, "ta", "ta")


# ---------------------------------------------------------------------------
# Section 6: Decoding
# ---------------------------------------------------------------------------

def test_decode_fst_string_basic():
    # encode then decode should round-trip for simple strings
    original = "apa"
    encoded = encode_fst_string(original)
    decoded = decode_fst_string(encoded)
    assert decoded == original, f"Expected '{original}' but got '{decoded}'"


def test_decode_fst_string_tone_symbols():
    from src.constants import HIGH_TONE, HIGH_TONE_SYMBOL
    # A string with the tone symbol should decode to the diacritic
    encoded = encode_fst_string("a" + HIGH_TONE_SYMBOL)
    decoded = decode_fst_string(encoded)
    assert HIGH_TONE in decoded, f"Expected high tone diacritic in '{decoded}'"


def test_decode_strips_tbu():
    from src.constants import TONE_SLOT_STR
    encoded = encode_fst_string("a" + TONE_SLOT_STR)
    decoded = decode_fst_string(encoded)
    assert TONE_SLOT_STR not in decoded
    assert "a" in decoded


def test_decode_word_boundary_to_space():
    from src.constants import WORD_BOUNDARY_STR
    encoded = encode_fst_string("a" + WORD_BOUNDARY_STR + "b")
    decoded = decode_fst_string(encoded)
    assert " " in decoded
