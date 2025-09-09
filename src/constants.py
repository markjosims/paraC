import os
import pynini
from pynini.lib import edit_transducer

###############
# Tira phonemes
###############

DENTAL_T = 't̪'
DENTAL_D = 'd̪'

TIRA_STOPS = [
    'p', DENTAL_T, 't', 'c', 'k', 'ʔ',
    'b', DENTAL_D, 'd', 'ɟ', 'g',
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

HIGH_TONE_SYMBOL = '<H>'
LOW_TONE_SYMBOL = '<L>'
FALL_TONE_SYMBOL = '<HL>'
RISE_TONE_SYMBOL = '<LH>'

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0306'
RISE_TONE = '\u030c'

SYMBOL2DIAC = {
    HIGH_TONE_SYMBOL: HIGH_TONE,
    LOW_TONE_SYMBOL: LOW_TONE,
    FALL_TONE_SYMBOL: FALL_TONE,
    RISE_TONE_SYMBOL: RISE_TONE,
}
DIAC2SYMBOL = {value:key for key, value in SYMBOL2DIAC.items()}


TIRA_TONE_SYMBOLS = [HIGH_TONE_SYMBOL, LOW_TONE_SYMBOL, FALL_TONE_SYMBOL, RISE_TONE_SYMBOL]
TIRA_TONE_DIACS = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE]

TIRA_TBUS = TIRA_VOWELS + TIRA_NASALS + TIRA_SONORANTS

#####################
# special FST symbols
#####################

INSERT = edit_transducer.EditTransducer.INSERT
DELETE = edit_transducer.EditTransducer.DELETE
SUBSTITUTE = edit_transducer.EditTransducer.SUBSTITUTE
SQUARE_BRACKETS = ['[', ']']

PLACEHOLDER_TBU_STR = 'x'
BOUNDARY_STR = '-'
WORD_BOUNDARY_STR = '|'
EPSILON_SYMBOL = '<eps>'

SPECIAL_SYMBOLS = [
    BOUNDARY_STR, WORD_BOUNDARY_STR, PLACEHOLDER_TBU_STR, INSERT, DELETE, SUBSTITUTE, *SQUARE_BRACKETS
]
MULTICHAR_TOKENS = [
    DENTAL_D, DENTAL_T, EPSILON_SYMBOL, INSERT, DELETE, SUBSTITUTE
]

TIRA_SYMBOL_TABLE = pynini.SymbolTable(name="Tira phones")
TIRA_SYMBOL_TABLE.add_symbol(EPSILON_SYMBOL)
for symbol in SPECIAL_SYMBOLS:
    TIRA_SYMBOL_TABLE.add_symbol(symbol)
for phone in TIRA_CONSONANTS+TIRA_VOWELS+TIRA_TONE_SYMBOLS:
    TIRA_SYMBOL_TABLE.add_symbol(phone)
TIRA_SYMBOL_TABLE

#########################
# edit transducer costs #
#########################

DEFAULT_INSERT_COST = edit_transducer.DEFAULT_INSERT_COST
DEFAULT_SUBSTITUTE_COST = edit_transducer.DEFAULT_SUBSTITUTE_COST
DEFAULT_DELETE_COST = edit_transducer.DEFAULT_DELETE_COST

#########
# paths #
#########

VERB_ROOTS_PATH = 'data/verb_roots_final.csv'
INFLECTED_VERBS_PATH = 'data/inflected_verb_forms.csv'

FST_DIR = "fst/"
ROOT2GLOSS_FST_PATH = os.path.join(FST_DIR, "root2gloss.fst")
ROOT2FV_FST_PATH = os.path.join(FST_DIR, "root2fv.fst")