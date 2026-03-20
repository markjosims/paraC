"""
[Placeholder for now]
This file implements the `PartOfSpeech` and `Lexicon` classes
as well as the `LexiconRegistry` class, which is responsible for
storing and managing the lexicon for a given language.
"""

from dataclasses import dataclass
from src.registry.registry_utils import Registry

@dataclass
class PartOfSpeech:
    """
    Object for representing a part of speech in the lexicon.
    """

@dataclass
class Lexicon:
    """
    Object for representing the lexicon for a given language.
    Stores a mapping from lemmas to their parts of speech and other
    relevant information (e.g. morphological features, etc.).
    """

@dataclass
class LexiconRegistry(Registry):
    """
    Object for storing and managing `Lexicon` and `PartOfSpeech` objects
    for a given language.
    """