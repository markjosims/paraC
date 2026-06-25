"""
The `Paradigm` class describes a paradigm or sub-paradigm in the
linguistic sense, represented here as a set of `Marker` lists over
a feature space. It also provides logic for defining the order of
application for markers, and for selecting stems and principal parts
from the lexicon.
"""

from loguru import logger
from src.grammar.classes import Registry
from src.grammar.registry.lexicon_registry import LexiconRegistry, Lexicon
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.registry.feature_combination_registry import FeatureValueCombinations
from src.grammar.registry.feature_marker_registry import (
    FeatureMarkers,
    MarkerList,
    Marker,
)
from src.grammar.registry.contingent_marker_registry import ContingentMarkers
from src.grammar.orchestrator.marker_orchestrator import MarkerOrchestrator
from src.validation import validate_file_reference_str
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.orchestrator.feature_orchestrator import (
    stringify_features,
    serialize_feature_str,
)
from src.fst_utils import FsaLike
from copy import deepcopy
from pathlib import Path
import itertools
import pynini
from pynini.lib import pynutil
from collections import defaultdict
import pandas as pd
from tqdm import tqdm
import os
import functools

EDIT_BOUND = 5
EDIT_COST = 1


class Paradigm:
    """
    Object for combining marker objects based on multiple feature values.
    Allows combination of standard marker objects (i.e. for one feature each)
    and contingent marker objects (i.e. for multiple features simultaneously).
    Contingent marker objects are given priority when combining.

    Validates that all feature values in the feature_value_combinations are
    recognized by the provided marker objects and that no 'order' values in
    the marker objects are unrecognized.

    Allows for querying of marker combinations based on feature values,
    and also provides string I/O with marker transducers.
    """

    def __init__(
        self,
        markers: list[FeatureMarkers],
        contingent_markers: list[ContingentMarkers],
        lexicon: Lexicon,
        fst_orchestrator: FstOrchestrator,
        name: str | None = None,
        pattern_filter: str | None = None,
        fixed_lexical_features: list[tuple[Feature, str]] | None = None,
        fixed_features: dict[str, str] | None = None,
        marker_order: list[str] | None = None,
        feature_value_combinations: FeatureValueCombinations | None = None,
        global_markers: MarkerList | None = None,
    ):
        self.is_initialized = False
        self.fst_orchestrator_initialized = False
        self.main_graphs_built = False
        self.edit_graphs_built = False

        self.name = name
        if name is None:
            self.name = "[UNNAMED]"
        self.feature_value_combinations = feature_value_combinations
        self.fixed_features = fixed_features or {}
        self.marker_order = marker_order or []
        self.features = lexicon.features
        self.part_of_speech = lexicon.part_of_speech
        self.lexicon = lexicon
        self.pattern_filter = pattern_filter
        self.fixed_lexical_features = fixed_lexical_features or []
        self.lexical_filter = None  # to be initialized later
        self.markers = deepcopy(markers)
        self.contingent_markers = deepcopy(contingent_markers)
        self.global_markers = global_markers
        self.fst_orchestrator = fst_orchestrator

        if self.fst_orchestrator and self.fst_orchestrator.is_initialized:
            self.fst_orchestrator_initialized = True
        else:
            logger.info(
                "FST registry not provided or not initialized. "
                "FST-based operations will not be available until the registry is initialized."
            )
        self.initialize()

    @classmethod
    def from_config(
        cls,
        config: dict,
        marker_orchestrator: MarkerOrchestrator,
        lexicon_registry: LexiconRegistry,
        fst_orchestrator: FstOrchestrator,
    ) -> "Paradigm":
        """
        Factory method for constructing a Paradigm object from a MarkerOrchestrator
        and a FeatureValueCombinations object. This method will pull the relevant
        marker objects from the MarkerOrchestrator based on the provided features,
        and will construct any inline markers as needed.
        """

        # load part of speech and lexicon
        paradigm_name = None
        paradigm_source = config.get("source_path", None)
        if paradigm_source is not None:
            paradigm_name = Path(paradigm_source).stem

        part_of_speech_name = config["part_of_speech"]
        lexicon = lexicon_registry.get_lexicon(part_of_speech_name)
        marker_order = config.get("order", None)

        feature_value_combinations = None
        feature_value_combination_name = config.get("feature_value_combinations")
        if feature_value_combination_name:
            feature_value_combinations = marker_orchestrator.get_feature_combinations(
                feature_value_combination_name
            )

        # load filters
        filter_config = config.get("filter", {})
        pattern_filter = filter_config.get("pattern", None)
        lexical_feature_strs: list[list[str]] = filter_config.get(
            "lexical_features", []
        )
        fixed_lexical_features = []
        for feature_name, feature_value in lexical_feature_strs:
            feature = marker_orchestrator.feature_values_registry.features[feature_name]
            fixed_lexical_features.append((feature, feature_value))

        fixed_features = {}
        markers = []
        for feature_name, marker_str in config["feature_markers"].items():
            if marker_str is None:
                # indicates that this feature is marked only with ContingentMarkers
                # and should not be included in the standard markers
                continue

            if not marker_str.startswith("$"):
                # indicates that feature is fixed to a single value
                # where 'marker_str' indicates the value
                fixed_features[feature_name] = marker_str
            else:
                marker_set = marker_orchestrator.get_feature_markers(marker_str)
                if marker_set.feature.name != feature_name:
                    raise ValueError(
                        f"Feature '{feature_name}' in paradigm config does not match feature '{marker_set.feature}' in marker config '{marker_str}'."
                    )
                markers.append(marker_set)

        contingent_markers = []
        for contingent_marker_str in config.get("contingent_markers", []):
            contingent_marker_set = marker_orchestrator.get_contingent_markers(
                contingent_marker_str
            )
            contingent_markers.append(contingent_marker_set)

        global_marker_config = config.get("global_markers", None)
        global_markers = MarkerList.from_config(global_marker_config)

        return cls(
            name=paradigm_name,
            markers=markers,
            pattern_filter=pattern_filter,
            fixed_lexical_features=fixed_lexical_features,
            contingent_markers=contingent_markers,
            fixed_features=fixed_features,
            marker_order=marker_order,
            lexicon=lexicon,
            feature_value_combinations=feature_value_combinations,
            fst_orchestrator=fst_orchestrator,
            global_markers=global_markers,
        )

    def get_markers_for_feature_values(
        self, feature_values: dict[str, str], ignore_extra: bool = True
    ) -> MarkerList:
        """
        Get the list of markers that should be applied for a given combination of feature values.
        This is determined by checking the feature markers and contingent markers in the paradigm
        for matches with the provided feature values, and then sorting the resulting markers
        according to the marker order specified in the paradigm.

        Priority is given to contingent markers over standard feature markers, such that if a
        contingent marker matches the provided feature values, any standard feature markers that
        also match those feature values will be ignored.
        """
        feature_values = deepcopy(feature_values)

        if (self.feature_value_combinations is not None) and (
            not self.feature_value_combinations.combination_is_valid(feature_values)
        ):
            raise ValueError(
                f"Feature value combination {feature_values} is not valid according to the paradigm's feature_value_combinations."
            )
        # TODO: add helper function for checking valid combination when feature_value_combinations is not built

        # TMP remove all unmarked features
        # TODO: standardize handling unmarked features
        feature_values = {k: v for k, v in feature_values.items() if v != "unmarked"}

        # filter out fixed features
        for fixed_feature, fixed_value in self.fixed_features.items():
            if fixed_feature not in feature_values:
                continue
            requested_value = feature_values[fixed_feature]
            if requested_value not in (fixed_value, "unmarked"):
                raise KeyError(
                    f"Cannot inflect for feature {fixed_feature}={requested_value} "
                    f"when paradigm has fixed value {fixed_feature}={fixed_value}"
                )
            else:
                feature_values.pop(fixed_feature)

        applicable_markers = []
        remaining_features = set(feature_values.keys())
        assigned_features = remaining_features.copy()

        # Vector-based contingent marker lookup
        for contingent_set in self.contingent_markers:
            for vector, marker_list in contingent_set.feature_mappings.items():
                if vector.issubset(feature_values.items()):
                    applicable_markers.extend(marker_list)
                    matched_feature_names = {k for k, v in vector}
                    remaining_features -= matched_feature_names

        for feature in remaining_features:
            feature_value_pair = (feature, feature_values[feature])
            if feature_value_pair in self.feature_marker_map:
                marker_list = self.feature_marker_map[feature_value_pair]
                applicable_markers.extend(marker_list)
            elif not ignore_extra:
                raise KeyError(
                    f"Cannot find FeatureMarker for  {feature_value_pair} for feature set {feature_values} "
                    f"where features {assigned_features} are assigned by ContingentMarkers"
                )
        if self.marker_order:
            applicable_markers.sort(
                key=lambda marker: (
                    self.marker_order.index(marker.order)
                    if marker.order in self.marker_order
                    else -1
                )
            )
        applicable_markers = MarkerList(applicable_markers)
        return applicable_markers

    def initialize(self):
        """
        Initialize the paradigm by validating features and building marker transducers.
        This is separate from __init__ to allow for lazy initialization.
        """
        self._validate_features_and_order_values()
        self._validate_principal_parts_and_filters()
        self._build_marker_mappings()
        if self.fst_orchestrator and not self.fst_orchestrator.is_initialized:
            logger.info("Initializing FST registry as part of paradigm initialization.")
            self.fst_orchestrator.initialize()
            self.fst_orchestrator_initialized = True
        if self.global_markers:
            self._add_global_markers()
        self._build_lexical_filter()
        self._build_all_marker_transducers()
        self.is_initialized = True

    def to_dict(self) -> dict:
        """Serialize to Paradigm YAML format."""
        fm_dict = {}
        # Fixed features
        for f, v in self.fixed_features.items():
            fm_dict[f] = v
        # Feature markers (refs)
        for fm in self.markers:
            if fm.source:
                fm_dict[fm.feature.name] = validate_file_reference_str(
                    Path(fm.source).stem
                )
            else:
                fm_dict[fm.feature.name] = "[UNRESOLVED]"

        # Reconstruct filter
        lf_list = [[f.name, v] for f, v in self.fixed_lexical_features]
        filter_doc = {"lexical_features": lf_list}
        if self.pattern_filter:
            filter_doc["pattern"] = self.pattern_filter

        doc = {
            "kind": "Paradigm",
            "part_of_speech": validate_file_reference_str(self.lexicon.name),
            "order": self.marker_order,
            "feature_markers": fm_dict,
            "contingent_markers": [
                validate_file_reference_str(Path(cm.source).stem)
                for cm in self.contingent_markers
                if cm.source
            ],
            "filter": filter_doc,
        }
        if self.feature_value_combinations and self.feature_value_combinations.source:
            doc["feature_value_combinations"] = validate_file_reference_str(
                Path(self.feature_value_combinations.source).stem
            )

        if self.global_markers:
            gm = self.global_markers.to_dict()
            if gm:
                doc["global_markers"] = gm

        return doc

    def _validate_features_and_order_values(self):
        """
        Validate that all feature values in markers or contingent markers
        are recognized by the Lexicon's part of speech features and, if
        applicable, the FeatureValueCombinations object.
        """
        supported_features = set()
        if self.feature_value_combinations:
            if set(self.feature_value_combinations.feature_names) != set(self.features):
                raise ValueError(
                    f"Feature names in feature_value_combinations do not match "
                    f"those in the lexicon's part of speech. "
                    f"Expected {self.features}, got {self.feature_value_combinations.feature_names}."
                )

        for marker_set in self.markers:
            # validate that inflectional feature in marker set is recognized
            self._validate_marker_set(marker_set)
            supported_features.add(marker_set.feature.name)

        for contingent_marker_set in self.contingent_markers:
            supported_features.update(
                self._validate_contingent_marker_set(contingent_marker_set)
            )

    def _validate_marker_set(self, marker_set: FeatureMarkers):
        """
        Validate that the inflectional feature in the marker set is recognized and that all
        order and lexical feature values in the marker set are recognized.
        """
        if marker_set.feature not in self.features:
            raise ValueError(
                f"Feature '{marker_set.feature}' in marker set not recognized. "
                f"Expected one of {self.features}."
            )

        # validate that order and lexical feature values are recognized
        for marker_list in marker_set.data.values():
            for marker in marker_list:
                order = marker.order
                if order and order not in self.marker_order:
                    raise ValueError(
                        f"Marker order '{order}' not recognized. "
                        f"Expected one of {self.marker_order}."
                    )
                lexical_features = marker.lexical_features
                for feature_name, feature_value in lexical_features.items():
                    feature = [
                        feature
                        for feature in self.lexicon.lexical_features
                        if feature.name == feature_name
                    ]
                    if not feature:
                        raise ValueError(
                            f"Marker {marker} has unrecognized lexical feature {feature_name}"
                        )
                    assert len(feature) == 1
                    feature = feature[0]
                    if feature_value not in feature.values:
                        raise ValueError(
                            f"Marker {marker} has unrecognized value {feature_value} for lexical feature {feature_name}"
                        )

    def _validate_contingent_marker_set(self, contingent_marker_set: ContingentMarkers):
        """
        Validate that all feature values in the contingent marker set are recognized and that all
        order values in the marker set are recognized.

        Returns the set of features that are marked by the contingent marker set,
        for later validation that all features are supported by markers in the paradigm.
        """
        supported_features = set()
        for vector, marker_list in contingent_marker_set.feature_mappings.items():
            for f_name, f_val in vector:
                # check if feature is recognized
                feature = next((f for f in self.features if f.name == f_name), None)
                if not feature:
                    raise ValueError(
                        f"Feature '{f_name}' in contingent marker vector not recognized. "
                        f"Expected one of {self.features}."
                    )
                supported_features.add(f_name)

            for marker in marker_list:
                order = marker.order
                if order and order not in self.marker_order:
                    raise ValueError(
                        f"Marker order '{order}' not recognized. "
                        f"Expected one of {self.marker_order}."
                    )
        return supported_features

    def _validate_principal_parts_and_filters(self):
        """
        Validate that all markers with 'principal_part' order have a corresponding
        stem in the lexicon, and that all markers with 'lexical' order have a
        corresponding stem in the lexicon marked as lexical.
        """
        for marker_set in self.markers:
            for marker_list in marker_set.data.values():
                if (marker_list.principal_part is not None) and (
                    marker_list.principal_part not in self.lexicon.principal_parts
                ):
                    raise ValueError(
                        f"Principal part marker '{marker_list.principal_part}' in feature marker set for feature '{marker_set.feature}' does not have a corresponding stem in the lexicon."
                    )

        expected_lexical_feature_names = [
            feature.name for feature in self.lexicon.lexical_features
        ]
        for feature, _ in self.fixed_lexical_features:
            if feature.name not in expected_lexical_feature_names:
                raise ValueError(
                    f"Lexical feature '{feature}' in paradigm config not recognized in lexicon. "
                    f"Expected one of {self.lexicon.lexical_features}."
                )

        if self.pattern_filter:
            if self.pattern_filter not in self.fst_orchestrator.patterns:
                raise ValueError(
                    f"Pattern filter '{self.pattern_filter}' not recognized in FstRegistry. "
                    "Check pattern configs."
                )

    def _build_marker_mappings(self):
        """
        Builds a mapping for feature markers that map from feature values
        (represented as tuples of (feature, value) pairs) to the list of
        markers that should be applied for that combination of feature values.

        Contingent marker mappings are handled directly within the
        ContingentMarkers objects.
        """

        # build flat mapping for feature markers
        self.feature_marker_map: dict[tuple[str, str], MarkerList] = {}
        for marker_set in self.markers:
            for feature_value, marker_list in marker_set.data.items():
                self.feature_marker_map[(marker_set.feature.name, feature_value)] = (
                    marker_list
                )

    def _add_global_markers(self):
        for marker_set in self.markers:
            for marker_list in marker_set.data.values():
                marker_list.merge_list(self.global_markers)
        for contingent_set in self.contingent_markers:
            for marker_list in contingent_set.feature_mappings.values():
                marker_list.merge_list(self.global_markers)

    def _build_all_marker_transducers(self):
        """
        For every feature and contingent feature marker list,
        instantiate the FST for all markers contained.
        """
        for marker_set in self.markers:
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)
        for contingent_set in self.contingent_markers:
            for marker_list in contingent_set.feature_mappings.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)

    def _build_marker_transducer(self, marker: Marker):
        if marker.transducer_built:
            logger.info(f"Transducer for marker '{marker}' already built. Skipping.")
            return
        if self.fst_orchestrator is None:
            raise ValueError(
                "Cannot build marker without FstRegistry but `self.FstRegistry` is None"
            )

        elif marker.type == "rule":
            assert isinstance(marker.value, str)
            marker_rule = self.fst_orchestrator.get_rule(marker.value)
        elif marker.type == "prefix":
            assert isinstance(marker.value, str)
            marker_rule = self.fst_orchestrator.prefix(marker.value)
        elif marker.type == "suffix":
            assert isinstance(marker.value, str)
            marker_rule = self.fst_orchestrator.suffix(marker.value)
        elif marker.type == "replace":
            assert isinstance(marker.value, tuple)
            marker_rule = self.fst_orchestrator.replace_transducer(
                marker.value[0], marker.value[1]
            )
        elif marker.type == "suppletion":
            sigma_star = self.fst_orchestrator.sigma_star
            assert isinstance(marker.value, str)
            marker_rule = self.fst_orchestrator.replace_transducer(
                sigma_star, marker.value
            )
        elif marker.type == "principal_part":
            assert isinstance(marker.value, str)
            marker_rule = self._get_principal_part_transducer(marker.value)
        else:
            raise ValueError(f"Unrecognized marker type {marker.type}")

        marker.set_transducer(marker_rule.fst)

    def _get_principal_part_transducer(self, principal_part: str):
        """
        Create a root -> principal_part transducer for the given principal
        part by computing a union over the lexical entries for all roots in
        the lexicon marked as that principal part. Lexical entries lacking
        the principal part will be transduced to themselves.
        """

        if not self.fst_orchestrator_initialized:
            raise ValueError(
                "FST registry must be initialized to get principal part transducer."
            )
        if principal_part not in self.lexicon.principal_parts:
            raise ValueError(f"Principal part '{principal_part}' not found in lexicon.")

        input_strings = self.lexicon.get_roots()
        output_strings = self.lexicon.get_column_data(principal_part, fill_w_root=True)
        string_map = list(zip(input_strings, output_strings))
        return self.fst_orchestrator.string_map_transducer(string_map)

    def _get_lexical_feature_transducer(self):
        """
        Creates a graph mapping bare roots to roots marked with lexical feature tags,
        e.g. [BOW]àpɾí[EOW] -> [sg_class=j][BOW]àpɾí[EOW].
        """

        entries = self.lexicon.entries

        # get a list of dicts [{feature: value}, {feature: value}, ...]
        # then stringify
        feature_cols = [feature.name for feature in self.lexicon.lexical_features]
        feature_values = entries.loc[self.lexical_filter, feature_cols]
        feature_strs = feature_values.apply(stringify_features, axis=1).tolist()

        # get transducer graph
        roots = self.get_filtered_roots()
        root_fsas = [self.fst_orchestrator.word_fsa(root) for root in roots]
        roots_w_feature = [
            self.fst_orchestrator.word_fsa(root, prefix=feature_str)
            for root, feature_str in zip(roots, feature_strs)
        ]
        lexical_feature_fst = pynini.union(
            *[
                pynini.cross(root, root_w_feature)
                for root, root_w_feature in zip(root_fsas, roots_w_feature)
            ]
        )

        return lexical_feature_fst

    def _get_lexical_feature_mask(self) -> pd.Series:
        """
        Apply pattern and lexical features to lexicon (if applicable)
        and return all remaining roots.
        """
        entries = self.lexicon.entries
        feature_mask = pd.Series([True] * len(entries))

        for feature, feature_value in self.fixed_lexical_features:
            feature_col = entries[feature.name]
            feature_mask &= feature_col == feature_value

        return feature_mask

    def _build_lexical_filter(self):
        """
        Get boolean filter after applying both lexical feature and
        pattern filters (if applicable). Equivalent to
        `self._get_fixed_lexical_features()` if no pattern filter is
        specified.
        """
        entries = self.lexicon.entries
        feature_mask = self._get_lexical_feature_mask()

        if not self.pattern_filter:
            self.lexical_filter = feature_mask
            return

        # pattern filter is present
        # test if `filter_strings_by_pattern` returns non-empty output
        if self.pattern_filter:
            self.pattern_filter: str
            pattern_mask = (
                entries["root"]
                .apply(
                    lambda root: self.fst_orchestrator.filter_strings_by_pattern(
                        root, self.pattern_filter
                    )
                )
                .apply(bool)
            )
        else:
            pattern_mask = pd.Series([True] * len(entries))

        lexical_filter = pattern_mask & feature_mask
        self.lexical_filter = lexical_filter

    def get_filtered_roots(self):
        """
        Return list of all roots that pass both lexical feature filters
        and pattern filters, if applicable.
        """

        roots = self.lexicon.entries.loc[self.lexical_filter, "root"].tolist()
        return roots

    def inflect(self, stem: FsaLike, feature_values: dict[str, str]) -> pynini.Fst:
        """
        Inflect a given stem according to the markers specified for the provided feature values.
        """

        if not self.is_initialized:
            raise ValueError("Paradigm must be fully initialized to inflect.")

        # attempt to transducer input stem to form with lexical features
        # assuming stem is recognized by lexicon
        try:
            stem = self.fst_orchestrator._cast_fsalike_to_fsa(stem)
            new_stem = stem @ self._get_lexical_feature_transducer()
            stem = new_stem
        # if unseccessful, just use input stem as-is
        except Exception as e:
            logger.exception(
                f"Could not map stem {stem} to recognized root with lexical features", e
            )

        markers = self.get_markers_for_feature_values(feature_values)
        inflected_form_fst = self._apply_markers(stem, markers)
        return inflected_form_fst

    def get_valid_combinations(
        self, fixed_features: dict[str, str] | None = None
    ) -> list[dict[str, str]]:
        """
        Return a list of dictionaries of shape {"feature_name": "feature_value"}
        describing all possible feature vectors allowed within a paradigm,
        optionally constrained by fixed feature values passed as a dictionary.
        """
        if fixed_features is None:
            fixed_features = self.fixed_features
        else:
            fixed_features = {**self.fixed_features, **fixed_features}

        if self.feature_value_combinations:
            # TODO: see why self.feature_value_combinations is not getting set
            return self.feature_value_combinations.get_all_combinations(fixed_features)
        # for each feature get a list of dicts
        # [{"feature_name": "feature_value"}, ...]
        # then get the cartesian product across those lists
        # to get all combinations
        free_features = [
            feature for feature in self.features if feature.name not in fixed_features
        ]

        # all features already specified, return as list
        if not free_features:
            return [fixed_features]

        feature_value_lists = []
        for feature in free_features:
            feature_value_lists.append(
                [{feature.name: value} for value in feature.values]
            )
        combination_tuples = itertools.product(*feature_value_lists)
        # itertools.product returns an iterator over tuples of shape
        # ({feature: value}, {feature: value}, ...)
        # collapse list of tuples to a list of dicts'
        combinations = [
            functools.reduce(lambda a, b: a | b, combo) for combo in combination_tuples
        ]

        # re-introduce fixed features to combinations
        combinations = [combo | fixed_features for combo in combinations]

        return combinations

    def inflect_subparadigm(
        self,
        stem: FsaLike,
        fixed_features: dict[str, str] | None = None,
        max_rows: int = None,
        skip_errors: bool = True,
    ) -> list[tuple[pynini.Fst, dict[str, str]]]:
        """
        Inflect a given stem according to the markers specified for the
        provided fixed feature values.
        """
        valid_combinations = self.get_valid_combinations(fixed_features)
        if max_rows is not None:
            valid_combinations = valid_combinations[:max_rows]

        results = []
        for combo in valid_combinations:
            try:
                fst = self.inflect(stem, combo)
                results.append((fst, combo))
            except Exception as e:
                error = f"Error {e} occurred while computing FST for stem {stem} and features {combo}"
                if skip_errors:
                    logger.warning(error + ", skipping...")
                else:
                    raise ValueError(error)

        if len(results) < len(valid_combinations):
            logger.warning(
                f"Successfully computed {len(results)} forms out of {len(valid_combinations)} expected"
            )
        else:
            logger.info(f"Successfully computed {len(results)} forms")

        return results

    def get_subparadigm_inflect_graph(
        self, fixed_features: dict[str, str] | None = None
    ) -> pynini.Fst:
        """
        Wraps `inflect_subparadigm` but passes the all-roots FSA as the stem input.
        Returns a single unioned FST.
        """
        all_roots = self.lexicon.get_roots()
        if not all_roots:
            return pynini.Fst()

        stem_fsa = pynini.union(
            *[self.fst_orchestrator.fsa(r) for r in all_roots]
        ).optimize()
        results = self.inflect_subparadigm(stem=stem_fsa, fixed_features=fixed_features)

        fsts = []
        for fst, _ in results:
            fsts.append(fst)

        if not fsts:
            return pynini.Fst()

        return pynini.union(*fsts).optimize()

    def get_subparadigm_table(
        self,
        stem: str,
        fixed_features: dict[str, str] | None = None,
        only_free_feature_columns: bool = True,
        max_rows: int | None = 100,
    ) -> list[dict[str, str]]:
        """
        Wraps `self.inflect_subparadigm` and formats the output
        in a list of dicts for displaying as a table.
        """
        inflected_results = self.inflect_subparadigm(
            stem=stem, fixed_features=fixed_features, max_rows=max_rows
        )

        if only_free_feature_columns:
            if fixed_features is None:
                fixed_features = self.fixed_features
            else:
                fixed_features = {**self.fixed_features, **fixed_features}

            free_features = [
                feature
                for feature in self.features
                if feature.name not in fixed_features
            ]

            inflected_results = [
                (fst, {k: v for k, v in combination.items() if k not in free_features})
                for fst, combination in inflected_results
            ]

        table_rows = []
        for fst, combination in inflected_results:
            form_strings = self.fst_orchestrator.fsm_strings(fst)
            concatenated_forms = "; ".join(form_strings)
            row_data = {"form": concatenated_forms, **combination}
            table_rows.append(row_data)
        return table_rows

    def get_inflection_stages(
        self, stem: str, feature_values: dict[str, str]
    ) -> list[dict[str, str]]:
        """
        Get the intermediate stages of inflection for a given stem and feature values.
        """
        if not self.is_initialized:
            raise ValueError(
                "Paradigm must be fully initialized to get inflection stages."
            )

        # attempt to transducer input stem to form with lexical features
        # assuming stem is recognized by lexicon
        try:
            stem = self.fst_orchestrator._cast_fsalike_to_fsa(stem)
            new_stem = stem @ self._get_lexical_feature_transducer()
            stem = new_stem
        # if unseccessful, just use input stem as-is
        except Exception as e:
            logger.exception(
                f"Could not map stem {stem} to recognized root with lexical features", e
            )

        markers = self.get_markers_for_feature_values(feature_values)
        stages = self._apply_markers(stem, markers, store_intermediate=True)

        table_data = []
        for stage_fst, marker in stages:
            stage_data = {}
            if marker is None:
                stage_data["order"] = "<INITIAL>"
                stage_data["marker_type"] = None
                stage_data["marker_value"] = None
                stage_data["feature_value"] = None
            else:
                stage_data["order"] = marker.order
                stage_data["marker_type"] = marker.type
                stage_data["marker_value"] = marker.value
                stage_data["feature_value"] = marker.feature_value

            stage_strings = self.fst_orchestrator.fsm_strings(
                stage_fst,
                strip_all_flags=False,
                strip_word_edge_symbols=True,
            )
            for string in stage_strings:
                table_data.append(
                    {
                        **stage_data,
                        "form": string,
                    }
                )

        final_form = self.fst_orchestrator.fsm_strings(
            stages[-1][0], strip_all_flags=True
        )
        for string in final_form:
            table_data.append(
                {
                    "order": "<FINAL>",
                    "marker_type": None,
                    "marker_value": None,
                    "feature_value": None,
                    "form": string,
                }
            )

        return table_data

    def _apply_markers(
        self,
        stem: FsaLike,
        markers: list[MarkerList],
        store_intermediate: bool = False,
    ) -> pynini.Fst | list[tuple[pynini.Fst, Marker]]:
        """
        Apply a list of markers to a given stem by composing the stem with
        the transducer for each marker in the list, in order.
        """
        if not self.is_initialized:
            raise ValueError("Paradigm must be fully initialized to apply markers.")

        result = None
        current_fst = self.fst_orchestrator._cast_fsalike_to_fsa(stem, is_word=True)

        if store_intermediate:
            result = [(current_fst, None)]

        for marker in markers:
            fst_list = marker.fst
            if isinstance(fst_list, pynini.Fst):
                fst_list = [fst_list]
            for fst in fst_list:
                current_fst = current_fst @ fst
                if store_intermediate:
                    result.append((current_fst, marker))

        if store_intermediate:
            return result

        return current_fst

    def build_all_graphs(self):
        self._build_main_graphs()
        self._build_edit_graphs()

    def _build_main_graphs(self):
        """
        Build a main graph for the paradigm by computing the union of all
        possible paths through the paradigm based on the feature markers and
        contingent markers, allowing for efficient inflection and parsing of
        forms.

        The graph is built by iterating through all stems and combinations
        and accumulating a list of root[features...] -> form transducers, then
        computing a union over each transducer as the main Inflector graph, and
        the Parser graph by inverting the Inflector graph.
        """
        logger.info(
            f"Building main (inflector and parser) graphs for paradigm {self.name}..."
        )

        roots = self.get_filtered_roots()
        inflect_fst_list = []
        for root in tqdm(roots, desc=f"Inflecting roots for paradigm {self.name}"):
            root_fsa = self.fst_orchestrator.word_fsa(root)

            # iter thru all feature combos and build transducers
            inflected_transducers = self.inflect_subparadigm(
                stem=root_fsa,
                fixed_features=None,
                max_rows=None,
                skip_errors=True,
            )

            for fst, combination in inflected_transducers:
                feature_str = stringify_features(combination)

                inflect_input = root_fsa + self.fst_orchestrator.fsa(feature_str)
                inflect_output = pynini.project(fst, "output")
                inflect_fst = pynini.cross(inflect_input, inflect_output)

                inflect_fst.optimize()
                inflect_fst_list.append(inflect_fst)

        inflect_graph = pynini.union(*inflect_fst_list)
        inflect_graph.optimize()

        parse_graph = pynini.invert(inflect_graph)
        parse_graph.optimize()

        self.inflect_graph = inflect_graph
        self.parse_graph = parse_graph
        self.main_graphs_built = True

        logger.info("Main graphs built.")

    def get_parses(
        self, form: FsaLike, serialize: bool = False
    ) -> list[str | dict[str, str]]:
        """
        Computes a parse lattice by composing the input string with the main parse graph
        then returns a list of strings of all candidate parses, where feature values
        are specified in the format "ROOT[feat=val][feat=val][feat=val]..."

        If `serialize=True`, casts the feature string to a dict using `serialize_feature_str`
        """
        if not self.main_graphs_built:
            logger.info("`get_parses` called without main graphs built, building...")
            self.build_all_graphs()

        form_fsa = self.fst_orchestrator._cast_fsalike_to_fsa(form, is_word=True)
        parse_lattice = form_fsa @ self.parse_graph
        parse_strings = self.fst_orchestrator.fsm_strings(parse_lattice)

        if serialize:
            serialized_parses = []
            for parse in parse_strings:
                feature_index = parse.index("[")
                root = parse[:feature_index]
                feature_str = parse[feature_index:]
                feature_dict = serialize_feature_str(feature_str)
                feature_dict["root"] = root
                serialized_parses.append(feature_dict)
            return serialized_parses

        return parse_strings

    def _build_edit_graphs(self):
        """
        Build left and right edit factors and a pre-compiled
        searchable lexicon.

        Based on code in the [Pynini EditTransducer](https://github.com/kylebgorman/pynini/blob/27ce19048193358cd362a4de6b157cb43ab6e2eb/pynini/lib/edit_transducer.py)
        """
        logger.info(f"Building edit graph for paradigm {self.name}...")
        if not self.main_graphs_built:
            raise ValueError("Cannot build edit graph without main graph")

        # shorthands for ease of life
        insert = self.fst_orchestrator.insert
        delete = self.fst_orchestrator.delete
        substitute = self.fst_orchestrator.substitute
        sigma = self.fst_orchestrator.sigma
        sigma_star = self.fst_orchestrator.sigma_star

        wfsa = self.fst_orchestrator.wfsa

        # build single edit transducers
        insert_fst = pynutil.insert(wfsa(insert, weight=EDIT_COST / 2))
        delete_fst = pynini.cross(sigma, wfsa(delete, weight=EDIT_COST / 2))
        substitute_fst = pynini.cross(sigma, wfsa(substitute, weight=EDIT_COST / 2))
        edit_fst = pynini.union(insert_fst, delete_fst, substitute_fst).optimize()

        # build left search factor
        left_factor = sigma_star.copy()
        for _ in range(EDIT_BOUND):
            left_factor.concat(edit_fst.ques).concat(sigma_star)
        left_factor.optimize()

        # build right factor from left
        right_factor = pynini.invert(left_factor)
        insert_label = self.fst_orchestrator.symbols.find(insert)
        delete_label = self.fst_orchestrator.symbols.find(delete)
        label_pairs = [(insert_label, delete_label), (delete_label, insert_label)]
        right_factor = right_factor.relabel_pairs(ipairs=label_pairs)

        # compose right factor with lexicon
        form_lattice = pynini.project(self.inflect_graph, "output")
        searchable_lexicon = right_factor @ form_lattice

        # set attrs
        self.left_factor = left_factor
        self.right_factor = right_factor
        self.searchable_lexicon = searchable_lexicon

        self.edit_graphs_built = True

        logger.info(f"Edit g1.raphs built for paradigm {self.name}.")

    def search_form(
        self, query: FsaLike, nshortest: int = 5
    ) -> list[tuple[str, float]]:
        """
        Searches the lexicon for fuzzy matches of an input string and returns
        the nshortest hits along with their edit costs.
        """
        if not self.edit_graphs_built:
            logger.info("`search_form` called without edit graphs built, building...")
            self.build_all_graphs()

        query_fsa = self.fst_orchestrator._cast_fsalike_to_fsa(query)
        search_lattice = (query_fsa @ self.left_factor) @ self.searchable_lexicon
        form_hits = self.fst_orchestrator.fsm_strings_and_weights(
            search_lattice, nshortest=nshortest
        )
        return form_hits

    def search_parses(
        self, query: FsaLike, nshortest: int = 5, serialize: bool = False
    ) -> list[dict[str, str]]:
        """
        Wraps `Paradigm.search_form` and also parses each hit and returns as a list
        of dicts.
        """
        form_hits = self.search_form(query, nshortest=nshortest)
        parsed_hits = []
        for form, weight in form_hits:
            parses = self.get_parses(form, serialize=serialize)
            for parse in parses:
                parse_object = {"form": form, "weight": weight}
                if isinstance(parse, dict):
                    parse_object.update(parse)
                else:  # parse is str
                    parse_object["parse"] = parse
                parsed_hits.append(parse_object)

        return parsed_hits


class ParadigmRegistry(Registry):
    def __init__(
        self,
        marker_orchestrator: MarkerOrchestrator,
        lexicon_registry: LexiconRegistry,
        fst_orchestrator: FstOrchestrator,
        data: dict[str, Paradigm] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.marker_orchestrator = marker_orchestrator
        self.lexicon_registry = lexicon_registry
        self.fst_orchestrator = fst_orchestrator
        super().__init__(kind="Paradigm", data=data, config_objects=config_objects)

    def get_paradigm(self, name: str) -> Paradigm:
        name = name.removeprefix("$")
        if name not in self.data:
            raise KeyError(f"Paradigm '{name}' not found in registry.")
        return self.data[name]

    def load_all_configs(self) -> dict[str, Paradigm]:
        config_items: dict[str, Paradigm] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate Paradigm '{key}' found in multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, Paradigm]:
        source_path = config.get("source_path", "")
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get("part_of_speech", "")
        )
        paradigm = Paradigm.from_config(
            config,
            self.marker_orchestrator,
            self.lexicon_registry,
            self.fst_orchestrator,
        )
        return {name: paradigm}
