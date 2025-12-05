import pynini
from string import digits
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
    'f', 's', 'ʃ','h',
    'v', 'ð',
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
FALLRISE_TONE_SYMBOL = '<HLH>'

HIGH_TONE = '\u0301'
LOW_TONE = '\u0300'
FALL_TONE = '\u0302'
RISE_TONE = '\u030c'
FALLRISE_TONE = '\u1dc9'

SYMBOL2DIAC = {
    HIGH_TONE_SYMBOL: HIGH_TONE,
    LOW_TONE_SYMBOL: LOW_TONE,
    FALL_TONE_SYMBOL: FALL_TONE,
    RISE_TONE_SYMBOL: RISE_TONE,
    FALLRISE_TONE_SYMBOL: FALLRISE_TONE,
}
DIAC2SYMBOL = {value:key for key, value in SYMBOL2DIAC.items()}


TIRA_TONE_SYMBOLS = [HIGH_TONE_SYMBOL, LOW_TONE_SYMBOL, FALL_TONE_SYMBOL, RISE_TONE_SYMBOL, FALLRISE_TONE_SYMBOL]
TIRA_TONE_DIACS = [HIGH_TONE, LOW_TONE, FALL_TONE, RISE_TONE, FALLRISE_TONE]

TIRA_TBUS = TIRA_VOWELS + TIRA_NASALS + TIRA_SONORANTS

#####################
# special FST symbols
#####################

INSERT = edit_transducer.EditTransducer.INSERT
DELETE = edit_transducer.EditTransducer.DELETE
SUBSTITUTE = edit_transducer.EditTransducer.SUBSTITUTE
BRACKETS = ['[', ']', '(', ')']

TONE_SLOT_STR = '<TBU>'
TONE_PLACEHOLDER_STR = '<FLOAT>'
BOUNDARY_STR = '-'
WORD_BOUNDARY_STR = '|'
SEARCH_SEPARATOR_STR = '#'
EPSILON_SYMBOL = '<eps>'
EOS_STR = '<ENDOFSENTENCE>'

SPECIAL_SYMBOLS = [
    BOUNDARY_STR, WORD_BOUNDARY_STR, TONE_SLOT_STR, TONE_PLACEHOLDER_STR,
    INSERT, DELETE, SUBSTITUTE, SEARCH_SEPARATOR_STR, EOS_STR,
    *BRACKETS, *digits
]
MULTICHAR_TOKENS = [symbol for symbol in SPECIAL_SYMBOLS if len(symbol)>1]\
    + [DENTAL_D, DENTAL_T]

################
# symbol table #
################

TIRA_SYMBOL_TABLE = pynini.SymbolTable(name="Tira phones")
TIRA_SYMBOL_TABLE.add_symbol(EPSILON_SYMBOL)
for symbol in SPECIAL_SYMBOLS:
    TIRA_SYMBOL_TABLE.add_symbol(symbol)
for phone in TIRA_CONSONANTS+TIRA_VOWELS+TIRA_TONE_SYMBOLS:
    TIRA_SYMBOL_TABLE.add_symbol(phone)
TIRA_SYMBOL_TABLE

TIRA_NUM_SYMBOLS = TIRA_SYMBOL_TABLE.num_symbols()
TIRA_SYMBOL_TO_CHAR = {
    **SYMBOL2DIAC,
    WORD_BOUNDARY_STR: ' ',
}

GENERATED_SYMBOL_TABLE = pynini.generated_symbols()
GENERATED_SYMBOLS = dict(GENERATED_SYMBOL_TABLE).values()
MULTICHAR_TOKENS.extend(GENERATED_SYMBOLS)
MULTICHAR_TOKENS.sort(key=lambda x: len(x), reverse=True)

for label, symbol in GENERATED_SYMBOL_TABLE:
    TIRA_SYMBOL_TABLE.add_symbol(symbol, label)

#########################
# k2 specific constants #
#########################

K2_FINAL_ARC_LABEL = -1