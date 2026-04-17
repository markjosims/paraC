"""
# aux_forms.py
Imperfective and itive perfective verb forms take an auxiliary /a/
that bears inflection for class, subject, and object. This module
builds auxiliary forms with the appropriate exponents.

Auxiliary forms for imperfective and itive perfective TAMD categories
are mostly identical, differing only in the tone on the auxiliary vowel
for some forms.
"""

from typing import Tuple, List, Dict, Union
from src.decorators import output_cache
from src.forms.form_helpers import (
    add_wh_suffixes_to_slots, suffix,
    add_class_prefixes_to_slots, make_feature_builder
)
from src.fst_helpers import fst, insert_fst, stringify_lexeme_features
from src.constants import INFLECTED_AUX, IPFV_AUX
import pynini
from pynini.lib import features, paradigms
from src.lexicon.phonology import VOWEL_COALESCENCE_RULE, BOUNDARY


from dataclasses import dataclass
from typing import Dict, Tuple

"""
## Auxiliary Person Markers
When present, the verbal auxiliary bears person marking for subject
and/or object. Subject marking is typically prefixed to the auxiliary,
while object marking is suffixed to it. Either prefixes or suffixes
may trigger coalescence with the auxiliary vowel.
E.g.

(1) kà və́lɛ̀ðɛ̀
    k   -à      və́lɛ̀ð       -ɛ̀
    CLg -AUX    pull.PFV.IT -FV
"(He) pulled"

(2) íŋgàŋâ və̀lɛ̀ðɛ̀
    1SG.SBJ- CLg- AUX -2SG.OBJ  pull.PFV.IT -FV
"I pulled you"

(3) ágéɲár və́lɛ̀ðɛ̀
    2SG.SBJ- CLg-   (AUX)   1PL.EXCL.OBJ    pull.PFV.IT -FV
"You pulled us (excl.)"    

Note that in (3) the auxiliary vowel is elided due to coalescence
with the object suffix -éɲár.

As with perfective ventive forms, 3rd sg and 3rd pl objects trigger special
subject suffixes, e.g.

(4) ŋgɛ̀ və́lɛ̀ðɛ̀
    ŋg-                -ɛ̀           və́lɛ̀ð       -ɛ̀
    CLg.3SG.OBJ- (AUX) -1SG.OBJ     pull.PFV.IT -FV
"I pulled him/her/it"
    
(5) lɛ̀ĺ və́lɛ̀ðɛ̀
    l-                 -ɛ̀       -ĺ          və́lɛ̀ð       -ɛ̀
    CLl.3PL.OBJ- (AUX) -1SG.OBJ -3PL.OBJ    pull.PFV.IT -FV
"I pulled them"
    
Note that (2), (4) and (5) all have a 1SG subject, even though the subject marker
is different in each sentence, being a prefix íŋ- in (2), a suffix -ɛ̀ in (4) and (5).

In (4) there is no overt 3SG object marker, instead the ŋɡ- class prefix agrees with
an implicit 3SG object. In (5) the l- class prefix agrees with an 3PL object, **and**
the marker -ĺ overtly indicates the 3PL object.

To organize the various prefixes and suffixes, we define a dataclass
`AuxPersonMarkers` that organizes dictionaries of marker forms
across the categories of subject prefixes, subject suffixes w/ 3sg and 3pl
object, and object suffixes.
"""

@dataclass
class AuxPersonMarkers:
    """
    Stores person marker forms for an auxiliary TAMD category.

    The marker strings use IPA with tone diacritics. Hyphens indicate
    morpheme boundaries.
    """
    aux_vowel: str  # Base auxiliary vowel ('á' for imperfective, 'à' for itive perfective)

    # Subject prefixes (with nominal object)
    # Format: {person: marker_string}
    subject_prefixes: Dict[str, Tuple[str, str]]  # (marker, class)

    # Subject suffixes when object is 3sg
    # These replace/include the auxiliary
    subject_3sg_obj: Dict[str, Union[str, Tuple[str,str]]]

    # Subject suffixes when object is 3pl
    subject_3pl_obj: Dict[str, Union[str, Tuple[str,str]]]

    # Object suffixes (replace auxiliary)
    object_suffixes: Dict[str, Union[str, Tuple[str,str]]]


