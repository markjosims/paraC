import pynini
import pytest
from src.form_builders.form_helpers import build_wh_parser
from src.fst_helpers import fst, get_lattice_strs

@pytest.mark.parametrize(
    "feature_str,form_str,composed_input", [
        ("kɛc[class=unmarked]","kɛ́c-í",None),
        ("kɛc[class=g]","kə̀-kɛ́c-í","kə̀-kɛ́c-í-gɛ́"),
        ("mɛð[class=l]","lə̀-mɛ̀ð-ɔ́","lə̀-mɛ̀ð-ɔ́-lɛ́"),
        ("mɛð[class=unmarked]","mɛ̀ð-á",None),
    ]
)
def test_get_wh_suffix_fst(feature_str, form_str, composed_input):
    lemmatizer_fst = fst(form_str, feature_str)
    wh_lemmatizer = build_wh_parser(lemmatizer_fst)
    input_strs = get_lattice_strs(wh_lemmatizer, project_type='input')
    if composed_input is None:
        assert len(input_strs) == 0
    else:
        assert len(input_strs) == 1
        assert input_strs[0] == composed_input
