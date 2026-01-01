from src.parser import parse_word, inflect_word
from src.search import search_word
from src.lexicon import get_gloss_for_root, get_root_for_gloss
from src.fst_helpers import get_gloss_str_from_dict
from functools import wraps

import os
import fire

verbose=os.env.get('verbose', False)

def parse_printer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return [
            get_gloss_str_from_dict(entry, include_form=True, verbose=False)
            for entry in result
        ]
    return wrapper

if __name__ == "__main__":
    fire.Fire({
        'parse_word': parse_printer(parse_word),
        'inflect_word': inflect_word,
        'search_word': parse_printer(search_word),
        'get_gloss_for_root': get_gloss_for_root,
        'get_root_for_gloss': get_root_for_gloss,
    })