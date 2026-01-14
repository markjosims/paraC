"""
# Verb form builders
This module builds the paradigms for Tira verbs and auxiliaries.
Unlike other parts of speech, due to the morphological complexity
of verbs, the verb lexicon is split up across several paradigms.

Paradigms are split across final vowel (FV) suffix classes, and
whether the stem is a verb stem w/o auxiliary, a verb stem w/ auxiliary,
or a bare auxiliary. The reason for this split is that the auxiliary are
often adjacent but may be separated by an intervening subject. In partic-
-ular, many cases of adjacent auxiliary+verb stem combinations are written
as a single word in our data, motivating a paradigm that combines both so
that coalesced forms can be properly recognized.

## Auxiliary verbs
Before we describe the verb paradigms, a note on the distribution of
the verbal auxiliary is merited. The auxiliary /a/ occurs alongside
verb stems in imperfective aspect, progressive aspect, and perfective
aspect itive deixis. All other TAMD values lack the auxiliary.
When present, the auxiliary bears person and class prefixes that
would otherwise be attached to the verb stem.
"""

from dataclasses import dataclass
from multiprocessing.pool import Pool
import pynini
from pynini.lib import features, paradigms
from src.decorators import output_cache
from src.forms.form_helpers import *
from src.lexicon.phonology import *
from src.fst_helpers import *
from src.lexicon import get_roots_for_class
from src.lexicon.phonology import REMOVE_HOMOPHONE_TAG
from src.constants import INFLECTED_VERB, FV_CLASSES
from typing import *

# =============================================================================
# FV Class Constants
# =============================================================================

"""
There are 7 FV classes in Tira verbs. FV suffixes are divided into 3 morphomes
(Kaldhol 2023) such that each morpheme has the same distribution within the
paradigm across classes. The morphemes are referred to as "a", "o", and "e"
morphomes based on the vowel qualities in the canonical aɔ class.
"""

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

# =============================================================================
# Feature Vector Utilities
# =============================================================================

def make_feature_builder(category, tamd_strs: List[str]):
    """
    Returns a function that creates feature vectors for a given category and TAMD.

    Arguments:
        category:   The feature category (e.g., INFLECTED_AUX, INFLECTED_VERB)
        tamd_strs:  List of TAMD feature strings (e.g., ["tam=imperfective", "deixis=unmarked"])

    Returns:
        A function get_features(sbj, obj, cl, wh) that returns a FeatureVector
    """
    def get_features(sbj: str = 'unmarked', obj: str = 'unmarked',
                     cl: str = 'unmarked', wh: str = 'unmarked') -> features.FeatureVector:
        features_list = [category]
        features_list.extend(tamd_strs)
        features_list.append(f"subject={sbj}")
        features_list.append(f"object={obj}")
        features_list.append(f"class={cl}")
        features_list.append(f"wh={wh}")
        return features.FeatureVector(*features_list)
    return get_features


# =============================================================================
# Person Marker Data Structures
# =============================================================================

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
    subject_3sg_obj: Dict[str, str]

    # Subject suffixes when object is 3pl
    subject_3pl_obj: Dict[str, str]

    # Object suffixes (replace auxiliary)
    object_suffixes: Dict[str, str]


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
        '3sg': 'á-l',
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


# =============================================================================
# Auxiliary Slot-Building Helpers
# =============================================================================

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


def _make_object_suffix_fst(marker) -> pynini.Fst:
    """Create FST for an object suffix, handling alternatives."""
    if isinstance(marker, tuple):
        return suffix(marker[0]) | suffix(marker[1])
    return suffix(marker)


