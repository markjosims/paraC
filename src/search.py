import pynini
from pynini.lib.edit_transducer import DEFAULT_INSERT_COST, DEFAULT_SUBSTITUTE_COST, DEFAULT_DELETE_COST

def get_searchable_lexicon(lexicon, edits, insert_cost=DEFAULT_INSERT_COST, sub_cost=DEFAULT_SUBSTITUTE_COST, delete_cost=DEFAULT_DELETE_COST):
    ...

def get_edit_factors(edits, insert_cost=DEFAULT_INSERT_COST, sub_cost=DEFAULT_SUBSTITUTE_COST, delete_cost=DEFAULT_DELETE_COST):
    ...

def get_matches(query, left_factor, lexicon):
    ...