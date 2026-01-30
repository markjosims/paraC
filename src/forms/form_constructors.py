from typing import Dict, Literal, Optional, Tuple, Union, List
from dataclasses import dataclass, field
import pandas as pd
from src.constants import (
    SUBJECT_PERSON_AND_NUMBER, OBJECT_PERSON_AND_NUMBER, CLASS_AGREE,
    FEATURES_TO_VALUES
)
from pynini import Fst

@dataclass
class Marker:
    """
    Dataclass for storing a single affix marker.
    
    Attributes:
        prefix: String to be added as a prefix
        suffix: String to be added as a suffix
        replace: Pair of strings indicating a substring to be replaced and its replacement
        rule: Name(s) of phonological rule(s) to apply (must be defined elsewhere)
        order: A unique name for ordering application of rules/affixes
        fst: (TODO) Finite State Transducer representing the marker (built automatically post-init)
        
    """
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    replace: Optional[List[Tuple[str, str]]] = None
    rule: Optional[Union[str, List[str]]] = None
    order: Optional[str] = None
    fst: Optional[Fst] = None  # Placeholder for FST object

    def __post_init__(self):
        # TODO: convert marker input to FST
        if self.fst is not None:
            raise ValueError("FST should not be provided directly; it will be built automatically.")
        # self.fst = build_fst_from_marker_input(self.marker_input)
    
@dataclass
class FeatureMarkers:
    """
    Dataclass mapping feature values to marker objects.
    
    Usage:
    >>> marker = MarkerClass()
    >>> marker.data['first_singular'] = [{'suffix': '-íŋí'}]
    >>> marker.data['second_singular'] = [{'prefix': 'jɛ́-'}]
    """
    data: Dict[str, Marker] = field(default_factory=dict)

    def __post_init__(self):
        # Set attributes dynamically based on keys in data
        for key, value in self.data.items():
            if not isinstance(value, dict):
                raise ValueError(f"Marker value for {key} must be a dictionary.")
            setattr(self, key, value)

class FeatureQueryMixin:
    """
    Mixin class providing methods for querying markers based on feature dictionaries.
    Allows retrieving markers by passing a dictionary or string of feature values,
    where strings have the format 'feature=value feature=value'. Ensures consistent
    ordering of features in strings regardless of input order.
    """

    def _feature_str_to_dict(self, feature_str: str) -> Dict[str, str]:
        """
        Convert a feature string of the format 'feature=value feature=value' to a dictionary.
        """
        feature_dict = {}
        for feature_value in feature_str.split(' '):
            feature, value = feature_value.split('=')
            feature_dict[feature] = value
        return feature_dict
    
    def _stringify_feature_dict(self, feature_dict: Dict[str, str]) -> str:
        """
        Convert a feature dictionary to a string of the format 'feature=value feature=value'.
        """
        return ' '.join(
            f"{feature}={value}"
            for feature, value in sorted(feature_dict.items())
        )

    def get_marker(self, **feature_dict: str) -> Marker:
        """
        Retrieve a marker based on a dictionary of feature values.
        """
        key = self._stringify_feature_dict(feature_dict)
        data = getattr(self, 'data', None)
        if data is None:
            raise ValueError("No data attribute found in the object.")
        if not data:
            raise ValueError("Data attribute is empty.")
        if key not in data:
            raise KeyError(f"No marker found for feature combination: {key}")
        return data[key]

