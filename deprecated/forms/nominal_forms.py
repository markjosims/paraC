"""
# Noun Paradigm Builder
This module builds the noun paradigm for Tira nouns using data from the noun lexicon.
The 'root' column is used as the lemma, which generally corresponds to the singular nominative form
with a homophone disambiguation suffix if necessary.

Marked features include case (nominative and accusative), number (singular and plural).

TODO: Support inalienably possessed nouns.
"""

import pandas as pd
import pynini
from pynini.lib import paradigms
from src.decorators import output_cache
from src.forms.form_helpers import aggregate_slot_dicts, suffix
from src.lexicon.phonology import *
from src.fst_helpers import *
from src.lexicon import load_lexical_data
from src.constants import (
    NOUN_FEATURE_ABBREVIATION_TO_VECTOR,
    BOUNDARY_STR,
    POS_GROUPS,
    POS2CATEGORY,
    POS2ROOT_VECTOR,
    INALIENABLE_POSSESSOR_PERSON,
    INALIENABLE_NOUN,
    INALIENABLE_NOUN_ROOT,
)
from typing import *


INALIENABLE_POSSESSIVE_SUFFIXES = {
    "1sg/1pl.excl": {"lower": "-áj", "higher": "-ɛ́j"},
    "2sg/2pl": "-àló",
    "3sg/3pl": "-ɛ́n",
    "1du.incl": "-ɜ̀lí",
    "1pl.incl": "-ɜ̀lí-r",
}

@output_cache(__file__)
def get_nominal_paradigm(part_of_speech: str) -> paradigms.Paradigm:
    """
    Create Paradigm object for the specified nominal part of speech
    (noun or pronoun).
    """
    df = load_lexical_data(part_of_speech=part_of_speech)
    if df.empty:
        raise ValueError(f"No lexical data found for part of speech: {part_of_speech}")
    slots = []
    root_col = df['root']

    # add forms for all case and number combinations
    for feature_str, feature_vec in NOUN_FEATURE_ABBREVIATION_TO_VECTOR.items():

        # need to filter out empty forms (e.g. no accusative or plural forms for some nouns)
        feature_col = df[feature_str]
        feature_mask = feature_col!=''
        if not feature_mask.any():
            continue
        
        feature_forms = feature_col[feature_mask].tolist()
        roots = root_col[feature_mask].tolist()
        feature_fsts = []

        # iter through variants of a form (separated by spaces)
        for form, root in zip(feature_forms, roots):
            for subform in form.split():
                feature_fsts.append(fst(root, subform))
        feature_fst = pynini.union(*feature_fsts).optimize()
        slots.append((feature_fst, feature_vec))
    root_fsas = [fst(root) for root in root_col.tolist()]

    root_acceptor = pynini.union(*root_fsas).optimize()
    root_feature = POS2ROOT_VECTOR[part_of_speech]
    slots.append((root_acceptor, root_feature))

    category = POS2CATEGORY[part_of_speech]

    nominal_paradigm = paradigms.Paradigm(
        category=category,
        name=stringify_lexeme_features({"part_of_speech": part_of_speech}),
        slots=slots,
        lemma_feature_vector=root_feature,
        stems=root_fsas,
        boundary=fst(BOUNDARY_STR),
    )
    return nominal_paradigm

def add_possessive_suffixes_to_slots(
        slot_dict: Dict[Tuple[str, str], pynini.Fst],
        vowel_class: Literal['lower', 'higher'],
) -> Dict[Tuple[str, str, str], pynini.Fst]:
    """
    Add inalienable possessive suffixes to the given list of slots,
    **excluding** 1st person singular which is handled separately
    as different nouns take different allomorphs.

    Arguments:
        slot_dict: A dict mapping feature couples (case, number) to FSTs.
    Returns:
        A dict mapping feature triples (case, number, possessor) to FSTs.
    """
    new_slot_dict = {}
    for feature_tuple, stem in slot_dict.items():
        for possessor_person, suffix_form in INALIENABLE_POSSESSIVE_SUFFIXES.items():
            if type(suffix_form) is dict:
                suffix_form = suffix_form[vowel_class]
            rule = suffix(suffix_form, stem)
            rule.optimize()
            features_with_possessor = feature_tuple + (f"possessor={possessor_person}",)
            new_slot_dict[features_with_possessor] = rule
    return new_slot_dict

