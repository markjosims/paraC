"""
# features.py
This module defines morphological and lexical features used by the Tira parser.
Morphological features are specific to each part of speech (verb, auxiliary, adjective,
noun, pronoun). Lexical features apply to all categories, and indicate either (1)
tonal processes that can occur regardless of part of speech or (2) information about
the words part of speech or lexical class.

Morphological features are used to build inflectional paradigms. A `pynini.lib.paradigms.Paradigm`
object takes a list of slots where each slot is a tuple of `(rule_fst, feature_vector)`.
The `rule_fst` is an FST describing a relation between strings, and the `feature_vector`
is a `pynini.lib.features.FeatureVector` object indicating the morphological features marked by
the string relation.

Lexical features are bit of an ad-hoc extension I hacked together for the Tira parser.
The make use of the `FeatureVector` object, but instead of associating with a slot in
a paradigm, they attach to an entire paradigm. This is useful because in `src/parser.py`
I define FSTs over the entire lexicon, and use `FeatureVector` objects specifying lexical
features to encode information pertaining to lexical class or to other string relations
which can apply regardless of part of speech (in particular, tone processes such as High
Tone Spreading and Final Lowering).
"""

from pynini.lib import features

"""
## Class prefixes
Tira has a system of *noun classes* where each noun is marked for a category,
similar to gender in Indo-European languages. Noun classes are associated with
distinct prefixes, e.g. "j-class" or "n-class". Verbs and adnominals show agreement
with a noun by bearing a prefix corresponding to the noun's inherent class, as
shown with -icəlo 'good' in the examples below.

    àpɾí        j-ícə̀lò
    (CLj)boy    CLj-good
    "The boy is good"

    ŋ-ɛ̂n        ŋ-ìcə̀lò
    Clŋ-dog     Clŋ-good
    "The dog is good"

Class agreement is shown on verbs, adjectives, and a few other adnominals
like possessive and demonstrative pronouns, and the genitive marker, which agrees
in class with the possessum (item possessed).

Class agreement is handled with the `CLASS_AGREE` feature, which depends on the
`CLASS_PREFIXES` constant that lists all unique class prefixes.
"""

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


