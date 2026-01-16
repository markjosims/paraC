import yaml
from src.constants import EOS_STR
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
        'update_sentence': '',
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
            gloss_str = get_gloss_str_from_dict(hit)
            predicted_form = hit['form']
            predicted_form_segmented = hit['analyzed_form']
            weight = hit['weight']
            word_obj['parses'][i]=[
                predicted_form,
                predicted_form_segmented,
                gloss_str,
                round(weight, 2),
            ]
        parsed_words.append(word_obj)
    markup_dict['words'] = parsed_words

    return markup_dict


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
        sentence, translation, split, index = line.strip().split(',')
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