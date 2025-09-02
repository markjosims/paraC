"""
Declare FSAs for phoneme inventory and phonological classes in Tira.
"""

import pynini
from pynini.lib import paradigms, pynutil

TIRA_STOPS = [
    'p', 't̪', 't', 'c', 'k',
    'b', 'd̪', 'd', 'ɟ', 'g',
]
TIRA_FRICATIVES = [
    's', 'v', 'ð',
]
TIRA_GLIDES = [
    'w', 'j',
]
TIRA_NASALS = [
    'm', 'n', 'ɲ', 'ŋ',
]
TIRA_SONORANTS = [
    'l', 'r', 'ɾ', 'ɽ',
]
TIRA_VOWELS = [
    'i',      'u',
    'ɪ',      'ʊ',
    'e', 'ə', 'o',
    'ɛ', 'ɜ', 'ɔ',
         'a',
]

TIRA_CONSONANTS = TIRA_STOPS + TIRA_FRICATIVES + TIRA_GLIDES + TIRA_NASALS + TIRA_SONORANTS

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0306'
RISE_TONE = '\u030c'
TIRA_TONES = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE]

PLACEHOLDER_TBU = 'x'
TIRA_TBUS = TIRA_VOWELS + TIRA_NASALS + TIRA_SONORANTS

BOUNDARY_STR = '-'
BOUNDARY=pynini.accep(BOUNDARY_STR)

TIRA_SYMBOL_TABLE = pynini.SymbolTable(name="Tira phones")
for phone in TIRA_CONSONANTS+TIRA_VOWELS+TIRA_TONES+[BOUNDARY_STR]:
    TIRA_SYMBOL_TABLE.add_symbol(phone)
TIRA_SYMBOL_TABLE

C = pynini.union(*TIRA_CONSONANTS).optimize()
V = pynini.union(*TIRA_VOWELS).optimize()
T = pynini.union(*TIRA_TONES).optimize()
TBU = pynini.union(*TIRA_TBUS).optimize()
SIGMA = pynini.union(C,V,T,BOUNDARY,PLACEHOLDER_TBU).optimize()
SIGMA_EXCEPT_PLACEHOLDER = pynini.union(C,V,T,BOUNDARY).optimize()
SIGMASTAR = SIGMA.closure().optimize()
SIGMASTAR_EXCEPT_PLACEHOLDER = SIGMA_EXCEPT_PLACEHOLDER.closure().optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# phonological processes

ADD_TBU_MARKER = pynini.cdrewrite(
    tau=pynutil.insert(PLACEHOLDER_TBU),
    l=TBU,
    r='',
    sigma_star=SIGMASTAR
)
REMOVE_TBU_MARKER_AFTER_ONSET_C = pynini.cdrewrite(
    tau=pynutil.delete(PLACEHOLDER_TBU),
    l=C@TBU,
    r=V,
    sigma_star=SIGMASTAR,
)
REMOVE_TBU_MARKER_AFTER_CODA_C = pynini.cdrewrite(
    tau=pynutil.delete(PLACEHOLDER_TBU),
    l=PLACEHOLDER_TBU+C@TBU,
    r='',
    sigma_star=SIGMASTAR,
)
CLEAN_TBU_MARKERS = pynini.cdrewrite(
    tau=pynutil.delete(PLACEHOLDER_TBU),
    l='',
    r='',
    sigma_star=SIGMASTAR
)

HTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + pynutil.insert(HIGH_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()
LTONE_SYLL = (SIGMASTAR_EXCEPT_PLACEHOLDER + PLACEHOLDER_TBU + pynutil.insert(LOW_TONE) + SIGMASTAR_EXCEPT_PLACEHOLDER).optimize()

HLSTAR = (HTONE_SYLL + LTONE_SYLL.closure()).optimize()
ALL_HIGH_TONE = HTONE_SYLL.closure()
ALL_LOW_TONE = LTONE_SYLL.closure().optimize()

compose_tone = lambda tone_fst: ADD_TBU_MARKER@\
    REMOVE_TBU_MARKER_AFTER_ONSET_C@\
    REMOVE_TBU_MARKER_AFTER_CODA_C@\
    tone_fst@\
    CLEAN_TBU_MARKERS

HLSTAR_RULE = compose_tone(HLSTAR)
ALL_HIGH_TONE_RULE = compose_tone(ALL_HIGH_TONE)
ALL_LOW_TONE_RULE = compose_tone(ALL_LOW_TONE)

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete("ə"+T),
    l='',
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()

ADD_PLACEHOLDER_TBU = pynini.cdrewrite(
    tau=pynutil.insert(PLACEHOLDER_TBU),
    l=C.plus,
    r='[EOS]',
    sigma_star=SIGMASTAR,
).optimize()

FLOAT_TONE_RULE = SIGMASTAR.copy()
for tone in TIRA_TONES:
    dock_floating_tone = pynini.cdrewrite(
        tau=pynutil.insert(tone),
        l=PLACEHOLDER_TBU+tone+C.closure()+TBU,
        r='',
        sigma_star=SIGMASTAR
    )
    delete_floating_tone = pynini.cdrewrite(
        tau=pynutil.delete(PLACEHOLDER_TBU+tone),
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