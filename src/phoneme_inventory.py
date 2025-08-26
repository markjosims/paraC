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
TIRA_TBUS = TIRA_VOWELS + TIRA_NASALS + TIRA_SONORANTS

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0306'
RISE_TONE = '\u030c'
TIRA_TONES = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE]

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
SIGMA = pynini.union(C,V,T,BOUNDARY).optimize()
SIGMASTAR = SIGMA.closure().optimize()
STEM = paradigms.make_byte_star_except_boundary(BOUNDARY)

# phonological processes

HTONE_SYLL = (C.closure() + TBU + pynutil.insert(HIGH_TONE) + C.closure()).optimize()
LTONE_SYLL = (C.closure() + TBU + pynutil.insert(LOW_TONE) + C.closure()).optimize()

HLSTAR = (HTONE_SYLL + LTONE_SYLL.closure()).optimize()
ALL_HIGH_TONE = HTONE_SYLL.closure().optimize()
ALL_LOW_TONE = LTONE_SYLL.closure().optimize()

DELETE_SCHWA_BEFORE_VOWEL = pynini.cdrewrite(
    tau=pynutil.delete("ə"+T),
    l='',
    r=BOUNDARY.ques+V,
    sigma_star=SIGMASTAR,
).optimize()