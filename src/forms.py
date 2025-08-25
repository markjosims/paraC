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

OO_IT_IPFV_FV = lambda stem: paradigms.suffix("-ɔ̀", stem).optimize()
AO_IT_IPFV_FV = lambda stem: paradigms.suffix("-à", stem).optimize()
VO_IT_PFV_FV = lambda stem: paradigms.suffix("-ɛ̀", stem).optimize()

AV_INF_FV = lambda stem: paradigms.suffix("-á", stem).optimize()
OV_INF_FV = lambda stem: paradigms.suffix("-ɔ́", stem).optimize()

ITIVE_D_STEM = C.closure() + V + pynutil.insert(HIGH_TONE) + STEM.closure()
VENTIVE_D_STEM = C.closure() + V + pynutil.insert(LOW_TONE) + STEM.closure()

ITIVE_D_STEM = ITIVE_D_STEM.optimize()
VENTIVE_D_STEM = VENTIVE_D_STEM.optimize()

# prefixes/auxiliaries

IPFV_AUX = lambda stem: paradigms.prefix("á-", stem).optimize()
PFV_IT_AUX = lambda stem: paradigms.prefix("à-", stem).optimize()
INFINITIVE_PREFIX = lambda stem: paradigms.prefix("ðə́-", stem).optimize()

# slots for verb paradigms

AO_IPFV_SLOTS = [
    (AO_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
    (VO_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
]
OO_IPFV_SLOTS = [
    (OO_IT_IPFV_FV(IPFV_AUX(HLSTAR)), IPFV_IT),
    (VO_VENT_FV(IPFV_AUX(ALL_LOW_TONE)), IPFV_VENT),
]
VO_PFV_SLOTS = [
    (VO_IT_PFV_FV(PFV_IT_AUX(HLSTAR)), PFV_IT),
    (VO_VENT_FV(ALL_LOW_TONE), PFV_VENT)
]

AO_IPFV_SLOTS = add_class_prefixes_to_slots(AO_IPFV_SLOTS)
OO_IPFV_SLOTS = add_class_prefixes_to_slots(OO_IPFV_SLOTS)
VO_PFV_SLOTS = add_class_prefixes_to_slots(VO_PFV_SLOTS)

INFINITIVE_STEM = INFINITIVE_PREFIX(ALL_HIGH_TONE)@DELETE_SCHWA_BEFORE_VOWEL
AV_INFINITIVE_SLOT = [(AV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)]
OV_INFINITIVE_SLOT = [(OV_INF_FV(INFINITIVE_STEM).optimize(), INFINITIVE)]

AO = paradigms.Paradigm(
    category=INFLECTED_VERB,
    name="AO class",
    slots=AO_IPFV_SLOTS+VO_PFV_SLOTS+AV_INFINITIVE_SLOT,
    lemma_feature_vector=INFINITIVE,
    stems=get_roots_for_class("aɔ"),
)