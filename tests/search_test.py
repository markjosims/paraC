import pynini
from pynini.lib import rewrite
from src.search import *
import pytest
from src.fst_helpers import *
from src.phonology import V, SIGMA
from src.lexicon import (
    get_gold_nouns,
    get_gold_verbs,
    get_gold_uninflected_words,
    get_gold_adjectives,
)
import math

substitutions = [
    ("ə", V-fst("ə"), 0.5),
    ("p", "k", 0.9),
]
insertions = [
    ("ɾ", 0.5),
]
deletions = [
    ("ə", 0.5),
    ("t", 0.5),
]
lexicon = [
    "ta",
    "ka",
    "ɾa",
    "ko",
    "patə",
    "pə",
]

def test_edit_factors():
    left_factor, right_factor = get_edit_factors(
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=SIGMA,
        bound=10,
    )
    query = "tə"
    target = "ta"
    output_fst = (fst(query)@left_factor)@(right_factor@fst(target))
    string = decode_fst_string(pynini.shortestpath(output_fst))
    assert string == target

def test_searchable_lexicon():
    left_factor, searchable_lexicon = get_searchable_lexicon(
        lexicon=lexicon,
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=SIGMA,
        bound=10,
    )
    query = "po"
    output_fst = (fst(query)@left_factor)@searchable_lexicon
    strings = decode_fst_lattice(output_fst)
    strings = set(strings)
    assert strings == set(lexicon)

    best_string = decode_fst_string(pynini.shortestpath(output_fst))
    
    # p>k preferred over other consonant changes
    assert best_string == "ko"

@pytest.mark.parametrize("query,top_string,expected_weight,top_n_strings", [
    ("tka", "ka", 0.5, ["ta", "ka"]),      # cheaper to delete /t/ than /k/
    ("a", "ɾa", 0.5,  ["ɾa", "ka", "ta"]),  # cheaper to insert /ɾ/ than /k/ or /t/
    ("tə", "ta", 0.5, ["ta", "pə"]),       # cheaper to substitute a>ə than t>p
])
def test_edit_weight(query, top_string, expected_weight, top_n_strings):
    left_factor, searchable_lexicon = get_searchable_lexicon(
        lexicon=lexicon,
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=SIGMA,
        bound=10,
    )
    output_fst = (fst(query)@left_factor)@searchable_lexicon
    predicted_top_string = decode_fst_string(pynini.shortestpath(output_fst))
    assert predicted_top_string == top_string

    predicted_weight = get_min_path_weight(output_fst)
    assert predicted_weight == expected_weight

    predicted_top_n_strings = decode_fst_lattice(fst(query)@left_factor@searchable_lexicon, nshortest=len(top_n_strings))
    assert set(predicted_top_n_strings) == set(top_n_strings)

@pytest.mark.parametrize("string_map_list,nbest", [
    ([("ðoo", "bar", 0.5), ("bar", "bað", 0.3)], 1),
    ([("ðoo", "bar", 1.0), ("bar", "bað", 0.3), ("bað", "baðð", 0.5)], 2),
    ([("ðoo", "bar", 0.1), ("bar", "bað", 0.3), ("bað", "baðð", 0.5), ("bað", "barð", 1.0)], 3),
])
def test_nbest_strs_and_weights(string_map_list: list, nbest: int):
    string_map_list.sort(key=lambda t:t[-1])
    nbest_gold = string_map_list[:nbest]
    string_map_lattice = pynini.union(*[fst(*triple) for triple in string_map_list])
    nbest_predicted = get_nbest_strs_and_weights(string_map_lattice, nbest)
    
    for gold_triple, predicted_triple in zip(nbest_gold, nbest_predicted):
        gold_intab, gold_outtab, gold_weight = gold_triple
        predicted_intab, predicted_outtab, predicted_weight = predicted_triple

        assert gold_intab == predicted_intab
        assert gold_outtab == predicted_outtab
        assert math.isclose(gold_weight, predicted_weight, rel_tol=0.001)

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_search_verb_form(gold_verb):
    gold_form = gold_verb['form']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_verb['fuzzy_form']
    gold_fv = gold_verb['fv']
    num_hits = 10
    
    expected_verb_type = 'stem'
    if ' ' in gold_form:
        expected_verb_type = 'stem_and_aux'

    hits = search_verb_form(fuzzy_form, num_hits=num_hits, return_parse=False, expected_verb_type=expected_verb_type)

    # assert len(hits) == num_hits # verb forms can get long
    # so make the tests less strict
    assert len(hits) >= 1
    hit_objs = [hit[0] for hit in hits]
    top_forms = [hit_obj['form'] for hit_obj in hit_objs]
    top_fvs = [hit_obj['fv'] for hit_obj in hit_objs]
    assert gold_form in top_forms
    assert gold_fv in top_fvs

@pytest.mark.parametrize("gold_noun", get_gold_nouns())
def test_search_noun_form(gold_noun):
    gold_form = gold_noun['gold_noun']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_noun['fuzzy_noun']
    num_hits = 3
    
    hits = search_noun_form(fuzzy_form, num_hits=num_hits, return_parse=False)

    assert len(hits) == num_hits
    top_form = hits[0][0]['form']
    assert top_form == gold_form

@pytest.mark.parametrize("uninflected_word", get_gold_uninflected_words())
def test_search_uninflected_word_form(uninflected_word):
    gold_form = uninflected_word['word']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = uninflected_word['fuzzy_form']
    num_hits = 1

    hits = search_uninflected_word(fuzzy_form, num_hits=num_hits, return_parse=False)

    assert len(hits) == num_hits
    top_form = hits[0][0]['form']
    assert top_form == gold_form

@pytest.mark.parametrize("gold_adjective", get_gold_adjectives())
def test_search_adjective_form(gold_adjective):
    gold_form = gold_adjective['form']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_adjective['fuzzy_form']
    num_hits = 3
    
    hits = search_adjective_form(fuzzy_form, num_hits=num_hits, return_parse=False)

    assert len(hits) == num_hits
    top_form = hits[0][0]['form']
    assert top_form == gold_form

@pytest.mark.parametrize("unhyphenated_str,hyphenated_str", [
    ("katə", "ka-tə"),
    ("katəɾa", "ka-tə-ɾa"),
    ("katəɾapə", "ka-tə-ɾa-pə")
])
def test_search_for_hyphenated_form_simple(unhyphenated_str, hyphenated_str):
    lexicon = fst(hyphenated_str)
    hits = search_for_hyphenated_form(unhyphenated_str, lattice=lexicon)
    assert len(hits) > 0
    top_form, _ = hits[0]
    assert top_form == hyphenated_str