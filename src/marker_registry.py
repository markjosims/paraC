from typing import Dict, Optional, Tuple, Union, List
from dataclasses import dataclass, field
import pandas as pd
from src.constants import FEATURES_TO_VALUES
from pynini import Fst

"""
Dataclasses and classes for constructing and querying affix markers
"""

@dataclass
class Marker:
    """
    Dataclass for storing a single affix marker.
    
    Attributes:
        prefix: String to be added as a prefix
        suffix: String to be added as a suffix
        replace: Pair of strings indicating a substring to be replaced and its replacement
        suppletion: Full form to use instead of the base form
        rule: Name(s) of phonological rule(s) to apply (must be defined elsewhere)
        order: A unique name for ordering application of rules/affixes
        fst: Finite State Transducer representing the marker (built by `FstRegistry` object)
        
    """
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    replace: Optional[Tuple[str, str]] = None
    suppletion: Optional[str] = None
    rule: Optional[Union[str, List[str]]] = None
    order: Optional[str] = None
    fst: Optional[Fst] = None  # Placeholder for FST object

    def __post_init__(self):
        if self.fst is not None:
            raise ValueError("FST should not be provided directly; it will be built automatically.")
        if self.suppletion is not None:
            if any([self.prefix, self.suffix, self.replace, self.rule]):
                raise ValueError("Suppletion cannot be combined with other marker attributes.")
    
@dataclass
class FeatureMarkers:
    """
    Dataclass mapping feature values to marker objects.
    
    Usage:
    >>> marker = MarkerClass()
    >>> marker.data['first_singular'] = Marker(suffix='-íŋí')
    >>> marker.data['second_singular'] = Marker(prefix='jɛ́-')
    """
    data: Dict[str, List[Marker]] = field(default_factory=dict)

    def __post_init__(self):
        # Set attributes dynamically based on keys in data
        for key, value in self.data.items():
            if isinstance(value, dict) or isinstance(value, Marker):
                value = [value]
            # Cast list of dicts to Markers
            if isinstance(value[0], dict):
                value = [Marker(d) for d in value]
            elif not isinstance(value, list):
                raise ValueError(f"Marker value for {key} must be a Marker or list of Markers.")
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

    def get_marker(self, **feature_dict: str) -> List[Marker]:
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
    >>> subj_obj_marker['object=third_singular subject=first_singular'] = Marker(suffix='-íŋí')
    >>> subj_obj_marker.get_marker(subject_person='first_singular', object_person='third_singular')
    [Marker(suffix='-íŋí')]
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