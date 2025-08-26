"""
WIP: Script that builds FSTs for generating various inflectional forms
of nouns and verbs in Tira.
"""

import pynini
from pynini.lib import features, paradigms, rewrite, pynutil
from phoneme_inventory import *
from features import *
from lexicon import get_roots_for_class

# helper functions

def print_forms(stem: str, paradigm: paradigms.Paradigm):
    lattice = rewrite.rewrite_lattice(
        stem,
        paradigm.stems_to_forms @ paradigm.feature_label_rewriter
    )
    for wordform in rewrite.lattice_to_strings(lattice):
        print(wordform)

def add_class_prefixes_to_slots(slot_list):
    slots_w_class_prefixes = []
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        feature_values = [f"{feature}={value}" for feature, value in feature_vector.values.items()]
        for prefix in CLASS_PREFIXES:
            features_with_class = features.FeatureVector(category, f"class={prefix}", *feature_values)
            prefixed_verb = (paradigms.prefix(f"{prefix}ə̀-", stem)@DELETE_SCHWA_BEFORE_VOWEL).optimize()
            slots_w_class_prefixes.append((prefixed_verb, features_with_class))
    return slots_w_class_prefixes

# curried FV functions

VO_VENT_FV = lambda stem: paradigms.suffix("-ɔ́", stem).optimize()
VU_VENT_FV = lambda stem: paradigms.suffix("-ú", stem).optimize()
VQ_VENT_FV = lambda stem: paradigms.suffix("-ó", stem).optimize()
VI_VENT_FV = lambda stem: paradigms.suffix("-í", stem).optimize()

OV_IT_IPFV_FV = lambda stem: paradigms.suffix("-ɔ̀", stem).optimize()
AV_IT_IPFV_FV = lambda stem: paradigms.suffix("-à", stem).optimize()

VO_IT_PFV_FV = lambda stem: paradigms.suffix("-ɛ̀", stem).optimize()
VI_IT_PFV_FV = lambda stem: paradigms.suffix("-ì", stem).optimize()


AV_INF_FV = lambda stem: paradigms.suffix("-á", stem).optimize()
OV_INF_FV = lambda stem: paradigms.suffix("-ɔ́", stem).optimize()

# prefixes/auxiliaries

IPFV_AUX = lambda stem: paradigms.prefix("á-", stem).optimize()
PFV_IT_AUX = lambda stem: paradigms.prefix("à-", stem).optimize()
INFINITIVE_PREFIX = lambda stem: paradigms.prefix("ðə́-", stem).optimize()

# slots for verb paradigms

IPFV_SLOTS = {
    "aɔ": [
        (AV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VO_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
    "ao": [
        (AV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VQ_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
    "au": [
        (AV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VU_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
    "ai": [
        (AV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VI_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
    "ɔɔ": [
        (OV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VO_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
    "ɔu": [
        (OV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VU_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
    "ɔi": [
        (OV_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
        (VI_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
    ],
}

PFV_SLOTS = {
    "aɔ": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VO_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
    "ao": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VQ_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
    "au": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VU_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
    "ai": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VI_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
    "ɔɔ": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VO_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
    "ɔu": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VU_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
    "ɔi": [
        (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
        (VI_VENT_FV(ALL_LOW_TONE), PFV_VENT),
    ],
}

IPFV_SLOTS = {k: add_class_prefixes_to_slots(v) for k, v in IPFV_SLOTS.items()}
PFV_SLOTS = {k: add_class_prefixes_to_slots(v) for k, v in PFV_SLOTS.items()}

INFINITIVE_STEM = INFINITIVE_PREFIX(ALL_HIGH_TONE)@DELETE_SCHWA_BEFORE_VOWEL
INFINITIVE_SLOTS = {
    'aɔ': [(AV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
    'ao': [(AV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
    'au': [(AV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
    'ai': [(AV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
    'ɔɔ': [(OV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
    'ɔu': [(OV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
    'ɔi': [(OV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)],
}

ALL_VERB_SLOTS = [IPFV_SLOTS, PFV_SLOTS, INFINITIVE_SLOTS]

def get_slots_for_class(fv_class: str):
    slots = [slot_dict[fv_class] for slot_dict in ALL_VERB_SLOTS].sum()
    fv_paradigm = paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=f"{fv_class} class",
        slots=slots,
        lemma_feature_vector=INFINITIVE,
        stems=get_roots_for_class("aɔ"),
    )
    return fv_paradigm

AO_PARADIGM = get_slots_for_class("aɔ")
AQ_PARADIGM = get_slots_for_class("ao")
AU_PARADIGM = get_slots_for_class("au")
AI_PARADIGM = get_slots_for_class("ai")
OO_PARADIGM = get_slots_for_class("ɔɔ")
OU_PARADIGM = get_slots_for_class("ɔu")
OI_PARADIGM = get_slots_for_class("ɔi")