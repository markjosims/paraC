from loguru import logger
from dataclasses import dataclass, field
import os

from src.grammar.classes import Registry

@dataclass
class Feature:
    """
    Represents a single morphological feature and its possible values.

    Attributes:
        name: Feature name (e.g. ``subject`` or ``tam``)
        values: Enumerated values for the feature
        source: Filepath this feature definition was loaded from
    """

    name: str
    values: list[str]
    source: os.PathLike | None = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Feature name cannot be empty.")
        if not self.values:
            raise ValueError(f"Feature '{self.name}' must define at least one value.")
        if len(self.values) != len(set(self.values)):
            raise ValueError(
                f"Feature '{self.name}' contains duplicate values: {self.values}"
            )
        # append "unmarked" to feature values
        self.values.append("unmarked")

    @classmethod
    def from_config(
        cls,
        name: str,
        values: list[str],
        source: os.PathLike = None,
    ) -> 'Feature':
        return cls(name=name, values=list(values), source=source)

    def __str__(self):
        return f"Feature(name='{self.name}', values={self.values})"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash((self.name, tuple(self.values)))

    def __eq__(self, other):
        if not isinstance(other, Feature):
            return NotImplemented
        return self.name == other.name and set(self.values) == set(other.values)


class FeatureValuesRegistry(Registry):
    """
    Registry for `FeatureDefinitions` configs. May be initialized from
    a `data` dict mapping feature name to `Feature` object or `config_objects`
    dict mapping filenames to YAML data.
    """

    def __init__(
        self,
        data: dict[str, Feature] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        super().__init__(kind="FeatureDefinitions", data=data, config_objects=config_objects)
        self._populate_features_to_values()

    def _populate_features_to_values(self):
        self.features_to_values = {
            feature.name: feature.values for feature in self.data.values()
        }

    def load_all_configs(self) -> dict[str, Feature]:
        config_items: dict[str, Feature] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate feature '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, Feature]:
        features = config.get("features", {})
        source_path = config.get("source_path")
        if not features:
            error = "No features found in config."
            logger.error(error)
            raise ValueError(error)

        return {
            feature_name: Feature.from_config(
                name=feature_name,
                values=feature_values,
                source=source_path,
            )
            for feature_name, feature_values in features.items()
        }

