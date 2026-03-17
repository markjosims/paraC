import pynini
from pynini.lib import paradigms
from typing import Optional
from dataclasses import dataclass, field
from src.registry_utils import ReservedSymbolMixin

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

@dataclass
class Prefix(Transducer):
    """
    Wraps the `Transducer` class but requires that a string be
    passed to the `value` field where the first character is a
    boundary symbol ('-' or '=')
    """
    stem: Acceptor = field(default_factory=Acceptor)

    def __post_init__(self):
        super().__post_init__()

        if (
            (not self.value) or
            (self.value[0] not in ReservedSymbolMixin.boundary_symbols)
        ):
            raise ValueError(
                "Prefixes require the `value` attribute to be specified " +\
                "with a string that begins with a boundary symbol " +\
                str(ReservedSymbolMixin.boundary_symbols) +\
                f"but got {self.value}"
            )
        
    def set_transducer(self, fsa: pynini.Fst, stem: Optional[pynini.Fst]=None):
        fst = paradigms.prefix(fsa, stem)
        return super().set_transducer(fst)
        
class Suffix(Transducer):
    """
    Wraps the `Transducer` class but requires that a string be
    passed to the `value` field where the last character is a
    boundary symbol ('-' or '=')
    """
    def __post_init__(self):
        super().__post_init__()

        if (
            (not self.value) or
            (self.value[-1] not in ReservedSymbolMixin.boundary_symbols)
        ):
            raise ValueError(
                "Suffixes require the `value` attribute to be specified " +\
                "with a string that ends with a boundary symbol " +\
                str(ReservedSymbolMixin.boundary_symbols) +\
                f"but got {self.value}"
            )
        
    def set_transducer(self, fsa: pynini.Fst, stem: Optional[pynini.Fst]=None):
        fst = paradigms.suffix(fsa, stem)
        return super().set_transducer(fst)