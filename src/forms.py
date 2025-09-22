"""
WIP: Script that builds FSTs for generating various inflectional forms
of nouns and verbs in Tira.
"""

import pynini
from pynini.lib import features, paradigms, rewrite, pynutil
import pandas as pd
from src.phonology import *
from src.fst_helpers import *
from src.lexicon import get_roots_for_class, get_all_verb_roots_and_fvs
from src.glossing import REMOVE_HOMOPHONE_TAG, feature_str_to_dict
from src.constants import INFLECTED_VERBS_PATH
from typing import *
import random

# helper functions

def generate_forms(
        stem: str,
        paradigm: paradigms.Paradigm,
        action: Literal['print', 'return']='print',
        parse: bool=False
):
    lattice = rewrite.rewrite_lattice(
        fst(stem),
        paradigm.stems_to_forms @ paradigm.feature_label_rewriter,
    )
    wordforms = []
    for wordform in rewrite.lattice_to_strings(lattice):
        if action=='return' and parse:
            parsed_wordform = feature_str_to_dict(wordform)
            wordforms.append(parsed_wordform)
        elif action=='return':
            wordforms.append(wordform)
        else:
            print(wordform)
    if action=='return':
        return wordforms

def add_class_prefix(stem: pynini.Fst, class_agree: str, prefix_tone=LOW_TONE) -> pynini.Fst:
    prefix_acceptor = fst(f"{class_agree}ə{prefix_tone}-")
    return (paradigms.prefix(prefix_acceptor, stem)@DELETE_SCHWA_BEFORE_VOWEL).optimize()

def add_class_prefixes_to_slots(slot_list):
    slots_w_class_prefixes = []
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        feature_values = [f"{feature}={value}" for feature, value in feature_vector.values.items()]
        for class_agree in CLASS_PREFIXES:
            features_with_class = features.FeatureVector(category, f"class={class_agree}", *feature_values)
            prefixed_verb = add_class_prefix(stem, class_agree)
            slots_w_class_prefixes.append((prefixed_verb, features_with_class))
    return slots_w_class_prefixes

# FV mappings

CLASS2FV = {
    "aɔ": {"a_morphome": "a", "o_morphome": "ɔ", "e_morphome": "ɛ"},
    "ao": {"a_morphome": "a", "o_morphome": "o", "e_morphome": "i"},
    "au": {"a_morphome": "a", "o_morphome": "u", "e_morphome": "i"},
    "ai": {"a_morphome": "a", "o_morphome": "i", "e_morphome": "i"},
    "ɔɔ": {"a_morphome": "ɔ", "o_morphome": "ɔ", "e_morphome": "ɛ"},
    "ɔu": {"a_morphome": "ɔ", "o_morphome": "u", "e_morphome": "i"},
    "ɔi": {"a_morphome": "ɔ", "o_morphome": "i", "e_morphome": "i"},
}
FV_CLASSES = list(CLASS2FV.keys())

# prefixes/auxiliaries

IPFV_AUX = lambda stem: paradigms.prefix(fst("á-"), stem).optimize()
PFV_IT_AUX = lambda stem: paradigms.prefix(fst("à-"), stem).optimize()
INFINITIVE_PREFIX = lambda stem: paradigms.prefix(fst("ðə́-"), stem).optimize()

# slots for verb paradigms