IMPERFECTIVE_AUX_MARKERS = AuxPersonMarkers(
    aux_vowel='á',
    subject_prefixes={
        '1sg': ('íŋ-g-á', 'g'),
        '2sg': ('á-g-á', 'g'),
        '1du.incl': ('á-l-á', 'l'),
        '1pl.incl': ('á-l-á', 'l'),
        '1pl.excl': ('ɲà-l-á', 'l'),
        '2pl': ('ɲá-l-á', 'l'),
    },
    subject_3sg_obj={
        '1sg': 'ɛ́',
        '2sg': 'á',
        '3sg': '-ŋ',
        '1du.incl': 'á-l',
        '1pl.incl': 'á-l',
        '1pl.excl': 'éɲâ',
        '2pl': 'éɲá',
        '3pl': 'á-l',
    },
    subject_3pl_obj={
        '1sg': 'ɛ́-ĺ',
        '2sg': 'á-ĺ',
        '3sg': 'á-ŋə́-ĺ',
        '1du.incl': 'á-ló',
        '1pl.incl': 'á-ló',
        '1pl.excl': 'éɲâ-ĺ',
        '2pl': 'éɲá-ĺ',
        '3pl': 'á-l-ló',
    },
    object_suffixes={
        '1sg': '-ŋɛ̂',
        '2sg': '-ŋâ',
        '1du.incl': '-tɛ́',
        '1pl.incl': '-tɛ́',
        '1pl.excl': '-éɲár',
        '2pl': '-tɛ́',
        '3pl': ('-ĺ', '-ló'),  # Tuple for alternatives
    },
)
ITIVE_PERFECTIVE_AUX_MARKERS = AuxPersonMarkers(
    aux_vowel='à',
    subject_prefixes={
        '1sg': ('íŋ-g-à', 'g'),
        '2sg': ('á-g-à', 'g'),
        '1du.incl': ('á-l-à', 'l'),
        '1pl.incl': ('á-l-à', 'l'),
        '1pl.excl': ('ɲà-l-à', 'l'),
        '2pl': ('ɲá-l-à', 'l'),
    },
    subject_3sg_obj={
        '1sg': 'ɛ̀',
        '2sg': 'à',
        '3sg': 'à-l',
        '1du.incl': 'á-l',
        '1pl.incl': 'á-l',
        '1pl.excl': 'éɲâ',
        '2pl': 'éɲá',
        '3pl': 'à-l',
    },
    subject_3pl_obj={
        '1sg': 'ɛ̀-ĺ',
        '2sg': 'à-ĺ',
        '3sg': 'à-ŋə́-ĺ',
        '1du.incl': 'á-ló',
        '1pl.incl': 'á-ló',
        '1pl.excl': 'éɲâ-ĺ',
        '2pl': 'éɲá-ĺ',
        '3pl': 'à-l-ló',
    },
    object_suffixes={
        '1sg': '-ŋɛ̂',
        '2sg': '-ŋâ',
        '1du.incl': '-tɛ́',
        '1pl.incl': '-tɛ́',
        '1pl.excl': '-éɲár',
        '2pl': '-tɛ́',
        '3pl': ('-ĺ', '-ló'),
    },
)

"""
## Auxiliary Slot-Building Helpers
Constructing all auxiliary forms requires building slots for class
prefixes, subject prefixes, subject suffixes for 3sg and 3pl objects, and object
suffixes. The following helper functions define the logic for constructing auxiliary
forms:
- _build_aux_non_pronominal_slots: Adds class prefixes to non-pronominal slots
- _build_aux_subject_prefix_slots: Builds slots for subject prefixes
- _build_aux_subject_3sg_obj_slots: Builds slots for subject suffixes when object is 3sg
- _build_aux_subject_3pl_obj_slots: Builds slots for subject suffixes when object is 3pl
- _build_aux_object_slots: Builds slots for object-only marking
- _build_aux_combined_sbj_obj_slots: Builds combined subject+object slots, filtering invalid combinations
- _add_auxiliary_personal_markers: Main function to add all personal markers to auxiliary verb forms
"""

def _build_aux_non_pronominal_slots(markers: AuxPersonMarkers, get_features) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for auxiliary with no person marking."""
    base_slots = [(insert_fst(markers.aux_vowel), get_features())]
    return add_class_prefixes_to_slots(base_slots, include_ng=True)


def _build_aux_subject_prefix_slots(markers: AuxPersonMarkers, get_features) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for subject marking via prefixes (with nominal object)."""
    slots = []
    for person, (marker, cl) in markers.subject_prefixes.items():
        slots.append((insert_fst(marker), get_features(sbj=person, cl=cl)))
    return slots


def _build_aux_subject_3sg_obj_slots(markers: AuxPersonMarkers, get_features) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for subject marking when object is 3sg."""
    slots = []
    for person, marker in markers.subject_3sg_obj.items():
        slots.append((insert_fst(marker), get_features(sbj=person, obj='3sg')))
    return add_class_prefixes_to_slots(slots, include_ng=True)


def _build_aux_subject_3pl_obj_slots(markers: AuxPersonMarkers, get_features) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for subject marking when object is 3pl."""
    slots = []
    for person, marker in markers.subject_3pl_obj.items():
        slots.append((insert_fst(marker), get_features(sbj=person, obj='3pl')))
    return add_class_prefixes_to_slots(slots, include_ng=True)


