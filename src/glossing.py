import pynini
from pynini.lib import pynutil
import string
from src.phonology import SIGMA
from typing import *
import re

DIGIT = pynini.union(*string.digits)
HOMOPHONE_TAG = "("+DIGIT+")"
SIGMASTAR_W_TAG = pynini.union(SIGMA, DIGIT, "(", ")").closure().optimize()
REMOVE_HOMOPHONE_TAG = pynini.cdrewrite(
    pynutil.delete(HOMOPHONE_TAG),
    '',
    '',
    sigma_star=SIGMASTAR_W_TAG,
).optimize()

def feature_str_to_dict(feature_str: str) -> Dict[str, str]:
    """
    Parses a feature string of form "stem[feature=value][feature=value]..." into a dict
    of shape {"stem": stem, "feature": value, ...}
    """
    items = feature_str.split(sep='[')
    stem = items[0]
    feature_dict = {"stem": stem}
    for item in items[1:]:
        item = item.removesuffix(']')
        feature, value = item.split('=')
        feature_dict[feature]=value
    return feature_dict
    
        