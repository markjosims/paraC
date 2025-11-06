from src.parser import get_main_parser, inflect_word, parse_word
from src.lexicon import *
from src.constants import VERB_FEATURE_VALUES, LEXICAL_FEATURE_VALUES
import pytest
from tests.utils import get_different_items

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_inflection(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form').replace('-', '')
    gold_verb["part_of_speech"]='verb'
    gold_verb['aux']= str(' ' in form).lower()

    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }
    predicted_form = inflect_word(root, feature_dict=gold_verb_filtered)

    assert form in predicted_form

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing(gold_verb):
    analyzed_form = gold_verb['form']
    gold_verb['analyzed_form']=analyzed_form
    form = analyzed_form.replace('-', '')
    gold_verb['form']=form
    gold_verb["part_of_speech"]='verb'
    gold_verb['aux']= str(' ' in form).lower()

    predicted_parse = parse_word(form)
    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if any(k in parse for parse in predicted_parse)
    }
    assert gold_verb_filtered in predicted_parse

@pytest.mark.parametrize("gold_verb", get_gold_derived_verbs())
def test_derived_verbs(gold_verb):
    form = gold_verb.pop('form')
    root = gold_verb.pop('root')
    gold_verb["part_of_speech"]='verb'
    gold_verb['aux']= ' ' in form

    verb_filtered = {
        k: v for k,v in gold_verb.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }

    predicted_forms = inflect_word(
        root=root,
        feature_dict=verb_filtered,
    )

    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_forms(gold_adj):
    root = gold_adj.pop('root')
    form = gold_adj.pop('form')
    form = form.replace('-', '')
    gold_adj["part_of_speech"]='adjective'

    predicted_forms = inflect_word(root, feature_dict=gold_adj)
    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_parsing(gold_adj):
    analyzed_form = gold_adj['form']
    gold_adj['analyzed_form']=analyzed_form
    gold_adj["part_of_speech"]='adjective'
    form = analyzed_form.replace('-', '')
    gold_adj['form']=form

    predicted_parses = parse_word(form)
    gold_adj_filtered = {
        k: v for k,v in gold_adj.items()
        if k in predicted_parses[0]
    }
    assert gold_adj_filtered in predicted_parses

@pytest.mark.parametrize("gold_word", get_uninflected_word_data())
def test_uninflected_forms(gold_word):
    word = gold_word['word']
    gold_word['analyzed_form']=word
    gold_word['root']=word

    parses = parse_word(word)
    gold_word_filtered = {
        k: v for k,v in gold_word.items()
        if k in parses[0]
    }
    assert gold_word_filtered in parses

@pytest.mark.parametrize("gold_aux", get_gold_auxs())
def test_gold_auxs(gold_aux):
    form = gold_aux.pop('form')
    gold_aux['part_of_speech']='verb'
    gold_aux['aux']='true'

    aux_filtered = {
        k: v for k,v in gold_aux.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }
    predicted_forms = inflect_word('', feature_dict=aux_filtered)

    assert form in predicted_forms