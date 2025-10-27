from src.glossing import *

def test_feature_str_to_dict():
    feature_str = "stem[case=nom][tense=never][deixis=nowhere][number=infinity]"
    feature_dict = feature_str_to_dict(feature_str, decode_form=False)
    assert feature_dict == {
        "form": "stem",
        "case": "nom",
        "tense": "never",
        "deixis": "nowhere",
        "number": "infinity",
    }