import yaml
from src.constants import EOS_STR, AUX_LEMMA_STR
from src.fst_helpers import EOS_STR, Any, Dict, List, get_gloss_str_from_dict, pynini
from src.parser import get_main_parser
from src.search import search_word
from argparse import ArgumentParser
from tqdm import tqdm
from typing import Optional
import os


from typing import Any, Dict, List


def get_annotation_markup_for_sentence(
        sentence: str,
        translation: Optional[str] = None,
        split: Optional[str] = None,
        index: Optional[int] = None,
        num_hits: int = 10,
        main_lemmatizer: Optional[pynini.Fst]=None,
        main_analyzer: Optional[pynini.Fst]=None,
) -> List[Dict[str, Any]]:
    """
    Given an unparsed sentence, generates hypothetical parses
    for each word and returns in a structured format for annotation,
    conforming to this schema:
    {
        'sentence': str,
        'words': [
            {
                'original_str': str,
                'updated_str': str,
                'updated_gloss': str,
                'parses': [
                    (
                        predicted_form,
                        predicted_form_segmented,
                        predicted_root,
                        predicted_gloss,
                        weight
                    ),
                    ...
                ]
            },
            ...
        ]
    }

    Arguments:
        sentence: str of space-separated words to search and annotate
        translation: optional str of translated sentence
        num_hits:  int, number of hits to return per word
        main_lemmatizer: FST of main lemmatizer
        main_analyzer: FST of main analyzer
    Returns:
        annotated_parses:  list of dicts representing annotated parses for each word
    """
    markup_dict = {
        'sentence': sentence.removesuffix(EOS_STR),
        'updated_sentence': '',
        'translation': translation,
        'split': split,
        'index': index,
        'checked_by_pi': False,
    }

    if main_lemmatizer is None or main_analyzer is None:
        main_lemmatizer, main_analyzer, _ = get_main_parser()

    words = sentence.split(' ')
    parsed_words = []
    for word in words:
        word_obj = {
            'original_str': word.removesuffix(EOS_STR),
            'updated_str': '',
            'updated_gloss': '',
            'chosen_parse': None,
            'comment': '',
            'parses': {},
        }
        hits = search_word(
            word,
            main_lemmatizer=main_lemmatizer,
            main_analyzer=main_analyzer,
            num_hits=num_hits,
        )
        for i, hit in enumerate(hits):
            word_obj['parses'][i]=get_parse_list_from_dict(hit)
        parsed_words.append(word_obj)
    markup_dict['words'] = parsed_words

    return markup_dict

def get_parse_list_from_dict(
        parse_dict: Dict[str, Any],
) -> List[Any]:
    """
    Converts a parse dict returned by search_word into a list format.

    Arguments:
        parse_dict: dict representing a parse
    Returns:
        parse_list: list representing the same parse
    """
    gloss_str = get_gloss_str_from_dict(parse_dict)
    predicted_form = parse_dict['form']
    predicted_form_segmented = parse_dict['analyzed_form']
    root = parse_dict['root']
    weight = parse_dict['weight']

    if ' ' in predicted_form:
        # space in predicted form indicates verb with auxiliary
        # format root and gloss to reflect AUX presence

        # sanity check: make sure AUX is marked in gloss
        # then change gloss str from shape 'root-FEATURE-FEATURE-aux'
        # to 'aux root-FEATURE-FEATURE'
        assert 'aux' in gloss_str
        gloss_str = gloss_str.replace('-aux', '').strip()
        gloss_str = 'aux '+gloss_str

        # similarly, adjust root to reflect AUX presence
        root = AUX_LEMMA_STR + ' ' + root

    parse_list = [
        predicted_form,
        predicted_form_segmented,
        root,
        gloss_str,
        round(weight, 2),
    ]
    return parse_list

def rewrite_sentence(
        sentence: str,
        main_lemmatizer: Optional[pynini.Fst]=None,
        main_analyzer: Optional[pynini.Fst]=None,
) -> str:
    """
    Arguments:
        sentence:   str of space-separated words to rewrite
    Returns:
        rewritten_sentence:  str of space-separated rewritten words
    """
    if main_lemmatizer is None or main_analyzer is None:
        main_lemmatizer, main_analyzer, _ = get_main_parser()


    words = sentence.split(' ')
    rewritten_words = []
    for word in words:
        hits = search_word(word, num_hits=1, main_lemmatizer=main_lemmatizer, main_analyzer=main_analyzer)
        if hits:
            best_hit = hits[0]['form']
            rewritten_words.append(best_hit)
        else:
            rewritten_words.append(word)
    rewritten_sentence = ' '.join(rewritten_words)
    return rewritten_sentence

if __name__ == '__main__':
    # when loaded as script, ingress sentences from a text file
    # and output .yaml file with annotation markup
    parser = ArgumentParser(
        description="Predicts parses for words in a text file using fuzzy search."
    )
    parser.add_argument('--input', '-i', help="Input text file")
    parser.add_argument('--output', '-o', help="Output .yaml file for annotation markup")
    parser.add_argument('--num_hits', '-n', default=10)
    parser.add_argument('--split', '-s', choices=['train', 'validation', 'test', 'all'], default='all')

    args = parser.parse_args()
    if getattr(args, 'output', None) is None:
        args.output = os.path.splitext(args.input)[0]+'.yaml'

    with open(args.input, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()

    main_lemmatizer, main_analyzer, _ = get_main_parser()
    all_markup = []

    if args.split != 'all':
        # filter lines by split
        split_index = 2  # assuming CSV format: sentence,translation,split,index
        lines = [line for line in lines if line.strip().split(',')[split_index] == args.split]


    for line in tqdm(lines):
        parts = line.strip().split(',')
        # pad line with None if data are missing
        while len(parts)<4:
            parts.append(None)
        sentence, translation, split, index = parts
        sentence = sentence.strip()
        # don't add EOS_STR since we're not parsing final lowering for now
        # sentence += EOS_STR
        if not sentence:
            continue
        markup = get_annotation_markup_for_sentence(
            sentence,
            translation,
            split,
            index,
            num_hits=int(args.num_hits),
            main_lemmatizer=main_lemmatizer,
            main_analyzer=main_analyzer,
        )
        all_markup.append(markup)

    with open(args.output, 'w', encoding='utf-8') as outfile:
        yaml.dump(all_markup, outfile, allow_unicode=True, sort_keys=False)
