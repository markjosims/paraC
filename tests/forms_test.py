import pytest
from src.verb_forms import *
from src.lexicon import get_all_verb_roots_and_fvs, get_all_gold_forms, get_gold_paradigms
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

@pytest.mark.parametrize("gold_verb", get_all_gold_forms())
def test_gold_features2forms(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form')
    fv = gold_verb.pop('fv')

    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if k in VERB_FEATURE_VALUES or k=='gloss'
    }
    predicted_form = inflect_verb_with_features(root, fv, features=gold_verb_filtered)

    assert form == predicted_form

@pytest.mark.parametrize("gold_verb", get_all_gold_forms())
def test_gold_forms2features(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form')
    form = form.replace('-', '')
    fv = gold_verb.pop('fv')
    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if k in VERB_FEATURE_VALUES or k=='gloss'
    }

    predicted_parse = parse_inflected_verb(form, fv)
    assert root == predicted_parse.pop('root')
    assert predicted_parse == gold_verb_filtered
    
@pytest.mark.parametrize("inflected_paradigm", get_gold_paradigms())
def test_gold_paradigms(inflected_paradigm):
    root = inflected_paradigm['root']
    fv = inflected_paradigm['fv']

    predicted_paradigm = get_inflected_paradigm_for_verb(root, fv)
    assert predicted_paradigm == inflected_paradigm