def _build_aux_object_slots(markers: AuxPersonMarkers, get_features) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for object-only marking."""
    object_suffixes = []
    for person, marker in markers.object_suffixes.items():
        object_suffixes.append((_make_object_suffix_fst(marker), get_features(obj=person)))

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

            obj_rule = _make_object_suffix_fst(marker)
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


# =============================================================================
# Auxiliary Form Builders
# =============================================================================

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


# =============================================================================
# Perfective Ventive Person Markers
# =============================================================================

@dataclass
class PerfectiveVentiveMarkers:
    """
    Stores person marker forms for perfective ventive verb forms.

    Unlike auxiliary markers which are insertions, these markers are
    prefixes and suffixes applied to the verb stem.

    Marker formats in dictionaries:
    - Simple string: '-íŋí' -> suffix('-íŋí')
    - Dict with 'prefix': {'prefix': 'jɛ́-'} -> prefix('jɛ́-')
    - Dict with 'prefix' and 'suffix': {'prefix': 'lə́-', 'suffix': '-ŕ'}
    - Dict with 'required' and 'optional': {'required': '-ŋ', 'optional': 'ú'}
    - Dict with 'required' list and 'optional': {'required': ['-l', '-ɔ́ŋ'], 'optional': 'ú'}
    """
    subject_prefixes: Dict[str, dict]
    subject_3sg_obj: Dict[str, dict]
    subject_3pl_obj: Dict[str, dict]
    object_suffixes: Dict[str, dict]


PERFECTIVE_VENTIVE_MARKERS = PerfectiveVentiveMarkers(
    subject_prefixes={
        '1sg': {'prefix': 'jɛ́-'},
        '2sg': {'prefix': 'á-'},
        '1du.incl': {'prefix': 'lə́-'},
        '1pl.incl': {'prefix': 'lə́-', 'suffix': '-ŕ'},
        '1pl.excl': {'prefix': 'ɲà-'},
        '2pl': {'prefix': 'ɲá-'},
    },
    subject_3sg_obj={
        '1sg': {'suffix': '-íŋí'},
        '2sg': {'suffix': '-áŋá'},
        '3sg': {'required': '-ŋ', 'optional': 'ú'},
        '1du.incl': {'suffix': '-ɜ́llí'},
        '1pl.incl': {'suffix': '-ɜ́llí-ŕ'},
        '1pl.excl': {'suffix': '-áɲà'},
        '2pl': {'suffix': '-áɲá'},
        '3pl': {'suffix': '-ɜ́l'},
    },
    subject_3pl_obj={
        '1sg': {'suffix': '-ɛ́-ló'},
        '2sg': {'suffix': '-á-ló'},
        '3sg': {'required': ['-l', '-ɔ́ŋ'], 'optional': 'ú'},
        '1du.incl': {'suffix': '-ɜ́llí'},
        '1pl.incl': {'suffix': '-ɜ́llí-ŕ'},
        '1pl.excl': {'suffix': '-áɲâ-l'},
        '2pl': {'suffix': '-áɲá-l'},
        '3pl': {'suffix': '-ɜ́l-ló'},
    },
    object_suffixes={
        '1sg': {'suffix': '-íŋì'},
        '2sg': {'suffix': '-áŋà'},
        '3sg': {'required': '-ŋ', 'optional': 'ú'},
        '1du.incl': {'suffix': '-átɛ́'},
        '1pl.incl': {'suffix': '-átɛ́-ŕ'},
        '1pl.excl': {'suffix': '-éɲárɛ́'},
        '2pl': {'suffix': '-átɛ́'},
    },
)


# =============================================================================
# Perfective Ventive Slot-Building Helpers
# =============================================================================

def _make_marker_rule(marker: dict) -> pynini.Fst:
    """
    Create FST from a marker dictionary.

    Handles formats:
    - {'prefix': 'X'} -> prefix('X')
    - {'suffix': 'X'} -> suffix('X')
    - {'prefix': 'X', 'suffix': 'Y'} -> prefix('X') @ suffix('Y')
    - {'required': 'X', 'optional': 'Y'} -> suffix('X') + suffix('Y').ques
    - {'required': ['X', 'Y'], 'optional': 'Z'} -> suffix('X') @ (suffix('Y') + suffix('Z').ques)
    """
    if 'required' in marker:
        required = marker['required']
        optional = marker.get('optional')

        if isinstance(required, list):
            # Multiple required parts: chain them, last one gets optional
            rule = suffix(required[0])
            for i, part in enumerate(required[1:], 1):
                if i == len(required) - 1 and optional:
                    rule = rule @ (suffix(part) + suffix(optional).ques)
                else:
                    rule = rule @ suffix(part)
            if optional and len(required) == 1:
                rule = rule + suffix(optional).ques
            return rule
        else:
            # Single required part with optional
            if optional:
                return suffix(required) + suffix(optional).ques
            return suffix(required)

    if 'prefix' in marker and 'suffix' in marker:
        return prefix(marker['prefix']) @ suffix(marker['suffix'])
    elif 'prefix' in marker:
        return prefix(marker['prefix'])
    elif 'suffix' in marker:
        return suffix(marker['suffix'])

    raise ValueError(f"Unknown marker format: {marker}")


def _build_pfv_vent_non_pronominal_slots(
    form_fst: pynini.Fst,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build non-pronominal slots with class prefixes."""
    return add_class_prefixes_to_slots(
        [(form_fst, get_features())],
        include_ng=False
    )


