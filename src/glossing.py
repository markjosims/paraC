import pynini
from pynini.lib import pynutil
import string
from src.phoneme_inventory import SIGMA

DIGIT = pynini.union(*string.digits)
HOMOPHONE_TAG = "("+DIGIT+")"
SIGMASTAR_W_TAG = pynini.union(SIGMA, DIGIT, "(", ")").closure().optimize()
REMOVE_HOMOPHONE_TAG = pynini.cdrewrite(
    pynutil.delete(HOMOPHONE_TAG),
    '',
    '',
    sigma_star=SIGMASTAR_W_TAG,
).optimize()