def make_verb_slots(fv_class: str) -> Dict[str, List[Tuple[pynini.Fst, features.FeatureVector]]]:
    a_morphome = CLASS2FV[fv_class]["a_morphome"]
    o_morphome = CLASS2FV[fv_class]["o_morphome"]
    e_morphome = CLASS2FV[fv_class]["e_morphome"]
    
    prepare_root_for_inflection = REMOVE_HOMOPHONE_TAG@ADD_PLACEHOLDER_TBU
    finalize_form = FLOAT_TONE_RULE@COMBINE_TONES_RULE

    compose_stem = lambda stem_rule: prepare_root_for_inflection@stem_rule@finalize_form

    imp_it_suffix=fst(f"-{o_morphome}{HIGH_TONE}")
    imp_vent_suffix=fst(f"-{a_morphome}{HIGH_TONE}")
    imp_it_stem=compose_stem(ALL_HIGH_TONE)
    imp_vent_stem=compose_stem(ALL_LOW_TONE)
    imp_slots = [
        (paradigms.suffix(imp_it_suffix, imp_it_stem), IMP_IT),
        (paradigms.suffix(imp_vent_suffix, imp_vent_stem), IMP_VENT),
    ]

    ipfv_it_suffix=fst(f"-{a_morphome}{LOW_TONE}")
    ipfv_it_stem = compose_stem(IPFV_AUX(HLSTAR))
    ipfv_vent_suffix=fst(f"-{o_morphome}{HIGH_TONE}")
    ipfv_vent_stem = compose_stem(IPFV_AUX(ALL_LOW_TONE))
    ipfv_slots = [
        (paradigms.suffix(ipfv_it_suffix, ipfv_it_stem), IPFV_IT),
        (paradigms.suffix(ipfv_vent_suffix, ipfv_vent_stem), IPFV_VENT),
    ]
    ipfv_slots = add_class_prefixes_to_slots(ipfv_slots)

    pfv_it_suffix = fst(f"-{e_morphome}{LOW_TONE}")
    pfv_it_stem = compose_stem(PFV_IT_AUX(HLSTAR))
    pfv_vent_suffix = ipfv_vent_suffix
    pfv_vent_stem = compose_stem(ALL_LOW_TONE)
    pfv_slots = [
        (paradigms.suffix(pfv_it_suffix, pfv_it_stem), PFV_IT),
        (paradigms.suffix(pfv_vent_suffix, pfv_vent_stem), PFV_VENT),
    ]
    pfv_slots = add_class_prefixes_to_slots(pfv_slots)

    inf_suffix = fst(f"-{a_morphome}{HIGH_TONE}")
    inf_class = 'ð'
    inf_stem = compose_stem(add_class_prefix(ALL_HIGH_TONE, inf_class, prefix_tone=HIGH_TONE))
    inf_slot = [(paradigms.suffix(inf_suffix, inf_stem), INFINITIVE)]

    dep_it_suffix = fst(f"-{e_morphome}{LOW_TONE}")
    dep_vent_suffix = fst(f"-{a_morphome}{LOW_TONE}")
    dep_stem = compose_stem(ALL_LOW_TONE)
    dep_slots = [
        (paradigms.suffix(dep_it_suffix, dep_stem), DEP_IT),
        (paradigms.suffix(dep_vent_suffix, dep_stem), DEP_VENT),
    ]
    dep_slots = add_class_prefixes_to_slots(dep_slots)

    slots = [*imp_slots, *ipfv_slots, *pfv_slots, *inf_slot, *dep_slots]
    return slots

def get_paradigm_for_class(fv_class: str):
    slots = make_verb_slots(fv_class)
    fv_paradigm = paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=f"{fv_class} class",
        slots=slots,
        lemma_feature_vector=INFINITIVE,
        stems=get_roots_for_class(fv_class, wrap_w_fsa=True),
        boundary=BOUNDARY_STR,
    )
    return fv_paradigm

AO_PARADIGM = get_paradigm_for_class("aɔ")
AQ_PARADIGM = get_paradigm_for_class("ao")
AU_PARADIGM = get_paradigm_for_class("au")
AI_PARADIGM = get_paradigm_for_class("ai")
OO_PARADIGM = get_paradigm_for_class("ɔɔ")
OU_PARADIGM = get_paradigm_for_class("ɔu")
OI_PARADIGM = get_paradigm_for_class("ɔi")

FV2PARADIGM = {
    "aɔ": AO_PARADIGM,
    "ao": AQ_PARADIGM,
    "au": AU_PARADIGM,
    "ai": AI_PARADIGM,
    "ɔɔ": OO_PARADIGM,
    "ɔu": OU_PARADIGM,
    "ɔi": OI_PARADIGM,
}

def debug_paradigm(root, paradigm):
    if type(paradigm) is str:
        paradigm = FV2PARADIGM[paradigm]
    for rule, feature_vector in paradigm.slots:
        try:
            form = decode_fst_string(fst(root)@rule)
            print(f"Successfully generated {form} from root {root} with values {feature_vector.values}")
        except:
            print(f"Error when generating {root} with values {feature_vector.values}")

def inflect_random_verb(fv_class: Optional[str]=None):
    if fv_class is None:
        fv_class = random.choice(FV_CLASSES)
    root = random.choice(get_roots_for_class(fv_class))
    print(root, fv_class)
    generate_forms(root, FV2PARADIGM[fv_class])

def inflect_verb_with_features(
        root: str,
        paradigm: Union[paradigms.Paradigm, str],
        features: Dict[str, str]
    ) -> str:
    if type(paradigm) is str:
        paradigm = FV2PARADIGM[paradigm]
    slot_for_features = [slot for slot in paradigm.slots if slot[1].values == features][0]
    rule, features = slot_for_features
    form = decode_fst_string(fst(root)@rule)

    return form

def main():
    rows = []
    for stem, fv_class in get_all_verb_roots_and_fvs():
        if fv_class=='IRREG':
            continue
        wordforms = generate_forms(stem, FV2PARADIGM[fv_class], action='return', parse=True)
        rows.extend(wordforms)
    df = pd.DataFrame(rows)
    df.to_csv(INFLECTED_VERBS_PATH, index=False)

if __name__ == '__main__':
    main()