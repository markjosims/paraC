import pynini
from pynini.lib import rewrite
from src.search import *
import pytest
from src.fst_helpers import fst, get_decoded_strings
from src.phonology import V, SIGMA

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
    output_fst = (query@left_factor)@(right_factor@target)
    string = pynini.shortestpath(output_fst).string()
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
    output_fst = query@left_factor@searchable_lexicon
    strings = get_decoded_strings(output_fst)
    strings = set(strings)
    assert strings == set(lexicon)

    best_string = pynini.shortestpath(output_fst).string()
    
    # p>k preferred over other consonant changes
    assert best_string == "ko"

@pytest.mark.parametrize("query,top_string,top_n_strings", [
    ("tka", "ka", ["ta", "ka"]),      # cheaper to delete /t/ than /k/
    ("a", "ɾa", ["ɾa", "ka", "ta"]),  # cheaper to insert /ɾ/ than /k/ or /t/
    ("tə", "ta", ["ta", "pə"]),       # cheaper to substitute a>ə than t>p
])
def test_edit_weight(query, top_string, top_n_strings):
    left_factor, searchable_lexicon = get_searchable_lexicon(
        lexicon=lexicon,
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions,
        sigma=SIGMA,
        bound=10,
    )
    output_fst = query@left_factor@searchable_lexicon
    predicted_top_string = pynini.shortestpath(output_fst).string()
    assert predicted_top_string == top_string

    predicted_top_n_strings = rewrite.top_rewrites(query@left_factor, searchable_lexicon, nshortest=len(top_n_strings))
    assert set(predicted_top_n_strings) == set(top_n_strings)