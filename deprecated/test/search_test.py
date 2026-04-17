import pynini
from pynini.lib import rewrite
from src.search import *
import pytest
from src.fst_helpers import *
from src.lexicon.phonology import V, SIGMA
from src.lexicon.lexicon import load_test_case_data
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
    string = get_lattice_strs(output_fst).pop(0)
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
    strings = get_lattice_strs(output_fst)
    assert set(strings) == set(lexicon)

    best_string = get_lattice_strs(output_fst).pop(0)
    
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
    predicted_top_string = get_lattice_strs(output_fst).pop(0)
    assert predicted_top_string == top_string

    predicted_weight = get_min_path_weight(output_fst)
    assert predicted_weight == expected_weight

    predicted_top_n_strings = get_lattice_strs(fst(query)@left_factor@searchable_lexicon, nshortest=len(top_n_strings))
    assert set(predicted_top_n_strings) == set(top_n_strings)

@pytest.mark.parametrize("gold_verb", load_test_case_data('gold_verbs'))
def test_search_verb_form(gold_verb):
    gold_form = gold_verb['form']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_verb['fuzzy_form']
    gold_fv = gold_verb['fv']
    num_hits = 10
    
    hits = search_word(fuzzy_form, num_hits=num_hits)

    # assert len(hits) >= 1 # verb forms can get long
    # so make the tests less strict
    assert len(hits) >= 1
    top_forms = [hit['form'] for hit in hits]
    top_fvs = [hit['fv'] for hit in hits]
    assert gold_form in top_forms
    assert gold_fv in top_fvs

@pytest.mark.parametrize("gold_verb", load_test_case_data('gold_verbs_derived'))
def test_search_derived_verb(gold_verb):
    gold_form = gold_verb['form']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_verb['fuzzy_form']
    num_hits = 10

    hits = search_word(
        fuzzy_form,
        num_hits=num_hits,
    )

    assert len(hits) >= 1
    top_forms = [hit['form'] for hit in hits]
    assert gold_form in top_forms

@pytest.mark.parametrize("gold_noun", load_test_case_data('gold_nouns'))
def test_search_noun_form(gold_noun):
    gold_form = gold_noun['gold_noun']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_noun['fuzzy_noun']
    num_hits = 3
    
    hits = search_word(fuzzy_form, num_hits=num_hits)

    assert len(hits) >= 1
    top_form = hits[0]['form']
    assert top_form == gold_form

@pytest.mark.parametrize("uninflected_word", load_test_case_data('gold_uninflected_words'))
def test_search_uninflected_word_form(uninflected_word):
    gold_form = uninflected_word['root']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = uninflected_word['fuzzy_form']
    num_hits = 1

    hits = search_word(fuzzy_form, num_hits=num_hits)

    assert len(hits) >= 1
    top_form = hits[0]['form']
    assert top_form == gold_form

@pytest.mark.parametrize("gold_adjective", load_test_case_data('gold_adjectives'))
def test_search_adjective_form(gold_adjective):
    gold_form = gold_adjective['form']
    gold_form = gold_form.replace('-', '')
    fuzzy_form = gold_adjective['fuzzy_form']
    num_hits = 3
    
    hits = search_word(fuzzy_form, num_hits=num_hits)

    top_form = hits[0]['form']
    assert top_form == gold_form

@pytest.mark.parametrize("unhyphenated_str,hyphenated_str", [
    ("katə", "ka-tə"),
    ("katəɾa", "ka-tə-ɾa"),
    ("katəɾapə", "ka-tə-ɾa-pə")
])
def test_search_for_hyphenated_form_simple(unhyphenated_str, hyphenated_str):
    lexicon = fst(hyphenated_str)
    hits = search_for_hyphenated_form(unhyphenated_str, lattice=lexicon)
    top_form, _ = hits[0]
    assert top_form == hyphenated_str