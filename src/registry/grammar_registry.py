"""
Implements the `Paradigm` and `GrammarRegistry` classes, which
are the highest-level objects in the registry system.

The `Paradigm` class describes a paradigm or sub-paradigm in the
linguistic sense, represented here as a set of `Marker` lists over
a feature space. It also provides logic for defining the order of
application for markers, and for selecting stems and principal parts
from the lexicon.

The `GrammarRegistry` class orchestrates all registries for a given language.
[At present, the `GrammarRegistry` is essentially a wrapper over the
`MarkerRegistry` and `FstRegistry`, but it will eventually also include
the `LexiconRegistry`, and will directly load in `Paradigm` objects.
Since paradigm objects are themselves the the highest level of abstraction
in the registry system, there is no intermediate `ParadigmRegistry` class.]
"""

from loguru import logger
import pynini
from pynini.lib import pynutil

from src.fst_utils import FsaLike
from src.registry.registry_utils import Registry
from src.registry.marker_registry import (
    Marker, MarkerList, MarkerRegistry, FeatureMarkers, ContingentMarkers
)
from src.registry.fst_registry import FstRegistry, InventoryItem
from src.registry.feature_registry import (
    FeatureRegistry, FeatureValueCombinations, Feature,
    stringify_features, serialize_feature_str
)
from src.registry.lexicon_registry import LexiconRegistry, Lexicon
from src.constants import EXAMPLE_CONFIG_DIR
from typing import Any, Dict, Dict, List, Optional, Tuple, Union
from collections import defaultdict
import itertools
import os
import pandas as pd
from pathlib import Path
import functools
from tqdm import tqdm

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
        name: Optional[str]=None,
        pattern_filter: Optional[str] = None,
        lexical_feature_filter: Optional[List[Tuple[Feature, str]]] = None,
        fixed_features: Optional[Dict[str, str]] = None,
        marker_order: Optional[List[str]] = None,
        feature_value_combinations: Optional[FeatureValueCombinations] = None,
        fst_registry: Optional[FstRegistry] = None,
    ):
        self.is_initialized = False
        self.fst_registry_initialized = False
        self.main_graphs_built = False
        self.edit_graphs_built = False

        self.name = name
        if name is None:
            self.name = "[UNNAMED]"
        self.feature_value_combinations = feature_value_combinations
        self.fixed_features = fixed_features or {}
        self.marker_order = marker_order or []
        self.features = lexicon.features
        self.marker_order = marker_order
        self.part_of_speech = lexicon.part_of_speech
        self.lexicon = lexicon
        self.pattern_filter = pattern_filter
        self.lexical_feature_filter = lexical_feature_filter or []
        self.markers = markers
        self.contingent_markers = contingent_markers
        self.fst_registry = fst_registry

        if self.fst_registry and self.fst_registry.is_initialized:
            self.fst_registry_initialized = True
        else:
            logger.info(
                "FST registry not provided or not initialized. "
                "FST-based operations will not be available until the registry is initialized."
            )
        self.initialize()

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        marker_registry: MarkerRegistry,
        lexicon_registry: LexiconRegistry,
        fst_registry: FstRegistry,
    ) -> 'Paradigm':
        """
        Factory method for constructing a Paradigm object from a MarkerRegistry
        and a FeatureValueCombinations object. This method will pull the relevant
        marker objects from the MarkerRegistry based on the provided features,
        and will construct any inline markers as needed.
        """

        # load part of speech and lexicon
        paradigm_name = None
        paradigm_source = config.get("source_path", None)
        if paradigm_source is not None:
            paradigm_name = Path(paradigm_source).stem

        part_of_speech_name = config['part_of_speech']
        lexicon = lexicon_registry.data[part_of_speech_name]
        marker_order = config['order']

        feature_value_combinations = None
        feature_value_combination_name = config.get('feature_value_combinations')
        if feature_value_combination_name:
            feature_value_combinations = marker_registry.feature_combinations[feature_value_combination_name]

        # load filters
        filter_config = config.get('filter', {})
        pattern_filter = filter_config.get('pattern', None)
        lexical_feature_strs: List[List[str]] = filter_config.get('lexical_features', [])
        lexical_feature_filter = []
        for feature_name, feature_value in lexical_feature_strs:
            feature = marker_registry.feature_registry.features[feature_name]
            lexical_feature_filter.append((feature, feature_value))

        fixed_features = {}
        markers = []
        for feature_name, marker_str in config['feature_markers'].items():
            if marker_str is None:
                # indicates that this feature is marked only with ContingentMarkers
                # and should not be included in the standard markers
                continue

            if not marker_str.startswith('$'):
                # indicates that feature is fixed to a single value
                # where 'marker_str' indicates the value
                fixed_features[feature_name] = marker_str
            else:
                marker_set_name = marker_str.removeprefix('$')
                marker_set = marker_registry.feature_markers[marker_set_name]
                if marker_set.feature.name != feature_name:
                    raise ValueError(
                        f"Feature '{feature_name}' in paradigm config does not match feature '{marker_set.feature}' in marker config '{marker_set_name}'."
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
            name=paradigm_name,
            markers=markers,
            pattern_filter=pattern_filter,
            lexical_feature_filter=lexical_feature_filter,
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
        if  (
                (self.feature_value_combinations is not None) and
                (not self.feature_value_combinations.combination_is_valid(feature_values))
            ):
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
        self._validate_principal_parts_and_filters()
        self._build_marker_mappings()
        if self.fst_registry and not self.fst_registry.is_initialized:
            logger.info("Initializing FST registry as part of paradigm initialization.")
            self.fst_registry.initialize()
            self.fst_registry_initialized = True
        self._build_all_marker_transducers()
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
            supported_features.add(marker_set.feature.name)
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    order = marker.order
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
            supported_features.add(contingent_marker_set.inner_feature.name)
            supported_features.add(contingent_marker_set.outer_feature.name)

            for marker_set in contingent_marker_set.inner_feature_map.values():
                for marker_list in marker_set.data.values():
                    for marker in marker_list:
                        order = marker.get('order')
                        if order and order not in self.marker_order:
                            raise ValueError(
                                f"Marker order '{order}' not recognized. "
                                f"Expected one of {self.marker_order}."
                            )
    
    def _validate_principal_parts_and_filters(self):
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
                
        expected_lexical_feature_names = [feature.name for feature in self.lexicon.lexical_features]
        for feature, _ in self.lexical_feature_filter:
            if feature.name not in expected_lexical_feature_names:
                raise ValueError(
                    f"Lexical feature '{feature}' in paradigm config not recognized in lexicon. "
                    f"Expected one of {self.lexicon.lexical_features}."
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
                self.feature_marker_map[(marker_set.feature.name, feature_value)] = marker_list
        
        # build nested mapping for contingent markers
        self.contingent_marker_map: Dict[
            Tuple[str, str], Dict[Tuple[str, str], MarkerList]
        ] = defaultdict(dict)
        for contingent_marker_set in self.contingent_markers:
            for outer_value, inner_map in contingent_marker_set.outer_feature_map.items():
                outer_pair = (contingent_marker_set.outer_feature.name, outer_value)
                for inner_value, marker_set in inner_map.items():
                    innner_pair = (contingent_marker_set.inner_feature.name, inner_value)
                    self.contingent_marker_map[outer_pair][innner_pair] = marker_set.data
                    self.contingent_marker_map[innner_pair][outer_pair] = marker_set.data

    def _build_all_marker_transducers(self):
        for marker_set in self.markers:
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)
        for marker_set in self.contingent_markers:
            for marker_list in marker_set.data.values():
                for marker in marker_list:
                    self._build_marker_transducer(marker)

    def _build_marker_transducer(self, marker: Marker):
        if marker.type == 'rule':
            rule_name = marker.value.removeprefix('$')
            marker_rule = self.fst_registry.rules[rule_name]
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
        if marker.transducer_built:
            logger.info(
                f"Transducer for marker '{marker}' already built. Skipping."
            )
            return
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
        string_map = list(zip(input_strings, output_strings))
        return self.fst_registry.string_map_transducer(string_map)

    def get_filtered_roots(self):
        """
        Apply pattern and lexical features to lexicon (if applicable)
        and return all remaining roots.
        """
        entries = self.lexicon.entries
        feature_mask = pd.Series([True]*len(entries))

        for feature, feature_value in self.lexical_feature_filter:
            feature_col = entries[feature.name]
            feature_mask &= feature_col == feature_value
        
        roots = entries[feature_mask]['root'].to_list()

        if self.pattern_filter:
            roots = self.fst_registry.filter_strings_by_pattern(
                roots, self.pattern_filter
            )
        
        return roots

    
    def inflect(self, stem: FsaLike, feature_values: Dict[str, str]) -> pynini.Fst:
        """
        Inflect a given stem according to the markers specified for the provided feature values.
        """
        if not self.is_initialized:
            raise ValueError("Paradigm must be fully initialized to inflect.")
        
        markers = self.get_markers_for_feature_values(feature_values)
        inflected_form_fst = self._apply_markers(stem, markers)
        return inflected_form_fst
    
    def get_valid_combinations(
            self,
            fixed_features: Optional[Dict[str, str]]=None
        ) -> List[Dict[str, str]]:
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
            return self.feature_value_combinations.get_all_combinations(fixed_features)
        # for each feature get a list of dicts
        # [{"feature_name": "feature_value"}, ...]
        # then get the cartesian product across those lists
        # to get all combinations
        free_features = [
            feature for feature in self.features
            if feature.name not in fixed_features
        ]
        feature_value_lists = []
        for feature in free_features:
            feature_value_lists.append([
                {feature.name: value} for value in feature.values
            ])
        combination_tuples = itertools.product(*feature_value_lists)
        # itertools.product returns an iterator over tuples of shape
        # ({feature: value}, {feature: value}, ...)
        # collapse list of tuples to a list of dicts
        combinations = [
            functools.reduce(lambda a,b: a|b, combo)
            for combo in combination_tuples
        ]

        return combinations

    
    def inflect_subparadigm(
            self,
            stem: FsaLike,
            fixed_features: Optional[Dict[str, str]] = None,
            max_rows: int=None,
    ) -> List[Tuple[pynini.Fst, Dict[str, str]]]:
        """
        Inflect a given stem according to the markers specified for the
        provided fixed feature values.
        """
        valid_combinations = self.get_valid_combinations(fixed_features)
        if max_rows is not None:
            valid_combinations = valid_combinations[:max_rows]

        results = [
            (self.inflect(stem, combo), combo)
            for combo in valid_combinations
        ]
        
        return results

    def get_subparadigm_table(
            self,
            stem: str,
            fixed_features: Optional[Dict[str, str]]=None,
            only_free_feature_columns: bool=True,
            max_rows: Optional[int]=100,
    ) -> List[Dict[str, str]]:
        """
        Wraps `self.inflect_subparadigm` and formats the output
        in a list of dicts for displaying as a table.
        """
        inflected_results = self.inflect_subparadigm(
            stem=stem,
            fixed_features=fixed_features,
            max_rows=max_rows
        )

        if only_free_feature_columns:        
            if fixed_features is None:
                fixed_features = self.fixed_features
            else:
                fixed_features = {**self.fixed_features, **fixed_features}

            free_features = [
                feature for feature in self.features
                if feature.name not in fixed_features
            ]

            inflected_results = [
                (fst, {
                    k: v for k, v in combination.items()
                    if k not in free_features
                })
                for fst, combination in inflected_results
            ]

        table_rows = []
        for fst, combination in inflected_results:
            form_strings = self.fst_registry.fsm_strings(fst)
            concatenated_forms = "; ".join(form_strings)
            row_data = {
                "form": concatenated_forms,
                **combination
            }
            table_rows.append(row_data)
        return table_rows
    
    def get_inflection_stages(
            self,
            stem: str,
            feature_values: Dict[str, str]
        ) -> List[Dict[str, str]]:
        """
        Get the intermediate stages of inflection for a given stem and feature values.
        """
        if not self.is_initialized:
            raise ValueError("Paradigm must be fully initialized to get inflection stages.")

        markers = self.get_markers_for_feature_values(feature_values)
        stages = self._apply_markers(stem, markers, store_intermediate=True)
        
        table_data = []
        for stage_fst, marker in stages:
            stage_data = {}
            if marker is None:
                stage_data['order'] = '<INITIAL>'
                stage_data['marker_type'] = None
                stage_data['marker_value'] = None
                stage_data['feature_value'] = None
            else:
                stage_data['order'] = marker.order
                stage_data['marker_type'] = marker.type
                stage_data['marker_value'] = marker.value
                stage_data['feature_value'] = marker.feature_value

            stage_strings = self.fst_registry.fsm_strings(stage_fst)
            for string in stage_strings:
                table_data.append({
                    **stage_data,
                    'form': string,
                })
            
        return table_data

    def _apply_markers(
            self, stem: FsaLike,
            markers: List[MarkerList],
            store_intermediate: bool=False,
        ) -> Union[pynini.Fst, List[Tuple[pynini.Fst, Marker]]]:
        """
        Apply a list of markers to a given stem by composing the stem with
        the transducer for each marker in the list, in order.
        """
        if not self.is_initialized:
            raise ValueError("Paradigm must be fully initialized to apply markers.")
        
        result = None
        current_fst = self.fst_registry._cast_fsalike_to_fsa(stem, is_word=True)

        if store_intermediate:
            result = [(current_fst, None)]
        
        for marker in markers:
            fst_list = marker.fst
            if isinstance(fst_list, pynini.Fst):
                fst_list = [fst_list]
            for fst in fst_list:
                current_fst = current_fst@fst
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
        logger.info(f"Building main (inflector and parser) graphs for paradigm {self.name}...")

        roots = self.get_filtered_roots()
        inflect_fst_list = []
        for root in tqdm(roots, desc=f"Inflecting roots for paradigm {self.name}"):
            root_fsa = self.fst_registry.word_fsa(root)

            # iter thru all feature combos and build transducers
            inflected_transducers = self.inflect_subparadigm(
                stem=root_fsa,
                fixed_features=None,
                max_rows=None,
            )

            for fst, combination in inflected_transducers:
                feature_str = stringify_features(combination)

                inflect_input = root_fsa + self.fst_registry.fsa(feature_str)
                inflect_output = pynini.project(fst, 'output')
                inflect_fst = pynini.cross(inflect_input, inflect_output)

                inflect_fst.optimize()
                inflect_fst_list.append(inflect_fst)

        inflect_graph = pynini.union(*inflect_fst_list)
        inflect_graph.optimize()

        parse_graph = pynini.invert(inflect_graph)
        parse_graph.optimize()

        self.inflect_graph = inflect_graph
        self.parse_graph = parse_graph
        self.main_graphs_built=True

        logger.info("Main graphs built.")

    def get_parses(self, form: FsaLike, serialize: bool=False) -> List[Union[str, Dict[str, str]]]:
        """
        Computes a parse lattice by composing the input string with the main parse graph
        then returns a list of strings of all candidate parses, where feature values
        are specified in the format "ROOT[feat=val][feat=val][feat=val]..."

        If `serialize=True`, casts the feature string to a dict using `serialize_feature_str`
        """
        form_fsa = self.fst_registry._cast_fsalike_to_fsa(form, is_word=True)
        parse_lattice = form_fsa @ self.parse_graph
        parse_strings = self.fst_registry.fsm_strings(parse_lattice)

        if serialize:
            serialized_parses = []
            for parse in parse_strings:
                feature_index = parse.index('[')
                root = parse[:feature_index]
                feature_str = parse[feature_index:]
                feature_dict = serialize_feature_str(feature_str)
                feature_dict['root']=root
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
        insert = self.fst_registry.insert
        delete = self.fst_registry.delete
        substitute = self.fst_registry.substitute
        sigma = self.fst_registry.sigma
        sigma_star = self.fst_registry.sigma_star

        fsa = self.fst_registry.fsa
        wfsa = self.fst_registry.wfsa

        # build single edit transducers
        insert_fst = pynutil.insert(wfsa(insert, weight=EDIT_COST/2))
        delete_fst = pynini.cross(sigma, wfsa(delete, weight=EDIT_COST/2))
        substitute_fst = pynini.cross(sigma, wfsa(substitute, weight=EDIT_COST/2))
        edit_fst = pynini.union(insert_fst, delete_fst, substitute_fst).optimize()

        # build left search factor
        left_factor = sigma_star.copy()
        for _ in range(EDIT_BOUND):
            left_factor.concat(edit_fst.ques).concat(sigma_star)
        left_factor.optimize()

        # build right factor from left
        right_factor = pynini.invert(left_factor)
        insert_label = self.fst_registry.symbols.find(insert)
        delete_label = self.fst_registry.symbols.find(delete)
        label_pairs = [(insert_label, delete_label), (delete_label, insert_label)]
        right_factor = right_factor.relabel_pairs(ipairs=label_pairs)

        # compose right factor with lexicon        
        form_lattice = pynini.project(self.inflect_graph, 'output')
        searchable_lexicon = right_factor @ form_lattice

        # set attrs
        self.left_factor = left_factor
        self.right_factor = right_factor
        self.searchable_lexicon = searchable_lexicon

        self.edit_graphs_built = True

        logger.info(f"Edit g1.raphs built for paradigm {self.name}.")

    def search_form(self, query: FsaLike, nshortest: int = 5) -> List[Tuple[str, float]]:
        """
        Searches the lexicon for fuzzy matches of an input string and returns
        the nshortest hits along with their edit costs.
        """
        query_fsa = self.fst_registry._cast_fsalike_to_fsa(query)
        search_lattice = (query_fsa @ self.left_factor) @ self.searchable_lexicon
        form_hits = self.fst_registry.fsm_strings_and_weights(
            search_lattice,
            nshortest=nshortest
        )
        return form_hits
    
    def search_parses(self, query: FsaLike, nshortest: int = 5, serialize: bool=False) -> List[Dict[str, str]]:
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
                else: # parse is str
                    parse_object['parse'] = parse
                parsed_hits.append(parse_object)

        return parsed_hits
        

class GrammarRegistry(Registry):
    """
    Orchestrates all registries for a given language.
    """
    def __init__(
        self,
        marker_registry: Optional[MarkerRegistry]=None,
        lexicon_registry: Optional[LexiconRegistry]=None,
        fst_registry: Optional[FstRegistry]=None,
        feature_registry: Optional[FeatureRegistry]=None,
        config_list: Optional[List[str]]=None,
        paradigms: Optional[Dict[str, Paradigm]]=None,
        do_initialize: bool=False,
    ):
        self.is_initialized = False
        super().__init__(
            kind="Paradigm", data=paradigms, config_list=config_list
        )

        self.marker_registry = marker_registry
        self.lexicon_registry = lexicon_registry
        self.fst_registry = fst_registry
        self.feature_registry = feature_registry

        self.paradigms = paradigms or []

        if do_initialize:
            self.initialize()
    
    @classmethod
    def from_config_dir(cls, config_dir: str) -> 'GrammarRegistry':
        """
        Factory method for constructing a GrammarRegistry object from a config directory.
        """
        
        logger.info("Initializing GrammarRegistry from config directory.")
        grammar_reg = super().from_config_dir(config_dir)

        # load dependent registries from lowest level of abstraction to highest
        # logging errors while loading as much as possible
        feature_registry = None
        try:
            feature_registry = FeatureRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading FeatureRegistry: {e}")

        fst_registry = None
        try:
            fst_registry = FstRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading FstRegistry: {e}")


        marker_registry = None
        lexicon_registry = None
        if feature_registry is not None:
            try:
                marker_registry = MarkerRegistry.from_config_dir(config_dir, feature_registry=feature_registry)
            except Exception as e:
                logger.exception(f"Error occurred while loading Marker registry: {e}")

            try:
                lexicon_registry = LexiconRegistry.from_config_dir(config_dir, feature_registry=feature_registry)
            except Exception as e:
                logger.exception(f"Error occurred while loading Lexicon registry: {e}")

        grammar_reg.marker_registry = marker_registry
        grammar_reg.feature_registry = feature_registry
        grammar_reg.lexicon_registry = lexicon_registry
        grammar_reg.fst_registry = fst_registry

        # only load paradigms if all child registries loaded successfully
        # since paradigm loading depends on all of them
        paradigms = None
        if all(reg is not None for reg in [marker_registry, lexicon_registry, fst_registry]):
            logger.info("All child registries loaded successfully. Loading paradigms.")
            try:
                paradigms = grammar_reg.load_all_configs()
                logger.info(f"Loaded {len(paradigms)} paradigms successfully.")
            except Exception as e:
                logger.exception(f"Error occurred while loading paradigms: {e}")
        grammar_reg.paradigms = paradigms
        grammar_reg.initialize()
        return grammar_reg

    def load_all_configs(self) -> Dict[str, Paradigm]:
        config_items: Dict[str, Paradigm] = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
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
        paradigm = Paradigm.from_config(
            config, self.marker_registry, self.lexicon_registry, self.fst_registry
        )
        return {name: paradigm}
    
    def initialize(self):
        if all(
            reg is not None for reg in
            [self.marker_registry, self.lexicon_registry, self.fst_registry, self.feature_registry]
        ):
            self._add_features_to_symbol_table()
            self.is_initialized = True
            logger.info("All child registries detected, GrammarRegistry loaded successfully.")
        else:
            if self.marker_registry is None:
                logger.warning("Grammar registry received None instead of MarkerRegistry")
            if self.fst_registry is None:
                logger.warning("Grammar registry received None instead of FstRegistry")
            if self.lexicon_registry is None:
                logger.warning("Grammar registry received None instead of LexiconRegistry")
            if self.feature_registry is None:
                logger.warning("Grammar registry received None instead of FeatureRegistry")

    def _add_features_to_symbol_table(self):
        feature_flags = []
        for feature_name, feature in self.feature_registry.features.items():
            for feature_value in feature.values:
                feature_str = f"[{feature_name}={feature_value}]"
                feature_flag = InventoryItem(
                    feature_str,
                    type="flag",
                    source=feature.source
                )
                feature_flags.append(feature_flag)
        self.fst_registry.update_flags(feature_flags)
                
    
if __name__ == "__main__":
    import random 

    reg = GrammarRegistry.from_config_dir(EXAMPLE_CONFIG_DIR)

    para = reg.paradigms['verbs']
    root = random.choice(para.get_filtered_roots())
    stages = para.get_inflection_stages(root, {'tense':'present', 'mood':'subjunctive', 'person_number':'1sg'})
    inflected_paradigm = para.get_subparadigm_table(root)

    para._build_main_graphs()
    random_form = random.choice(inflected_paradigm)['form'].split(';')[0]
    parse = para.get_parses(random_form)

    para._build_edit_graphs()
    random_index = random.randint(0, len(random_form)-1)
    random_form_list = list(random_form)
    random_form_list.pop(random_index)
    random_form_deletion = ''.join(random_form_list)
    search_hits = para.search_form(random_form_deletion)
    search_parses = [para.get_parses(hit_str) for hit_str, _ in search_hits]
    
    logger.info(f"random_form: {random_form}")
    logger.info(f"parse: {parse}")
    logger.info(f"random_form_deletion: {random_form_deletion}")
    logger.info(f"search_hits: {search_hits}")
    logger.info(f"search_parses: {search_parses}")

    breakpoint()
