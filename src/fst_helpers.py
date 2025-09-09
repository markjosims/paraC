import pynini
from pynini.lib import pynutil, rewrite
from src.constants import *
from typing import *
import pydot

# symbol table wrappers

def set_symbols(fst: pynini.Fst) -> pynini.Fst:
    fst.set_input_symbols(TIRA_SYMBOL_TABLE)
    fst.set_output_symbols(TIRA_SYMBOL_TABLE)
    return fst

def tone2diac(tone_str: str) -> str:
    for tone_symbol, tone_diac in SYMBOL2DIAC.items():
        tone_str = tone_str.replace(tone_symbol, tone_diac)
    return tone_str

def tone2symbol(tone_str: str) -> str:
    for tone_diac, tone_symbol in DIAC2SYMBOL.items():
        tone_str = tone_str.replace(tone_diac, tone_symbol)
    return tone_str

def collapse_dental_bridge(encoded_string: str) -> str:
    for dental_consonant in DENTAL_T, DENTAL_D:
        expanded_dental_consonant = ' '.join(dental_consonant)
        encoded_string = encoded_string.replace(expanded_dental_consonant, dental_consonant)
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
    str_w_collapsed_dentals = collapse_dental_bridge(str_w_tone_symbols)
    return str_w_collapsed_dentals

def decode_fst_string(
        input_string: Union[str, Sequence[str], pynini.Fst]
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
        fst_input: Union[str, Sequence[str], pynini.Fst],
        fst_output: Union[str, Sequence[str], pynini.Fst, None] = None,
        weight: pynini.WeightLike = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  String or list of strings to be accepted by the FST (or an FSA)
        fst_output: (Optional) string or list of strings to be output by the FST (or an FSA)
        weight:     (Optional) weight value for FST
    Returns:
        f:          Finite State Transducer
    
    FST factory used to automatically set `TIRA_SYMBOL_TABLE`.
    Input and output may be string or list of strings. If only input is passed,
    returns an FSA over the input string or unin of strings. If output is passed,
    return an FST transducing input to output.
    """
    if type(fst_input) is str:
        f = pynini.accep(encode_fst_string(fst_input), token_type=TIRA_SYMBOL_TABLE, weight=weight)
    elif type(fst_input) is pynini.Fst:
        f = fst_input
    else:
        f = pynini.union(*[fst(fst_element) for fst_element in fst_input])
    
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
    ) -> List[str]:
    """
    Wraps `pynini.lib.rewrite.lattice_to_strings`. Sets `TIRA_SYMBOL_TABLE`
    and calls `decode_fst_string` on output.
    """
    lattice = pynini.project(lattice, project_type=project_type)
    tokenized_strings =  rewrite.lattice_to_strings(lattice, token_type=TIRA_SYMBOL_TABLE)
    decoded_strings = decode_fst_string(tokenized_strings)
    if unique_only:
        return list(set(decoded_strings))
    return decoded_strings

def draw_svg(fst: pynini.Fst, filepath: str = 'tmp.svg', title: Optional[str]=None):
    basename = os.path.basename(filepath)
    dotfile = basename+'.dot'
    fst.draw(
        source=dotfile,
        show_weight_one=True,
        isymbols=fst.input_symbols(),
        osymbols=fst.output_symbols(),
        portrait=True,
        title=title or basename,
    )
    graph = pydot.graph_from_dot_file(dotfile)[0]
    graph.write_svg(filepath)