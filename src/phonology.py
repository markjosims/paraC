"""
Declare FSAs for phoneme inventory and phonological classes in Tira.
"""

import pynini
from pynini.lib import paradigms, pynutil, rewrite
from typing import *
from src.constants import *
from src.fst_helpers import (
    fst, insert_fst, delete_fst,
)

BOUNDARY = fst(BOUNDARY_STR)
C = fst(TIRA_CONSONANTS)
V = fst(TIRA_VOWELS)
T = fst(TIRA_TONE_DIACS)
TBU = fst(TIRA_TBUS)
PLACEHOLDER_TBU = fst(PLACEHOLDER_TBU_STR)
SIGMA = C|V|T|BOUNDARY|PLACEHOLDER_TBU
SIGMA_EXCEPT_PLACEHOLDER = C|V|T|BOUNDARY
SIGMASTAR = pynini.closure(SIGMA).optimize()
SIGMASTAR_EXCEPT_PLACEHOLDER = pynini.closure(SIGMA_EXCEPT_PLACEHOLDER).optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# phonological processes

ADD_TBU_MARKER = pynini.cdrewrite(
    tau=insert_fst(PLACEHOLDER_TBU_STR),
    l=TBU,
    r=fst(''),
    sigma_star=SIGMASTAR
)
REMOVE_TBU_MARKER_AFTER_ONSET_C = pynini.cdrewrite(
    tau=delete_fst(PLACEHOLDER_TBU_STR),
    l=C@TBU,
    r=V,
    sigma_star=SIGMASTAR,
)
REMOVE_TBU_MARKER_AFTER_CODA_C = pynini.cdrewrite(
    tau=delete_fst(PLACEHOLDER_TBU_STR),
    l=PLACEHOLDER_TBU+C@TBU,
    r='',
    sigma_star=SIGMASTAR,
)
CLEAN_TBU_MARKERS = pynini.cdrewrite(
    tau=delete_fst(PLACEHOLDER_TBU_STR),
    l='',
    r='',
    sigma_star=SIGMASTAR
)

PREPARE_TONE = ADD_TBU_MARKER@REMOVE_TBU_MARKER_AFTER_ONSET_C@REMOVE_TBU_MARKER_AFTER_CODA_C
FINALIZE_TONE = CLEAN_TBU_MARKERS
compose_tone = lambda tone_fst: PREPARE_TONE@tone_fst@FINALIZE_TONE

HTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + insert_fst(HIGH_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()
LTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + insert_fst(LOW_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()

HLSTAR = (HTONE_SYLL + pynini.closure(LTONE_SYLL)).optimize()
ALL_HIGH_TONE = pynini.closure(HTONE_SYLL).optimize()
ALL_LOW_TONE = pynini.closure(LTONE_SYLL).optimize()

HLSTAR_RULE = compose_tone(HLSTAR)
ALL_HIGH_TONE_RULE = compose_tone(ALL_HIGH_TONE)
ALL_LOW_TONE_RULE = compose_tone(ALL_LOW_TONE)

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete(fst("ə")+T),
    l='',
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

ADD_PLACEHOLDER_TBU = pynini.cdrewrite(
    tau=insert_fst(PLACEHOLDER_TBU_STR),
    l=C.plus,
    r='[EOS]',
    sigma_star=SIGMASTAR,
).optimize()

FLOAT_TONE_RULE = SIGMASTAR.copy()
for tone in TIRA_TONE_DIACS:
    dock_floating_tone = pynini.cdrewrite(
        tau=insert_fst(tone),
        l=PLACEHOLDER_TBU+tone+pynini.closure(C)+TBU,
        r='',
        sigma_star=SIGMASTAR
    )
    delete_floating_tone = pynini.cdrewrite(
        tau=delete_fst(PLACEHOLDER_TBU_STR+tone),
        l='',
        r='',
        sigma_star=SIGMASTAR
    )
    rule = dock_floating_tone@delete_floating_tone
    FLOAT_TONE_RULE = FLOAT_TONE_RULE@rule
FLOAT_TONE_RULE = FLOAT_TONE_RULE.optimize()

COMBINE_TONES = pynini.string_map([
    (LOW_TONE+HIGH_TONE, RISE_TONE),
    (HIGH_TONE+LOW_TONE, FALL_TONE),
    (HIGH_TONE+HIGH_TONE, HIGH_TONE),
    (LOW_TONE+LOW_TONE, LOW_TONE),
])
COMBINE_TONES_RULE = pynini.cdrewrite(
    tau=COMBINE_TONES,
    l='',
    r='',
    sigma_star=SIGMASTAR,
)