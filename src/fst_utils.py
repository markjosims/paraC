import pynini
from dataclasses import dataclass, field
from loguru import logger


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
        + (pipe_operator, caret_operator)
        + reserved_refs
        + bow_eow_flags
        + edit_flags
        + boundary_symbols
        + (word_edge,)
    )


def is_acceptor(fsa: pynini.Fst) -> bool:
    if not isinstance(fsa, pynini.Fst):
        raise ValueError(f"Expected pynini.Fst but got {fsa} for fsa arg.")
    return fsa.properties(pynini.ACCEPTOR, True)


@dataclass
class Acceptor:
    """
    Wrapper for FSAs with an optional string representation.
    """

    value: str | None = None
    fsa: pynini.Fst | None = None

    def __post_init__(self):
        self.acceptor_built = False

        if self.value is not None and type(self.value) is not str:
            raise ValueError(
                f"Value must be a string or None, but got {self.value} of type {type(self.value)}"
            )

        if self.fsa is not None:
            raise ValueError(
                "Acceptor should not be passed on init but instead set with the "
                "`Acceptor.set_acceptor` method, usually called by an "
                "`FstRegistry` object."
            )

    def set_acceptor(self, fsa: pynini.Fst):
        if self.acceptor_built:
            logger.info("Acceptor already built, skipping set_acceptor.")
            return
        if not is_acceptor(fsa):
            raise ValueError("Must be an acceptor FST")
        self.fsa = fsa
        self.acceptor_built = True


@dataclass
class Transducer:
    """
    Wrapper for FSTs with an optional string representation.
    """

    value: str | None = None
    fst: pynini.Fst | None = None

    def __post_init__(self):
        self.transducer_built = False

        if self.fst is not None:
            raise ValueError(
                "Transducer should not be passed on init but instead set with the "
                "`Transducer.set_transducer` method, usually called by an "
                "`FstRegistry` object."
            )

    def set_transducer(self, fst: pynini.Fst):
        if self.transducer_built:
            raise ValueError(f"Transducer (value={self.value}) cannot be overridden.")
        if is_acceptor(fst):
            logger.warning(f"Transducer (value={self.value}) is a vacuous FST")
        self.fst = fst
        self.transducer_built = True


class TransducerList(Transducer):
    """
    Wrapper for FSTs allowing for the actual FST object to
    be a list of FSTs, to be applied in sequence.
    """

    fst: pynini.Fst | list[pynini.Fst] | None = None

    def set_transducer(self, fst: pynini.Fst | list[pynini.Fst]):
        if self.fst is not None:
            raise ValueError(f"Transducer (value={self.value}) cannot be overridden.")

        if isinstance(fst, list):
            for f in fst:
                if is_acceptor(f):
                    logger.warning(
                        f"Transducer (value={self.value}) contains a vacuous FST"
                    )
        elif isinstance(fst, pynini.Fst):
            if is_acceptor(fst):
                logger.warning(f"Transducer (value={self.value}) is a vacuous FST")

        self.fst = fst
        self.transducer_built = True


@dataclass
class Prefix(Transducer):
    """
    Wraps the `Transducer` class but requires that a string be
    passed to the `value` field where the first character is a
    boundary symbol ('-' or '=')
    """

    stem: pynini.Fst = field(default_factory=pynini.Fst)

    def __post_init__(self):
        super().__post_init__()

        if not self.value:
            logger.warning("Prefix with no value.")
        elif not any(
            self.value.strip("()").endswith(boundary)
            for boundary in ReservedSymbolMixin.boundary_symbols
        ):
            logger.warning(f"Prefix with no boundary symbol at end: {self.value}")

    def set_transducer(
        self,
        prefix_fsa: pynini.Fst,
        bow_fsa: pynini.Fst,
        stem: pynini.Fst | None = None,
        left_context: Acceptor | None = None,
    ):
        if stem is None:
            stem = self.stem

        # need to write a context-dependent rewrite function rather
        # than using paradigms.prefix because we use a special [BOW]
        # symbol to mark the beginning of the word

        fst = pynini.cdrewrite(
            tau=pynini.cross(bow_fsa, bow_fsa + prefix_fsa),
            l=left_context or "",
            r="",
            sigma_star=stem,
        )

        return super().set_transducer(fst)


@dataclass
class Suffix(Transducer):
    """
    Wraps the `Transducer` class but requires that a string be
    passed to the `value` field where the last character is a
    boundary symbol ('-' or '=')
    """

    stem: pynini.Fst = field(default_factory=pynini.Fst)

    def __post_init__(self):
        super().__post_init__()

        if not self.value:
            logger.warning("Suffix with no value.")
        elif not any(
            self.value.strip("()").startswith(boundary)
            for boundary in ReservedSymbolMixin.boundary_symbols
        ):
            logger.warning(f"Suffix with no boundary symbol at beginning: {self.value}")

    def set_transducer(
        self,
        suffix_fsa: pynini.Fst,
        eow_fsa: pynini.Fst,
        stem: pynini.Fst | None = None,
        left_context: Acceptor | None = None,
    ):
        if stem is None:
            stem = self.stem

        # need to write a context-dependent rewrite function rather
        # than using paradigms.prefix because we use a special [EOW]
        # symbol to mark the end of the word
        fst = pynini.cdrewrite(
            tau=pynini.cross(eow_fsa, suffix_fsa + eow_fsa),
            l=left_context or "",
            r="",
            sigma_star=stem,
        )
        return super().set_transducer(fst)


FsaLike = str | pynini.Fst | Acceptor