def _build_aux_object_slots(markers: AuxPersonMarkers, get_features) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for object-only marking."""
    object_suffixes = []
    for person, marker in markers.object_suffixes.items():
        object_suffixes.append((suffix(marker), get_features(obj=person)))

    # Compose with auxiliary vowel and vowel coalescence
    object_slots = [
        (insert_fst(markers.aux_vowel) @ rule @ VOWEL_COALESCENCE_RULE, features_vec)
        for rule, features_vec in object_suffixes
    ]
    return add_class_prefixes_to_slots(object_slots, include_ng=True)


def _build_aux_combined_sbj_obj_slots(
    subject_prefix_slots: List[Tuple[pynini.Fst, features.FeatureVector]],
    markers: AuxPersonMarkers,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build combined subject+object slots, filtering invalid combinations."""
    slots = []

    for sbj_rule, sbj_features_vec in subject_prefix_slots:
        for person, marker in markers.object_suffixes.items():
            subject_feature = sbj_features_vec.values['subject']
            class_feature = sbj_features_vec.values['class']
            object_feature = person

            # Skip duplicate person combinations
            if subject_feature.startswith('1') and object_feature.startswith('1'):
                continue
            if subject_feature.startswith('2') and object_feature.startswith('2'):
                continue

            obj_rule = suffix(marker)
            combined_features_vec = get_features(
                sbj=subject_feature,
                obj=object_feature,
                cl=class_feature
            )
            slots.append((
                sbj_rule @ obj_rule @ VOWEL_COALESCENCE_RULE,
                combined_features_vec
            ))

    return slots


def build_aux_forms(
    markers: AuxPersonMarkers,
    tamd_strs: List[str],
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Build auxiliary forms with personal markers for a given TAMD category.

    Arguments:
        markers:    AuxPersonMarkers dataclass with person marker forms
        tamd_strs:  List of TAMD feature strings

    Returns:
        List of (FST, FeatureVector) tuples representing all auxiliary forms
    """
    get_features = make_feature_builder(INFLECTED_AUX, tamd_strs)

    non_pronominal_slots = _build_aux_non_pronominal_slots(markers, get_features)
    subject_prefix_slots = _build_aux_subject_prefix_slots(markers, get_features)
    subject_3sg_obj_slots = _build_aux_subject_3sg_obj_slots(markers, get_features)
    subject_3pl_obj_slots = _build_aux_subject_3pl_obj_slots(markers, get_features)
    object_slots = _build_aux_object_slots(markers, get_features)
    combined_slots = _build_aux_combined_sbj_obj_slots(subject_prefix_slots, markers, get_features)

    slots = (
        non_pronominal_slots +
        subject_prefix_slots +
        subject_3sg_obj_slots +
        subject_3pl_obj_slots +
        object_slots +
        combined_slots
    )

    return slots

"""
## Aux factory functions
These functions build auxiliary forms for specific TAMD categories
using the general `build_aux_forms` function defined above.
"""

def build_imperfective_aux_forms() -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build imperfective auxiliary forms with personal markers."""
    return build_aux_forms(
        IMPERFECTIVE_AUX_MARKERS,
        ["tam=imperfective", "deixis=unmarked"]
    )


def build_itive_perfective_aux_forms() -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build perfective itive auxiliary forms with personal markers."""
    return build_aux_forms(
        ITIVE_PERFECTIVE_AUX_MARKERS,
        ["tam=perfective", "deixis=itive"]
    )


@output_cache(__file__)
def get_aux_paradigm() -> paradigms.Paradigm:
    """Get the auxiliary paradigm."""
    aux_slots = []
    aux_slots.extend(build_itive_perfective_aux_forms())
    aux_slots.extend(build_imperfective_aux_forms())
    aux_slots = add_wh_suffixes_to_slots(aux_slots)

    # Set lemma to IPFV_AUX with g class
    lemma_features = IPFV_AUX.values.copy()
    lemma_features['class'] = 'g'
    lemma_feature_strs = [f"{feature}={value}" for feature, value in lemma_features.items()]
    aux_lemma = features.FeatureVector(INFLECTED_AUX, *lemma_feature_strs)

    paradigm_name = stringify_lexeme_features({"part_of_speech": 'aux'})

    return paradigms.Paradigm(
        category=INFLECTED_AUX,
        name=paradigm_name,
        slots=aux_slots,
        lemma_feature_vector=aux_lemma,
        stems=[fst("")],
        boundary=BOUNDARY,
    )