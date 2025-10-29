"""
Script that builds FSTs for generating various inflectional forms of verbs in Tira.
"""

import pynini
from pynini.lib import features, paradigms
import pandas as pd
from src.form_builders.form_helpers import *
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

# person marking

def build_imperfective_aux_forms() -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Returns:
        slots: List of Tuples of (FST, FeatureVector) representing perfective itive auxiliary forms

    Builds perfective itive auxiliary forms with personal markers.
    Personal markers for perfective itive verbs have the following forms:
    Subject w/ nominal object:
        1sg: íŋ-g-
        2sg: á-g-
        3sg: ŋg-
        1du.incl: á-l
        1pl.incl: á-l -ŕ
        1pl.excl: ɲà-l
        2pl: ɲá-l
        3pl: l-
    Subject w/ 3sg object (takes place of or includes Aux /a/):
        1sg:  CL-ɛ́
        2sg:  CL-á
        3sg:  CL-á-l
        1du.incl:  CL-á-l
        1pl.incl:  CL-á-l- -ŕ
        1pl.excl:  CL-éɲâ (blocks H-tone spreading onto verb)
        2pl:  CL-éɲá
        3pl:  CL-á-l- (blocks H-tone spreading onto verb)
    Subject w/ 3pl object (takes place of or includes Aux /a/):
        1sg: l- ɛ́- ĺ
        2sg: l- á- ĺ
        3sg: l- á- ŋə́- ĺ
        1du.incl: l- á- ló
        1pl.incl: l- á- ló -ŕ
        1pl.excl: l- éɲâ- ĺ
        2pl: l- éɲá- ĺ
        3pl: l- á- l- ló
    Object: (takes place of Aux /a/)
        1sg: -á-ŋɛ̂-
        2sg: -á-ŋâ-
        3sg: CL-
        1du.incl: -á-tɛ́-
        1pl.incl: -á-tɛ́-
        1pl.excl: -éɲár-
        2pl: -á-tɛ́-
        3pl: CL-á-l(ó)-
    """
    tamd_strs = ["tam=imperfective", "deixis=unmarked"]
    def get_features(sbj: str='unmarked', obj: str='unmarked', cl: str='unmarked') -> List[str]:
        features_list = [INFLECTED_AUX]
        features_list.extend(tamd_strs)
        features_list.append(f"subject={sbj}")
        features_list.append(f"object={obj}")
        features_list.append(f"class={cl}")
        return features.FeatureVector(*features_list)
    
    # make non-pronominal slots
    non_pronominal_slots = add_class_prefixes_to_slots([(insert_fst("á"), get_features())], include_ng=True)

    # subject marking
    subject_prefixes_slots = [
        (insert_fst("íŋ-g-á"), get_features(sbj='1sg', cl='g')),
        (insert_fst("á-g-á"), get_features(sbj='2sg', cl='g')),
        (insert_fst("á-l-á"), get_features(sbj='1du.incl', cl='l')),
        (insert_fst("á-l-á"), get_features(sbj='1pl.incl', cl='l')),
        (insert_fst("ɲà-l-á"), get_features(sbj='1pl.excl', cl='l')),
        (insert_fst("ɲá-l-á"), get_features(sbj='2pl', cl='l')),
    ]

    # subject with 3sg object
    subject_suffixes_3sg_obj = [
        (insert_fst("ɛ́"), get_features(sbj='1sg', obj='3sg')),
        (insert_fst("á"), get_features(sbj='2sg', obj='3sg')),
        (insert_fst("á-l"), get_features(sbj='3sg', obj='3sg')),
        (insert_fst("á-l"), get_features(sbj='1du.incl', obj='3sg')),
        (insert_fst("á-l"), get_features(sbj='1pl.incl', obj='3sg')),
        (insert_fst("éɲâ"), get_features(sbj='1pl.excl', obj='3sg')),
        (insert_fst("éɲá"), get_features(sbj='2pl', obj='3sg')),
        (insert_fst("á-l"), get_features(sbj='3pl', obj='3sg')),
    ]
    subject_suffixes_3sg_obj_slots = add_class_prefixes_to_slots(subject_suffixes_3sg_obj, include_ng=True)

    # subject with 3pl object
    subject_suffixes_3pl_obj = [
        (insert_fst("ɛ́-ĺ"), get_features(sbj='1sg', obj='3pl')),
        (insert_fst("á-ĺ"), get_features(sbj='2sg', obj='3pl')),
        (insert_fst("á-ŋə́-ĺ"), get_features(sbj='3sg', obj='3pl')),
        (insert_fst("á-ló"), get_features(sbj='1du.incl', obj='3pl')),
        (insert_fst("á-ló"), get_features(sbj='1pl.incl', obj='3pl')),
        (insert_fst("éɲâ-ĺ"), get_features(sbj='1pl.excl', obj='3pl')),
        (insert_fst("éɲá-ĺ"), get_features(sbj='2pl', obj='3pl')),
        (insert_fst("á-l-ló"), get_features(sbj='3pl', obj='3pl')),
    ]
    subject_suffixes_3pl_obj_slots = add_class_prefixes_to_slots(subject_suffixes_3pl_obj, include_ng=True)

    # object marking
    object_suffixes = [
        (suffix("-ŋɛ̂"), get_features(obj='1sg')),
        (suffix("-ŋâ"), get_features(obj='2sg')),
        (suffix("-tɛ́"), get_features(obj='1du.incl')),
        (suffix("-tɛ́"), get_features(obj='1pl.incl')),
        (suffix("-éɲár"), get_features(obj='1pl.excl')),
        (suffix("-tɛ́"), get_features(obj='2pl')),
        (suffix("-ĺ")|suffix("-"), get_features(obj='3pl')),
    ]
    object_slots = [
        (insert_fst('á')@rule@VOWEL_COALESCENCE_RULE, features_vec)
        for rule, features_vec in object_suffixes
    ]
    object_slots = add_class_prefixes_to_slots(object_slots, include_ng=True)

    # joint subject+object marking
    subject_object_slots = []
    for sbj_rule, sbj_features_vec in subject_prefixes_slots:
        for obj_rule, obj_features_vec in object_suffixes:
            subject_feature = sbj_features_vec.values['subject']
            class_feature = sbj_features_vec.values['class']
            object_feature = obj_features_vec.values['object']
            if subject_feature.startswith('1') and object_feature.startswith('1'):
                # avoid duplicating 1st person markers
                continue
            if subject_feature.startswith('2') and object_feature.startswith('2'):
                # avoid duplicating 2nd person markers
                continue
            combined_features_vec = get_features(
                sbj=subject_feature,
                obj=object_feature,
                cl=class_feature
            )
            subject_object_slots.append((
                sbj_rule@obj_rule@VOWEL_COALESCENCE_RULE,
                combined_features_vec
            ))
    
    slots = non_pronominal_slots\
        + subject_prefixes_slots\
        + subject_suffixes_3sg_obj_slots\
        + subject_suffixes_3pl_obj_slots\
        + object_slots\
        + subject_object_slots
    for rule, _ in slots:
        rule.optimize() 
    return slots

def build_itive_perfective_aux_forms() -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Returns:
        slots: List of Tuples of (FST, FeatureVector) representing perfective itive auxiliary forms

    Builds perfective itive auxiliary forms with personal markers.
    Personal markers for perfective itive verbs have the following forms:
    Subject w/ nominal object:
        1sg: íŋ-g-
        2sg: á-g-
        3sg: ŋg-
        1du.incl: á-l-
        1pl.incl: á-l- -ŕ
        1pl.excl: ɲà-l-
        2pl: ɲá-l-
        3pl: l-
    Subject w/ 3sg object (takes place of or includes Aux /a/):
        1sg:  CL-ɛ̀
        2sg:  CL-à
        3sg:  CL-à-l
        1du.incl:  CL-á-l
        1pl.incl:  CL-á-l- -ŕ
        1pl.excl:  CL-éɲâ (blocks H-tone spreading onto verb)
        2pl:  CL-éɲá
        3pl:  CL-á-l- (blocks H-tone spreading onto verb)
    Subject w/ 3pl object (takes place of or includes Aux /a/):
        1sg: l- ɛ̀- ĺ
        2sg: l- à- ĺ
        3sg: l- à- ŋə́- ĺ
        1du.incl: l- á- ló
        1pl.incl: l- á- ló -ŕ
        1pl.excl: l- éɲâ- ĺ
        2pl: l- éɲá- ĺ
        3pl: l- á- l- ló
    Object: (takes place of Aux /a/)
        1sg: -à-ŋɛ̂-
        2sg: -à-ŋâ-
        3sg: CL-
        1du.incl: -à-tɛ́-
        1pl.incl: -à-tɛ́- -ŕ
        1pl.excl: -éɲár-
        2pl: -à-tɛ́-
        3pl: CL-à-l(ó)-
    """
    tamd_strs = ["tam=perfective", "deixis=itive"]
    def get_features(sbj: str='unmarked', obj: str='unmarked', cl: str='unmarked') -> List[str]:
        features_list = [INFLECTED_AUX]
        features_list.extend(tamd_strs)
        features_list.append(f"subject={sbj}")
        features_list.append(f"object={obj}")
        features_list.append(f"class={cl}")
        return features.FeatureVector(*features_list)
    
    # make non-pronominal slots
    non_pronominal_slots = add_class_prefixes_to_slots([(insert_fst("à"), get_features())], include_ng=True)

    # subject marking
    subject_prefixes_slots = [
        (insert_fst("íŋ-g-à"), get_features(sbj='1sg', cl='g')),
        (insert_fst("á-g-à"), get_features(sbj='2sg', cl='g')),
        (insert_fst("á-l-à"), get_features(sbj='1du.incl', cl='l')),
        (insert_fst("á-l-à"), get_features(sbj='1pl.incl', cl='l')),
        (insert_fst("ɲà-l-à"), get_features(sbj='1pl.excl', cl='l')),
        (insert_fst("ɲá-l-à"), get_features(sbj='2pl', cl='l')),
    ]

    # subject with 3sg object
    subject_suffixes_3sg_obj = [
        (insert_fst("ɛ̀"), get_features(sbj='1sg', obj='3sg')),
        (insert_fst("à"), get_features(sbj='2sg', obj='3sg')),
        (insert_fst("à-l"), get_features(sbj='3sg', obj='3sg')),
        (insert_fst("á-l"), get_features(sbj='1du.incl', obj='3sg')),
        (insert_fst("á-l"), get_features(sbj='1pl.incl', obj='3sg')),
        (insert_fst("éɲâ"), get_features(sbj='1pl.excl', obj='3sg')),
        (insert_fst("éɲá"), get_features(sbj='2pl', obj='3sg')),
        (insert_fst("à-l"), get_features(sbj='3pl', obj='3sg')),
    ]
    subject_suffixes_3sg_obj_slots = add_class_prefixes_to_slots(subject_suffixes_3sg_obj, include_ng=True)

    # subject with 3pl object
    subject_suffixes_3pl_obj = [
        (insert_fst("ɛ̀-ĺ"), get_features(sbj='1sg', obj='3pl')),
        (insert_fst("à-ĺ"), get_features(sbj='2sg', obj='3pl')),
        (insert_fst("à-ŋə́-ĺ"), get_features(sbj='3sg', obj='3pl')),
        (insert_fst("á-ló"), get_features(sbj='1du.incl', obj='3pl')),
        (insert_fst("á-ló"), get_features(sbj='1pl.incl', obj='3pl')),
        (insert_fst("éɲâ-ĺ"), get_features(sbj='1pl.excl', obj='3pl')),
        (insert_fst("éɲá-ĺ"), get_features(sbj='2pl', obj='3pl')),
        (insert_fst("à-l-ló"), get_features(sbj='3pl', obj='3pl')),
    ]
    subject_suffixes_3pl_obj_slots = add_class_prefixes_to_slots(subject_suffixes_3pl_obj, include_ng=True)

    # object marking
    object_suffixes = [
        (suffix("-ŋɛ̂"), get_features(obj='1sg')),
        (suffix("-ŋâ"), get_features(obj='2sg')),
        (suffix("-tɛ́"), get_features(obj='1du.incl')),
        (suffix("-tɛ́"), get_features(obj='1pl.incl')),
        (suffix("-éɲár"), get_features(obj='1pl.excl')),
        (suffix("-tɛ́"), get_features(obj='2pl')),
        (suffix("-ĺ")|suffix("-ló"), get_features(obj='3pl')),
    ]
    object_slots = [
        (insert_fst('à')@rule@VOWEL_COALESCENCE_RULE, features_vec)
        for rule, features_vec in object_suffixes
    ]
    object_slots = add_class_prefixes_to_slots(object_slots, include_ng=True)

    # joint subject+object marking
    subject_object_slots = []
    for sbj_rule, sbj_features_vec in subject_prefixes_slots:
        for obj_rule, obj_features_vec in object_suffixes:
            subject_feature = sbj_features_vec.values['subject']
            class_feature = sbj_features_vec.values['class']
            object_feature = obj_features_vec.values['object']
            if subject_feature.startswith('1') and object_feature.startswith('1'):
                # avoid duplicating 1st person markers
                continue
            if subject_feature.startswith('2') and object_feature.startswith('2'):
                # avoid duplicating 2nd person markers
                continue
            combined_features_vec = get_features(
                sbj=subject_feature,
                obj=object_feature,
                cl=class_feature
            )
            subject_object_slots.append((
                sbj_rule@obj_rule@VOWEL_COALESCENCE_RULE,
                combined_features_vec
            ))
    
    slots = non_pronominal_slots\
        + subject_prefixes_slots\
        + subject_suffixes_3sg_obj_slots\
        + subject_suffixes_3pl_obj_slots\
        + object_slots\
        + subject_object_slots
    for rule, _ in slots:
        rule.optimize() 
    return slots

