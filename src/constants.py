import os
import pynini
from pynini.lib import edit_transducer, features
from string import digits

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
EPSILON_SYMBOL = '<eps>'

SPECIAL_SYMBOLS = [
    BOUNDARY_STR, WORD_BOUNDARY_STR, TONE_SLOT_STR, TONE_PLACEHOLDER_STR,
    INSERT, DELETE, SUBSTITUTE, *BRACKETS, *digits
]
MULTICHAR_TOKENS = [symbol for symbol in SPECIAL_SYMBOLS if len(symbol)>1]\
    + [DENTAL_D, DENTAL_T]

################
# class prefixes
################

CLASS_PREFIXES = [
    "j",
    "g",
    "t̪",
    "ð",
    "n",
    "ɲ",
    "ŋ",
    "r",
    "l",
]
CLASS_AGREE = features.Feature("class", *CLASS_PREFIXES+['unmarked'])

###############
# verb features
###############

SUBJECT_AND_DEIXIS_MARKED_TAM = [
    "imperfective",
    "perfective",
    "dependent",
]
DEIXIS_MARKED_TAM = [
    "imperative"
]
NONFINITE_TAM = [
    "infinitive",
]

TAM = features.Feature(
    "tam",
    "unmarked",
    *SUBJECT_AND_DEIXIS_MARKED_TAM,
    *DEIXIS_MARKED_TAM,
    *NONFINITE_TAM,
)

DEIXIS_VALUES = ["ventive", "itive"]
DEIXIS = features.Feature("deixis", "unmarked", *DEIXIS_VALUES)

INFLECTED_VERB = features.Category(TAM, DEIXIS, CLASS_AGREE)
VERB_FEATURE_VALUES = {
    feature.name: feature.values for feature in INFLECTED_VERB.features
}

VERB_PARADIGM_SIZE = len(SUBJECT_AND_DEIXIS_MARKED_TAM)*len(CLASS_PREFIXES)*len(DEIXIS_VALUES) +\
    len(DEIXIS_MARKED_TAM)*len(DEIXIS_VALUES)+\
    len(NONFINITE_TAM)

######################
# verb feature bundles
######################

INFINITIVE = features.FeatureVector(INFLECTED_VERB, "tam=infinitive", "class=ð", "deixis=unmarked")
IPFV_IT = features.FeatureVector(INFLECTED_VERB, "tam=imperfective", "deixis=itive")
IPFV_VENT = features.FeatureVector(INFLECTED_VERB, "tam=imperfective", "deixis=ventive")
PFV_IT = features.FeatureVector(INFLECTED_VERB, "tam=perfective", "deixis=itive")
PFV_VENT = features.FeatureVector(INFLECTED_VERB, "tam=perfective", "deixis=ventive")
DEP_IT = features.FeatureVector(INFLECTED_VERB, "tam=dependent", "deixis=itive")
DEP_VENT = features.FeatureVector(INFLECTED_VERB, "tam=dependent", "deixis=ventive")
IMP_IT = features.FeatureVector(INFLECTED_VERB, "tam=imperative", "deixis=itive", "class=unmarked")
IMP_VENT = features.FeatureVector(INFLECTED_VERB, "tam=imperative", "deixis=ventive", "class=unmarked")
VERB_ROOT = features.FeatureVector(INFLECTED_VERB, "tam=unmarked", "deixis=unmarked", "class=unmarked")

#################
# noun features #
#################

NOUN_CASE_VALUES = ["nominative", "accusative"]
NOUN_NUMBER_VALUES = ["singular", "plural"]

NOUN_CASE = features.Feature("case", "unmarked", *NOUN_CASE_VALUES)
NOUN_NUMBER = features.Feature("number", "unmarked", *NOUN_NUMBER_VALUES)
NOUN = features.Category(NOUN_CASE, NOUN_NUMBER)

NOMSG = features.FeatureVector(NOUN, "case=nominative", "number=singular")
NOMPL = features.FeatureVector(NOUN, "case=nominative", "number=plural")

ACCSG = features.FeatureVector(NOUN, "case=accusative", "number=singular")
ACCPL = features.FeatureVector(NOUN, "case=accusative", "number=plural")

NOUN_ROOT = features.FeatureVector(NOUN, "case=unmarked", "number=unmarked")

NOUN_FEATURE_ABBREVIATION_TO_VECTOR = {
    "nom.sg": NOMSG,
    "nom.pl": NOMPL,
    "acc.sg": ACCSG,
    "acc.pl": ACCPL,
}
NOUN_FEATURE_ABBREVIATIONS = list(NOUN_FEATURE_ABBREVIATION_TO_VECTOR.keys())

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

#########################
# edit transducer costs #
#########################

DEFAULT_INSERT_COST = edit_transducer.DEFAULT_INSERT_COST
DEFAULT_SUBSTITUTE_COST = edit_transducer.DEFAULT_SUBSTITUTE_COST
DEFAULT_DELETE_COST = edit_transducer.DEFAULT_DELETE_COST
DEFAULT_EDIT_BOUND = 5

#########
# paths #
#########

VERB_ROOTS_PATH = 'data/verb_roots_final.csv'
INFLECTED_VERBS_PATH = 'data/inflected_verb_forms.csv'
GOLD_VERBS_PATH = 'data/gold_verbs.csv'
GOLD_PARADIGMS_PATH = 'data/gold_paradigms.json'
ANALYSES_PATH = 'data/analyses.csv'
NOUNS_PATH = 'data/nouns.csv'
FUZZY_NOUNS_PATH = 'data/fuzzy_nouns.csv'

FST_DIR = "fst/"
ROOT2GLOSS_FST_PATH = os.path.join(FST_DIR, "root2gloss.fst")
ROOT2FV_FST_PATH = os.path.join(FST_DIR, "root2fv.fst")