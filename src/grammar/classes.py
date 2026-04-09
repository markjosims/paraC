"""
Defines two principal classes: `Registry` and `Orchestrator`.
`Registry` stores all the data associated with a particular type
of YAML config. `Orchestrator` sits over `Registry` and manages
all configs for a particular area of the grammar.

Grammars is initialized in two primary stages: reading and loading.
'Reading' refers to reading YAML files into Python dictionaries, but
not interpreting or acting on the data in any way. The `ConfigWalker` class
handles all reading logic, and passes YAML data to the `Grammar` class
(the orchestrator of orchestrators), which passes data onto child Orchestrator
classes, which in turn pass data onto child Registries.

The 'loading' phase is where YAML data is interpreted into actionable logic,
e.g. the phones from an inventory config are built into FSTs.
'loading' is shared between orchestrators and registries, and the steps involved
differ greatly based on the area of grammar concerned.
"""

from src.config_utils.schema_validation import load_schema

class Orchestrator:
    """
    `Orchestrator` class resides over a group of `Registry` classes.
    At present there is no shard logic among orchestrators, but we
    still implement a dummy parent class for organizational purposes.
    """
    def __init__(self):
        pass


class Registry:
    def __init__(
        self,
        kind: str,
        data: dict | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.kind = kind
        self.schema = load_schema(kind)

        if data is None and config_objects is None:
            self.data = {}
            self.config_objects = {}
        elif data is not None and config_objects is None:
            self.data = data
            self.config_objects = {}
        elif data is None and config_objects is not None:
            self.config_objects = config_objects
            self.data = self.load_all_configs()
        else:
            raise ValueError("Cannot specify both data and config_objects")

    def load_all_configs(self) -> dict:
        raise NotImplementedError(
            "Must be implemented by subclass to load and merge all configs in config_objects."
        )

    def load_data_from_config(self, config: dict) -> dict:
        raise NotImplementedError(
            "Must be implemented by subclass to load data from a single config dict."
        )


class ReservedSymbolMixin:
    """
    Mixin class for registries to define reserved symbols that cannot be used as
    inventory item values. This is to prevent collisions between user-defined
    inventory items and special symbols used in pattern/rule contexts.
    """

    bow = "[BOW]"
    eow = "[EOW]"
    insert = "[INSERT]"
    substitute = "[SUBSTITUTE]"
    delete = "[DELETE]"

    word_edge = "#"
    phone_ref = "<Phone>"
    flag_ref = "<Flag>"
    sigma_ref = "<Sigma>"
    dot = "."
    epsilon_ref = "<Empty>"
    boundary_ref = "<Boundary>"

    affix_boundary = "-"
    clitic_boundary = "="
    periphrasis_break = "_"

    star = "*"
    plus = "+"
    optional = "?"
    union = "|"
    caret = "^"
    left_paren = "("
    right_paren = ")"
    # curly braces indicate union of tokens, e.g. {A B} matches either A or B
    # similar to square brackets in regex
    left_brace = "{"
    right_brace = "}"

    left_delimiters = (left_paren, left_brace)
    right_delimiters = (right_paren, right_brace)
    unary_operators = (star, plus, optional)
    pipe_operator = union  # (for now) pipe operator is only binary operator
    caret_operator = caret  # for negation in braced expressions
    reserved_refs = (phone_ref, flag_ref, epsilon_ref, dot, sigma_ref, boundary_ref)
    bow_eow_flags = (bow, eow)
    edit_flags = (insert, substitute, delete)
    boundary_symbols = (affix_boundary, clitic_boundary, periphrasis_break)

    reserved_symbols = (
        left_delimiters
        + right_delimiters
        + unary_operators
        + (pipe_operator,)
        + reserved_refs
        + bow_eow_flags
        + boundary_symbols
    )