def add_perfective_ventive_personal_markers(
    form_fst: pynini.Fst,
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Arguments:
        form_fst: FST representing a perfective ventive verb form
    Returns:
        slots_w_markers: List of Tuples of (FST, FeatureVector) with personal and class markers added

    Adds personal and class markers to perfective verb forms in the given slots.
    Subject:  
    - 1sg: jɛ́-  
    - 2sg: á-  
    - 3sg: CL-  
    - 1du.incl: lə́-  
    - 1pl.incl: lə́- -ŕ  
    - 1pl.excl: ɲà-  
    - 2pl: ɲá-  
    - 3pl: CL-  
    Subject w/ 3sg object:  
    - 1sg: CL-  -ɛ́ŋí  
    - 1sg: CL-  -áŋá  
    - 3sg: CL-  -ŋ(ú)  
    - 1du.incl: CL-  -ɜ́llí  
    - 1pl.incl: CL-  -ɜ́llí -ŕ  
    - 1pl.excl: CL-  -áɲâ  
    - 2pl: CL- -áɲá  
    - 3pl: CL- -ɜ́l  
    Subject w/ 3pl object:  
    - 1sg: CL- -ɛ́-ló  
    - 2sg: CL- -á-ló  
    - 3sg: CL- -l -ɔ́ŋ(ú)  
    - 1du.incl: CL- -ɜ́llí  
    - 1pl.incl: CL- -ɜ́llí -ŕ  
    - 1pl.excl: CL- -áɲâ-l  
    - 2pl: CL- -áɲá-l  
    - 3pl: CL- -ɜ́l-ló  
    Object:
    - 1sg: -íŋî  
    - 2sg: -áŋà  
    - 3sg: kə̀- -ŋú  
    - 1du.incl: -átɛ́  
    - 1pl.incl: -átɛ́-ŕ  
    - 1pl.excl: -éɲárɛ́  
    - 2pl: -átɛ́  
    - 3pl: CL-  
    """
    tamd_strs = ["tam=perfective", "deixis=ventive"]
    def get_features(sbj: str='unmarked', obj: str='unmarked') -> List[str]:
        features_list = [INFLECTED_VERB]
        features_list.extend(tamd_strs)
        features_list.append(f"subject={sbj}")
        features_list.append(f"object={obj}")
        return features.FeatureVector(*features_list)

    non_pronominal_slots = add_class_prefixes_to_slots([(form_fst, get_features())], include_ng=False)

    subject_prefixes = [
        (prefix("jɛ́-"), get_features(sbj='1sg')),
        (prefix("á-"), get_features(sbj='2sg')),
        (prefix("lə́-"), get_features(sbj='1du.incl')),
        (prefix("lə́")@suffix("-ŕ"), get_features(sbj='1pl.incl')),
        (prefix("ɲà-"), get_features(sbj='1pl.excl')),
        (prefix("ɲá-"), get_features(sbj='2pl')),
    ]
    subject_prefix_slots = [(form_fst@rule, features_vec) for rule, features_vec in subject_prefixes]

    # subject with 3sg object
    subject_suffixes_3sg_obj = [
        (suffix("-íŋí"), get_features(sbj='1sg', obj='3sg')),
        (suffix("-áŋá"), get_features(sbj='2sg', obj='3sg')),
        (suffix("-ŋ")+suffix('ú').ques, get_features(sbj='3sg', obj='3sg')),
        (suffix("-ɜ́llí"), get_features(sbj='1du.incl', obj='3sg')),
        (suffix("-ɜ́llí-ŕ"), get_features(sbj='1pl.incl', obj='3sg')),
        (suffix("-áɲà"), get_features(sbj='1pl.excl', obj='3sg')),
        (suffix("-áɲá"), get_features(sbj='2pl', obj='3sg')),
        (suffix("-ɜ́l"), get_features(sbj='3pl', obj='3sg')),
    ]
    # object marking handled w class prefixes
    subject_suffixes_3sg_obj_slots = [
        (form_fst@rule@VOWEL_COALESCENCE_RULE, features_vec)
        for rule, features_vec in subject_suffixes_3sg_obj
    ]
    subject_suffixes_3sg_obj_slots = add_class_prefixes_to_slots(subject_suffixes_3sg_obj_slots, include_ng=False)

    # subject with 3pl object
    subject_suffixes_3pl_obj = [
        (suffix("-ɛ́-ló"), get_features(sbj='1sg', obj='3pl')),
        (suffix("-á-ló"), get_features(sbj='2sg', obj='3pl')),
        (suffix("-l")@(suffix("-ɔ́ŋ")+suffix("ú").ques), get_features(sbj='3sg', obj='3pl')),
        (suffix("-ɜ́llí"), get_features(sbj='1du.incl', obj='3pl')),
        (suffix("-ɜ́llí-ŕ"), get_features(sbj='1pl.incl', obj='3pl')),
        (suffix("-áɲâ-l"), get_features(sbj='1pl.excl', obj='3pl')),
        (suffix("-áɲá-l"), get_features(sbj='2pl', obj='3pl')),
        (suffix("-ɜ́l-ló"), get_features(sbj='3pl', obj='3pl')),
    ]
    subject_suffixes_3pl_obj = add_class_prefixes_to_slots(subject_suffixes_3pl_obj, include_ng=False)
    subject_suffixes_3pl_obj_slots = [(form_fst@rule@VOWEL_COALESCENCE_RULE, features_vec) for rule, features_vec in subject_suffixes_3pl_obj]

    # object marking
    object_suffixes = [
        (suffix("-íŋì"), get_features(obj='1sg')),
        (suffix("-áŋà"), get_features(obj='2sg')),
        (suffix("-ŋú"), get_features(obj='3sg')),
        (suffix("-átɛ́"), get_features(obj='1du.incl')),
        (suffix("-átɛ́-ŕ"), get_features(obj='1pl.incl')),
        (suffix("-éɲárɛ́"), get_features(obj='1pl.excl')),
        (suffix("-átɛ́"), get_features(obj='2pl')),
    ]
    object_slots = add_class_prefixes_to_slots(object_suffixes, include_ng=False)
    object_slots = [(form_fst@rule@VOWEL_COALESCENCE_RULE, features_vec) for rule, features_vec in object_slots]

    # joint subject+object marking
    subject_object_slots = []
    for sbj_rule, sbj_features_vec in subject_prefixes:
        for obj_rule, obj_features_vec in object_suffixes:
            subject_feature = sbj_features_vec.values['subject']
            object_feature = obj_features_vec.values['object']
            if subject_feature.startswith('1') and object_feature.startswith('1'):
                # avoid duplicating 1st person markers
                continue
            if subject_feature.startswith('2') and object_feature.startswith('2'):
                # avoid duplicating 2nd person markers
                continue
            combined_features_vec = get_features(sbj=subject_feature, obj=object_feature)
            subject_object_slots.append((form_fst@sbj_rule@obj_rule, combined_features_vec))

    slots_w_markers = non_pronominal_slots\
        + subject_prefix_slots\
        + subject_suffixes_3sg_obj_slots\
        + subject_suffixes_3pl_obj_slots\
        + object_slots\
        + subject_object_slots

    for rule, _ in slots_w_markers:
        rule.optimize()
    
    return slots_w_markers

def add_1pl_incl_r_suffix(slots: List[Tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:   
    """
    Adds -ŕ suffix for 1pl.incl forms in the given slots.
    """
    for rule, features_vec in slots[:]:
        new_rule = rule@suffix('-ŕ')
        for role in ['subject', 'object']:
            new_features = features_vec.values.copy()
            new_features[role] = '1pl.incl'
            new_features_vec = features.FeatureVector(INFLECTED_VERB, *[f"{k}={v}" for k, v in new_features.items()])
            slots.append((new_rule, new_features_vec))
    return slots

def add_imperative_object_markers(
    slots: List[tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Object:
        3pl: -l
    """

    

# slots for verb paradigms

def make_verb_slots(fv_class: str) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
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

    # no class or personal markers for imperfective forms

    ipfv_it_suffix=fst(f"-{a_morphome}{LOW_TONE}")
    if is_OV:
        ipfv_it_stem = compose_stem_harmony(HLSTAR_RULE)
    else:
        ipfv_it_stem = compose_stem(HLSTAR_RULE)

    ipfv_vent_suffix=fst(f"-{o_morphome}{HIGH_TONE}")
    if is_OV and o_morphome == 'ɔ':
        ipfv_vent_stem = compose_stem_harmony(ALL_LOW_TONE_RULE)
    else:
        ipfv_vent_stem = compose_stem(ALL_LOW_TONE_RULE)
    ipfv_slots = [
        (paradigms.suffix(ipfv_it_suffix, ipfv_it_stem), IPFV_IT),
        (paradigms.suffix(ipfv_vent_suffix, ipfv_vent_stem), IPFV_VENT),
    ]
    ipfv_slots = add_1pl_incl_r_suffix(ipfv_slots)

    ####################
    # Perfective forms #
    ####################

    # perfective ventive has class and personal markers
    # perfective itive does not

    pfv_it_suffix = fst(f"-{e_morphome}{LOW_TONE}")
    pfv_it_stem = compose_stem(HLSTAR_RULE)

    pfv_vent_suffix = ipfv_vent_suffix
    if is_OV and o_morphome == 'ɔ':
        pfv_vent_stem = compose_stem_harmony(ALL_LOW_TONE_RULE)
    else:
        pfv_vent_stem = compose_stem(ALL_LOW_TONE_RULE)

    pfv_it_slots=[(paradigms.suffix(pfv_it_suffix, pfv_it_stem), PFV_IT)]
    pfv_it_slots = add_1pl_incl_r_suffix(pfv_it_slots)
    pfv_vent_form = paradigms.suffix(pfv_vent_suffix, pfv_vent_stem)
    pfv_vent_slots = add_perfective_ventive_personal_markers(pfv_vent_form)
    pfv_slots = [*pfv_vent_slots, *pfv_it_slots]

    ##############
    # Infinitive #
    ##############

    # only one form, no deixis, class or personal markers

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

    # dependent forms have specific personal markers
    # TODO: replace class prefixes with personal markers

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

@output_cache(__file__)
def get_paradigm_for_class(
        fv_class: str,
        stems: Union[str, pynini.Fst, None]=None
) -> paradigms.Paradigm:
    slots = make_verb_slots(fv_class)
    if type(stems) is str:
        stems = [stems]
    
    if type(stems) is list:
        stems = [fst(stem) for stem in stems]
    elif stems is None:
        stems = get_roots_for_class(fv_class, wrap_w_fsa=True)

    fv_paradigm = paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=f"{fv_class} class",
        slots=slots,
        lemma_feature_vector=VERB_ROOT,
        stems=stems,
        boundary=BOUNDARY,
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

@paradigm_cache(__file__)
def make_aux_paradigm() -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    aux_slots = []
    aux_slots.extend(build_itive_perfective_aux_forms())
    aux_slots.extend(build_imperfective_aux_forms())

    # arbitarily set lemma to IPFV_AUX w/ g class
    lemma_features = IPFV_AUX.values.copy()
    lemma_features['class'] = 'g'
    lemma_feature_strs = [f"{feature}={value}" for feature, value in lemma_features.items()]
    aux_lemma = features.FeatureVector(INFLECTED_AUX, *lemma_feature_strs)

    aux_paradigm = paradigms.Paradigm(
        category=INFLECTED_AUX,
        name="TAMD auxiliary",
        slots=aux_slots,
        lemma_feature_vector=aux_lemma,
        stems=[fst("")],
        boundary=BOUNDARY,
    )
    return aux_paradigm

AUX_PARADIGM = make_aux_paradigm()

@output_cache(__file__)
def make_verb_w_aux_paradigm(
        verb_paradigm: Union[str, paradigms.Paradigm]
) -> paradigms.Paradigm:
    verb_w_aux_slots = []
    if type(verb_paradigm) is str:
        verb_paradigm = FV2PARADIGM[verb_paradigm]
    for aux_rule, feature_vector in AUX_PARADIGM.slots:
        new_feature_values = feature_vector.values.copy()
        # certain pronouns can trigger H-tone spreading from aux to ventive verbs
        ventive_allows_hspread = (
            (new_feature_values['object'] in ['1du.incl', '1pl.incl', '1pl.excl', '2pl']) or
            (
                new_feature_values['subject'] in ['1du.incl', '1pl.incl', '2pl'] and
                new_feature_values['object'].startswith('3')
            )
        )
        deixis_values = [new_feature_values['deixis']]
        if deixis_values[0] == 'unmarked':
            deixis_values = DEIXIS_VALUES
        for deixis in deixis_values:
            new_feature_values['deixis']=deixis
            new_feature_vector = features.FeatureVector(
                INFLECTED_VERB,
                *(f"{k}={v}" for k,v in new_feature_values.items())
            )
            features_to_match = new_feature_values.copy()

            # set unmarked for subject, object, class to find verb slot
            # except for 1pl.incl, as this is marked on the verb with -ŕ
            if features_to_match['subject'] != '1pl.incl':
                features_to_match['subject']='unmarked'
            if features_to_match['object'] != '1pl.incl':
                features_to_match['object']='unmarked'
            features_to_match['class']= 'unmarked'
            verb_slot = [slot for slot in verb_paradigm.slots if slot[1].values == features_to_match]
            assert len(verb_slot) == 1, f"Could not find verb slot for aux features {features_to_match}"
            verb_rule, _ = verb_slot[0]
            combined_rule = aux_rule+insert_fst(WORD_BOUNDARY_STR)+verb_rule
            combined_rule = combined_rule@FALL_BLOCKS_H_RULE@VOWEL_COALESCENCE_RULE
            if deixis == 'itive' or ventive_allows_hspread:
                combined_rule = combined_rule@H_SPREAD_RULE
            combined_rule.optimize()
            verb_w_aux_slots.append((combined_rule, new_feature_vector))

    lemma_slot = (SIGMASTAR, VERB_ROOT)
    verb_w_aux_slots.append(lemma_slot)

    verb_w_aux_paradigm = paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=f"{fv_class} class with TAMD auxiliary",
        slots=verb_w_aux_slots,
        lemma_feature_vector=VERB_ROOT,
        stems=verb_paradigm.stems,
        boundary=BOUNDARY,
    )
    return verb_w_aux_paradigm

