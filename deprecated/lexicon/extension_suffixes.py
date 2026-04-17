"""
## Verbal extensions
Tira has a set of derivational suffixes which attach to verbs and modify the argument
structure and valency of the verb. This set of suffixes is referred to as "verbal extensions"
since they extend the verb root, preceding the Final Vowel suffix.

"""

from src.lexicon.phonology import LOCATIVE_ROUNDING_RULE
from src.constants import BOUNDARY_STR
from typing import *
from src.fst_helpers import fst, get_lattice_strs_and_weights
from itertools import product

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

def extension_abbreviations_to_long(
    extension_seq: Union[str, Tuple[str, str]]
):
    """
    Arguments:
        extension_seq: A single extension or a tuple of two extensions.
    Returns:
        A list of long-form extension names corresponding to the input.
    """
    if type(extension_seq) == str:
        return ABBREVIATION2EXTENSION[extension_seq]
    else:
        return list(ABBREVIATION2EXTENSION[ext] for ext in extension_seq)
    
def extension_long_to_abbreviations(
    extension_seq: Union[str, Tuple[str, str]]
):
    """
    Arguments:
        extension_seq: A single extension or a tuple of two extensions.
    Returns:
        A list of abbreviation-form extension names corresponding to the input.
    """
    if type(extension_seq) == str:
        return EXTENSION2ABBREVIATION[extension_seq]
    else:
        return list(EXTENSION2ABBREVIATION[ext] for ext in extension_seq)

def get_derived_stem_and_fv(
        base_stem: Union[str, List[str]],
        gloss: Union[str, List[str]],
        fv: str,
        extension_seq: Union[str, Sequence[str]]
) -> Tuple[List[str], List[str], str]:
    """
    Arguments:
        base_stem: The root form of the verb.
        gloss: The gloss of the base verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
    Returns:
        (derived_stem, derived_glosses, derived_fv): The derived verb stem, glosses
        and FV class with the appropriate extensions applied.

    Given a base verb stem and an extension sequence (e.g., 'causative', 'passive'),
    return the derived stem with the appropriate suffixes.
    """
    if type(extension_seq) == str:
        extension_seq = [extension_seq]
    if extension_seq[0] in ABBREVIATION2EXTENSION:
        extension_seq = extension_abbreviations_to_long(extension_seq)
    extension_seq_short = extension_long_to_abbreviations(extension_seq)

    outer_fv = fv
    extension_suffix_str = ''
    for ext in extension_seq:
        suffix = EXTENSION_MAP[ext]
        if type(suffix) is dict:
            suffix_str, suffix_fv = suffix[outer_fv]
            extension_suffix_str+= BOUNDARY_STR+suffix_str
        else: # type(suffix) is tuple
            suffix_str, suffix_fv = suffix
            extension_suffix_str+= BOUNDARY_STR+suffix_str
        outer_fv = suffix_fv
    
    if type(base_stem) is str:
        derived_stems = [base_stem + extension_suffix_str]
    else:
        derived_stems = [
            stem + extension_suffix_str
            for stem in base_stem
        ]
    if type(gloss) is str:
        derived_glosses = [BOUNDARY_STR.join([gloss, *extension_seq_short])]
    else:
        derived_glosses = [
            BOUNDARY_STR.join([g, *extension_seq_short])
            for g in gloss
        ]


    if extension_seq[0] == 'locative':
        # locative extension may assimilate in rounding to the stem vowel
        derived_stems_w_rounding = []
        derived_glosses_w_rounding = []
        for stem, gloss in zip(derived_stems, derived_glosses):
            stem = fst(stem) @ LOCATIVE_ROUNDING_RULE
            new_stems = get_lattice_strs_and_weights(stem)
            new_stems = [s for s, _ in new_stems]
            derived_stems_w_rounding.extend(new_stems)
            derived_glosses_w_rounding.extend([gloss]*len(new_stems))
        derived_glosses = derived_glosses_w_rounding
        derived_stems = derived_stems_w_rounding
    return derived_stems, derived_glosses, outer_fv