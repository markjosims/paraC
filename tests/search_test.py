import pynini
from src.search import *

vowel = pynini.union(*"aeiouə")
consonant = pynini.union(*"ptk")
substitutions = [
    (vowel, "ə", 0.5),
]
insertions = [
    ("ə", 0.5),
]
deletions = [
    ("ə", 0.5),
    ("t", 0.5),
]
lexicon = [
    "ta",
    "ka",
    "ko",
    "patə",
]

def test_edit_factors():
    left_factor, right_factor = get_edit_factors(
        insertions=insertions,
        substitutions=substitutions,
        deletions=deletions
    )
    query = "tə"
    target = "ta"
    output_fst = (query@left_factor)@(right_factor@target)
    assert output_fst.string() == target