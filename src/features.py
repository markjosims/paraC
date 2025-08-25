"""
TODO: Script that defines feature sets for inflectional paradigms
for nouns and verbs in Tira.
"""

from pynini.lib import features

# class prefixes

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
CLASS_AGREE = features.Feature("class", *CLASS_PREFIXES)

# verb features

TAM = features.Feature(
    "tam",
    "imperfective",
    "perfective",
    "dependent",
    "infinitive",
    "imperative"
)
DEIXIS = features.Feature("deixis", "ventive", "itive")

INFLECTED_VERB = features.Category(TAM, DEIXIS, CLASS_AGREE)

# verb feature bundles

IPFV_IT = features.FeatureVector(INFLECTED_VERB, "tam=imperfective", "deixis=itive")
IPFV_VENT = features.FeatureVector(INFLECTED_VERB, "tam=imperfective", "deixis=ventive")
PFV_IT = features.FeatureVector(INFLECTED_VERB, "tam=perfective", "deixis=itive")
PFV_VENT = features.FeatureVector(INFLECTED_VERB, "tam=perfective", "deixis=ventive")