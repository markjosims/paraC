import pynini
from typing import Optional, Union, List
from dataclasses import dataclass, field
from src.registry.registry_utils import ReservedSymbolMixin

def is_acceptor(fsa: pynini.Fst) -> bool:
    return fsa.properties(pynini.ACCEPTOR, True)

@dataclass
class Acceptor:
    """
    Wrapper for FSAs with an optional string representation.
    """
    value: Optional[str] = None
    fsa: Optional[pynini.Fst] = None

    def __post_init__(self):
        self.acceptor_built = False

        if self.fsa is not None:
            raise ValueError(
                "Acceptor should not be passed on init but instead set with the "
                "`Acceptor.set_acceptor` method, usually called by an "
                "`FstRegistry` object."
            )

    def set_acceptor(self, fsa: pynini.Fst):
        if self.acceptor_built:
            raise ValueError("Acceptor cannot be overridden.")
        if not is_acceptor(fsa):
            raise ValueError("Must be an acceptor FST")
        self.fsa = fsa
        self.acceptor_built = True

@dataclass
class Transducer:
    """
    Wrapper for FSTs with an optional string representation.
    """
    value: Optional[str] = None
    fst: Optional[pynini.Fst] = None

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
            raise ValueError("Transducer cannot be overridden.")
        if is_acceptor(fst):
            raise ValueError("Must be a non-vacuous FST")
        self.fst = fst
        self.transducer_built = True

class TransducerList(Transducer):
    """
    Wrapper for FSTs allowing for the actual FST object to
    be a list of FSTs, to be applied in sequence.
    """

    fst: Union[pynini.Fst, List[pynini.Fst], None] = None

    def set_transducer(self, fst: Union[pynini.Fst, List[pynini.Fst]]):
        if self.fst is not None:
            raise ValueError("Transducer cannot be overridden.")
        
        if isinstance(fst, list):
            for f in fst:
                if is_acceptor(f):
                    raise ValueError("Transducer must be a non-vacuous FST or list of non-vacuous FSTs")
        elif isinstance(fst, pynini.Fst):
            if is_acceptor(fst):
                raise ValueError("Transducer must be a non-vacuous FST or list of non-vacuous FSTs")
        
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

        if (
            (not self.value) or
            (self.value.strip("()")[-1] not in ReservedSymbolMixin.boundary_symbols)
        ):
            raise ValueError(
                "Prefixes require the `value` attribute to be specified " +\
                "with a string that ends with a boundary symbol " +\
                str(ReservedSymbolMixin.boundary_symbols) +\
                f"but got {self.value}"
            )
        
    def set_transducer(
            self,
            prefix_fsa: pynini.Fst,
            bow_fsa: pynini.Fst,
            stem: Optional[pynini.Fst]=None
        ):
        if stem is None:
            stem = self.stem

        # need to write a context-dependent rewrite function rather
        # than using paradigms.prefix because we use a special [BOW]
        # symbol to mark the beginning of the word
        fst = pynini.cdrewrite(
            tau=pynini.cross(bow_fsa, bow_fsa+prefix_fsa),
            l='',
            r='',
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

        if (
            (not self.value) or
            (self.value.strip("()")[0] not in ReservedSymbolMixin.boundary_symbols)
        ):
            raise ValueError(
                "Suffixes require the `value` attribute to be specified " +\
                "with a string that begins with a boundary symbol " +\
                str(ReservedSymbolMixin.boundary_symbols) +\
                f"but got {self.value}"
            )
        
    def set_transducer(
            self,
            suffix_fsa: pynini.Fst,
            eow_fsa: pynini.Fst,
            stem: Optional[pynini.Fst]=None
        ):
        if stem is None:
            stem = self.stem

        # need to write a context-dependent rewrite function rather
        # than using paradigms.prefix because we use a special [EOW]
        # symbol to mark the end of the word
        fst = pynini.cdrewrite(
            tau=pynini.cross(eow_fsa, suffix_fsa+eow_fsa),
            l='',
            r='',
            sigma_star=stem,
        )
        return super().set_transducer(fst)