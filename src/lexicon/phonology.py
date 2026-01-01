"""
Declare FSAs for phoneme inventory and phonological classes in Tira.
"""

import pynini
from pynini.lib import paradigms, pynutil, rewrite
from typing import *
from src.constants import *
from src.fst_helpers import (
    fst, insert_fst, delete_fst, pynini,
)
import string

BOUNDARY = fst(BOUNDARY_STR)
WORD_BOUNDARY = fst(WORD_BOUNDARY_STR)
EOS = fst(EOS_STR)
C = fst(TIRA_CONSONANTS)
V = fst(TIRA_VOWELS)
T = fst(TIRA_TONE_DIACS)
H = fst(HIGH_TONE)
L = fst(LOW_TONE)
F = fst(FALL_TONE)
R = fst(RISE_TONE)
SEGMENT = C|V
TBU = fst(TIRA_TBUS)
TONE_SLOT = fst(TONE_SLOT_STR)
TONE_PLACEHOLDER = fst(TONE_PLACEHOLDER_STR)
TONE_SLOT_OR_PLACEHOLDER = TONE_SLOT|TONE_PLACEHOLDER
SIGMA = C|V|T|BOUNDARY|WORD_BOUNDARY|TONE_SLOT_OR_PLACEHOLDER|EOS
SIGMA_EXCEPT_PLACEHOLDER = C|V|T|BOUNDARY
SIGMASTAR = pynini.closure(SIGMA).optimize()
FEATURE = fst(ALL_FEATURE_STRS).optimize()
FEATURESTAR = pynini.closure(FEATURE).optimize()
DIGIT = fst(list(string.digits))
HOMOPHONE_TAG = fst("(")+DIGIT+fst(")")
SIGMASTAR_W_TAG = fst([SIGMA, DIGIT, fst("("), fst(")")]).closure().optimize()
SIGMASTAR_EXCEPT_PLACEHOLDER = pynini.closure(SIGMA_EXCEPT_PLACEHOLDER).optimize()
SIGMASTAR_W_SYMBOLS = pynini.closure(FEATURE|SIGMASTAR_W_TAG).optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# ---------------------- #
# phonological processes #
# ---------------------- #

REMOVE_DOUBLE_BOUNDARIES = pynini.cdrewrite(
    tau=delete_fst(BOUNDARY),
    l=fst(),
    r=BOUNDARY,
    sigma_star=SIGMASTAR,
).optimize()

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

DELETE_EOS = pynini.cdrewrite(
    tau=delete_fst(EOS_STR),
    l=fst(''),
    r=fst(''),
    sigma_star=SIGMASTAR,
).optimize()

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete(fst("ə")+T.ques),
    l=fst(),
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

ROUNDING_HARMONY_TARGET = fst("ɛ") | fst("a") | fst("ɜ")
ROUNDING_HARMONY_OUTPUT = fst("ɔ")
BLOCKING_VOWELS = fst(["i", "ɪ", "e"])
ROUNDING_RIGHT_CONTEXT = pynini.closure(SIGMA-BLOCKING_VOWELS)

ROUNDING_HARMONY = pynini.cdrewrite(
    tau=pynini.cross(ROUNDING_HARMONY_TARGET, ROUNDING_HARMONY_OUTPUT),
    l=fst(''),
    r=ROUNDING_RIGHT_CONTEXT+'[EOS]',
    sigma_star=SIGMASTAR,
).optimize()

