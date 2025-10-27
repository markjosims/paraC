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
TONE_SLOT = fst(TONE_SLOT_STR)
TONE_PLACEHOLDER = fst(TONE_PLACEHOLDER_STR)
TONE_SLOT_OR_PLACEHOLDER = TONE_SLOT|TONE_PLACEHOLDER
SIGMA = C|V|T|BOUNDARY|TONE_SLOT_OR_PLACEHOLDER
SIGMA_EXCEPT_PLACEHOLDER = C|V|T|BOUNDARY
SIGMASTAR = pynini.closure(SIGMA).optimize()
SIGMASTAR_EXCEPT_PLACEHOLDER = pynini.closure(SIGMA_EXCEPT_PLACEHOLDER).optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# ---------------------- #
# phonological processes #
# ---------------------- #

ADD_TBU_MARKER = pynini.cdrewrite(
    tau=insert_fst(TONE_SLOT_STR),
    l=TBU,
    r=fst(''),
    sigma_star=SIGMASTAR
)
REMOVE_TBU_MARKER_AFTER_ONSET_C = pynini.cdrewrite(
    tau=delete_fst(TONE_SLOT_STR),
    l=C@TBU,
    r=V,
    sigma_star=SIGMASTAR,
)
REMOVE_TBU_MARKER_AFTER_CODA_C = pynini.cdrewrite(
    tau=delete_fst(TONE_SLOT_STR),
    l=TONE_SLOT+C@TBU,
    r=fst(),
    sigma_star=SIGMASTAR,
)
CLEAN_TBU_MARKERS = pynini.cdrewrite(
    tau=delete_fst(TONE_SLOT_STR),
    l=fst(),
    r=fst(),
    sigma_star=SIGMASTAR
)

PREPARE_TONE = ADD_TBU_MARKER@REMOVE_TBU_MARKER_AFTER_ONSET_C@REMOVE_TBU_MARKER_AFTER_CODA_C
FINALIZE_TONE = CLEAN_TBU_MARKERS
compose_tone = lambda tone_fst: PREPARE_TONE@tone_fst@FINALIZE_TONE

HTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + TONE_SLOT_OR_PLACEHOLDER + insert_fst(HIGH_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()
LTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + TONE_SLOT_OR_PLACEHOLDER + insert_fst(LOW_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()

HLSTAR = (HTONE_SYLL + pynini.closure(LTONE_SYLL)).optimize()
ALL_HIGH_TONE = pynini.closure(HTONE_SYLL).optimize()
ALL_LOW_TONE = pynini.closure(LTONE_SYLL).optimize()

HLSTAR_RULE = compose_tone(HLSTAR)
ALL_HIGH_TONE_RULE = compose_tone(ALL_HIGH_TONE)
ALL_LOW_TONE_RULE = compose_tone(ALL_LOW_TONE)

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete(fst("ə")+T.ques),
    l=fst(),
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

ROUNDING_HARMONY_TARGET = fst("ɛ") | fst("a") | fst("ɜ")
ROUNDING_HARMONY_TRIGGER = fst("ɔ")

ROUNDING_HARMONY = pynini.cdrewrite(
    tau=pynini.cross(ROUNDING_HARMONY_TARGET, ROUNDING_HARMONY_TRIGGER),
    l=fst(''),
    r=fst(''),
    sigma_star=SIGMASTAR,
).optimize()

ADD_PLACEHOLDER_TBU = pynini.cdrewrite(
    tau=insert_fst(TONE_PLACEHOLDER_STR),
    l=C,
    r='[EOS]',
    sigma_star=SIGMASTAR,
).optimize()

FLOAT_TONE_RULE = SIGMASTAR.copy()
for tone in TIRA_TONE_DIACS:
    dock_floating_tone = pynini.cdrewrite(
        tau=insert_fst(tone),
        l=TONE_PLACEHOLDER+tone+pynini.closure(C)+TBU,
        r=fst(),
        sigma_star=SIGMASTAR
    )
    delete_floating_tone = pynini.cdrewrite(
        tau=delete_fst(TONE_PLACEHOLDER_STR+tone),
        l=fst(),
        r=fst(),
        sigma_star=SIGMASTAR
    )
    rule = dock_floating_tone@delete_floating_tone
    FLOAT_TONE_RULE = FLOAT_TONE_RULE@rule
FLOAT_TONE_RULE = FLOAT_TONE_RULE.optimize()

COMBINE_TONES = pynini.union(*[
    fst(LOW_TONE+HIGH_TONE, RISE_TONE),
    fst(HIGH_TONE+LOW_TONE, FALL_TONE),
    fst(HIGH_TONE+HIGH_TONE, HIGH_TONE),
    fst(LOW_TONE+LOW_TONE, LOW_TONE),
])
COMBINE_TONES_RULE = pynini.cdrewrite(
    tau=COMBINE_TONES,
    l=fst(),
    r=fst(),
    sigma_star=SIGMASTAR,
)

# ---------- #
# edit costs #
# ---------- #

REDUCED_EDIT_COST = 0.2

INSERTION_COSTS = [
    ('ə', REDUCED_EDIT_COST),
    (V, REDUCED_EDIT_COST),
    (T, REDUCED_EDIT_COST),
]
DELETION_COSTS = [
    ('ə', REDUCED_EDIT_COST),
    (V, REDUCED_EDIT_COST),
    (T, REDUCED_EDIT_COST),
]
SUBSTITUTION_COSTS = [
    ('ə', V, REDUCED_EDIT_COST),      # underlying vowel reduced to schwa
    ('ɛ', 'ə', REDUCED_EDIT_COST),    # underlying schwa fronted to /ɛ/

    ('ɜ', 'ɛ', REDUCED_EDIT_COST),    # ɜ~ɛ interchange
    ('ɛ', 'ɜ', REDUCED_EDIT_COST),

    ('ɜ', 'a', REDUCED_EDIT_COST),    # ɜ~a interchange
    ('a', 'ɜ', REDUCED_EDIT_COST),

    ('ɜ', 'ə', REDUCED_EDIT_COST),    # ɜ~ə interchange
    ('ə', 'ɜ', REDUCED_EDIT_COST),

    ('ɛ', 'e', REDUCED_EDIT_COST),    # ɛ~e interchange
    ('e', 'ɛ', REDUCED_EDIT_COST),

    ('ɪ', 'e', REDUCED_EDIT_COST),    # ɪ~ɛ interchange
    ('e', 'ɪ', REDUCED_EDIT_COST),

    ('o', 'u', REDUCED_EDIT_COST),    # o~u interchange
    ('u', 'o', REDUCED_EDIT_COST),

    ('ɔ', 'o', REDUCED_EDIT_COST),    # o~ɔ interchange
    ('o', 'ɔ', REDUCED_EDIT_COST),

    ('ʊ', 'o', REDUCED_EDIT_COST),    # o~ʊ interchange
    ('o', 'ʊ', REDUCED_EDIT_COST),

    ('d', DENTAL_D, REDUCED_EDIT_COST),   # dental stop written as alveolar
    ('t', DENTAL_T, REDUCED_EDIT_COST),

    ('g', 'k', REDUCED_EDIT_COST),        # g~k interchange
    ('k', 'g', REDUCED_EDIT_COST),

    ('r', 'ɾ', REDUCED_EDIT_COST),        # tap written as trill
]
for intab_tone in TIRA_TONE_DIACS:
    for outtab_tone in TIRA_TONE_DIACS:
        if intab_tone == outtab_tone:
            continue
        SUBSTITUTION_COSTS.append((intab_tone, outtab_tone, REDUCED_EDIT_COST))

# ------------ #
# search rules #
# ------------ #

INSERT_HYPHEN_RULE = pynini.cdrewrite(
    tau=insert_fst('-').ques,
    l=SIGMA,
    r=SIGMA,
    sigma_star=SIGMASTAR,
)
INSERT_HYPHEN_RULE = INSERT_HYPHEN_RULE.optimize()