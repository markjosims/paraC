from src.parser import get_main_parser, inflect_word, parse_word
from src.lexicon import *
from src.constants import EOS_STR, VERB_FEATURE_VALUES, LEXICAL_FEATURE_VALUES
from src.lexicon.phonology import FINAL_LOWERING_RULE, LEFT_H_RULE, EOS
from src.fst_helpers import get_lattice_strs, fst
import pytest
from tests.utils import filter_query_and_hits, get_different_items

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_inflection_wh(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form').replace('-', '')
    agree_class = gold_verb['class']

    if ' ' in form or agree_class == 'unmarked':
        return

    gold_verb["part_of_speech"]='verb'
    gold_verb['wh']='class'

    gold_verb['aux']= 'false'
    form+=f"{agree_class}ɛ́" 

    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }
    predicted_form = inflect_word(root, **gold_verb_filtered)

    assert form in predicted_form

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_inflection_loc(gold_verb):
    root = gold_verb.pop('root')
    form = gold_verb.pop('form').replace('-', '')
    gold_verb["part_of_speech"]='verb'
    gold_verb['wh']='locative'
    if ' ' in form or gold_verb['class']=='unmarked':
        return
    form+="l" 
    gold_verb['aux']= 'false'

    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }
    predicted_form = inflect_word(root, **gold_verb_filtered)

    assert form in predicted_form

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
    predicted_form = inflect_word(root, **gold_verb_filtered)

    assert form in predicted_form

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing(gold_verb):
    analyzed_form = gold_verb['form']
    gold_verb['analyzed_form']=analyzed_form
    form = analyzed_form.replace('-', '')
    gold_verb['form']=form
    gold_verb["part_of_speech"]='verb'
    gold_verb['aux']= str(' ' in form).lower()
    gold_verb['weight']=0.0
    for unused_feature in ['final_lowering', 'left_h', 'wh']:
        gold_verb[unused_feature] = 'unmarked'

    predicted_parse = parse_word(form)
    gold_verb_filtered = {
        k: v for k,v in gold_verb.items()
        if any(k in parse for parse in predicted_parse)
    }
    assert gold_verb_filtered in predicted_parse

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing_final_lowering(gold_verb):
    hyphenated_form = gold_verb['form']
    orig_form = gold_verb['form'].replace('-', '')
    fl_form = orig_form
    if ' ' in fl_form:
        aux, stem = fl_form.split(' ')
        stem_w_fl = get_lattice_strs(
            (fst(stem)+EOS) @ FINAL_LOWERING_RULE,
            strip_eos=False,
        )[0]
        fl_form = aux + ' ' + stem_w_fl
        gold_verb['aux']='true'
    else:
        fl_form = get_lattice_strs(
            (fst(fl_form)+EOS) @ FINAL_LOWERING_RULE,
            strip_eos=False,
        )[0]
        gold_verb['aux']='false'
    gold_verb['analyzed_form']=hyphenated_form
    gold_verb['form']=fl_form
    gold_verb["part_of_speech"]='verb'
    gold_verb['weight']=0.0
    gold_verb['final_lowering']='true'

    predicted_parse = parse_word(fl_form)
    gold_verb_filtered, predicted_parse_filtered = filter_query_and_hits(gold_verb, predicted_parse)

    if fl_form.removesuffix(EOS_STR) != orig_form:
        assert gold_verb_filtered in predicted_parse_filtered
    else:
        assert gold_verb_filtered not in predicted_parse_filtered

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing_lefth_and_final_lowering(gold_verb):
    hyphenated_form = gold_verb['form']
    orig_form = gold_verb['form'].replace('-', '')
    fl_form = orig_form
    if ' ' in fl_form:
        return
    fl_form = get_lattice_strs(
        (fst(fl_form)+EOS) @ FINAL_LOWERING_RULE @ LEFT_H_RULE,
        strip_eos=False,
    )[0]
    gold_verb['aux']='false'
    fl_form = fl_form
    gold_verb['analyzed_form']=hyphenated_form
    gold_verb['form']=fl_form
    gold_verb["part_of_speech"]='verb'
    gold_verb['weight']=0.0
    gold_verb['final_lowering']='true'
    gold_verb['left_h']='true'

    predicted_parse = parse_word(fl_form)
    gold_verb_filtered, predicted_parse_filtered = filter_query_and_hits(gold_verb, predicted_parse)

    if fl_form != orig_form:
        assert gold_verb_filtered in predicted_parse_filtered
    else:
        assert gold_verb_filtered not in predicted_parse_filtered