LOCATIVE_ROUNDING_RULE = pynini.cdrewrite(
    tau=fst("a", "ɔ")|fst("a"),
    l=fst("ɔ")+T.ques+(C|BOUNDARY).plus,
    r=T.ques+fst(DENTAL_T),
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

H_SPREAD_RULE = pynini.cdrewrite(
    tau=fst(T, HIGH_TONE),
    l=fst([HIGH_TONE, RISE_TONE])+pynini.closure(C|BOUNDARY)+WORD_BOUNDARY+pynini.closure(SEGMENT),
    r=fst(),
    sigma_star=SIGMASTAR,
)

# used in perfective itive forms where prefix fall blocks H docking
FALL_BLOCKS_H_RULE = pynini.cdrewrite(
    tau=fst(HIGH_TONE, LOW_TONE),
    l=fst(FALL_TONE)+pynini.closure(C|BOUNDARY)+WORD_BOUNDARY+pynini.closure(SEGMENT),
    r=fst(),
    sigma_star=SIGMASTAR,
).optimize()

# vowel coalescence
# for now assuming that V[-high,-front]+i > ɛ
# and any other V+V goes to the second V

LOW_BACK_VOWEL = fst(["ɔ", "a", "ɜ"])
HIGH_FRONT_VOWEL = fst("i")
MID_FRONT_VOWEL = fst("ɛ")

COALESCE_W_HIGH_FRONT_VOWEL = pynini.union(*[
    fst(LOW_BACK_VOWEL+T.ques+HIGH_FRONT_VOWEL, MID_FRONT_VOWEL),
])
COALESCE_W_HIGH_FRONT_VOWEL_BOUNDARY = pynini.union(*[
    fst(LOW_BACK_VOWEL+T.ques+BOUNDARY+HIGH_FRONT_VOWEL, BOUNDARY+MID_FRONT_VOWEL),
])
COALESCE_W_HIGH_FRONT_VOWEL_RULE = pynini.cdrewrite(
    tau=COALESCE_W_HIGH_FRONT_VOWEL_BOUNDARY | COALESCE_W_HIGH_FRONT_VOWEL,
    l=fst(),
    r=fst(),
    sigma_star=SIGMASTAR,
).optimize()

DELETE_VOWEL_IN_HIATUS = pynini.cdrewrite(
    tau=delete_fst(V+T.ques),
    l=fst(),
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

VOWEL_COALESCENCE_RULE = COALESCE_W_HIGH_FRONT_VOWEL_RULE@DELETE_VOWEL_IN_HIATUS

VOWEL_COALESCENCE_RULE = VOWEL_COALESCENCE_RULE@REMOVE_DOUBLE_BOUNDARIES

# special case: L>HL when L is the only tone in the word

LEFT_H_MONOSYLL = pynini.cdrewrite(
    tau=fst(L, F),
    l='[BOS]'+pynini.closure(C|BOUNDARY)+V.ques+BOUNDARY.ques,
    r=pynini.closure(C|BOUNDARY)+EOS.ques+'[EOS]',
    sigma_star=SIGMASTAR,
)

LEFT_H_GENERIC = pynini.cdrewrite(
    tau=fst(T-F, HIGH_TONE),
    l='[BOS]'+pynini.closure(C|BOUNDARY)+V.ques+BOUNDARY.ques,
    r=fst(''),
    sigma_star=SIGMASTAR,
)

LEFT_H_RULE = LEFT_H_MONOSYLL @ LEFT_H_GENERIC

# need to apply left-to-right so we don't feed

FINAL_LOWERING_MONOSYLL = pynini.cdrewrite(
    tau=fst(H, F),
    l='[BOS]'+pynini.closure(C|BOUNDARY)+V.ques+BOUNDARY.ques,
    r=pynini.closure(C|BOUNDARY)+EOS,
    sigma_star=SIGMASTAR,
)

# final lowering turns the rightmost H into L
# since an H can span multiple syllables, we need to look for H
# where no L tones follow, and then apply left to right

FINAL_LOWERING_RIGHT_CONTEXT = (
        pynini.closure(SEGMENT|BOUNDARY)+(H+pynini.closure(SIGMA-L)).ques
)+EOS
FINAL_LOWERING_GENERIC = pynini.cdrewrite(
    tau=fst(T-F, L),
    l=fst(''),
    r=FINAL_LOWERING_RIGHT_CONTEXT,
    sigma_star=SIGMASTAR,
    direction='ltr',
)

FINAL_LOWERING_RULE = FINAL_LOWERING_MONOSYLL @ FINAL_LOWERING_GENERIC
# make rule optional
FINAL_LOWERING_RULE = FINAL_LOWERING_RULE | SIGMASTAR_W_SYMBOLS

# ---------- #
# edit costs #
# ---------- #

REDUCED_EDIT_COST = 0.5
MINOR_EDIT_COST = 0.05

INSERTION_COSTS = [
    ('ə', MINOR_EDIT_COST),
    (V, REDUCED_EDIT_COST),
    (T, MINOR_EDIT_COST),
    (WORD_BOUNDARY_STR, REDUCED_EDIT_COST),
]
DELETION_COSTS = [
    ('ə', MINOR_EDIT_COST),
    (V, REDUCED_EDIT_COST),
    (T, MINOR_EDIT_COST),
]
SUBSTITUTION_COSTS = [
    ('ə', V, MINOR_EDIT_COST),      # underlying vowel reduced to schwa
    ('ɛ', 'ə', MINOR_EDIT_COST),    # underlying schwa fronted to /ɛ/

    ('ɜ', 'ɛ', MINOR_EDIT_COST),    # ɜ~ɛ interchange
    ('ɛ', 'ɜ', MINOR_EDIT_COST),

    ('ɜ', 'a', MINOR_EDIT_COST),    # ɜ~a interchange
    ('a', 'ɜ', MINOR_EDIT_COST),

    ('ɜ', 'ə', MINOR_EDIT_COST),    # ɜ~ə interchange
    ('ə', 'ɜ', MINOR_EDIT_COST),

    ('ɛ', 'e', MINOR_EDIT_COST),    # ɛ~e interchange
    ('e', 'ɛ', MINOR_EDIT_COST),

    ('ɪ', 'e', MINOR_EDIT_COST),    # ɪ~ɛ interchange
    ('e', 'ɪ', MINOR_EDIT_COST),

    ('o', 'u', MINOR_EDIT_COST),    # o~u interchange
    ('u', 'o', MINOR_EDIT_COST),

    ('ɔ', 'o', MINOR_EDIT_COST),    # o~ɔ interchange
    ('o', 'ɔ', MINOR_EDIT_COST),

    ('ʊ', 'o', MINOR_EDIT_COST),    # o~ʊ interchange
    ('o', 'ʊ', MINOR_EDIT_COST),

    ('d', DENTAL_D, MINOR_EDIT_COST),   # dental stop written as alveolar
    ('t', DENTAL_T, MINOR_EDIT_COST),

    ('g', 'k', MINOR_EDIT_COST),        # g~k interchange
    ('k', 'g', MINOR_EDIT_COST),

    ('r', 'ɾ', MINOR_EDIT_COST),        # tap written as trill
]
for intab_tone in TIRA_TONE_DIACS:
    for outtab_tone in TIRA_TONE_DIACS:
        if intab_tone == outtab_tone:
            continue
        SUBSTITUTION_COSTS.append((intab_tone, outtab_tone, MINOR_EDIT_COST))

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
REMOVE_HOMOPHONE_TAG = pynini.cdrewrite(
    delete_fst(HOMOPHONE_TAG),
    fst(),
    fst(),
    sigma_star=SIGMASTAR_W_TAG,
).optimize()