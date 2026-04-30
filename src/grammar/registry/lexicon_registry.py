"""
This file implements the `PartOfSpeech` and `Lexicon` classes
as well as the `LexiconRegistry` class, which is responsible for
storing and managing the lexicon for a given language.
"""

from dataclasses import dataclass, field
import os
import pynini
from loguru import logger
from src.grammar.classes import Registry
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.orchestrator.feature_orchestrator import (
    FeatureOrchestrator,
    stringify_features,
)
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
import pandas as pd
import numpy as np
from typing import Literal


@dataclass
class PartOfSpeech:
    """
    Object for representing a part of speech in the lexicon.
    """

    name: str
    features: list[Feature] = field(default_factory=list)
    lexical_features: list[Feature] = field(default_factory=list)
    principal_parts: list[str] = field(default_factory=list)
    source: str | None = None

    def __post_init__(self):
        if self.name is None:
            raise ValueError("PartOfSpeech must have a name.")

        for feature in self.features + self.lexical_features:
            if type(feature).__name__ != "Feature":
                raise ValueError(
                    f"Feature '{feature}' of type {type(feature)} is not an instance of the Feature class."
                )

        for feature in self.lexical_features:
            if feature in self.features:
                raise ValueError(
                    f"Invariant feature '{feature}' also listed as a inflected feature."
                )

    @classmethod
    def from_config(
        cls, config: dict, feature_orchestrator: FeatureOrchestrator
    ) -> "PartOfSpeech":
        name = config.get("name", None)
        feature_names = config.get("features", [])
        features = []
        for feature_name in feature_names:
            feature = feature_orchestrator.get_feature(feature_name)
            if feature is None:
                raise ValueError(
                    f"Feature '{feature_name}' not found in feature registry."
                )
            features.append(feature)

        lexical_feature_names = config.get("lexical_features", [])
        lexical_features = []
        for feature_name in lexical_feature_names:
            feature = feature_orchestrator.get_feature(feature_name)
            if feature is None:
                raise ValueError(
                    f"Lexical feature '{feature_name}' not found in feature registry."
                )
            lexical_features.append(feature)

        principal_parts = config.get("principal_parts", [])
        source = config.get("source_path", None)
        return cls(
            name=name,
            features=features,
            lexical_features=lexical_features,
            principal_parts=principal_parts,
            source=source,
        )


