"""
Implements the `Paradigm` and `GrammarRegistry` classes, which
are the highest-level objects in the registry system.

The `Paradigm` class describes a paradigm or sub-paradigm in the
linguistic sense, represented here as a set of `Marker` lists over
a feature space. It also provides logic for defining the order of
application for markers, and for selecting stems and principle parts
from the lexicon.

The `GrammarRegistry` class orchestrates all registries for a given language.
[At present, the `GrammarRegistry` is essentially a wrapper over the
`MarkerRegistry` and `FstRegistry`, but it will eventually also include
the `LexiconRegistry`, and will directly load in `Paradigm` objects.
Since paradigm objects are themselves the the highest level of abstraction
in the registry system, there is no intermediate `ParadigmRegistry` class.]
"""

from loguru import logger

from src.registry.registry_utils import Registry
from src.registry.marker_registry import (
    Marker, MarkerList, MarkerRegistry, FeatureMarkers, ContingentMarkers
)
from src.registry.fst_registry import FstRegistry
from src.registry.feature_registry import FeatureRegistry, FeatureValueCombinations
from src.registry.lexicon_registry import LexiconRegistry, PartOfSpeech, Lexicon
from typing import Any, Dict, Dict, List, Optional, Tuple
from collections import defaultdict
import itertools
import os

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

    The `__init__` function expects all markers and contingent markers to be
    passed directly, whereas the `from_config` factory method expects a
    `MarkerRegistry` object from which it can pull the relevant marker objects,
    and constructs any inline markers as needed.
    """

    def __init__(
        self,
        markers: List[FeatureMarkers],
        contingent_markers: List[ContingentMarkers],
        lexicon: Lexicon,
        pattern_filter: Optional[str] = None,
        lexical_flag_filter: Optional[List[str]] = None,
        fixed_features: Optional[Dict[str, str]] = None,
        marker_order: Optional[List[str]] = None,
        feature_value_combinations: Optional[FeatureValueCombinations] = None,
        fst_registry: Optional[FstRegistry] = None,
    ):
        self.feature_value_combinations = feature_value_combinations
        self.fixed_features = fixed_features or {}
        self.marker_order = marker_order or []
        self.features = lexicon.features
        self.marker_order = marker_order
        self.part_of_speech = lexicon.part_of_speech
        self.lexicon = lexicon
        self.pattern_filter = pattern_filter
        self.lexical_flag_filter = lexical_flag_filter or []
        self.markers = markers
        self.contingent_markers = contingent_markers
        self.fst_registry = fst_registry

        self.is_initialized = False
        self.fst_registry_initialized = False
        if self.fst_registry and self.fst_registry.is_initialized:
            self.fst_registry_initialized = True
        else:
            logger.info(
                "FST registry not provided or not initialized. "
                "FST-based operations will not be available until the registry is initialized."
            )
        self.initialize()

    def from_config(
        cls,
        marker_registry: MarkerRegistry,
        lexicon_registry: LexiconRegistry,
        fst_registry: FstRegistry,
        config: Dict[str, Any]
    ) -> 'Paradigm':
        """
        Factory method for constructing a Paradigm object from a MarkerRegistry
        and a FeatureValueCombinations object. This method will pull the relevant
        marker objects from the MarkerRegistry based on the provided features,
        and will construct any inline markers as needed.
        """

        # load part of speech and lexicon
        part_of_speech_name = config['part_of_speech']
        lexicon = lexicon_registry[part_of_speech_name]
        marker_order = config['order']

        feature_value_combination_name = config.get('feature_value_combinations')
        if feature_value_combination_name:
            feature_value_combinations = marker_registry.feature_combinations[feature_value_combination_name]

        fixed_features = {}
        markers = []
        for feature, marker_str in config['feature_markers'].items():
            if marker_str is None:
                # indicates that this feature is marked only with ContingentMarkers
                # and should not be included in the standard markers
                continue

            if not marker_str.startswith('$'):
                # indicates that feature is fixed to a single value
                # where 'marker_str' indicates the value
                fixed_features[feature] = marker_str
            else:
                marker_set_name = marker_str.removeprefix('$')
                marker_set = marker_registry.feature_markers[marker_set_name]
                if marker_set.feature != feature:
                    raise ValueError(
                        f"Feature '{feature}' in paradigm config does not match feature '{marker_set.feature}' in marker config '{marker_set_name}'."
                    )
                markers.append(marker_set)

        contingent_markers = []
        for contingent_marker_str in config.get('contingent_markers', []):
            if not contingent_marker_str.startswith('$'):
                raise ValueError(
                    f"Contingent marker '{contingent_marker_str}' in paradigm config must start with '$' to indicate a marker set."
                )
            contingent_marker_set_name = contingent_marker_str.removeprefix('$')
            contingent_marker_set = marker_registry.contingent_markers[contingent_marker_set_name]
            contingent_markers.append(contingent_marker_set)

        return cls(
            markers=markers,
            contingent_markers=contingent_markers,
            fixed_features=fixed_features,
            marker_order=marker_order,
            lexicon=lexicon,
            feature_value_combinations=feature_value_combinations,
            fst_registry=fst_registry,
        )
    
    def get_markers_for_feature_values(self, feature_values: Dict[str, str]) -> MarkerList:
        """
        Get the list of markers that should be applied for a given combination of feature values.
        This is determined by checking the feature markers and contingent markers in the paradigm
        for matches with the provided feature values, and then sorting the resulting markers
        according to the marker order specified in the paradigm.

        Priority is given to contingent markers over standard feature markers, such that if a
        contingent marker matches the provided feature values, any standard feature markers that
        also match those feature values will be ignored.
        """
        if not self.feature_value_combinations.combination_is_valid(feature_values):
            raise ValueError(
                f"Feature value combination {feature_values} is not valid according to the paradigm's feature_value_combinations."
            )

        applicable_markers = []
        remaining_features = set(feature_values.keys())

        for feature_couple in itertools.combinations(feature_values.keys(), 2):
            feature_value_couple = tuple((feature, feature_values[feature]) for feature in feature_couple)
            if feature_value_couple in self.contingent_marker_map:
                marker_list = self.contingent_marker_map[feature_value_couple]
                applicable_markers.extend(marker_list)
                remaining_features -= set(feature_couple)
        for feature in remaining_features:
            feature_value_pair = (feature, feature_values[feature])
            if feature_value_pair in self.feature_marker_map:
                marker_list = self.feature_marker_map[feature_value_pair]
                applicable_markers.extend(marker_list)

        applicable_markers.sort(
            key=lambda marker: self.marker_order.index(marker.order)
            if marker.order in self.marker_order else -1
        )
        applicable_markers = MarkerList(applicable_markers)
        return applicable_markers

    def initialize(self):
        """
        Initialize the paradigm by validating features and building marker transducers.
        This is separate from __init__ to allow for lazy initialization.
        """
        self._validate_features_and_order_values()
        self._validate_principle_parts_and_filters()
        self._build_marker_mappings()
        if self.fst_registry and not self.fst_registry.is_initialized:
            logger.info("Initializing FST registry as part of paradigm initialization.")
            self.fst_registry.initialize()
            self.fst_registry_initialized = True
        self._build_marker_transducers()
        self.is_initialized = True
    
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
            if marker_set.feature not in self.features:
                raise ValueError(
                    f"Feature '{marker_set.feature}' in marker set not recognized. "
                    f"Expected one of {self.features}."
                )
            supported_features.add(marker_set.feature)
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    order = marker.get('order')
                    if order and order not in self.marker_order:
                        raise ValueError(
                            f"Marker order '{order}' not recognized. "
                            f"Expected one of {self.marker_order}."
                        )
        for contingent_marker_set in self.contingent_markers:
            if contingent_marker_set.inner_feature not in self.features:
                raise ValueError(
                    f"Feature '{contingent_marker_set.inner_feature}' in contingent marker set not recognized. "
                    f"Expected one of {self.features}."
                )
            if contingent_marker_set.outer_feature not in self.features:
                raise ValueError(
                    f"Feature '{contingent_marker_set.outer_feature}' in contingent marker set not recognized. "
                    f"Expected one of {self.features}."
                )
            supported_features.add(contingent_marker_set.inner_feature)
            supported_features.add(contingent_marker_set.outer_feature)

            for marker_set in contingent_marker_set.inner_feature_map.values():
                for marker_list in marker_set.data.values():
                    for marker in marker_list:
                        order = marker.get('order')
                        if order and order not in self.marker_order:
                            raise ValueError(
                                f"Marker order '{order}' not recognized. "
                                f"Expected one of {self.marker_order}."
                            )
    
    def _validate_principle_parts_and_filters(self):
        """
        Validate that all markers with 'principal_part' order have a corresponding
        stem in the lexicon, and that all markers with 'lexical' order have a
        corresponding stem in the lexicon marked as lexical.
        """
        for marker_set in self.markers:
            for marker_list in marker_set.data.values():
                if (
                    (marker_list.principal_part is not None) and
                    (marker_list.principal_part not in self.lexicon.principal_parts)
                ):
                    raise ValueError(
                        f"Principal part marker '{marker_list.principal_part}' in feature marker set for feature '{marker_set.feature}' does not have a corresponding stem in the lexicon."
                    )
        for flag in self.lexical_flag_filter:
            if flag not in self.lexicon.lexical_flags:
                raise ValueError(
                    f"Lexical flag '{flag}' in paradigm config not recognized in lexicon. "
                    f"Expected one of {self.lexicon.lexical_flags}."
                )
        
        if self.pattern_filter:
            if self.pattern_filter not in self.fst_registry.patterns:
                raise ValueError(
                    f"Pattern filter '{self.pattern_filter}' not recognized in FstRegisry. "
                    "Check pattern configs."
                )

    def _build_marker_mappings(self):
        """
        Builds two mappings, one for feature markers and one for
        contingent markers, that map from feature values (represented
        as tuples of (feature, value) pairs) to the list of markers that
        should be applied for that combination of feature values.

        For feature markers, the mapping is from (feature, value) to the
        list of markers in the corresponding marker set. For contingent
        markers, the mapping is nested and order-insensitive, such that
        contingent_map[(feature1, value1)][(feature2, value2)] gives
        the same result as contingent_map[(feature2, value2)][(feature1, value1)].
        """

        # build flat mapping for feature markers
        self.feature_marker_map: Dict[Tuple[str, str], MarkerList] = {}
        for marker_set in self.markers:
            for feature_value, marker_list in marker_set.data.items():
                self.feature_marker_map[(marker_set.feature, feature_value)] = marker_list
        
        # build nested mapping for contingent markers
        self.contingent_marker_map: Dict[
            Tuple[str, str], Dict[Tuple[str, str], MarkerList]
        ] = defaultdict(dict)
        for contingent_marker_set in self.contingent_markers:
            for outer_value, inner_map in contingent_marker_set.outer_feature_map.items():
                outer_pair = (contingent_marker_set.outer_feature, outer_value)
                for inner_value, marker_set in inner_map.items():
                    innner_pair = (contingent_marker_set.inner_feature, inner_value)
                    self.contingent_marker_map[outer_pair][innner_pair] = marker_set.data
                    self.contingent_marker_map[innner_pair][outer_pair] = marker_set.data

    def _build_all_marker_transducers(self):
        for marker_set in self.feature_markers.values():
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)
        for marker_set in self.contingent_markers.values():
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)

    def _build_marker_transducer(self, marker: Marker):
        if marker.type == 'rule':
            marker_rule = self.fst_registry.rules[marker.value]
        elif marker.type == 'prefix':
            marker_rule = self.fst_registry.prefix(marker.value)
        elif marker.type == 'suffix':
            marker_rule = self.fst_registry.suffix(marker.value)
        elif marker.type == 'replace':
            marker_rule = self.fst_registry.replace_transducer(
                marker.value[0], marker.value[1]
            )
        elif marker.type == 'suppletion':
            sigma_star = '<Sigma>*'
            marker_rule = self.fst_registry.replace_transducer(
                sigma_star, marker.value
            )
        elif marker.type == 'principal_part':
            marker_rule = self._get_principal_part_transducer(marker.value)
        marker.set_transducer(marker_rule.fst)

    def _get_principal_part_transducer(self, principal_part: str):
        """
        Create a root -> principal_part transducer for the given principal
        part by computing a union over the lexical entries for all roots in
        the lexicon marked as that principal part. Lexical entries lacking
        the principal part will be transduced to themselves.
        """

        if not self.fst_registry_initialized:
            raise ValueError("FST registry must be initialized to get principal part transducer.")
        if principal_part not in self.lexicon.principal_parts:
            raise ValueError(f"Principal part '{principal_part}' not found in lexicon.")
        
        input_strings = self.lexicon.get_roots()
        output_strings = self.lexicon.get_column_data(principal_part, fill_w_root=True)
        return self.fst_registry.string_map_transducer(input_strings, output_strings)

class GrammarRegistry(Registry):
    """
    Orchestrates all registries for a given language.
    """
    def __init__(
        self,
        marker_registry: Optional[MarkerRegistry]=None,
        lexicon_registry: Optional[LexiconRegistry]=None,
        fst_registry: Optional[FstRegistry]=None,
        config_list: Optional[List[str]]=None,
        paradigms: Optional[Dict[str, Paradigm]]=None,
    ):
        super().__init__(
            kind="Paradigm", data=paradigms, config_list=config_list
        )

        self.marker_registry = marker_registry
        self.lexicon_registry = lexicon_registry
        self.fst_registry = fst_registry
        self.feature_registry: FeatureRegistry = marker_registry.feature_registry if marker_registry else None

        self.paradigms = paradigms or []
    
    @classmethod
    def from_config_dir(cls, config_dir: str) -> 'GrammarRegistry':
        """
        Factory method for constructing a GrammarRegistry object from a config directory.
        """
        grammar_reg = super().from_config_dir(config_dir)
        marker_registry = MarkerRegistry.from_config_dir(config_dir)
        lexicon_registry = LexiconRegistry.from_config_dir(config_dir)
        fst_registry = FstRegistry.from_config_dir(config_dir)

        grammar_reg.marker_registry = marker_registry
        grammar_reg.lexicon_registry = lexicon_registry
        grammar_reg.fst_registry = fst_registry
        grammar_reg.feature_registry = marker_registry.feature_registry

        paradigms = grammar_reg.load_all_configs()
        grammar_reg.paradigms = paradigms
        return grammar_reg

    def load_all_configs(self) -> Dict[str, Paradigm]:
        config_items: Dict[str, Paradigm] = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config, self.feature_registry)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate Paradigm '{key}' found in "
                        f"multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items
        
    def load_data_from_config(self, config: dict) -> Dict[str, Paradigm]:
        source_path = config.get('source_path', '')
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get('part_of_speech', '')
        )
        Paradigm = Paradigm.from_config(
            config, self.marker_registry, self.lexicon_registry, self.fst_registry
        )
        return {name: Paradigm}
    