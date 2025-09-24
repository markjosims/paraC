import pytest
from src.forms import *
from src.lexicon import get_all_verb_roots_and_fvs, get_all_gold_forms

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

@pytest.mark.parametrize("gold_verb", get_all_gold_forms())
def test_gold_features2forms(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form')
    fv = gold_verb.pop('fv')

    predicted_form = inflect_verb_with_features(root, fv, features=gold_verb)
    assert form == predicted_form

@pytest.mark.parametrize("gold_verb", get_all_gold_forms())
def test_gold_forms2features(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form')
    form = form.replace('-', '')
    fv = gold_verb.pop('fv')

    predicted_parse = parse_inflected_verb(form, fv)
    assert root == predicted_parse.pop('root')
    assert predicted_parse == gold_verb
    