AO_PARADIGM_W_AUX = make_verb_w_aux_paradigm("aɔ")
AQ_PARADIGM_W_AUX = make_verb_w_aux_paradigm("ao")
AU_PARADIGM_W_AUX = make_verb_w_aux_paradigm("au")
AI_PARADIGM_W_AUX = make_verb_w_aux_paradigm("ai")
OO_PARADIGM_W_AUX = make_verb_w_aux_paradigm("ɔɔ")
OU_PARADIGM_W_AUX = make_verb_w_aux_paradigm("ɔu")
OI_PARADIGM_W_AUX = make_verb_w_aux_paradigm("ɔi")

FV2PARADIGM_W_AUX = {
    "aɔ": AO_PARADIGM_W_AUX,
    "ao": AQ_PARADIGM_W_AUX,
    "au": AU_PARADIGM_W_AUX,
    "ai": AI_PARADIGM_W_AUX,
    "ɔɔ": OO_PARADIGM_W_AUX,
    "ɔu": OU_PARADIGM_W_AUX,
    "ɔi": OI_PARADIGM_W_AUX,
}
PARADIGM_W_AUX2FV = {v:k for v,k in FV2PARADIGM_W_AUX.items()}

ALL_VERB_PARADIGMS = {
    'aux': AUX_PARADIGM,
    **{k+'_aux':v for k, v in FV2PARADIGM_W_AUX.items()},
    **FV2PARADIGM,
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
        features: Dict[str, str],
        expected_verb_type: Literal['stem', 'stem_and_aux', 'all']='all',
    ) -> List[str]:
    """
    Arguments:
        root:           str indicating verb root to inflect
        paradigm:       Paradigm object or str of FV class shorthand e.g. 'aɔ'
        features:       dict mapping feature labels to values
        expected_verb_type: Literal['stem', 'stem_and_aux', 'all']='all',
                        (if paradigm is `Paradigm` object, this is ignored)
    Returns:
        form:       list of strs of root verb inflected with given features
    """
    if type(paradigm) is paradigms.Paradigm:
        pass
    elif type(paradigm) is str and expected_verb_type == 'stem_and_aux':
        paradigm = FV2PARADIGM_W_AUX[paradigm]
    elif type(paradigm) is str and expected_verb_type == 'stem':
        paradigm = FV2PARADIGM[paradigm]
    else:
        forms_stem = inflect_verb_with_features(
            root,
            FV2PARADIGM[paradigm],
            features,
            expected_verb_type='stem'
        )
        forms_aux = inflect_verb_with_features(
            root,
            FV2PARADIGM_W_AUX[paradigm],
            features,
            expected_verb_type='stem_and_aux'
        )
        forms = [*forms_stem, *forms_aux]
        return forms
    forms = []
    expected_keys = [feature.name for feature in INFLECTED_VERB.features]
    features_filtered = {k:v for k,v in features.items() if k in expected_keys}
    slot_for_features = [slot for slot in paradigm.slots if slot[1].values == features_filtered]
    for slot in slot_for_features:
        rule, _ = slot
        form = decode_fst_string(fst(root)@rule)
        forms.append(form)

    return forms

