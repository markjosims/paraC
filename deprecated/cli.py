from src.parser import parse_word, inflect_word
from src.search import search_word, search_corpus, search_parse_csv
from src.lexicon import get_gloss_for_root, get_root_for_gloss
from src.fst_helpers import get_gloss_str_from_dict
from functools import wraps

import os
import fire

verbose=os.environ.get('verbose', False)

def parse_printer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return [
            get_gloss_str_from_dict(entry, include_form=True, verbose=False)
            for entry in result
        ]
    return wrapper

def print_list_as_markdown_table(dict_list):
    if not dict_list:
        print("No results found.")
        return
    # Extract keys for header
    columns = dict_list[0].keys()

    # Print header
    print(f"| {' | '.join(columns)} |")
    print("|------| ------------|-------|")
    for d in dict_list:
        row_data = [str(value) for value in d.values()]
        print(f"| {' | '.join(row_data)} |")

def search_printer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        print_list_as_markdown_table(result)
    return wrapper

def main():
    fire.Fire({
        'parse_word': parse_printer(parse_word),
        'inflect_word': inflect_word,
        'search_word': parse_printer(search_word),
        'get_gloss_for_root': get_gloss_for_root,
        'get_root_for_gloss': get_root_for_gloss,
        'search_corpus': search_printer(search_corpus),
        'search_parse_csv': search_printer(search_parse_csv),
    })

if __name__ == "__main__":
    main()