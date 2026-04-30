from src.grammar.classes import Registry
from src.grammar.orchestrator.feature_orchestrator import (
    FeatureOrchestrator,
    stringify_features,
)
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from dataclasses import dataclass, field
import os
import pynini
from loguru import logger
from typing import Literal


@dataclass
class MorphemeSet:
    """
    Maps arbitrary feature vectors to morpheme strings.
    Corresponds to a ``kind: MorphemeSet`` YAML config.

    Attributes:
        feature_mappings: Dict mapping feature vector (frozenset of items) to MarkerList
        source: Filepath this config was loaded from
    """

    feature_mappings: dict[frozenset[tuple[str, str]], str] = field(
        default_factory=dict
    )
    source: os.PathLike | None = None
    fst_orchestrator: FstOrchestrator | None = None

    @classmethod
    def from_config(
        cls,
        config: dict,
        feature_orchestrator: FeatureOrchestrator,
        fst_orchestrator: FstOrchestrator,
    ) -> "MorphemeSet":
        """Build a MorphemeSet from a full YAML config dict."""
        source = config.get("source_path")
        morpheme_config = config.get("data", [])

        feature_mappings: dict[frozenset[tuple[str, str]], str] = {}
        for entry in morpheme_config:
            features_dict = entry.get("features", {})
            morpheme = entry.get("morpheme", [])

            # Validate features
            for f_name, f_val in features_dict.items():
                feature = feature_orchestrator.get_feature(f_name)
                if f_val not in feature.values:
                    raise ValueError(
                        f"Invalid value '{f_val}' for feature '{f_name}' in {source}"
                    )

            vector = frozenset(features_dict.items())
            feature_mappings[vector] = morpheme

        return cls(
            feature_mappings=feature_mappings,
            source=source,
            fst_orchestrator=fst_orchestrator,
        )

    def get_morpheme(self, **feature_dict: str) -> str:
        """Retrieve morpheme matching the feature vector."""
        for vector, morpheme in self.feature_mappings.items():
            if vector.issubset(feature_dict.items()):
                return morpheme

        raise KeyError(
            f"No matching feature vector in {self.source} for {feature_dict}"
        )

    def _morpheme_analysis_fst(
        self,
        direction: Literal["morpheme_to_analysis", "analysis_to_morpheme"],
        **feature_dict: str,
    ) -> pynini.Fst:
        """Get a transducer 'morpheme' -> [feature=val][feature=val]..."""
        for vector, morpheme in self.feature_mappings.items():
            if vector.issubset(feature_dict.items()):
                vector_str = stringify_features(vector)
                vector_fsa = self.fst_orchestrator.fsa(vector_str)
                morpheme_fsa = self.fst_orchestrator.fsa(morpheme)
                if direction == "morpheme_to_analysis":
                    analyzer_fst = pynini.cross(vector_fsa, morpheme_fsa)
                elif direction == "analysis_to_morpheme":
                    analyzer_fst = pynini.cross(morpheme_fsa, vector_fsa)
                return analyzer_fst

        raise KeyError(
            f"No matching feature vector in {self.source} for {feature_dict}"
        )

    def morpheme_to_analysis(self, **feature_dict: str) -> pynini.Fst:
        """
        Transduces a morpheme to a stringified vector of all of the
        morpheme's feature specifications.
        """
        return self._morpheme_analysis_fst(
            direction="morpheme_to_analysis", **feature_dict
        )

    def analysis_to_morpheme(self, **feature_dict: str) -> pynini.Fst:
        """
        Transduces a stringified vector of all of the morpheme's feature
        specifications to just the morpheme.
        """
        return self._morpheme_analysis_fst(
            direction="analysis_to_morpheme", **feature_dict
        )

    def __str__(self):
        return (
            f"MorphemeSet(source='{self.source}', "
            f"vectors={len(self.feature_mappings)})"
        )

    def __repr__(self):
        return self.__str__()


class MorphemeSetRegistry(Registry):
    """
    Registry for ``kind: MorphemeSetRegistry`` configs.
    ``data`` maps config filename stems to MorphemeSet objects.
    """

    def __init__(
        self,
        feature_orchestrator: FeatureOrchestrator,
        fst_orchestrator: FstOrchestrator,
        data: dict[str, MorphemeSet | None] = None,
        config_objects: dict[str, dict | None] = None,
    ):
        self.feature_orchestrator = feature_orchestrator
        self.fst_orchestrator = fst_orchestrator
        super().__init__(
            kind="MorphemeSet",
            data=data,
            config_objects=config_objects,
        )

    def get_morpheme_set(self, name: str) -> MorphemeSet:
        name = name.removeprefix("$")
        if name not in self.data:
            raise KeyError(f"MorphemeSet '{name}' not found in registry.")
        return self.data[name]

    def load_all_configs(self) -> dict[str, MorphemeSet]:
        config_items: dict[str, MorphemeSet] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate MorphemeSet '{key}' found in "
                        f"multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, MorphemeSet]:
        source_path = config.get("source_path", "")
        name = os.path.splitext(os.path.basename(source_path))[0] if source_path else ""
        contingent_markers = MorphemeSet.from_config(
            config, self.feature_orchestrator, self.fst_orchestrator
        )
        return {name: contingent_markers}