@dataclass
class ContingentMarkers(FeatureMarkers, FeatureQueryMixin):
    """
    Similar to `FeatureMarkers`, but for markers that depend on several feature values
    simultaneously (e.g. subject and object person/number). Maps a string of feature
    values to a marker dictionary, where feature values are specified in the format
    'feature=value feature=value'.

    Allows retrieving markers based on the string used when setting them, or by
    passing a dictionary of feature values.

    Requires that all keys specify the same set of features when creating.

    Usage:
    >>> subj_obj_marker = ContingentMarkers()
    >>> subj_obj_marker['object=third_singular subject=first_singular'] = [{'suffix': '-íŋí'}]
    >>> subj_obj_marker.get_marker(subject_person='first_singular', object_person='third_singular')
    [{'suffix': '-íŋí'}]
    """
    def __post_init__(self):
        # Set feature names from the first key
        first_key = next(iter(self.data))
        feature_names = self._feature_str_to_dict(first_key).keys()
        feature_names = list(sorted(feature_names))
        self.feature_names = feature_names

        # Set attributes dynamically based on keys in data
        # Sort feature values in keys to ensure consistent ordering
        for key, value in self.data.items():
            if not isinstance(value, dict):
                raise ValueError(f"Marker value for {key} must be a dictionary.")
            
            key_feature_dict = self._feature_str_to_dict(key)
            key_features = list(sorted(key_feature_dict.keys()))
            if key_features != feature_names:
                raise ValueError(
                    f"All keys must have the same feature names. "
                    f"Expected {feature_names}, got {key_features}."
                )

            sorted_key = self._stringify_feature_dict(key_feature_dict)
            setattr(self, sorted_key, value)

class FeatureValueCombinations:
    """
    Class for tracking licit combinations of person (both subject and object)
    and class values. Initialize with a list of combination dictionaries.
    Each dictionary specifies valid values for features.
    A value of '*' indicates all possible values for that feature.
    Note that every combination dictionary must specify the same set of features.

    Usage:

    >>> combinations # list of dicts
    [{'subject_value': 'unmarked', 'object_value': ...}]
    >>> feature_combos = FeatureValueCombinations(combinations)
    >>> feature_combos.get_all_combinations()
    [{'subject_value': 'first_singular', 'object_value': 'second_singular', 'class_value': 'g'}, ...]
    >>> feature_combos.is_licit_combination('first_singular', 'second_singular', 'g')
    True
    >>> feature_combos.is_licit_combination('first_singular', 'first_singular', 'g')
    False
    
    `combinations` is a list of dicts where each map a valid combination set,
    e.g.

    ```python
    [
        # no subject/object marking, all classes permitted
        {
            'subject_value': 'unmarked',
            'object_value': 'unmarked',
            'class_value': '*',
        },
        # second person subject marking, which co-occurs with g-class agreement
        {
            'subject_value': ['second_singular'],
            'object_value': ['unmarked', 'first_singular', 'first_exclusive_plural'],
            'class_value': 'g',
        },
        # first person subject marking, which co-occurs with g-class agreement
        {
            'subject_value': ['first_singular'],
            'object_value': ['unmarked', 'second_singular', 'second_plural'],
            'class_value': 'g',
        },
    ]
    ```
    
    Creates a list of all possible feature combinations specified
    in the input dictionaries to use for querying.
    """

    def __init__(self, combinations: List[
            Dict[str, Union[str, List[str]]]
        ]
    ):
        first_combination = combinations[0]
        expected_features = set(first_combination.keys())
        self.feature_names = list(sorted(expected_features))

        all_combinations = pd.DataFrame()
        for combination in combinations:
            combination_features = set(combination.keys())
            if combination_features != expected_features:
                raise ValueError(
                    f"All combination dictionaries must have the same feature names. "
                    f"Expected {expected_features}, got {combination_features}."
                )
            expanded_df = self._expand_combination_dict(combination)
            all_combinations = pd.concat([all_combinations, expanded_df], ignore_index=True)
        self.valid_combinations = all_combinations.drop_duplicates().reset_index(drop=True)

    def _expand_combination_dict(self, combination: Dict[str, Union[List[str], str]]) -> pd.DataFrame:
        """
        Expand a single combination dictionary into a dataframe where each row
        is a single combination of the specified features.
        """
        row = {}
        for feature, values in combination.items():
            if values == '*':
                values = FEATURES_TO_VALUES[feature]
            row[feature] = values
        df = pd.DataFrame(row)
        for feature in combination.keys():
            df = df.explode(feature).reset_index(drop=True)
        return df

    def is_licit_combination(
        self,
        **feature_values: str
    ) -> bool:
        """
        Check if a given combination of feature values is licit.
        """
        for expected_feature in self.feature_names:
            if expected_feature not in feature_values:
                feature_values[expected_feature] = 'unmarked'
        
        for provided_feature in feature_values.keys():
            if provided_feature not in self.feature_names:
                raise ValueError(
                    f"Unexpected feature '{provided_feature}' provided. "
                    f"Expected features: {self.feature_names}."
                )

        feature_mask = pd.Series([True] * len(self.valid_combinations))
        for feature, value in feature_values.items():
            feature_mask &= (self.valid_combinations[feature] == value)
        return bool(feature_mask.any())

    def get_all_combinations(self) -> List[Dict[str, str]]:
        return self.valid_combinations.to_dict(orient='records') #type: ignore

