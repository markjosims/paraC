"""
[Placeholder for now]
This file implements the `PartOfSpeech` and `Lexicon` classes
as well as the `LexiconRegistry` class, which is responsible for
storing and managing the lexicon for a given language.
"""

from asyncio.log import logger
from dataclasses import dataclass, field
import os

from loguru import logger
from typing import Dict, Optional, Tuple, List
from src.registry.registry_utils import Registry
from src.registry.feature_registry import Feature, FeatureRegistry
import pandas as pd

@dataclass
class PartOfSpeech:
    """
    Object for representing a part of speech in the lexicon.
    """
    name: str
    features: List[Feature] = field(default_factory=list)
    invariant_features: List[Feature] = field(default_factory=list)
    lexical_flags: List[str] = field(default_factory=list)
    principal_parts: List[str] = field(default_factory=list)
    source: Optional[str] = None

    def __post_init__(self):
        if self.name is None:
            raise ValueError("PartOfSpeech must have a name.")
        
        for feature in self.features + self.invariant_features:
            if not isinstance(feature, Feature):
                raise ValueError(f"Feature '{feature}' is not an instance of the Feature class.")
            
        for feature in self.invariant_features:
            if feature in self.features:
                raise ValueError(f"Invariant feature '{feature}' also listed as a inflected feature.")

    def from_config(config: dict, feature_registry: FeatureRegistry) -> 'PartOfSpeech':
        name = config.get('name', None)
        feature_names = config.get('features', [])
        features = []
        for feature_name in feature_names:
            feature = feature_registry.get_feature(feature_name)
            if feature is None:
                raise ValueError(f"Feature '{feature_name}' not found in feature registry.")
            features.append(feature)

        invariant_feature_names = config.get('invariant_features', [])
        invariant_features = []
        for feature_name in invariant_feature_names:
            feature = feature_registry.get_feature(feature_name)
            if feature is None:
                raise ValueError(f"Invariant feature '{feature_name}' not found in feature registry.")
            invariant_features.append(feature)
        
        lexical_flags = config.get('lexical_flags', [])
        principal_parts = config.get('principal_parts', [])
        source = config.get('source_path', None)
        return PartOfSpeech(
            name=name,
            features=features,
            invariant_features=invariant_features,
            lexical_flags=lexical_flags,
            principal_parts=principal_parts,
            source=source
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
    source: Optional[str] = None
    lexical_flags: List[str] = field(init=False)
    principal_parts: List[str] = field(init=False)
    features: List[Feature] = field(init=False)
    invariant_features: List[Feature] = field(init=False)

    def __post_init__(self):
        if 'root' not in self.entries.columns:
            raise ValueError("Entries dataframe must contain a 'root' column")
        if 'gloss' not in self.entries.columns:
            raise ValueError("Entries dataframe must contain a 'gloss' column")

        # Validate that the columns of the entries dataframe match the expected features
        expected_columns = self.part_of_speech.lexical_flags\
            + self.part_of_speech.principal_parts\
            + [feature.name for feature in self.part_of_speech.invariant_features]
        expected_columns = set(expected_columns)
        actual_columns = set(self.entries.columns)
        if not expected_columns.issubset(actual_columns):
            missing_columns = expected_columns - actual_columns
            raise ValueError(f"Missing columns in entries dataframe: {missing_columns}")

        self.lexical_flags = self.part_of_speech.lexical_flags
        self.principal_parts = self.part_of_speech.principal_parts
        self.features = self.part_of_speech.features
        self.invariant_features = self.part_of_speech.invariant_features
        
    @classmethod
    def from_config(cls, config, feature_registry: FeatureRegistry) -> 'Lexicon':
        """
        Get the lexicon entries dataframe for a given part of speech name.
        """
        part_of_speech = PartOfSpeech.from_config(config, feature_registry)
        config_source = part_of_speech.source
        if config_source is None:
            raise ValueError(f"Part of speech '{part_of_speech}' does not have a source config file.")
        
        part_of_speech_dir = os.path.dirname(config_source)
        config_dir = os.path.dirname(part_of_speech_dir)
        lexicon_dir = os.path.join(config_dir, 'lexicon')
        lexicon_stem = part_of_speech.name + '.csv'
        lexicon_path = os.path.join(lexicon_dir, lexicon_stem)
        if not os.path.exists(lexicon_path):
            raise ValueError(f"Lexicon file '{lexicon_path}' not found for part of speech '{part_of_speech.name}'.")
        entries_df = pd.read_csv(lexicon_path)
        return cls(
            part_of_speech=part_of_speech,
            entries=entries_df,
            source=lexicon_path,
        )
    
    def get_roots(self) -> List[str]:
        return self.entries['root'].tolist()
    
    def get_column_data(self, column: str, fill_w_root: bool=False) -> List[str]:
        if column not in self.entries.columns:
            raise KeyError(f"Column '{column}' not found in entries dataframe, expected columns are: {self.entries.columns.tolist()}")
        if fill_w_root:
            return self.entries[column].fillna(self.entries['root']).tolist()
        return self.entries[column].tolist()

@dataclass
class LexiconRegistry(Registry):
    """
    Object for storing and managing `Lexicon` and `PartOfSpeech` objects
    for a given language.
    """
    def __init__(
        self,
        data: Optional[List[pd.DataFrame]] = None,
        config_lists: Optional[List[dict]] = None,
        feature_registry: Optional[FeatureRegistry] = None
    ):
        super().__init__(
            kind="PartOfSpeech", data=data, config_list=config_lists
        )
        self.feature_registry = feature_registry

    @classmethod
    def from_config_dir(cls, config_dir: str) -> "LexiconRegistry":
        """
        Factory method for creating a `LexiconRegistry` from a configuration directory.
        """
        lexicon_reg = super().from_config_dir(config_dir)
        feature_reg = FeatureRegistry.from_config_dir(config_dir)
        lexicon_reg.feature_registry = feature_reg

        data = lexicon_reg.load_all_configs()
        lexicon_reg.data = data
        return lexicon_reg


    def load_all_configs(self) -> Dict[str, Lexicon]:
        config_items: Dict[str, Lexicon] = {}
        for config in self.config_list:
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate Lexicon '{key}' found in "
                        f"multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items
        
    def load_data_from_config(
        self, config: dict
    ) -> Dict[str, Lexicon]:
        source_path = config.get('source_path', '')
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get('name', '')
        )
        lexicon = Lexicon.from_config(config, self.feature_registry)
        return {name: lexicon}