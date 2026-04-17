from pynini.lib import edit_transducer

"""
Constants related to fuzzy string search operations,
including arc costs for each edit operation, and the
default edit distance bound (i.e. maximum allowed edit
distance).

For edit costs, use default values from pynini.lib.edit_transducer
(set to 1 for each edit).
"""

DEFAULT_INSERT_COST = edit_transducer.DEFAULT_INSERT_COST
DEFAULT_SUBSTITUTE_COST = edit_transducer.DEFAULT_SUBSTITUTE_COST
DEFAULT_DELETE_COST = edit_transducer.DEFAULT_DELETE_COST
DEFAULT_EDIT_BOUND = 5