class ParadigmMarkers(FeatureQueryMixin):
    """
    Object for combining marker objects based on multiple feature values.
    Allows combination of standard marker objects (i.e. for one feature each)
    and contingent marker objects (i.e. for multiple features simultaneously).
    Contingent marker objects are given priority when combining.
    """

    def __init__(
        self,
        feature_value_combinations: FeatureValueCombinations,
        marker_objects: Dict[str, FeatureMarkers],
        contingent_marker_objects: List[ContingentMarkers],
        marker_order: List[str],
    ):
        self.feature_value_combinations = feature_value_combinations
        self.feature_names = feature_value_combinations.feature_names
        self.marker_order = marker_order

        recognized_features = marker_objects.keys()

        self.marker_objects = marker_objects

        # verify no overlap in contingent marker feature sets
        contingent_features = []
        for contingent_marker in contingent_marker_objects:
            for feature in contingent_marker.feature_names:
                if feature in contingent_features:
                    raise ValueError(
                        f"Overlapping feature '{feature}' in contingent feature maps."
                    )
            contingent_features.extend(contingent_marker.feature_names)

        self.contingent_marker_objects = contingent_marker_objects

        recognized_features = set(recognized_features).union(contingent_features)
        if set(self.feature_names) != recognized_features:
            raise ValueError(
                f"Feature names in feature_value_combinations do not match "
                f"those in marker_objects and contingent_marker_objects. "
                f"Expected {self.feature_names}, got {recognized_features}."
            )
        
        self.data = self._populate_data()

    def _get_marker_dict(
        self,
        **feature_values: str
    ) -> List[Dict[str, str]]:
        """
        Get the marker dictionary for a given feature combination.
        This performs non-hashed searching through all provided marker objects,
        and is used during init to build the hashtable for efficient querying.
        """
        provided_features = set(feature_values.keys())
        expected_features = set(self.feature_names)
        if provided_features != expected_features:
            raise ValueError(
                f"Provided feature values do not match expected features. "
                f"Expected {expected_features}, got {provided_features}."
            )

        features_to_match = provided_features.copy()
        marker = []

        # first check contingent markers
        for contingent_marker_map in self.contingent_marker_objects:
            features_for_marker = contingent_marker_map.feature_names
            feature_subset = {feature: feature_values[feature] for feature in features_for_marker}
            marker_part = contingent_marker_map.get_marker(**feature_subset)
            if marker_part:
                marker.append(marker_part)
                features_to_match -= set(features_for_marker)
        
        # then check standard markers
        for feature in features_to_match:
            marker_map = self.marker_objects[feature]
            feature_value = feature_values[feature]
            marker_part = getattr(marker_map, feature_value, {})
            if marker_part:
                marker.append(marker_part)
            else:
                raise KeyError(
                    f"No marker found for feature '{feature}' with value '{feature_value}'."
                )

        # ensure marker 'order' values are recognized
        for m in marker:
            order = m.get('order')
            if order and order not in self.marker_order:
                raise ValueError(
                    f"Marker order '{order}' not recognized. "
                    f"Expected one of {self.marker_order}."
                )

        # sort marker parts according to specified order
        marker.sort(
            key=lambda m: self.marker_order.index(m.get('order', float('inf')))
        )

        return marker


    def _populate_data(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Build a dictionary mapping feature combination strings to marker lists.
        """
        all_combinations = self.feature_value_combinations.get_all_combinations()
        data = {}
        for combination in all_combinations:
            marker_list = self._get_marker_dict(**combination)
            key = self._stringify_feature_dict(combination)
            data[key] = marker_list

        return data