@dataclass
class Lexicon:
    """
    Object for representing the lexicon for a given language.
    Essentially a wrapper around a `PartOfSpeech` object and
    a `pandas.DataFrame` containing the lexicon entries for that
    part of speech, performing validation between the columns of
    the dataframe and those expected by the `PartOfSpeech` object.
    """

    part_of_speech: PartOfSpeech
    entries: pd.DataFrame
    fst_orchestrator: FstOrchestrator
    source: str | None = None
    principal_parts: list[str] = field(init=False)
    lexical_features: list[Feature] = field(init=False)
    features: list[Feature] = field(init=False)

    def __post_init__(self):
        if "root" not in self.entries.columns:
            raise ValueError("Entries dataframe must contain a 'root' column")
        if "gloss" not in self.entries.columns:
            raise ValueError("Entries dataframe must contain a 'gloss' column")

        # Validate that the columns of the entries dataframe match the expected features
        expected_feature_names = [
            feature.name for feature in self.part_of_speech.lexical_features
        ]
        expected_columns = expected_feature_names + self.part_of_speech.principal_parts
        expected_columns = set(expected_columns)
        actual_columns = set(self.entries.columns)
        if not expected_columns.issubset(actual_columns):
            missing_columns = expected_columns - actual_columns
            raise ValueError(f"Missing columns in entries dataframe: {missing_columns}")

        self.lexical_features = self.part_of_speech.lexical_features
        self.principal_parts = self.part_of_speech.principal_parts
        self.features = self.part_of_speech.features

    @classmethod
    def from_config(
        cls,
        config,
        feature_orchestrator: FeatureOrchestrator,
        fst_orchestrator: FstOrchestrator,
    ) -> "Lexicon":
        """
        Get the lexicon entries dataframe for a given part of speech name.
        """
        part_of_speech = PartOfSpeech.from_config(config, feature_orchestrator)
        config_source = part_of_speech.source
        if config_source is None:
            raise ValueError(
                f"Part of speech '{part_of_speech}' does not have a source config file."
            )

        # TODO: implement lazy loading of CSVs, should be handled by `ConfigWalker`
        part_of_speech_dir = os.path.dirname(config_source)
        config_dir = os.path.dirname(part_of_speech_dir)
        lexicon_dir = os.path.join(config_dir, "lexicon")
        lexicon_stem = part_of_speech.name + ".csv"
        lexicon_path = os.path.join(lexicon_dir, lexicon_stem)
        if not os.path.exists(lexicon_path):
            raise ValueError(
                f"Lexicon file '{lexicon_path}' not found for part of speech '{part_of_speech.name}'."
            )
        entries_df = pd.read_csv(lexicon_path, keep_default_na=False)
        return cls(
            part_of_speech=part_of_speech,
            entries=entries_df,
            source=lexicon_path,
            fst_orchestrator=fst_orchestrator,
        )

    def get_roots(self) -> list[str]:
        return self.entries["root"].tolist()

    def get_column_data(self, column: str, fill_w_root: bool = False) -> list[str]:
        if column not in self.entries.columns:
            raise KeyError(
                f"Column '{column}' not found in entries dataframe, expected columns are: {self.entries.columns.tolist()}"
            )
        if fill_w_root:
            return (
                self.entries[column]
                .replace("", np.nan)
                .fillna(self.entries["root"])
                .tolist()
            )
        return self.entries[column].tolist()

    def _root_analysis_fst(
        self,
        features: dict[str, str] | None = None,
        direction: Literal[
            "roots_to_analyses", "analyses_to_roots"
        ] = "roots_to_analyses",
    ) -> pynini.Fst:
        """
        Transduces a root to a root with a stringified vector of all of the
        root's lexical feature specifications.
        """
        filtered_df = self.entries
        if features:
            for feat_name, feat_val in features.items():
                if feat_name in filtered_df.columns:
                    mask = (
                        (filtered_df[feat_name] == feat_val)
                        | (filtered_df[feat_name] == "")
                        | (filtered_df[feat_name].isna())
                    )
                    filtered_df = filtered_df[mask]

        fsts = []
        lexical_feat_names = [f.name for f in self.lexical_features]

        for _, row in filtered_df.iterrows():
            root = str(row["root"])
            row_feats = {}
            for fn in lexical_feat_names:
                val = str(row.get(fn, "unmarked"))
                if not val or val == "nan":
                    val = "unmarked"
                row_feats[fn] = val

            analysis_suffix = stringify_features(row_feats)

            root_fsa = self.fst_orchestrator.fsa(root)
            analysis_fsa = self.fst_orchestrator.fsa(root + analysis_suffix)

            if direction == "roots_to_analyses":
                fsts.append(pynini.cross(root_fsa, analysis_fsa))
            else:
                # direction == "analyses_to_roots"
                fsts.append(pynini.cross(analysis_fsa, root_fsa))

        if not fsts:
            return pynini.Fst()

        return pynini.union(*fsts).optimize()

    def roots_to_analyses(self, features: dict[str, str] | None = None) -> pynini.Fst:
        """
        Transduces a root to a root with a stringified vector of all of the
        root's lexical feature specifications.
        """
        return self._root_analysis_fst(features=features, direction="roots_to_analyses")

    def analyses_to_roots(self, features: dict[str, str] | None = None) -> pynini.Fst:
        """
        Transduces a root with a stringified vector of all of the
        root's lexical feature specifications to just the root.
        """
        return self._root_analysis_fst(features=features, direction="analyses_to_roots")


@dataclass
class LexiconRegistry(Registry):
    """
    Object for storing and managing `Lexicon` and `PartOfSpeech` objects
    for a given language.
    """

    def __init__(
        self,
        feature_orchestrator: FeatureOrchestrator,
        fst_orchestrator: FstOrchestrator,
        data: dict[str, Lexicon] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.feature_orchestrator = feature_orchestrator
        self.fst_orchestrator = fst_orchestrator
        super().__init__(kind="PartOfSpeech", data=data, config_objects=config_objects)

    def get_lexicon(self, name: str) -> Lexicon:
        name = name.removeprefix("$")
        if name not in self.data:
            raise KeyError(f"Lexicon '{name}' not found in registry.")
        return self.data[name]

    def load_all_configs(self) -> dict[str, Lexicon]:
        config_items: dict[str, Lexicon] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate Lexicon '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, Lexicon]:
        source_path = config.get("source_path", "")
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get("name", "")
        )
        lexicon = Lexicon.from_config(
            config=config,
            feature_orchestrator=self.feature_orchestrator,
            fst_orchestrator=self.fst_orchestrator,
        )
        return {name: lexicon}
