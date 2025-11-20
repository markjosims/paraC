import os
import pynini
from pynini.lib import edit_transducer, features
from string import digits
from itertools import product

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
CLASS_AGREE = features.Feature("class", *CLASS_PREFIXES, default='unmarked')

PERSON_AND_NUMBER_VALUES = [
    "1sg",
    "2sg",
    "3sg",
    "1du.incl",
    "1pl.incl",
    "1pl.excl",
    "2pl",
    "3pl",
]

SUBJECT_PERSON_AND_NUMBER = features.Feature(
    "subject",
    "unmarked",
    *PERSON_AND_NUMBER_VALUES,
)
OBJECT_PERSON_AND_NUMBER = features.Feature(
    "object",
    "unmarked",
    *PERSON_AND_NUMBER_VALUES,
)


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

WH = features.Feature("wh", "unmarked", "class", "locative")

INFLECTED_VERB = features.Category(
    TAM,
    DEIXIS,
    CLASS_AGREE,
    SUBJECT_PERSON_AND_NUMBER,
    OBJECT_PERSON_AND_NUMBER,
    WH,
)
VERB_FEATURE_VALUES = {
    feature.name: feature.values for feature in INFLECTED_VERB.features
}

VERB_PARADIGM_SIZE = len(SUBJECT_AND_DEIXIS_MARKED_TAM)*len(CLASS_PREFIXES)*len(DEIXIS_VALUES) +\
    len(DEIXIS_MARKED_TAM)*len(DEIXIS_VALUES)+\
    len(NONFINITE_TAM)

######################
# verb feature bundles
######################

INFINITIVE_VALUES = {"tam": "infinitive", "class": "ð"}
IPFV_IT_VALUES = {"tam": "imperfective", "deixis": "itive"}
IPFV_VENT_VALUES = {"tam": "imperfective", "deixis": "ventive"}
PFV_IT_VALUES = {"tam": "perfective", "deixis": "itive"}
PFV_VENT_VALUES = {"tam": "perfective", "deixis": "ventive"}
DEP_IT_VALUES = {"tam": "dependent", "deixis": "itive"}
DEP_VENT_VALUES = {"tam": "dependent", "deixis": "ventive"}
IMP_IT_VALUES = {"tam": "imperative", "deixis": "itive"}
IMP_VENT_VALUES = {"tam": "imperative", "deixis": "ventive"}
VERB_ROOT_VALUES = {"tam": "unmarked"}
VERB_FEATURE_BUNDLE_DICTS = [
    INFINITIVE_VALUES,
    IPFV_IT_VALUES,
    IPFV_VENT_VALUES,
    PFV_IT_VALUES,
    PFV_VENT_VALUES,
    DEP_IT_VALUES,
    DEP_VENT_VALUES,
    IMP_IT_VALUES,
    IMP_VENT_VALUES,
    VERB_ROOT_VALUES,
]
for feature_bundle in VERB_FEATURE_BUNDLE_DICTS:
    for feature in VERB_FEATURE_VALUES.keys():
        if feature not in feature_bundle:
            feature_bundle[feature] = 'unmarked'
INFINITIVE = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in INFINITIVE_VALUES.items()]
)
IPFV_IT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in IPFV_IT_VALUES.items()]
)
IPFV_VENT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in IPFV_VENT_VALUES.items()]
)
PFV_IT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in PFV_IT_VALUES.items()]
)
PFV_VENT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in PFV_VENT_VALUES.items()]
)
DEP_IT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in DEP_IT_VALUES.items()]
)
DEP_VENT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in DEP_VENT_VALUES.items()]
)
IMP_IT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in IMP_IT_VALUES.items()]
)
IMP_VENT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in IMP_VENT_VALUES.items()]
)
VERB_ROOT = features.FeatureVector(
    INFLECTED_VERB,
    *[f"{k}={v}" for k, v in VERB_ROOT_VALUES.items()]
)
VERB_FETURE_BUNDLES = [
    INFINITIVE,
    IPFV_IT,
    IPFV_VENT,
    PFV_IT,
    PFV_VENT,
    DEP_IT,
    DEP_VENT,
    IMP_IT,
    IMP_VENT,
    VERB_ROOT,
]
FV_CLASSES = ['aɔ', 'ao', 'au', 'ai', 'ɔɔ', 'ɔi', 'ɔu']

######################
# auxiliary features #
######################

INFLECTED_AUX = features.Category(*INFLECTED_VERB.features)
AUX_LEMMA_STR = 'ŋgá'
IPFV_AUX = features.FeatureVector(INFLECTED_AUX, "tam=imperfective")
PFV_IT_AUX = features.FeatureVector(INFLECTED_AUX, "tam=perfective", "deixis=itive")
AUX_FEATURE_BUNDLES = [
    IPFV_AUX,
    PFV_IT_AUX,
]
for feature_bundle in AUX_FEATURE_BUNDLES:
    for feature in VERB_FEATURE_VALUES.keys():
        if feature not in feature_bundle.values:
            feature_bundle.values[feature] = 'unmarked' 

##################
# verb extension #
##################

CAUS_STR = 'ij'
PASS_STR = 'in'
ANTIP_STR = 'ið'
BEN_STR = 'it̪'
LOC_AV_STR = 'at̪'
LOC_OV_STR = 'ɛt̪'
LOC_AI_STR = 'ac'
LOC_OI_STR = 'ɛc'
LOC_STRS = [LOC_AV_STR, LOC_OV_STR, LOC_AI_STR, LOC_OI_STR]