def build_inalienable_accusative_forms(
        stems: List[str],
        roots: List[str],
        number: Literal['singular', 'plural'],
        vowel_class: Literal['lower', 'higher'],
    ) -> Dict[Tuple[str, str, str], pynini.Fst]:
    """
    Only a few inalienably possessed nouns have distinct accusative forms,
    marked with a grammatical low tone on the root.
    """
    root2stem_fst = [fst(root, stem) for root, stem in zip(roots, stems)]
    root2stem_fst = pynini.union(*root2stem_fst).optimize()
    stem = root2stem_fst @ ALL_LOW_TONE_RULE
    feature_tuple = ("case=accusative", f"number={number}")
    slot = {feature_tuple: stem}
    slots_w_possessors = add_possessive_suffixes_to_slots(
        slot_dict=slot,
        vowel_class=vowel_class,
    )
    return slots_w_possessors

def build_inalienable_nominative_forms(
        stems: List[str],
        roots: List[str],
        number: Literal['singular', 'plural'],
        vowel_class: Literal['lower', 'higher'],
        grammatical_tone: bool = False,
    ) -> Dict[Tuple[str, str, str], pynini.Fst]:
    """
    Returns a dict of feature tuples mapping to FSTs for inalienably possessed
    noun nominative forms. If `grammatical_tone` is True, shifts all tones to high,
    otherwise makes no edits apart from adding possessive suffixes.
    """
    root2stem_fst = [fst(root, stem) for root, stem in zip(roots, stems)]
    root2stem_fst = pynini.union(*root2stem_fst).optimize()
    feature_tuple = ("case=nominative", f"number={number}")
    slot = {feature_tuple: root2stem_fst}
    slots_w_possessors = add_possessive_suffixes_to_slots(
        slot_dict=slot,
        vowel_class=vowel_class,
    )
    if grammatical_tone:
        for feature_tuple, stem in slots_w_possessors.items():
            stem_with_grammatical_tone = stem @ REMOVE_ALL_TONE @ ALL_HIGH_TONE_RULE
            slots_w_possessors[feature_tuple] = stem_with_grammatical_tone
    return slots_w_possessors

@output_cache(__file__)
def get_inalienable_noun_paradigm() -> paradigms.Paradigm:
    """
    Create Paradigm object for inalienably possessed nouns.
    """
    df = load_lexical_data(part_of_speech='inalienable_noun')

    # some nouns have pronunciation variants separated by spaces
    # explode the data frame to have one variant per row
    df['singular'] = df['singular'].str.split()
    df['plural'] = df['plural'].str.split()
    df = df.explode('singular')
    df = df.explode('plural')

    root_fsas = [fst(root) for root in df['root'].tolist()]
    
    slot_dicts = []
    slot_dicts.append(populate_root_slot_dict(root_fsas=root_fsas))
    slot_dicts.extend(populate_grammatical_tone_slot_dicts(df))
    slot_dicts.extend(populate_remaining_slot_dicts(df))
    slots = aggregate_slot_dicts(
        slot_dicts=slot_dicts,
        category=INALIENABLE_NOUN,
    )

    nominal_paradigm = paradigms.Paradigm(
        category=INALIENABLE_NOUN,
        name=stringify_lexeme_features({"part_of_speech": "inalienable_noun"}),
        slots=slots,
        lemma_feature_vector=INALIENABLE_NOUN_ROOT,
        stems=root_fsas,
        boundary=fst(BOUNDARY_STR),
    )
    return nominal_paradigm

def populate_root_slot_dict(
        root_fsas: List[pynini.Fst],
    ) -> Dict[Tuple[str, str], pynini.Fst]:
    """
    Build slot dict for inalienably possessed noun roots.
    """
    root_acceptor = pynini.union(*root_fsas).optimize()
    slot_dict = {}
    feature_tuple = ()
    for feature in INALIENABLE_NOUN_ROOT.values:
        feature_tuple += (f"{feature}=unmarked",)
    slot_dict[feature_tuple] = root_acceptor
    return slot_dict


