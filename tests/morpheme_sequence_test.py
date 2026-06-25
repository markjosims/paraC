import pytest
from src.grammar import Grammar
from src.config_utils.config_walker import ConfigWalker
from pathlib import Path

@pytest.fixture
def grammar():
    # Use the example config for fast testing
    config_dir = Path("config/example")
    walker = ConfigWalker(config_dir)
    return Grammar(**walker.config_data)

def test_morpheme_sequence_initialization(grammar):
    # Check if MorphemeSequence registry exists and is loaded
    assert hasattr(grammar, "morpheme_sequence_registry")
    registry = grammar.morpheme_sequence_registry
    assert registry is not None

def test_morpheme_sequence_inflection(grammar):
    registry = grammar.morpheme_sequence_registry
    if not registry.data:
        pytest.skip("No MorphemeSequence found in example config")
    
    seq_name = list(registry.data.keys())[0]
    sequence = registry.get_sequence(seq_name)
    
    # Attempt inflection with some features
    forms = sequence.get_inflected_form({})
    print(f"Inflected forms for {seq_name}: {forms}")
    assert isinstance(forms, list)