EXTENSION_MAP = {
    'causative': (CAUS_STR, 'ɔi'),
    'passive': (PASS_STR, 'ɔɔ'),
    'antipassive': {
        'aɔ': (ANTIP_STR, 'ao'),
        'ao': (ANTIP_STR, 'ao'),
        'au': (ANTIP_STR, 'au'),
        'ai': (ANTIP_STR, 'au'),
        'ɔɔ': (ANTIP_STR, 'ɔu'),
        'ɔi': (ANTIP_STR, 'ɔu'),
        'ɔu': (ANTIP_STR, 'ɔu'),
    },
    'benefactive': (BEN_STR, 'ɔɔ'),
    'locative': {
        'aɔ': (LOC_AV_STR, 'aɔ'),
        'ao': (LOC_AV_STR, 'aɔ'),
        'au': (LOC_AV_STR, 'aɔ'),
        'ɔɔ': (LOC_OV_STR, 'ɔɔ'),
        'ɔu': (LOC_OV_STR, 'ɔɔ'),
        'ai': (LOC_AI_STR, 'ai'),
        'ɔi': (LOC_OI_STR, 'ɔi'),
    }
}

EXTENSION2ABBREVIATION = {
    'causative': 'caus',
    'passive': 'pass',
    'antipassive': 'antip',
    'benefactive': 'ben',
    'locative': 'loc',
}

ABBREVIATION2EXTENSION = {
    v: k for k, v in EXTENSION2ABBREVIATION.items()
}

_extension_couples = list(
    product(ABBREVIATION2EXTENSION.keys(), repeat=2)
)
_allowed_repeats = ['locative', 'benefactive']
_filtered_extension_couples = [
    couple for couple in _extension_couples
    if couple[0] != couple[1] or couple[0] in _allowed_repeats
]
_single_extensions = [[ext] for ext in EXTENSION_MAP.keys()]
ALL_POSSIBLE_EXTENSION_SEQS = _single_extensions + _filtered_extension_couples
ALL_POSSIBLE_EXTENSION_SEQ_STRS = [
    '+'.join(seq) for seq in ALL_POSSIBLE_EXTENSION_SEQS
]


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

######################
# adjective features #
######################

ADJECTIVE_CLASS_VALUES = CLASS_PREFIXES
ADJECTIVE_CLASS = features.Feature("class", "unmarked", *ADJECTIVE_CLASS_VALUES)
ADJECTIVE = features.Category(ADJECTIVE_CLASS)
ADJECTIVE_ROOT = features.FeatureVector(ADJECTIVE, "class=unmarked")

####################
# lexical features #
####################

# 'features' used to distinguish lexical classes
# useful for the unified parser

POS2CATEGORY = {
    'noun': NOUN,
    'verb': INFLECTED_VERB,
    'aux': INFLECTED_AUX,
    'adjective': ADJECTIVE,
    'adverb': None,
    'postposition': None,
    'preposition': None,
    'conjunction': None,
    'particle': None,
}


POS_TAG = features.Feature(
    "part_of_speech", "unmarked", *POS2CATEGORY.keys()
)

FV_TAG = features.Feature("fv", "unmarked", *FV_CLASSES)

# ternary/binary features
AUX_TAG = features.Feature("aux", "unmarked", "true", "false")
# aux is ternary since verb stems that are discontinuous with Aux
# are marked as aux=false
FINAL_LOWERING_TAG = features.Feature("final_lowering", "unmarked", "true")
LEFTH_TAG = features.Feature("left_h", "unmarked", "true")

LEXICAL_FEATURES = [
    POS_TAG, FV_TAG, AUX_TAG,
    FINAL_LOWERING_TAG, LEFTH_TAG
]
LEXICAL_FEATURE_VALUES = {
    feature.name: feature.values for feature in LEXICAL_FEATURES
}
LEXEME = features.Category(*LEXICAL_FEATURES)

################
# all features #
################

FEATURES_TO_VALUES = {}
for category in [INFLECTED_VERB, INFLECTED_AUX, NOUN, ADJECTIVE, LEXEME]:
    for feature in category.features:
        if feature.name not in FEATURES_TO_VALUES:
            FEATURES_TO_VALUES[feature.name] = feature.values

ALL_FEATURE_STRS = []
for feature_name, feature_values in FEATURES_TO_VALUES.items():
    for feature_value in feature_values:
        ALL_FEATURE_STRS.append(f"{feature_name}={feature_value}")

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
# edit transducer costs #
#########################

DEFAULT_INSERT_COST = edit_transducer.DEFAULT_INSERT_COST
DEFAULT_SUBSTITUTE_COST = edit_transducer.DEFAULT_SUBSTITUTE_COST
DEFAULT_DELETE_COST = edit_transducer.DEFAULT_DELETE_COST
DEFAULT_EDIT_BOUND = 5

#########
# paths #
#########

LEXICON_DIR = "data/lexicon/"
TEST_CASE_DIR = "data/test_cases/"

FST_DIR = "fst/"
ROOT2GLOSS_FST_PATH = os.path.join(FST_DIR, "root2gloss.fst")
ROOT2FV_FST_PATH = os.path.join(FST_DIR, "root2fv.fst")