def populate_grammatical_tone_slot_dicts(
        df: pd.DataFrame
    ) -> List[Dict[Tuple[str, str, str], pynini.Fst]]:
    """
    Build slot dicts for inalienably possessed nouns with grammatical tone.
    These nouns have distinct accusative forms marked with a low tone on the root,
    and the nominative forms have all high tones.
    """

    slot_dicts = []
    grammatical_tone_both_numbers = df['grammatical_tone'] == 'both'
    grammatical_tone_plural_only = df['grammatical_tone'] == 'plural_only'
    for vowel_class in ['lower', 'higher']:
        vowel_class_mask = df['vowel_class'] == vowel_class

        sg_df = df[
            (grammatical_tone_both_numbers & vowel_class_mask)
        ]
        sg_roots = sg_df['root'].tolist()
        sg_stems = sg_df['singular'].tolist()

        pl_df = df[
            (grammatical_tone_both_numbers | grammatical_tone_plural_only)
            & vowel_class_mask
        ]
        pl_stems = pl_df['plural'].tolist()
        pl_roots = pl_df['root'].tolist()
        if sg_stems:
            acc_sg_slot = build_inalienable_accusative_forms(
                stems=sg_stems,
                roots=sg_roots,
                number='singular',
                vowel_class=vowel_class,
            )
            nom_sg_slot = build_inalienable_nominative_forms(
                stems=sg_stems,
                roots=sg_roots,
                number='singular',
                vowel_class=vowel_class,
                grammatical_tone=True,
            )
            slot_dicts.extend([acc_sg_slot, nom_sg_slot])

        if pl_stems:
            acc_pl_slot = build_inalienable_accusative_forms(
                stems=pl_stems,
                roots=pl_roots,
                number='plural',
                vowel_class=vowel_class,
            )
            nom_pl_slot = build_inalienable_nominative_forms(
                stems=pl_stems,
                roots=pl_roots,
                number='plural',
                vowel_class=vowel_class
            )
            slot_dicts.extend([acc_pl_slot, nom_pl_slot])
    return slot_dicts

def populate_remaining_slot_dicts(
        df: pd.DataFrame
    ) -> List[Dict[Tuple[str, str, str], pynini.Fst]]:
    """
    Build slot dicts for inalienably possessed nouns not marked with
    grammatical tone. These nouns have no distinct accusative forms,
    and the nominative forms have tone marked lexically.
    """

    slot_dicts = []
    no_grammatical_tone_mask = df['grammatical_tone'] == 'none'
    for vowel_class in ['lower', 'higher']:
        vowel_class_mask = df['vowel_class'] == vowel_class
        
        sg_df = df[
            (no_grammatical_tone_mask & vowel_class_mask)
        ]
        sg_stems = sg_df['singular'].tolist()
        sg_roots = sg_df['root'].tolist()


        pl_df = df[
            (no_grammatical_tone_mask)
            & vowel_class_mask
        ]
        pl_stems = pl_df['plural'].tolist()
        pl_roots = pl_df['root'].tolist()

        if sg_stems:
            nom_sg_slot = build_inalienable_nominative_forms(
                stems=sg_stems,
                roots=sg_roots,
                number='singular',
                vowel_class=vowel_class,
            )
            slot_dicts.append(nom_sg_slot)

        if pl_stems:
            nom_pl_slot = build_inalienable_nominative_forms(
                stems=pl_stems,
                roots=pl_roots,
                number='plural',
                vowel_class=vowel_class
            )
            slot_dicts.append(nom_pl_slot)
    return slot_dicts

def get_all_nominal_paradigms() -> List[paradigms.Paradigm]:
    """
    Get paradigms for all nominal parts of speech.
    """
    nominal_paradigms = []
    for pos in POS_GROUPS['nominal']:
        try:
            nominal_paradigms.append(get_nominal_paradigm(part_of_speech=pos))
        except ValueError:
            # no lexical data for this part of speech
            continue
    nominal_paradigms.append(get_inalienable_noun_paradigm())
    return nominal_paradigms

if __name__ == "__main__":
    # when run as a script, build all nominal paradigms and drop into debugger
    paradigms = get_all_nominal_paradigms()
    breakpoint()