"""
## Verb features
Verbs in Tira are marked for class, subject, object, tense/aspect/mood (TAM) and deixis.
Morphologically, verbs follow the general structure of:

1. Verb.stem-Final.Vowel
    və̀lɛ̀ð-á
    pull-FV
    "pull here!"
2. Class.prefix-Verb.stem-Final.Vowel
    lə̀-və̀lɛ̀ð-ɔ́
    CLl-pull-FV
    "they pulled"
3. Class.prefix-Verbal.auxiliary   Verb.stem-Final.Vowel
    l-á və́lɛ̀ð-à
    CLl-Aux pull-FV

Class prefixes are described in the section above, and verbal auxiliaries (Aux) in the next
section. The Final Vowel (FV) suffix is a suffix that follows the verb stem. The particular
vowel it conssits of varies as a function of inflectional features of the verb (specifically,
TAM and deixis), and also based on the particular verb root. See `src/forms/verb_forms.py`
for more details.

### Class
See above.

### Subject/object
Verbs do not show subject or object agreement *per se*, rather subject and object
pronouns attach to verb stem, e.g.

    kúkù        kə̀-və̀lɛ̀ð-ɔ́
    (Clg)Kuku   Clg-pull-FV
    "Kuku pulled"

    jɛ́-və̀lɛ̀ð-ɔ́
    1sg-pull-FV
    "I pulled"

Subject and object pronouns can be marked for person (1/2/3), clusivity (inclusive/exclusive)
and number (singular, dual, plural). The following combinations of features are valid in Tira:

- 1 singular
- 2 singular
- 3 singular
- 1 dual
- 1 plural inclusive
- 1 plural exclusive
- 2 plural
- 3 plural

The `SUBJECT_PERSON_AND_NUMBER` and `OBJECT_PERSON_AND_NUMBER` feature classes fuse the three
features of person, clusivity and number into one, with one feature value for each of the eight
possible combinations.

### Tense, aspect, mood
Tense refers to the time of an event, aspect to the temporal structure and mood to the epistemic
reality of the event. These three conceptual categories are combined into one feature, abbreviated
as TAM. Possible TAM values for Tira include:

- Infinitive (unmarked verb form)
- Imperative (command)
- Perfective (completed action)
- Progressive (action in progress) TODO: not implemented yet!
- Imperfective (incompleted action)
- Dependent (verb in a subordinate clause)

### Deixis
Deixis refers to motion or location associated with a verb. There are two categories of verbal
deixis in Tira: itive and ventive. Itive denotes motion away from the speaker or, for static verbs,
a verb which occurs near the speaker. Ventive denotes motion toward the speaker or, for static verbs,
a verb which occurs away from the speaker. Both deixis values can combine with any TAM value in Tira
except for the infinitive, which is unmarked for deixis.
"""

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
VERB_FEATURE_BUNDLES = [
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

"""
## Verbal auxiliary
Tira has a verbal auxiliary which is the vowel /a/. This auxiliary appears in the imperfective and progressive
aspects, and with the perfective ventive. This is shown below with the itive/ventive imperfective/perfective forms
of the verb *vəlɛð* 'pull.'

                Itive                   Ventive
Imperfective    l-á     və́lɛ̀ð-à         l-á     və̀lɛ̀ð-ɔ́
                CLl-Aux pull-FV         CLl-Aux pull-FV
Perfective      l-à     və́lɛð-ɛ̀         lə̀-və̀lɛ̀ð-ɔ́
                CLl-Aux pull-FV         CLl-pull-FV
        
Here all forms except for the perfective ventive have a preceding auxiliary /a/. In the perfective ventive,
the class prefix attaches directly to the verb, since there is no auxiliary. In the remaining forms, the
auxiliary /a/ takes the class prefix instead. The auxiliary participates in aspect marking since a high toned
auxiliary /á/ is associated with the imperfective and a low toned /à/ with the perfective itive.

In short, verbal exponence is cumulative across the auxiliary and the verb stem (Hagen Kaldhol 2024).
I use the same set of features for verb stems and verb auxiliaries. For more information on how verb forms
are built in the Tira parser, see src/forms/verb_forms.py.
"""

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


"""
## Noun features
Nouns in Tira are marked for case and number.

### Case
Two case values are marked in Tira, nominative and accusative. Broadly speaking, nominative denotes the subject of
a verb and accusative the object. In Tira, nominative is the 'unmarked' or default case: nouns are nominative if they
are the subject of the sentence, the object of an adposition, or a verbal object that has been fronted. Accusative case
marks the direct and indirect objects of a verb *assuming they follow the verb* in the sentence. Some examples of nominative
and accusative case are given below.

ð-ɔ̀ndɔ̀          ð-ìcə̀lò
CLð-gourd.NOM   CLð-good
"The gourd is good"

í-ŋɡ-á  nɔ́n-à   ðɔ̀nd-à      nd̪ɔ̀bà
1sg-CLg see-FV  gourd-ACC   tomorrow

### Number
Nominal number in Tira is marked as a function of noun class. That is, noun roots generally take one of two classes, where
one class marks the singular and another class marks the plural.

ŋ-ɛ̂n        ɲ-ɛ̂n
CLŋ-dog     CLɲ-dog
"dog"       "dogs"

ð-ɔ̀mɔ̀cɔ̀     r-ɔ̀mɔ̀cɔ̀
CLð-man     CLr-man
"man"       "men"

The word 'dog' takes *ŋ* class agreement in the singular and *ɲ* class in the plural, and the word 'man' takes *ð*
class agreement in the singular and *r* class agreement in the plural.

As depicted in the trilinear glosses above, normally in Tira literature we do not gloss number directly on the noun,
instead glossing the class membership. For the time being, the Tira parser mark singular/plural directly as opposed to class
membership on nouns. This simplifies the code (since there are only two number values, but at least 9 noun classes),
but deviates from annotation standards for Tira. This behavior might change at a later date.
"""

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

"""
## Wh Pronoun
Wh pronouns in Tira are marked for case and number like regular nouns, e.g.
ɔ́ɟɔ́ (who-NOM.SG) ɔ́ɟɔ́-ŋá (who-ACC.SG).
"""

WH_PRONOUN = features.Category(
    NOUN_CASE,
    NOUN_NUMBER,
)
WH_PRONOUN_ROOT = features.FeatureVector(WH_PRONOUN, "case=unmarked", "number=unmarked")

"""
## Inalienable noun
While possession in Tira is typically conveyed with a possessive pronoun
(see Pronouns below), a subset of nouns in Tira are *inalienably possessed*.
This means that they cannot occur without a possessive *suffix* indicating
the possessor. These suffixes are particular to inalienably possessed nouns.

1sg/1excl   -ɛ́j/áj
2sg/2pl     -àló
3sg/3pl     -ɛ́n
1du         -ɜ̀lí
1incl       -ɜ̀lír

Inalienably possessed are generally kinship terms, e.g. ðɛt̪- 'father'
and íd̪ɛ́r- 'maternal uncle/aunt'.

"""

POSSESSOR_PERSON = features.Feature(
    "possessor",
    "unmarked",
    *PERSON_AND_NUMBER_VALUES
)
INALIENABLE_NOUN = features.Category(
    NOUN_CASE,
    NOUN_NUMBER,
    POSSESSOR_PERSON,
)

NOMSG_INALIENABLE = features.FeatureVector(NOUN, "case=nominative", "number=singular")
NOMPL_INALIENABLE = features.FeatureVector(NOUN, "case=nominative", "number=plural")

ACCSG_INALIENABLE = features.FeatureVector(NOUN, "case=accusative", "number=singular")
ACCPL_INALIENABLE = features.FeatureVector(NOUN, "case=accusative", "number=plural")

INALIENABLE_NOUN_ROOT = features.FeatureVector(
    INALIENABLE_NOUN,
    "case=unmarked",
    "number=unmarked",
    "possessor=unmarked"
)
INALIENABLE_NOUN_FEATURE_ABBREVIATION_TO_VECTOR = {
    "nom.sg": NOMSG_INALIENABLE,
    "nom.pl": NOMPL_INALIENABLE,
    "acc.sg": ACCSG_INALIENABLE,
    "acc.pl": ACCPL_INALIENABLE,
}
INALIENABLE_NOUN_FEATURE_ABBREVIATIONS = list(INALIENABLE_NOUN_FEATURE_ABBREVIATION_TO_VECTOR.keys())

"""
## Adjective features
Adjectives in Tira (which, syntactically speaking, might not be true adjectives, but rather stative verbs) are marked with
class agreeing with the noun they modify, as indicated in the earlier example repeated here.

    àpɾí        j-ícə̀lò
    (CLj)boy    CLj-good
    "The boy is good"

    ŋ-ɛ̂n        ŋ-ìcə̀lò
    Clŋ-dog     Clŋ-good
    "The dog is good"

Note the term 'adnominal' as used here is inclusive to both adjectives and demonstrative pronouns.
"""

ADNOMINAL_CLASS_VALUES = CLASS_PREFIXES
ADNOMINAL_CLASS = features.Feature("class", "unmarked", *ADNOMINAL_CLASS_VALUES)
ADJECTIVE = features.Category(ADNOMINAL_CLASS)
ADJECTIVE_ROOT = features.FeatureVector(ADJECTIVE, "class=unmarked")

"""
## Demonstrative
Demonstratives, like adjectives, are marked with a class prefix agreeing with the noun they modify. There are
three demonstrative pronouns in Tira, the proximal demonstrative CL-ɛ́ (equivalent to 'this' in English) and the
distal demonstrative CL-âj (equivalent to 'that' in English), and locative distal demonstrative CL-ɔ̂n (equivalent
to 'that/there' in English).
"""

DEMONSTRATIVE = features.Category(ADNOMINAL_CLASS)
DEMONSTRATIVE_ROOT = features.FeatureVector(DEMONSTRATIVE, "class=unmarked")

"""
## Possessive pronoun
Possessive pronouns in Tira agree in class with the noun they modify and are marked for person and number
of the possessor.
"""

POSSESSIVE_PRONOUN = features.Category(ADNOMINAL_CLASS, POSSESSOR_PERSON)
POSSESSIVE_PRONOUN_ROOT = features.FeatureVector(POSSESSIVE_PRONOUN, "class=unmarked")

"""
## Possessive marker
The possessive marker CL-ɛ̀ agrees in class with the possessum (item possessed), and as such shares the
same feature as other adnominal categories.
"""

POSSESSIVE_MARKER = features.Category(ADNOMINAL_CLASS)
POSSESSIVE_MARKER_ROOT = features.FeatureVector(POSSESSIVE_MARKER, "class=unmarked")

"""
## Lexical features
Different from the morphological features defined above, these 'features' apply to all parts of speech.
They are used in `src/parser.py` to specify lexical information for an entire paradigm, so that FSTs for
individual paradigms can be combined into one main parser.

### Part of speech
Parts of speech include noun, inalienable noun, pronoun, verb, aux, adjective, adverb, postposition,
preposition, conjunction, interjection and particle.

Adverbs, postpositions, prepositions, conjunctions and particles are all considered 'uninflected' words,
and lack any morphological features of their own.

### Final Vowel
This is a tag marking the Final Vowel Class of the given verb stem. While only pertinent to verbs,
this is included as a *lexical* feature because it is an immutable feature of a particular verb
stem (where stem is a verb root or root + extension suffix), and not a feature that changes with
inflection. See `src/forms/verb_forms.py` for more information.

For parts of speech other than verbs, the Final Vowel feature is set to 'unmarked'.

### Aux
This is a tag indicating whether the verb form includes in auxiliary or not. Verb forms that
lack an auxiliary (e.g. imperative, perfective ventive) have Aux set to False by necessity.
Verb forms where an auxiliary is present have two paradigms: one paradigm that consists only
of the verb stem without the auxiliary, and another where both auxiliary and verb stem are
included in the same string. See `src/forms/verb_forms.py` for more information.

Like Final Vowel, Aux is set to 'unmarked' for parts of speech other than verbs.

### Final_lowering
Final lowering is a tonal process whereby a high tone at the end of a word in sentence-final
position is lowered.

àpɾí        j-á         və́lɛ̀ð-à
(CLj)boy    CLj-Aux     pull-FV
"The boy pulled"

àpɾì
(Clj)boy
"The boy"

Notice that the high tone at the end of àpɾí "boy" becomes low, àpɾì, when the word is at
the end of the sentence.

### Left High
This 'feature' describes words where a high tone attaches to the left edge of the word.
This can happen for various reasons, including high tone spreading from a previous word,
or grammatical high tone insertion from e.g. focus or locative constructions.
See `src/lexicon/phonology.py` for more information.
"""

POS2CATEGORY = {
    'noun': NOUN,
    'wh_pronoun': WH_PRONOUN,
    'inalienable_noun': INALIENABLE_NOUN,
    'adjective': ADJECTIVE,
    'demonstrative': DEMONSTRATIVE,
    'possessive_pronoun': POSSESSIVE_PRONOUN,
    'possessive_marker': POSSESSIVE_MARKER,
    'verb': INFLECTED_VERB,
    'aux': INFLECTED_AUX,
    'adverb': None,
    'postposition': None,
    'adposition': None,
    'conjunction': None,
    'particle': None,
    'interjection': None,
}

POS2ROOT_VECTOR = {
    'noun': NOUN_ROOT,
    'wh_pronoun': WH_PRONOUN_ROOT,
    'inalienable_noun': INALIENABLE_NOUN_ROOT,
    'adjective': ADJECTIVE_ROOT,
    'demonstrative': DEMONSTRATIVE_ROOT,
    'possessive_pronoun': POSSESSIVE_PRONOUN_ROOT,
    'possessive_marker': POSSESSIVE_MARKER_ROOT,
}

INFLECTED_POS = [
    k for k, v in POS2CATEGORY.items() if v is not None
]


POS_TAG = features.Feature(
    "part_of_speech", "unmarked", *POS2CATEGORY.keys()
)

FV_TAG = features.Feature("fv", "unmarked", *FV_CLASSES)

# binary features
AUX_TAG = features.Feature("aux", "unmarked", "true")
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

"""
Here I define constants aggregating all features across all categories.
"""

FEATURES_TO_VALUES = {}
for category in [INFLECTED_VERB, INFLECTED_AUX, NOUN, ADJECTIVE, LEXEME]:
    for feature in category.features:
        if feature.name not in FEATURES_TO_VALUES:
            FEATURES_TO_VALUES[feature.name] = feature.values

ALL_FEATURE_STRS = []
for feature_name, feature_values in FEATURES_TO_VALUES.items():
    for feature_value in feature_values:
        ALL_FEATURE_STRS.append(f"{feature_name}={feature_value}")

"""
This is a mapping from full feature names to abbreviations used in glosses.
"""

FEATURE2ABBREVIATION = {
    'nominative': 'NOM',
    'accusative': 'ACC',
    'singular': 'SG',
    'plural': 'PL',
    'infinitive': 'INF',
    'imperative': 'IMP',
    'imperfective': 'IPFV',
    'perfective': 'PFV',
    'dependent': 'DEP',
    'progressive': 'PROG',
    'itive': 'IT',
    'ventive': 'VENT',
}

"""
Certain parts of speech with similar inflectional behaviors are grouped
in lexical data loading functions. Here I define a mapping from group names
to lists of parts of speech.
"""

POS_GROUPS = {
    'nominal': ['noun', 'wh_pronoun'],
    'adnominal': ['demonstrative', 'possessive_pronoun', 'possessive_marker'],
}