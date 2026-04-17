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

TODO: continue refactor, moving small helpers out to form_helpers.py
and dividing aux/stem logic between verb_forms.py and aux_forms.py,
and adding more documentation, esp. including Tira language examples.
"""

from dataclasses import dataclass
import pynini
from pynini.lib import features, paradigms
from src.decorators import output_cache
from src.forms.aux_forms import get_aux_paradigm
from src.forms.form_helpers import *
from src.forms.form_helpers import make_feature_builder
from src.forms.form_helpers import make_marker_rule
from src.forms.form_helpers import add_1pl_incl_r_suffix
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

"""
## Perfective Ventive Person Markers
The perfective ventive form does not include an auxiliary, so all person
markers are applied directly to the verb stem. Perfective ventive verbs
can be marked with a class prefix, a subject prefix and/or an object suffix.
E.g.

(1) kə̀-     və̀lɛ̀ð           -ɔ́
    CLg-    pull.PFV.VENT   -FV

(2) jə̀-         və̀lɛ̀ð           -áŋà
    1SG.SBJ-    pull.PFV.VENT   -2SG.OBJ

As with the auxiliary, 3rd sg and 3rd pl objects trigger special subject
suffixes, e.g.

(3) kə̀-             və̀lɛ̀ð           -ɛ́ŋí
    CLg.3SG.OBJ-    pull.PFV.VENT   -1SG.SBJ

(4) lə̀-             və̀lɛ̀ð           -ɛ́          -ló
    CLl.3PL.OBJ-    pull.PFV.VENT   -1SG.SBJ    -3PL.OBJ

Note that (2), (3) and (4) all have a 1SG subject, even though the subject marker
is different in each sentence, being a prefix jə̀- in (2) and suffixes -ɛ́ŋí in (3)
and -ɛ́ in (4).

In (3), there is no overt 3SG object marker. Rather, the class prefix agrees with
an implicit 3SG object, and the fact that the subject suffix is the special form for 3SG
objects indicates that the object is 3SG. In (4) the class prefix agrees -l with a 3PL object,
**and** there is an overt 3PL object suffix -ló as well.

To organize the various prefixes and suffixes, we define a dataclass
`PerfectiveVentiveMarkers` that organizes dictionaries of marker forms
across the categories of subject prefixes, subject suffixes w/ 3sg and 3pl
object, and object suffixes.
"""

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
        '3sg': {'suffix': {'required': '-ŋ', 'optional': 'ú'}},
        '1du.incl': {'suffix': '-ɜ́llí'},
        '1pl.incl': {'suffix': '-ɜ́llí-ŕ'},
        '1pl.excl': {'suffix': '-áɲà'},
        '2pl': {'suffix': '-áɲá'},
        '3pl': {'suffix': '-ɜ́l'},
    },
    subject_3pl_obj={
        '1sg': {'suffix': '-ɛ́-ló'},
        '2sg': {'suffix': '-á-ló'},
        '3sg': {'suffix': {'required': '-lɔ́-ŋ', 'optional': 'ú'}},
        '1du.incl': {'suffix': '-ɜ́llí'},
        '1pl.incl': {'suffix': '-ɜ́llí-ŕ'},
        '1pl.excl': {'suffix': '-áɲâ-l'},
        '2pl': {'suffix': '-áɲá-l'},
        '3pl': {'suffix': '-ɜ́l-ló'},
    },
    object_suffixes={
        '1sg': {'suffix': '-íŋì'},
        '2sg': {'suffix': '-áŋà'},
        '3sg': {'suffix': {'required': '-ŋ', 'optional': 'ú'}},
        '1du.incl': {'suffix': '-átɛ́'},
        '1pl.incl': {'suffix': '-átɛ́-ŕ'},
        '1pl.excl': {'suffix': '-éɲárɛ́'},
        '2pl': {'suffix': '-átɛ́'},
    },
)


"""
## Perfective Ventive Slot-Building Helpers
Constructing all perfective ventive forms requires building slots for class
prefixes, subject prefixes, subject suffixes for 3sg and 3pl objects, and object
suffixes. The following helper functions define the logic for constructing perfective
ventive forms:

- _build_pfv_vent_non_pronominal_slots: Adds class prefixes to non-pronominal slots
- _build_pfv_vent_subject_prefix_slots: Builds slots for subject prefixes
- _build_pfv_vent_subject_3sg_obj_slots: Builds slots for subject suffixes when object is 3sg
- _build_pfv_vent_subject_3pl_obj_slots: Builds slots for subject suffixes when object is 3pl
- _build_pfv_vent_object_slots: Builds slots for object-only marking
- _build_pfv_vent_combined_sbj_obj_slots: Builds combined subject+object slots, filtering invalid combinations
- _add_perfective_ventive_personal_markers: Main function to add all personal markers to perfective ventive verb forms
"""

def _build_pfv_vent_non_pronominal_slots(
    form_fst: pynini.Fst,
    get_features
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Build non-pronominal slots with class prefixes.
    Wraps `add_class_prefixes_to_slots`.
    """
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
        rule = make_marker_rule(marker)
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
        rule = make_marker_rule(marker)
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
        rule = make_marker_rule(marker)
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
    """
    Build slots for object-only marking (i.e. subject indicated
    only by class prefix).
    """
    suffix_slots = []
    for person, marker in markers.object_suffixes.items():
        rule = make_marker_rule(marker)
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
        sbj_rule = make_marker_rule(sbj_marker)

        for obj_person, obj_marker in markers.object_suffixes.items():
            # Skip same-person combinations (e.g., 1sg subject + 1sg object)
            if sbj_person[0] == obj_person[0]:
                continue

            obj_rule = make_marker_rule(obj_marker)
            slots.append((
                form_fst @ sbj_rule @ obj_rule,
                get_features(sbj=sbj_person, obj=obj_person)
            ))

    return slots


def add_perfective_ventive_personal_markers(
    form_fst: pynini.Fst,
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Add person and class markers to perfective ventive verb forms.

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
    tone_rule = add_class_prefix(stem=ALL_HIGH_TONE_RULE, class_agree=inf_class, prefix_tone=HIGH_TONE)
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

@output_cache(__file__)
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
    for paradigm_tuple in map(_build_fv_paradigm_pair, FV_CLASSES):
        verb_paradigms.extend(paradigm_tuple)

    return verb_paradigms

def get_verb_paradigm_dict():
    """
    Get a dict mapping paradigm names to Paradigm objects.
    Dict has shape:
    {
        'stem': {
            'aɔ': Paradigm,
            'ao': Paradigm,
            ...
        },
        'stem_and_aux': {
            'aɔ': Paradigm,
            'ao': Paradigm,
            ... 
        },
        'aux': Paradigm,
    }
    """
    paradigms_list = get_verb_paradigms()
    paradigm_dict = {
        'stem': {},
        'stem_and_aux': {},
    }
    aux_paradigm = [p for p in paradigms_list if p.name == 'aux=true'][0]
    paradigm_dict['aux'] = aux_paradigm

    for paradigm in paradigms_list:
        if paradigm.name == 'aux=true':
            continue
        lexical_flags = vectorize_lexeme_string(paradigm.name).values
        fv_class = lexical_flags['fv']
        if lexical_flags['aux'] == 'true':
            paradigm_dict['stem_and_aux'][fv_class] = paradigm
        else:
            paradigm_dict['stem'][fv_class] = paradigm
    return paradigm_dict

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
    else: # type(paradigm) is str and expected_verb_type == 'all'
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