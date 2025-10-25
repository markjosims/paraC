import pytest
from src.form_builders.adjective_forms import ADJECTIVE_PARADIGM, inflect_adjective_with_features, parse_adjective
from src.form_builders.form_helpers import generate_forms
from src.form_builders.uninflected_forms import parse_uninflected_word
from src.form_builders.verb_forms import *
from src.lexicon import *
from src.constants import VERB_FEATURE_VALUES

@pytest.mark.parametrize("verb_root,fv_class", get_all_verb_roots_and_fvs())
def test_compile_regular_paradigms(verb_root, fv_class):
    if fv_class == 'IRREG':
        # skipping irregular verbs for now
        return
    try:
        forms = generate_forms(verb_root, FV2PARADIGM[fv_class], action='return')
        assert len(forms) >= VERB_PARADIGM_SIZE
    except Exception as error:
        print(verb_root, fv_class)
        raise error

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_inflection(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form')
    fv = gold_verb.pop('fv')

    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if k in VERB_FEATURE_VALUES or k=='gloss'
    }
    predicted_form = inflect_verb_with_features(root, fv, features=gold_verb_filtered)

    assert form in predicted_form

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing(gold_verb):
    analyzed_form = gold_verb['form']
    gold_verb['analyzed_form']=analyzed_form
    form = analyzed_form.replace('-', '')
    gold_verb['form']=form
    fv = gold_verb.pop('fv')

    predicted_parse = parse_inflected_verb(form, fv)
    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if any(k in parse for parse in predicted_parse)
    }
    assert gold_verb_filtered in predicted_parse
    
@pytest.mark.parametrize("inflected_paradigm", get_gold_paradigms())
def test_gold_paradigms(inflected_paradigm):
    root = inflected_paradigm['root']
    fv = inflected_paradigm['fv']

    predicted_paradigm = get_inflected_paradigm_for_verb(root, fv)
    assert predicted_paradigm == inflected_paradigm

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_forms(gold_adj):
    root = gold_adj.pop('root')
    form = gold_adj.pop('form')
    agree_class = gold_adj.pop('class')

    predicted_forms = inflect_adjective_with_features(root, agree_class)
    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_parsing(gold_adj):
    analyzed_form = gold_adj['form']
    gold_adj['analyzed_form']=analyzed_form
    form = analyzed_form.replace('-', '')
    gold_adj['form']=form

    predicted_parse = parse_adjective(form)[0]
    gold_adj_filtered = {
        k: v for k,v in gold_adj.items()
        if k in predicted_parse
    }
    assert predicted_parse == gold_adj_filtered

@pytest.mark.parametrize("uninflected_word", get_uninflected_word_data())
def test_uninflected_forms(uninflected_word):
    word = uninflected_word['word']
    pos = uninflected_word['part_of_speech']
    gloss = uninflected_word['gloss']

    parsed = parse_uninflected_word(word)[0]
    assert parsed['part_of_speech'] == pos
    assert parsed['gloss'] == gloss

@pytest.mark.parametrize("aux", get_gold_auxs())
def test_gold_auxs(aux):
    form = aux.pop('form')

    aux_filtered = {
        k: v for k,v in aux.items()
        if k in VERB_FEATURE_VALUES or k=='gloss'
    }
    predicted_forms = inflect_aux_with_features(features=aux_filtered)

    assert form in predicted_forms