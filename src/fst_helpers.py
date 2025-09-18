import pynini
from pynini.lib import pynutil, rewrite
from src.constants import *
from typing import *
import pydot

# symbol table wrappers

def set_symbols(fst: pynini.Fst) -> pynini.Fst:
    """
    Set input and output symbols to `TIRA_SYMBOL_TABLE`.
    """
    fst.set_input_symbols(TIRA_SYMBOL_TABLE)
    fst.set_output_symbols(TIRA_SYMBOL_TABLE)
    return fst

def tone2diac(tone_str: str) -> str:
    """
    Replace all tone symbols with combining diacritics,
    i.e. \<H> --> \u0301
    """
    for tone_symbol, tone_diac in SYMBOL2DIAC.items():
        tone_str = tone_str.replace(tone_symbol, tone_diac)
    return tone_str

def tone2symbol(tone_str: str) -> str:
    """
    Replace all tone combining diacritics with symbols,
    i.e. \u0301 --> \<H>
    """
    for tone_diac, tone_symbol in DIAC2SYMBOL.items():
        tone_str = tone_str.replace(tone_diac, tone_symbol)
    return tone_str

def collapse_multichar_tokens(encoded_string: str) -> str:
    """
    For all multicharacter tokens in `MULTICHAR_TOKENS`
    remove spaces added during encoding, i.e.
    < d e l e t e > --> \<delete>.
    """
    for token in MULTICHAR_TOKENS:
        expanded_token = ' '.join(token)
        encoded_string = encoded_string.replace(expanded_token, token)
    return encoded_string

def encode_fst_string(input_string: Union[str, Sequence[str]]) -> Union[str, List[str]]:
    """
    Replace all word boundaries with the `WORD_BOUNDARY_STR` symbol (default "|"),
    separates all characters with spaces, and replaces tone diacritics with
    dedicated symbols.
    """
    if type(input_string) is not str:
        return [encode_fst_string(input_element) for input_element in input_string]
    str_w_word_boundaries = input_string.replace(' ', WORD_BOUNDARY_STR)
    tokenized_str = " ".join(str_w_word_boundaries)
    str_w_tone_symbols = tone2symbol(tokenized_str)
    str_w_collapsed_dentals = collapse_multichar_tokens(str_w_tone_symbols)
    return str_w_collapsed_dentals

def decode_fst_string(
        input_string: Union[str, Sequence[str], pynini.Fst],
    ) -> Union[str, List[str]]:
    """
    Condense all separated characters, replaces `WORD_BOUNDARY_STR` symbol (default "|")
    with a space, and changes tone symbols back to diacritics.
    If `input_string` is an FST, call `Fst.string()` first.
    """
    if type(input_string) is pynini.Fst:
        input_string = input_string.string(token_type=TIRA_SYMBOL_TABLE)
    elif type(input_string) is not str:
        return [decode_fst_string(input_element) for input_element in input_string]
    detokenized_str = input_string.replace(' ', '')
    str_w_word_spaces = detokenized_str.replace(WORD_BOUNDARY_STR, ' ')
    str_w_tone_diacs = tone2diac(str_w_word_spaces)
    return str_w_tone_diacs

