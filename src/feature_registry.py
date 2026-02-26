class FeatureRegistry:
    ...

@dataclass
class FeatureSet:
    # abstracts over Feature and FeatureValueCombinations for an arbitrary number of features
    ...

@dataclass
class Feature:
    ...

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