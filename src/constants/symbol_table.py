import pynini
from string import digits
from pynini.lib import edit_transducer

"""
## Tira phone inventory
The standard Tira phone inventory consists of:

            Labial  Dental  Alv.    Retro.  Palatal Velar
Nasal:      m               n               ɲ       ŋ
Stop:       p       t̪       t               c       k
            b       d̪       d               ɟ       g
Fricative:  f               s
            v       ð
Glide:      w                               j
Lateral:                    l
Trill:                      r      
Tap/flap:                   ɾ       ɽ


The postalveolar fricative ʃ, the glottal fricative h and the glottal stop ʔ
are used occasionally in loanwords from English, and so are included in the
symbol table.

Vowels:
            Front       Central     Back
High:       i                       u
            ɪ                       ʊ
Mid:        e           ə           o
            ɛ           ɜ           ɔ
Low:                    a
"""

DENTAL_BRIDGE = '\u032a'
DENTAL_T = 't' + DENTAL_BRIDGE
DENTAL_D = 'd' + DENTAL_BRIDGE

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

"""
## Tira tone symbols and diacritics
We implement two representations of Tira tones:
1. Symbolic representation using special symbols: <H>, <L>, <HL>, <LH>, <HLH>
2. Diacritic representation using Unicode combining diacritics.
Either symbol can be used when building FSTs with factory functions
(see src/fst_helpers.py). Internally, we convert all diacritics to tone
symbols, which is beneficial when visualizing FSTs as a .dot file. When
decoding an FST into strings, we convert tone symbols back to diacritics.
"""

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

"""
## Special symbols
We define special symbols for various purposes, including edit operations,
tone slots, boundaries, and placeholders.

### Edit symbols
Pynini provides an `EditTransducer` class that defines standard edit operations:
- INSERT: Insertion of a symbol
- DELETE: Deletion of a symbol
- SUBSTITUTE: Substitution of one symbol for another
We implement our own edit transducer (src/search.py), recycling these standard symbols.
"""

INSERT = edit_transducer.EditTransducer.INSERT
DELETE = edit_transducer.EditTransducer.DELETE
SUBSTITUTE = edit_transducer.EditTransducer.SUBSTITUTE

"""
### Tone slots
To facilitate tone assignment during parsing, we define special symbols
for tone slots and placeholders:
- TONE_SLOT_STR: Indicates that the preceding segment requires a tone
- TONE_PLACEHOLDER_STR: Represents a floating tone that is inserted by
    a grammatical process but cannot attach to the preceding segment.
    This symbol indicates that a later process should assign this tone
    to an appropriate segment.
"""

TONE_SLOT_STR = '<TBU>'
TONE_PLACEHOLDER_STR = '<FLOAT>'

"""
### Other special symbols
- CLASS_SYMBOL: Placeholder for noun class morphemes
- BOUNDARY_STR: Morpheme boundary symbol
- WORD_BOUNDARY_STR: Word boundary symbol
- EPSILON_SYMBOL: Epsilon (empty) symbol for FSTs
- EOS_STR: End-of-sentence symbol
- BRACKETS: List of bracket symbols used in various contexts
"""

CLASS_SYMBOL = '<CL>'
BOUNDARY_STR = '-'
WORD_BOUNDARY_STR = '|'
EPSILON_SYMBOL = '<eps>'
EOS_STR = '<ENDOFSENTENCE>'
BRACKETS = ['[', ']', '(', ')']

"""
### Symbol lists
- SPECIAL_SYMBOLS: List of all special symbols defined above
- MULTICHAR_TOKENS: List of special symbols and Tira tone symbols
    that consist of more than one character (including dental t̪ and d̪)
"""

SPECIAL_SYMBOLS = [
    BOUNDARY_STR, WORD_BOUNDARY_STR, TONE_SLOT_STR, TONE_PLACEHOLDER_STR,
    CLASS_SYMBOL, INSERT, DELETE, SUBSTITUTE, EOS_STR,
    *BRACKETS, *digits
]
MULTICHAR_TOKENS = [symbol for symbol in SPECIAL_SYMBOLS+TIRA_TONE_SYMBOLS if len(symbol)>1]\
    + [DENTAL_D, DENTAL_T]

"""
## Tira symbol table
We create a Pynini symbol table that includes all Tira phones, special symbols,
and generated symbols used by Pynini (e.g., for feature values).
"""

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

"""
## K2 constants
K2_FINAL_ARC_LABEL: The special label used by K2 to indicate final arcs
in FSTs.

Note: not currently using k2, but defined here for future use.
"""

K2_FINAL_ARC_LABEL = -1