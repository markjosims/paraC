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
                marker.extend(marker_part)
                features_to_match -= set(features_for_marker)
        
        # then check standard markers
        for feature in features_to_match:
            marker_map = self.marker_objects[feature]
            feature_value = feature_values[feature]
            marker_part = getattr(marker_map, feature_value, {})
            if marker_part:
                marker.extend(marker_part)
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
    
    def to_pandas(self) -> pd.DataFrame:
        """
        Convert the paradigm markers data to a pandas DataFrame.
        Each row corresponds to a feature combination and its associated markers.
        """
        records = []
        for feature_str, markers in self.data.items():
            feature_dict = self._feature_str_to_dict(feature_str)
            record = {**feature_dict, 'markers': markers}
            records.append(record)
        return pd.DataFrame(records)