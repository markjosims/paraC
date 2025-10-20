"""
Script that builds FSTs for generating various inflectional forms of verbs in Tira.
"""

import pynini
from pynini.lib import features, paradigms
import pandas as pd
from src.form_builders.form_helpers import add_class_prefix, add_class_prefixes_to_slots, generate_forms
from src.phonology import *
from src.fst_helpers import *
from src.lexicon import get_roots_for_class, get_all_verb_roots_and_fvs, get_gloss_for_verb
from src.glossing import REMOVE_HOMOPHONE_TAG
from src.constants import INFLECTED_VERBS_PATH, INFLECTED_VERB
from typing import *
import random

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

# person marking

def add_imperfective_personal_markers(
    slots: List[tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Adds personal markers to imperfective verb forms in the given slots.
    Personal markers for imperfective verbs have the following forms:
    Subject (second form is when 3sg object is present):
        1sg: íŋ-g-
        2sg: á-g-
        3sg: ŋg-
        1du.incl: á-l-
        1pl.incl: á-l- -ŕ
        1pl.excl: ɲà-l-
        2pl: ɲá-l-
        3pl: l-
    Subject w/ 3sg object (takes place of or includes Aux /a/):
        1sg: ŋg- é-
        2sg: ng- á-
        3sg: ŋg- á-
        1du.incl: ŋg- ál-
        1pl.incl: ŋg- ál- -ŕ
        1pl.excl: ŋg- éɲâ- (blocks H-tone spreading onto verb)
        2pl: ŋg- éɲá-
        3pl: ŋg- á- l̀- (blocks H-tone spreading onto verb)
    Subject w/ 3pl object (takes place of or includes Aux /a/):
        1sg: l- é- ĺ-
        2sg: l- á- ĺ-
        3sg: l- á- ŋə́- ĺ-
        1du.incl: l- á- ló-
        1pl.incl: l- á- ló- -ŕ
        1pl.excl: l- éɲâ- ĺ
        2pl: l- éɲá- ĺ-
        3pl: l- á- l̀- ló-
    Subject w/ 3pl object:
    Object: (takes place of Aux /a/)
        1sg: -éŋî-
        2sg: -áŋâ-
        3sg: kə̀-
        1du.incl: -átɛ́-
        1pl.incl: -átɛ́- -ŕ
        1pl.excl: -ɛ́ɲár-
        2pl: -átɛ́-
        3pl: CL-a-l(ó)-
    """
    ...

def add_perfective_personal_markers(
    slots: List[tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Adds personal markers to perfective verb forms in the given slots.
    Subject:
        1sg: jɛ́-
        2sg: á-
        3sg: CL-
        1du.incl: lə́-
        1pl.incl: lə́- -ŕ
        1pl.excl: ɲà-
        2pl: ɲá-
        3pl: CL-
    Subject w/ 3sg object:
        1sg: CL-  -ɛ́ŋí
        1sg: CL-  -áŋá
        3sg: CL-  -ŋ(ú)
        1du.incl: CL-  -álí
        1pl.incl: CL-  -álí -r
        1pl.excl: CL-  -áɲâ
        2pl: CL- -áɲá
        3pl: CL- -ɜ́l
    Subject w/ 3pl object:
        1sg: CL- -ɛ́-ló
        2sg: CL- -á-ló
        3sg: CL- -l -ɔ́ŋ(ú)
        1du.incl: CL- -álí
        1pl.incl: CL- -álí -r
        1pl.excl: CL- -áɲâ-l
        2pl: CL- -áɲá-l
        3pl: CL- -ɜ́l-ló
    Object:
        1sg: -ɛ́ŋî
        2sg: -áŋâ
        3sg: kə̀-, -ŋú
        1du.incl: -átɛ́
        1pl.incl: -átɛ́-ŕ
        1pl.excl: -ɛ́ɲárɛ́
        2pl: -átɛ́
        3pl: CL-
    """
    ...

def add_imperative_object_markers(
    slots: List[tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Object:
        3pl: -l̀
    """

    

# slots for verb paradigms

def make_verb_slots(fv_class: str) -> Dict[str, List[Tuple[pynini.Fst, features.FeatureVector]]]:
    root_slot = (STEM, VERB_ROOT)

    a_morphome = CLASS2FV[fv_class]["a_morphome"]
    o_morphome = CLASS2FV[fv_class]["o_morphome"]
    e_morphome = CLASS2FV[fv_class]["e_morphome"]

    is_OV = a_morphome == 'ɔ'
    
    prepare_root_for_inflection = REMOVE_HOMOPHONE_TAG@ADD_PLACEHOLDER_TBU
    finalize_form = FLOAT_TONE_RULE@COMBINE_TONES_RULE

    compose_stem = lambda stem_rule: prepare_root_for_inflection@stem_rule@finalize_form
    compose_stem_harmony = lambda stem_rule: prepare_root_for_inflection\
        @ROUNDING_HARMONY\
        @stem_rule\
        @finalize_form

    ####################
    # Imperative forms #
    ####################

    imp_it_suffix=fst(f"-{o_morphome}{HIGH_TONE}")
    if is_OV and o_morphome == 'ɔ':
        imp_it_stem=compose_stem_harmony(ALL_HIGH_TONE_RULE)
    else:
        imp_it_stem=compose_stem(ALL_HIGH_TONE_RULE)

    imp_vent_suffix=fst(f"-{a_morphome}{HIGH_TONE}")
    if is_OV:
        imp_vent_stem=compose_stem_harmony(ALL_LOW_TONE_RULE)
    else:
        imp_vent_stem=compose_stem(ALL_LOW_TONE_RULE)
    imp_slots = [
        (paradigms.suffix(imp_it_suffix, imp_it_stem), IMP_IT),
        (paradigms.suffix(imp_vent_suffix, imp_vent_stem), IMP_VENT),
    ]

    ######################
    # Imperfective forms #
    ######################

    ipfv_it_suffix=fst(f"-{a_morphome}{LOW_TONE}")
    if is_OV:
        ipfv_it_stem = compose_stem_harmony(IPFV_AUX(HLSTAR_RULE))
    else:
        ipfv_it_stem = compose_stem(IPFV_AUX(HLSTAR_RULE))

    ipfv_vent_suffix=fst(f"-{o_morphome}{HIGH_TONE}")
    if is_OV and o_morphome == 'ɔ':
        ipfv_vent_stem = compose_stem_harmony(IPFV_AUX(ALL_LOW_TONE_RULE))
    else:
        ipfv_vent_stem = compose_stem(IPFV_AUX(ALL_LOW_TONE_RULE))
    ipfv_slots = [
        (paradigms.suffix(ipfv_it_suffix, ipfv_it_stem), IPFV_IT),
        (paradigms.suffix(ipfv_vent_suffix, ipfv_vent_stem), IPFV_VENT),
    ]
    ipfv_slots = add_class_prefixes_to_slots(ipfv_slots)

    ####################
    # Perfective forms #
    ####################

    pfv_it_suffix = fst(f"-{e_morphome}{LOW_TONE}")
    pfv_it_stem = compose_stem(PFV_IT_AUX(HLSTAR_RULE))

    pfv_vent_suffix = ipfv_vent_suffix
    if is_OV and o_morphome == 'ɔ':
        pfv_vent_stem = compose_stem_harmony(ALL_LOW_TONE_RULE)
    else:
        pfv_vent_stem = compose_stem(ALL_LOW_TONE_RULE)
    pfv_slots = [
        (paradigms.suffix(pfv_it_suffix, pfv_it_stem), PFV_IT),
        (paradigms.suffix(pfv_vent_suffix, pfv_vent_stem), PFV_VENT),
    ]
    pfv_slots = add_class_prefixes_to_slots(pfv_slots)

    ##############
    # Infinitive #
    ###############

    inf_suffix = fst(f"-{a_morphome}{HIGH_TONE}")
    inf_class = 'ð'
    if is_OV:
        inf_stem = compose_stem_harmony(add_class_prefix(
            ALL_HIGH_TONE_RULE,
            inf_class,
            prefix_tone=HIGH_TONE,
        ))
    else:
        inf_stem = compose_stem(add_class_prefix(
            ALL_HIGH_TONE_RULE,
            inf_class,
            prefix_tone=HIGH_TONE,
        ))
    inf_slot = [(paradigms.suffix(inf_suffix, inf_stem), INFINITIVE)]

    ###################
    # Dependent forms #
    ###################

    dep_it_suffix = fst(f"-{e_morphome}{LOW_TONE}")
    dep_it_stem = compose_stem(ALL_LOW_TONE_RULE)

    dep_vent_suffix = fst(f"-{a_morphome}{LOW_TONE}")
    if is_OV:
        dep_vent_stem = compose_stem_harmony(ALL_LOW_TONE_RULE)
    else:
        dep_vent_stem = dep_it_stem

    dep_slots = [
        (paradigms.suffix(dep_it_suffix, dep_it_stem), DEP_IT),
        (paradigms.suffix(dep_vent_suffix, dep_vent_stem), DEP_VENT),
    ]
    dep_slots = add_class_prefixes_to_slots(dep_slots)

    slots = [root_slot, *imp_slots, *ipfv_slots, *pfv_slots, *inf_slot, *dep_slots]
    return slots

def get_paradigm_for_class(fv_class: str):
    slots = make_verb_slots(fv_class)
    fv_paradigm = paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=f"{fv_class} class",
        slots=slots,
        lemma_feature_vector=VERB_ROOT,
        stems=get_roots_for_class(fv_class, wrap_w_fsa=True),
        boundary=fst(BOUNDARY_STR),
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
PARADIGM2FV = {v:k for v,k in FV2PARADIGM.items()}

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
    """
    Arguments:
        root:       str indicating verb root to inflect
        paradigm:   Paradigm object or str of FV class shorthand e.g. 'aɔ'
        features:   dict mapping feature labels to values
    Returns:
        form:       str of root verb inflected with given features
    """
    if type(paradigm) is str:
        paradigm = FV2PARADIGM[paradigm]
    expected_keys = [feature.name for feature in INFLECTED_VERB.features]
    features_filtered = {k:v for k,v in features.items() if k in expected_keys}
    slot_for_features = [slot for slot in paradigm.slots if slot[1].values == features_filtered][0]
    rule, _ = slot_for_features
    form = decode_fst_string(fst(root)@rule)

    return form

def get_inflected_paradigm_for_verb(
        root: str,
        paradigm: Union[paradigms.Paradigm, str],
) -> Dict[str, Any]:
    """
    Arguments:
        root:               str indicating verb root to inflect
        paradigm:           Paradigm object or str of FV class shorthand e.g. 'aɔ'
    Returns:
        inflected_paradigm: dict mapping feature values to inflected forms of the verb
    """
    if type(paradigm) is str:
        fv_class = paradigm
        paradigm = FV2PARADIGM[paradigm]
    else:
        fv_class = PARADIGM2FV[paradigm]
    gloss = get_gloss_for_verb(root)
    inflected_paradigm = {"root": root, "fv": fv_class, "gloss": gloss}

    finite_class = "l"
    for tam_value in DEIXIS_MARKED_TAM+SUBJECT_AND_DEIXIS_MARKED_TAM:
        inflected_paradigm[tam_value]={}
        class_value = finite_class
        if tam_value == 'imperative':
            class_value = 'unmarked'
        for deixis_value in DEIXIS_VALUES:
            form = inflect_verb_with_features(
                root=root,
                paradigm=paradigm,
                features={
                    "tam": tam_value,
                    "deixis": deixis_value,
                    "class": class_value,
                }
            )
            inflected_paradigm[tam_value][deixis_value]=form
    inflected_paradigm['infinitive']=inflect_verb_with_features(
        root=root,
        paradigm=paradigm,
        features={
            "tam": "infinitive",
            "deixis": "unmarked",
            "class": "ð",
        }
    )
    return inflected_paradigm

def parse_inflected_verb(
        form: str,
        paradigm: Union[paradigms.Paradigm, str, None]=None,
        add_gloss: bool=True,
) -> Dict[str, str]:
    """
    Arguments:
        form:       str of inflected verb form
        paradigm:   Paradigm object or str of FV class shorthand e.g. 'aɔ'
    Returns:        dict of shape {'root': root, '$feature': feature_value}
    """
    parses = []

    if paradigm is None:
        for _, paradigm in FV2PARADIGM.items():
            parses_for_fv = parse_inflected_verb(form, paradigm, add_gloss)
            parses.extend(parses_for_fv)
    if type(paradigm) is str:
        paradigm = FV2PARADIGM[paradigm]

    lemmata = paradigm.lemmatize(fst(form))
    analyzed_forms = paradigm.analyze(fst(form))
    for lemma, analyzed_form in zip(lemmata, analyzed_forms):
        root, feature_vec = lemma
        root = decode_byte_str(root)

        analyzed_form = analyzed_form[0]
        analyzed_form = decode_byte_str(analyzed_form)

        parse = feature_vec.values
        parse['root'] = root
        parse['analyzed_form'] = analyzed_form
        parse['form'] = form
        if add_gloss:
            parse['gloss'] = get_gloss_for_verb(root)
        parses.append(parse)
    return parses


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