def _build_pfv_vent_subject_prefix_slots(
    form_fst: pynini.Fst,
    markers: PerfectiveVentiveMarkers,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for subject marking via prefixes."""
    slots = []
    for person, marker in markers.subject_prefixes.items():
        rule = _make_marker_rule(marker)
        slots.append((form_fst @ rule, get_features(sbj=person)))
    return slots


def _build_pfv_vent_subject_3sg_obj_slots(
    form_fst: pynini.Fst,
    markers: PerfectiveVentiveMarkers,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for subject marking when object is 3sg."""
    slots = []
    for person, marker in markers.subject_3sg_obj.items():
        rule = _make_marker_rule(marker)
        slots.append((
            form_fst @ rule @ VOWEL_COALESCENCE_RULE,
            get_features(sbj=person, obj='3sg')
        ))
    return add_class_prefixes_to_slots(slots, include_ng=False)


def _build_pfv_vent_subject_3pl_obj_slots(
    form_fst: pynini.Fst,
    markers: PerfectiveVentiveMarkers,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for subject marking when object is 3pl."""
    suffix_slots = []
    for person, marker in markers.subject_3pl_obj.items():
        rule = _make_marker_rule(marker)
        suffix_slots.append((rule, get_features(sbj=person, obj='3pl')))

    slots_w_class = add_class_prefixes_to_slots(suffix_slots, include_ng=False)
    return [
        (form_fst @ rule @ VOWEL_COALESCENCE_RULE, fv)
        for rule, fv in slots_w_class
    ]


def _build_pfv_vent_object_slots(
    form_fst: pynini.Fst,
    markers: PerfectiveVentiveMarkers,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build slots for object-only marking."""
    suffix_slots = []
    for person, marker in markers.object_suffixes.items():
        rule = _make_marker_rule(marker)
        suffix_slots.append((rule, get_features(obj=person)))

    slots_w_class = add_class_prefixes_to_slots(suffix_slots, include_ng=False)
    return [
        (form_fst @ rule @ VOWEL_COALESCENCE_RULE, fv)
        for rule, fv in slots_w_class
    ]


def _build_pfv_vent_combined_sbj_obj_slots(
    form_fst: pynini.Fst,
    markers: PerfectiveVentiveMarkers,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build combined subject+object slots, filtering invalid combinations."""
    slots = []

    for sbj_person, sbj_marker in markers.subject_prefixes.items():
        sbj_rule = _make_marker_rule(sbj_marker)

        for obj_person, obj_marker in markers.object_suffixes.items():
            # Skip same-person combinations (e.g., 1sg subject + 1sg object)
            if sbj_person[0] == obj_person[0]:
                continue

            obj_rule = _make_marker_rule(obj_marker)
            slots.append((
                form_fst @ sbj_rule @ obj_rule,
                get_features(sbj=sbj_person, obj=obj_person)
            ))

    return slots


def add_perfective_ventive_personal_markers(
    form_fst: pynini.Fst,
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Add personal and class markers to perfective ventive verb forms.

    Arguments:
        form_fst:   FST representing a perfective ventive verb form

    Returns:
        List of (FST, FeatureVector) tuples with personal and class markers added
    """
    tamd_strs = ["tam=perfective", "deixis=ventive"]
    get_features = make_feature_builder(INFLECTED_VERB, tamd_strs)
    markers = PERFECTIVE_VENTIVE_MARKERS

    slots = (
        _build_pfv_vent_non_pronominal_slots(form_fst, get_features) +
        _build_pfv_vent_subject_prefix_slots(form_fst, markers, get_features) +
        _build_pfv_vent_subject_3sg_obj_slots(form_fst, markers, get_features) +
        _build_pfv_vent_subject_3pl_obj_slots(form_fst, markers, get_features) +
        _build_pfv_vent_object_slots(form_fst, markers, get_features) +
        _build_pfv_vent_combined_sbj_obj_slots(form_fst, markers, get_features)
    )

    return slots


# =============================================================================
# Additional Person Marker Helpers
# =============================================================================

def add_1pl_incl_r_suffix(
    slots: List[Tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Add -ŕ suffix for 1pl.incl forms in the given slots."""
    for rule, features_vec in slots[:]:
        new_rule = rule @ suffix('-ŕ')
        for role in ['subject', 'object']:
            new_features = features_vec.values.copy()
            new_features[role] = '1pl.incl'
            new_features_vec = features.FeatureVector(
                INFLECTED_VERB,
                *[f"{k}={v}" for k, v in new_features.items()]
            )
            slots.append((new_rule, new_features_vec))
    return slots


def add_imperative_object_markers(
    slots: List[tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    TODO: Add object markers for imperative forms.
    Object: 3pl: -l
    """
    ...


def add_dependent_markers(
    slots: List[Tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """TODO: Add dependent markers."""
    ...


# =============================================================================
# Stem Composition
# =============================================================================

@dataclass
class StemComposer:
    """
    Encapsulates stem composition logic for a given FV class.

    The composer handles the common pattern of preparing a root for inflection,
    applying a tone rule, optionally applying rounding harmony, and finalizing
    the form with tone rules.
    """
    a_morphome: str
    o_morphome: str
    e_morphome: str

    def __post_init__(self):
        self._prepare = (REMOVE_HOMOPHONE_TAG @ ADD_PLACEHOLDER_TBU).optimize()
        self._finalize = (FLOAT_TONE_RULE @ COMBINE_TONES_RULE).optimize()

    @property
    def is_OV(self) -> bool:
        """True if this is an ɔ-initial vowel class (triggers rounding harmony)."""
        return self.a_morphome == 'ɔ'

    def compose(self, tone_rule: pynini.Fst) -> pynini.Fst:
        """Compose a stem with the given tone rule."""
        return self._prepare @ tone_rule @ self._finalize

    def compose_with_harmony(self, tone_rule: pynini.Fst) -> pynini.Fst:
        """Compose a stem with rounding harmony applied."""
        return self._prepare @ tone_rule @ ROUNDING_HARMONY @ self._finalize

    def compose_conditional_harmony(self, tone_rule: pynini.Fst, use_harmony: bool) -> pynini.Fst:
        """Compose a stem, applying harmony only if use_harmony is True."""
        if use_harmony:
            return self.compose_with_harmony(tone_rule)
        return self.compose(tone_rule)

    @classmethod
    def for_class(cls, fv_class: str) -> 'StemComposer':
        """Create a StemComposer for a given FV class."""
        morphomes = CLASS2FV[fv_class]
        return cls(
            a_morphome=morphomes["a_morphome"],
            o_morphome=morphomes["o_morphome"],
            e_morphome=morphomes["e_morphome"],
        )


# =============================================================================
# Verb Slot Builders
# =============================================================================

def _build_imperative_slots(composer: StemComposer) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build imperative itive and ventive slots."""
    # Itive: o-morphome suffix, all high tone
    it_suffix = fst(f"-{composer.o_morphome}{HIGH_TONE}")
    it_stem = composer.compose_conditional_harmony(
        ALL_HIGH_TONE_RULE,
        use_harmony=composer.is_OV and composer.o_morphome == 'ɔ'
    )

    # Ventive: a-morphome suffix, all low tone
    vent_suffix = fst(f"-{composer.a_morphome}{HIGH_TONE}")
    vent_stem = composer.compose_conditional_harmony(ALL_LOW_TONE_RULE, use_harmony=composer.is_OV)

    return [
        (paradigms.suffix(it_suffix, it_stem), IMP_IT),
        (paradigms.suffix(vent_suffix, vent_stem), IMP_VENT),
    ]


def _build_imperfective_slots(composer: StemComposer) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build imperfective itive and ventive slots."""
    # Itive: a-morphome suffix with low tone, HL* tone pattern
    it_suffix = fst(f"-{composer.a_morphome}{LOW_TONE}")
    it_stem = composer.compose_conditional_harmony(HLSTAR_RULE, use_harmony=composer.is_OV)

    # Ventive: o-morphome suffix with high tone, all low tone
    vent_suffix = fst(f"-{composer.o_morphome}{HIGH_TONE}")
    vent_stem = composer.compose_conditional_harmony(
        ALL_LOW_TONE_RULE,
        use_harmony=composer.is_OV and composer.o_morphome == 'ɔ'
    )

    slots = [
        (paradigms.suffix(it_suffix, it_stem), IPFV_IT),
        (paradigms.suffix(vent_suffix, vent_stem), IPFV_VENT),
    ]
    return add_1pl_incl_r_suffix(slots)


def _build_perfective_slots(composer: StemComposer) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build perfective itive and ventive slots."""
    # Itive: e-morphome suffix with low tone, HL* tone pattern
    it_suffix = fst(f"-{composer.e_morphome}{LOW_TONE}")
    it_stem = composer.compose(HLSTAR_RULE)
    it_slots = [(paradigms.suffix(it_suffix, it_stem), PFV_IT)]
    it_slots = add_1pl_incl_r_suffix(it_slots)

    # Ventive: o-morphome suffix (same as imperfective ventive), all low tone
    vent_suffix = fst(f"-{composer.o_morphome}{HIGH_TONE}")
    vent_stem = composer.compose_conditional_harmony(
        ALL_LOW_TONE_RULE,
        use_harmony=composer.is_OV and composer.o_morphome == 'ɔ'
    )
    vent_form = paradigms.suffix(vent_suffix, vent_stem)
    vent_slots = add_perfective_ventive_personal_markers(vent_form)
    vent_slots = add_wh_suffixes_to_slots(vent_slots)

    return [*vent_slots, *it_slots]


def _build_infinitive_slots(composer: StemComposer) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build infinitive slot with ð-class prefix."""
    inf_class = 'ð'
    suffix_fst = fst(f"-{composer.a_morphome}{HIGH_TONE}")
    tone_rule = add_class_prefix(ALL_HIGH_TONE_RULE, inf_class, prefix_tone=HIGH_TONE)
    stem = composer.compose_conditional_harmony(tone_rule, use_harmony=composer.is_OV)
    return [(paradigms.suffix(suffix_fst, stem), INFINITIVE)]


def _build_dependent_slots(composer: StemComposer) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Build dependent itive and ventive slots."""
    # Itive: e-morphome suffix, all low tone
    it_suffix = fst(f"-{composer.e_morphome}{LOW_TONE}")
    it_stem = composer.compose(ALL_LOW_TONE_RULE)

    # Ventive: a-morphome suffix, all low tone (with harmony if OV class)
    vent_suffix = fst(f"-{composer.a_morphome}{LOW_TONE}")
    vent_stem = composer.compose_conditional_harmony(ALL_LOW_TONE_RULE, use_harmony=composer.is_OV)

    slots = [
        (paradigms.suffix(it_suffix, it_stem), DEP_IT),
        (paradigms.suffix(vent_suffix, vent_stem), DEP_VENT),
    ]
    return add_class_prefixes_to_slots(slots)


@output_cache(__file__)
def make_verb_slots(fv_class: str) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Create verb paradigm slots for a given FV class.

    Arguments:
        fv_class:   The FV class (e.g., 'aɔ', 'ao', 'au', etc.)

    Returns:
        List of (FST, FeatureVector) tuples for all verb forms
    """
    composer = StemComposer.for_class(fv_class)

    slots = [
        (STEM, VERB_ROOT),
        *_build_imperative_slots(composer),
        *_build_imperfective_slots(composer),
        *_build_perfective_slots(composer),
        *_build_infinitive_slots(composer),
        *_build_dependent_slots(composer),
    ]

    for rule, _ in slots:
        rule.optimize()

    return slots


# =============================================================================
# Paradigm Builders
# =============================================================================

def get_verb_stem_paradigm(
    fv_class: str,
    stems: Union[str, pynini.Fst, None] = None,
    paradigm_name: Optional[str] = None,
) -> paradigms.Paradigm:
    """
    Get a verb paradigm for stems without auxiliary.

    Arguments:
        fv_class:       The FV class (e.g., 'aɔ')
        stems:          Optional stems to use (defaults to lexicon roots)
        paradigm_name:  Optional paradigm name

    Returns:
        A Paradigm object for the given FV class
    """
    slots = make_verb_slots(fv_class)

    if type(stems) is str:
        stems = [stems]

    if type(stems) is list:
        stems = [fst(stem) for stem in stems]
    elif stems is None:
        stems = get_roots_for_class(fv_class, wrap_w_fsa=True, include_extensions=True)

    if paradigm_name is None:
        paradigm_name = stringify_lexeme_features(
            {"fv": fv_class, "part_of_speech": 'verb', 'aux': 'unmarked'}
        )

    return paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=paradigm_name,
        slots=slots,
        lemma_feature_vector=VERB_ROOT,
        stems=stems,
        boundary=BOUNDARY,
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


# =============================================================================
# Verb+Aux Paradigm Helpers
# =============================================================================

def _allows_h_spread(feature_values: dict) -> bool:
    """Check if H-tone spreading applies based on pronouns."""
    return (
        (feature_values['object'] in ['1du.incl', '1pl.incl', '1pl.excl', '2pl']) or
        (
            feature_values['subject'] in ['1du.incl', '1pl.incl', '2pl'] and
            feature_values['object'].startswith('3')
        )
    )


def _find_verb_slot(verb_paradigm, features_to_match: dict):
    """Find the verb slot matching given features."""
    matching_slots = [
        slot for slot in verb_paradigm.slots
        if slot[1].values == features_to_match
    ]
    assert len(matching_slots) == 1, f"Could not find verb slot for aux features {features_to_match}"
    return matching_slots[0]


def _compose_aux_verb_rule(aux_rule, verb_rule, deixis: str, ventive_allows_hspread: bool) -> pynini.Fst:
    """Compose aux and verb FSTs with appropriate phonological rules."""
    combined_rule = aux_rule + insert_fst(WORD_BOUNDARY_STR) + verb_rule
    combined_rule = combined_rule @ FALL_BLOCKS_H_RULE @ VOWEL_COALESCENCE_RULE

    if deixis == 'itive' or ventive_allows_hspread:
        combined_rule = combined_rule @ H_SPREAD_RULE

    return combined_rule


def get_verb_paradigm_w_aux(
    verb_paradigm: Union[str, paradigms.Paradigm],
    **paradigm_kwargs,
) -> paradigms.Paradigm:
    """
    Get a verb paradigm with auxiliary forms.

    Arguments:
        verb_paradigm:  FV class string or existing Paradigm
        **paradigm_kwargs:  Additional kwargs for get_verb_stem_paradigm

    Returns:
        A Paradigm object combining verb stems with auxiliary
    """
    aux_paradigm = get_aux_paradigm()

    if type(verb_paradigm) is str:
        verb_paradigm = get_verb_stem_paradigm(verb_paradigm, **paradigm_kwargs)

    verb_w_aux_slots = []

    for aux_rule, feature_vector in aux_paradigm.slots:
        new_feature_values = feature_vector.values.copy()

        # Skip forms where aux has wh=marked
        if new_feature_values['wh'] != 'unmarked':
            continue

        ventive_allows_hspread = _allows_h_spread(new_feature_values)

        # Handle unmarked deixis by expanding to all values
        deixis_values = [new_feature_values['deixis']]
        if deixis_values[0] == 'unmarked':
            deixis_values = DEIXIS_VALUES

        for deixis in deixis_values:
            new_feature_values['deixis'] = deixis
            new_feature_vector = features.FeatureVector(
                INFLECTED_VERB,
                *(f"{k}={v}" for k, v in new_feature_values.items())
            )

            # Find matching verb slot
            features_to_match = new_feature_values.copy()

            # Set unmarked for subject, object, class to find verb slot
            # except for 1pl.incl, as this is marked on the verb with -ŕ
            if features_to_match['subject'] != '1pl.incl':
                features_to_match['subject'] = 'unmarked'
            if features_to_match['object'] != '1pl.incl':
                features_to_match['object'] = 'unmarked'
            features_to_match['class'] = 'unmarked'

            verb_rule, _ = _find_verb_slot(verb_paradigm, features_to_match)
            combined_rule = _compose_aux_verb_rule(
                aux_rule, verb_rule, deixis, ventive_allows_hspread
            )
            verb_w_aux_slots.append((combined_rule, new_feature_vector))

    # Add lemma slot
    lemma_slot = (SIGMASTAR, VERB_ROOT)
    verb_w_aux_slots.append(lemma_slot)

    # Build paradigm
    lexical_flags = vectorize_lexeme_string(verb_paradigm.name).values
    lexical_flags['aux'] = 'true'
    paradigm_name = stringify_lexeme_features(lexical_flags)

    return paradigms.Paradigm(
        category=INFLECTED_VERB,
        name=paradigm_name,
        slots=verb_w_aux_slots,
        lemma_feature_vector=VERB_ROOT,
        stems=verb_paradigm.stems,
        boundary=BOUNDARY,
    )

@output_cache(__file__, build_only=True)
def _build_fv_paradigm_pair(fv_class):
    """Helper function for parallel processing"""
    fv_paradigm = get_verb_stem_paradigm(fv_class)
    aux_paradigm = get_verb_paradigm_w_aux(fv_paradigm)
    return fv_paradigm, aux_paradigm

def get_verb_paradigms():
    verb_paradigms = []
    verb_paradigms.append(get_aux_paradigm())

    # build paradigms in parallel, but don't return them from the worker processes
    # with Pool() as pool:
        # pool.map(_build_fv_paradigm_pair, FV_CLASSES)
    # BUG: multiprocessing causes instability
    # don't use multiprocessing for now
    map(_build_fv_paradigm_pair, FV_CLASSES)

    # now gather the built paradigms from disk
    for fv_class in FV_CLASSES:
        fv_paradigm = get_verb_stem_paradigm(fv_class)
        fv_with_aux = get_verb_paradigm_w_aux(fv_paradigm)
        verb_paradigms.append(fv_paradigm)
        verb_paradigms.append(fv_with_aux)

    return verb_paradigms

# =============================================================================
# Inflection Utilities
# =============================================================================

def inflect_verb_with_features(
    root: str,
    paradigm: Union[paradigms.Paradigm, str],
    feature_dict: Dict[str, str],
    expected_verb_type: Literal['stem', 'stem_and_aux', 'all'] = 'all',
) -> List[str]:
    """
    Inflect a verb root with given features.

    Arguments:
        root:               Verb root string to inflect
        paradigm:           Paradigm object or FV class shorthand (e.g., 'aɔ')
        feature_dict:       Dict mapping feature labels to values
        expected_verb_type: Which paradigm(s) to use

    Returns:
        List of inflected form strings
    """
    if type(paradigm) is paradigms.Paradigm:
        pass
    elif type(paradigm) is str and expected_verb_type == 'stem_and_aux':
        paradigm = get_verb_paradigm_w_aux(paradigm)
    elif type(paradigm) is str and expected_verb_type == 'stem':
        paradigm = get_verb_stem_paradigm(paradigm)
    else:
        forms_stem = inflect_verb_with_features(
            root,
            get_verb_stem_paradigm(paradigm),
            feature_dict,
            expected_verb_type='stem'
        )
        forms_aux = inflect_verb_with_features(
            root,
            get_verb_paradigm_w_aux(paradigm),
            feature_dict,
            expected_verb_type='stem_and_aux'
        )
        return [*forms_stem, *forms_aux]

    forms = []
    expected_keys = [feature.name for feature in INFLECTED_VERB.features]
    features_filtered = {k: v for k, v in feature_dict.items() if k in expected_keys}
    slot_for_features = [slot for slot in paradigm.slots if slot[1].values == features_filtered]

    for slot in slot_for_features:
        rule, _ = slot
        form = get_lattice_strs(fst(root) @ rule)
        forms.extend(form)

    return forms


def inflect_aux_with_features(feature_dict: Dict[str, str]) -> List[str]:
    """
    Inflect the auxiliary with given features.

    Arguments:
        feature_dict:   Dict mapping feature labels to values

    Returns:
        List of inflected auxiliary form strings
    """
    forms = []
    aux_paradigm = get_aux_paradigm()
    expected_keys = [feature.name for feature in INFLECTED_AUX.features]
    features_filtered = {k: v for k, v in feature_dict.items() if k in expected_keys}
    slot_for_features = [slot for slot in aux_paradigm.slots if slot[1].values == features_filtered]

    for slot in slot_for_features:
        rule, _ = slot
        form = decode_fst_string(fst("") @ rule)
        forms.append(form)

    return forms

if __name__ == "__main__":
    get_verb_paradigms()