@pytest.mark.parametrize("gold_verb", get_gold_verbs())
def test_verb_parsing_lefth(gold_verb):
    hyphenated_form = gold_verb['form']
    orig_form = gold_verb['form'].replace('-', '')
    lefth_form = orig_form
    if ' ' in lefth_form:
        return
    lefth_form = get_lattice_strs(
        (fst(lefth_form)) @ LEFT_H_RULE,
    )[0]
    gold_verb['aux']='false'
    gold_verb['analyzed_form']=hyphenated_form
    gold_verb['form']=lefth_form
    gold_verb["part_of_speech"]='verb'
    gold_verb['weight']=0.0
    gold_verb['left_h']='true'

    predicted_parse = parse_word(lefth_form)
    gold_verb_filtered, predicted_parse_filtered = filter_query_and_hits(gold_verb, predicted_parse)

    if lefth_form != orig_form:
        assert gold_verb_filtered in predicted_parse_filtered
    else:
        assert gold_verb_filtered not in predicted_parse_filtered

@pytest.mark.parametrize("gold_verb", get_gold_derived_verbs())
def test_derived_verbs(gold_verb):
    form = gold_verb.pop('form').replace('-', '')
    root = gold_verb.pop('root').replace('-', '')
    gold_verb['fv']=gold_verb.pop('derived_fv')
    gold_verb["part_of_speech"]='verb'
    gold_verb['aux']= str(' ' in form).lower()

    verb_filtered = {
        k: v for k,v in gold_verb.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }

    predicted_forms = inflect_word(
        root=root,
        **verb_filtered,
    )

    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_forms(gold_adj):
    root = gold_adj.pop('root')
    form = gold_adj.pop('form')
    form = form.replace('-', '')
    gold_adj["part_of_speech"]='adjective'

    predicted_forms = inflect_word(root, **gold_adj)
    assert form in predicted_forms

@pytest.mark.parametrize("gold_adj", get_gold_adjectives())
def test_adjective_parsing(gold_adj):
    analyzed_form = gold_adj['form']
    gold_adj['analyzed_form']=analyzed_form
    gold_adj["part_of_speech"]='adjective'
    form = analyzed_form.replace('-', '')
    gold_adj['form']=form
    gold_adj['weight']=0.0
    for unused_feature in ['final_lowering', 'left_h', 'aux', 'fv']:
        gold_adj[unused_feature] = 'unmarked'

    predicted_parses = parse_word(form)
    gold_adj_filtered = {
        k: v for k,v in gold_adj.items()
        if k in predicted_parses[0]
    }
    assert gold_adj_filtered in predicted_parses

@pytest.mark.parametrize("gold_word", get_uninflected_word_data())
def test_uninflected_forms(gold_word):

    root = gold_word['root']
    form = root.split('(')[0]
    gold_word['analyzed_form']=root
    gold_word['root']=root
    gold_word['weight']=0.0

    parses = parse_word(form)
    gold_word_filtered = {
        k: v for k,v in gold_word.items()
        if k in parses[0]
    }
    parses_filtered = []
    for parse in parses:
        parse_filtered = {
            k: v for k,v in parse.items()
            if k in gold_word_filtered
        }
        parses_filtered.append(parse_filtered)
    assert gold_word_filtered in parses_filtered

@pytest.mark.parametrize("gold_aux", get_gold_auxs())
def test_gold_auxs(gold_aux):
    form = gold_aux.pop('form').replace('-', '')
    gold_aux['part_of_speech']='aux'

    aux_filtered = {
        k: v for k,v in gold_aux.items()
        if (k in VERB_FEATURE_VALUES or k in LEXICAL_FEATURE_VALUES)
    }
    aux_root = 'ŋgá'
    predicted_forms = inflect_word(aux_root, **aux_filtered)

    assert form in predicted_forms