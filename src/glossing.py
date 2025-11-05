import pynini
from pynini.lib import pynutil
import string
from src.phonology import SIGMA
from src.fst_helpers import *
from typing import *
import re

DIGIT = fst(list(string.digits))
HOMOPHONE_TAG = fst("(")+DIGIT+fst(")")
SIGMASTAR_W_TAG = fst([SIGMA, DIGIT, fst("("), fst(")")]).closure().optimize()
REMOVE_HOMOPHONE_TAG = pynini.cdrewrite(
    delete_fst(HOMOPHONE_TAG),
    fst(),
    fst(),
    sigma_star=SIGMASTAR_W_TAG,
).optimize()

def feature_str_to_dict(feature_str: str, decode_form: bool=True) -> Dict[str, str]:
    """
    Parses a feature string of form "form[feature=value][feature=value]..." into a dict
    of shape {"form": form, "feature": value, ...}.
    If `decode_form` is True, call `decode_byte_str` on form.
    """
    raise DeprecationWarning
    
        