def inflect_aux_with_features(
        features: Dict[str, str]
    ) -> List[str]:
    """
    Arguments:
        features:   dict mapping feature labels to values
    Returns:
        form:       list of strs of auxiliary inflected with given features
    """
    forms = []
    expected_keys = [feature.name for feature in INFLECTED_AUX.features]
    features_filtered = {k:v for k,v in features.items() if k in expected_keys}
    slot_for_features = [slot for slot in AUX_PARADIGM.slots if slot[1].values == features_filtered]
    for slot in slot_for_features:
        rule, _ = slot
        form = decode_fst_string(fst("")@rule)
        forms.append(form)

    return forms

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
        expected_verb_type: Literal['stem', 'aux', 'stem_and_aux', 'auto'] = 'auto',
) -> Dict[str, str]:
    """
    Arguments:
        form:                   str of inflected verb form
        paradigm:               Paradigm object or str of FV class shorthand e.g. 'aɔ'
        add_gloss:              bool indicating whether to add gloss to output
        expected_verb_type:     indicates whether to parse as 'stem' (inflected verb),
                                'aux' (auxiliary verb), 'stem_and_aux' (both), or 'auto'
                                (automatic detection). Default 'auto'. If paradigm is `Paradigm`
                                object, this is ignored.
    Returns:        dict of shape {'root': root, '$feature': feature_value}
    """
    parses = []

    if expected_verb_type == 'aux':
        # only one paradigm for auxiliaries
        paradigm = AUX_PARADIGM
    elif paradigm is None:
        for fv in FV2PARADIGM.keys():
            parses_for_fv = parse_inflected_verb(form, fv, add_gloss, expected_verb_type)
            parses.extend(parses_for_fv)
    if type(paradigm) is str and expected_verb_type == 'stem':
        paradigm = FV2PARADIGM[paradigm]
    elif type(paradigm) is str and expected_verb_type == 'stem_and_aux':
        paradigm = FV2PARADIGM_W_AUX[paradigm]
    elif type(paradigm) is str and expected_verb_type == 'auto':
        # try all possible verb types
        for verb_type in ['stem', 'aux', 'stem_and_aux']:
            parses_for_type = parse_inflected_verb(form, paradigm, add_gloss, verb_type)
            parses.extend(parses_for_type)
        return parses

    try:
        lemmata = paradigm.lemmatize(fst(form))
        analyzed_forms = paradigm.analyze(fst(form))
    except pynini.lib.rewrite.Error:
        return parses
    for lemma, analyzed_form in zip(lemmata, analyzed_forms):
        root, feature_vec = lemma
        root = decode_byte_str(root)

        analyzed_form = analyzed_form[0]
        analyzed_form = decode_byte_str(analyzed_form)

        parse = feature_vec.values
        parse['root'] = root
        parse['analyzed_form'] = analyzed_form
        parse['form'] = form
        if add_gloss and expected_verb_type == 'aux':
            parse['gloss'] = 'aux'
        elif add_gloss:
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