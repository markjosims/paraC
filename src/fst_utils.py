import pynini
from typing import Optional
from dataclasses import dataclass


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
        if not fsa.properties(pynini.ACCEPTOR, True):
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
        if fst.properties(pynini.ACCEPTOR, True):
            raise ValueError("Must be a non-vacuous FST")
        self.fst = fst
        self.transducer_built = True