def fst(
        fst_input: Union[str, Sequence[str], pynini.Fst, None]=None,
        fst_output: Union[str, Sequence[str], pynini.Fst, None] = None,
        weight: pynini.WeightLike = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  (Optional) string or list of strings to be accepted by the FST (or an FSA)
        fst_output: (Optional) string or list of strings to be output by the FST (or an FSA)
        weight:     (Optional) weight value for FST
    Returns:
        f:          Finite State Transducer
    
    FST factory used to automatically set `TIRA_SYMBOL_TABLE`.
    Input and output may be string or list of strings. If only input is passed,
    returns an FSA over the input string or unin of strings. If output is passed,
    return an FST transducing input to output.
    
    For both input and output, if an FST is passed the only modification done is adding
    the specified weight. All FSTs passed to this function must have their symbol table
    set already.

    If input is null, return an FST accepting epsilon (useful for defining unconditioned rules).
    """
    if type(fst_input) is str:
        f = pynini.accep(encode_fst_string(fst_input), token_type=TIRA_SYMBOL_TABLE, weight=weight)
    elif fst_input is None:
        return fst(fst_input='', fst_output=fst_output, weight=weight)
    elif type(fst_input) is pynini.Fst:
        f = fst_input + fst('', weight=weight)
    else:
        f = pynini.union(*[fst(fst_element, weight=weight) for fst_element in fst_input])
    
    if fst_output is None:
        # no output, just return acceptor
        f = set_symbols(f)
        f.optimize()
        return f
    
    # create acceptor for output
    output_fsa = fst(fst_input=fst_output, fst_output=None)
    f = pynini.cross(f, output_fsa)
    f = set_symbols(f)
    f.optimize()
    return f

def insert_fst(
        fst_output: Union[str, Sequence[str]],
        weight: Optional[pynini.WeightLike] = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_output:  String or list of strings to be output by the FST
        weight:     (Optional) weight value for FST
    Returns:
        f:          FST mapping <eps> to the output string(s)
    
    Wraps `pynutil.insert`, calling `fst` factory on output.
    """
    output_fsa = fst(fst_input=fst_output, weight=weight)
    f = pynutil.insert(output_fsa)
    f = set_symbols(f)
    return f

def delete_fst(
        fst_input: Union[str, Sequence[str]],
        weight: Optional[pynini.WeightLike] = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  String or list of strings to be accepted by the FST
        weight:     (Optional) weight value for FST
    Returns:
        f:          FST mapping the input string(s) to <eps>
    
    Wraps `pynutil.delete`, calling `fst` factory on input.
    """
    input_fsa = fst(fst_input=fst_input, weight=weight)
    f = pynutil.delete(input_fsa)
    f = set_symbols(f)
    return f

def get_decoded_strings(
        lattice: pynini.Fst,
        project_type: Literal['input', 'output']='output',
        unique_only: bool=True,
        nshortest: Optional[int]=None,
    ) -> List[str]:
    """
    Wraps `rewrite.lattice_to_strings`. Sets `TIRA_SYMBOL_TABLE`
    and calls `decode_fst_string` on output. If `nshortest` is passed,
    call `rewrite.lattice_to_nshortest` first.
    """
    lattice = pynini.project(lattice, project_type=project_type)
    if nshortest is not None:
        lattice = rewrite.lattice_to_nshortest(lattice, nshortest=nshortest)
    tokenized_strings =  rewrite.lattice_to_strings(lattice, token_type=TIRA_SYMBOL_TABLE)
    decoded_strings = decode_fst_string(tokenized_strings)
    if unique_only:
        return list(set(decoded_strings))
    return decoded_strings

def decode_byte_str(byte_str: str) -> str:
    """
    Arguments:
        byte_str:       String of encoded Tira symbol indices
    Returns:
        decoded_string: `byte_str` decoded using TIRA_SYMBOL_TABLE
    
    Decodes a string the byte value of each character is the index of
    a symbol in TIRA_SYMBOL_TABLE. This occurs when an FST with the
    symbol table set is combined with an FST using byte tokens, as is the
    case when using FST graphs generated by the `paradigms` module of Pynini.
    """
    byte_values = [ord(char) for char in byte_str]
    symbols = [TIRA_SYMBOL_TABLE.find(i) for i in byte_values]
    symbol_str = ' '.join(symbols)
    decoded_string = decode_fst_string(symbol_str)
    return decoded_string

def draw_svg(fst: pynini.Fst, filepath: str = 'tmp/tmp.svg', title: Optional[str]=None):
    """
    Saves .dot and .svg representations of `fst`, with an optionally specified `title`
    (defaults to `filepath`).
    """
    stem = os.path.splitext(filepath)[0]
    fst = set_symbols(fst)
    dotfile = stem+'.dot'
    fst.draw(
        source=dotfile,
        show_weight_one=True,
        isymbols=fst.input_symbols(),
        osymbols=fst.output_symbols(),
        portrait=True,
        title=title or stem,
    )
    graph = pydot.graph_from_dot_file(dotfile)[0]
    graph.write_svg(filepath)

def get_min_path_weight(f: pynini.Fst) -> float:
    """
    Arguments:
        f:  FST to calculate path weight for
    Returns:
        path_weight: float indicating weight of shortest path.
    """
    f_shortest = pynini.shortestpath(f)
    path_weight = 0
    for state in f_shortest.states():
        state_arcs = list(f_shortest.arcs(state))
        assert len(state_arcs)<=1
        for arc in state_arcs:
            path_weight+=float(arc.weight)
        final_weight = f_shortest.final(state)
        weight_type = f_shortest.weight_type()
        if final_weight != pynini.Weight.zero(weight_type):
            path_weight+=float(final_weight)
    return path_weight