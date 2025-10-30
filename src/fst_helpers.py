import pynini
from pynini.lib import pynutil, rewrite, paradigms
from sqlalchemy import func
from src.constants import *
from typing import *
import pydot
from functools import wraps
import hashlib
import pickle
import unicodedata

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
    nfkd_norm = unicodedata.normalize('NFKD', input_string)
    str_w_word_boundaries = nfkd_norm.replace(' ', WORD_BOUNDARY_STR)
    tokenized_str = " ".join(str_w_word_boundaries)
    str_w_tone_symbols = tone2symbol(tokenized_str)
    str_w_collapsed_dentals = collapse_multichar_tokens(str_w_tone_symbols)
    return str_w_collapsed_dentals

def decode_fst_string(
        input_string: Union[str, Sequence[str], pynini.Fst],
        is_byte_str: bool=False,
    ) -> Union[str, List[str]]:
    """
    Condense all separated characters, replaces `WORD_BOUNDARY_STR` symbol (default "|")
    with a space, and changes tone symbols back to diacritics.
    If `input_string` is an FST, call `Fst.string()` first.
    If `is_byte_str` is passed, call `decode_byte_str` first.
    """
    if type(input_string) is pynini.Fst:
        input_string = input_string.string(token_type=TIRA_SYMBOL_TABLE)
    elif type(input_string) is not str:
        return [
            decode_fst_string(input_element, is_byte_str)
            for input_element in input_string
        ]
    if is_byte_str:
        return decode_byte_str(input_string)
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

def get_nbest_strs_and_weights(
        lattice: pynini.Fst,
        n: int=5,
        return_input_strs: bool=True,
        use_byte_tokens: bool=False,
    ) -> List[Tuple[str, str, float]]:
    """
    Arguments:
        lattice:            pynini.Fst with multiple output strings.
        n:                  int indicating number of strings to fetch.
        return_input_strs:  bool indicating whether input strings ('intabs')
                            should be returned.
        use_byte_tokens:    bool indicating whether `lattice` uses  byte tokens
                            or symbol table (default)
    Returns:
        hits:       List of tuples `[(intab?, outtab, cost), ...]`
    
    Finds n best strings from the output vocabulary of the given lattice
    and returns as a list of 2/3-tuples containing the (input string?), output string
    and cost for each path.

    Finding n best unique strings from the lattice requires projecting the output
    and then performing epsilon removal. If only output strs are requested, return
    the strs and weight from the nbest paths from the output projection.
    If `return_input_strs=True`, then we need to compose each output str with the lattice
    in order to compute the shortest distance as well as the associated input str
    which obtains the output str.
    """
    lattice_acceptor = pynini.project(lattice, 'output')
    lattice_acceptor.optimize()
    nbest_paths = pynini.shortestpath(lattice_acceptor, nshortest=n, unique=True).paths()
    if not return_input_strs:
        # don't need to map output strs to best input
        nbest_couples = []
        for _, outtab, weight in nbest_paths.items():
            outtab = decode_fst_string(outtab, is_byte_str=use_byte_tokens)
            weight = float(weight)
            nbest_couples.append((outtab, weight))
        return nbest_couples

    nbest_strs = list(nbest_paths.ostrings())
    # pass opposite value of `use_byte_tokens here`
    # since string will be composed with the lattice directly
    # therefore they need to be of the same type
    # nbest_strs = [
    #     decode_byte_str(byte_str, is_byte_str=not use_byte_tokens)
    #     for byte_str in nbest_strs
    # ]
    nbest_strs = [decode_byte_str(byte_str) for byte_str in nbest_strs]

    nbest_triples = []
    for hit_str in nbest_strs:
        hit_transducer = lattice@fst(hit_str)
        hit_shortestpath = pynini.shortestpath(hit_transducer)
        hit_triple = list(
            hit_shortestpath.paths(
                input_token_type=TIRA_SYMBOL_TABLE,               
                output_token_type=TIRA_SYMBOL_TABLE,               
            ).items())
        hit_triple = hit_triple[0]
        intab, outtab, weight = hit_triple
        intab = decode_fst_string(intab, is_byte_str=use_byte_tokens)
        outtab = decode_fst_string(outtab, is_byte_str=use_byte_tokens)
        weight = float(weight)
        nbest_triples.append((intab, outtab, weight))
    return nbest_triples

def cache_is_updated(current_file: str, cache_path: str) -> bool:
    """
    Check if the cache is updated relative to the script file.
    """
    file_date = os.path.getmtime(current_file)
    if os.path.exists(cache_path):
        cache_date = os.path.getmtime(cache_path)
        return cache_date >= file_date
    return False

def get_hashable_args_str(args, kwargs):
    """
    Arguments:
        args:   Positional arguments to be hashed.
        kwargs: Keyword arguments to be hashed.
    Returns:
        args_str:  String representation of hashable arguments.
    Raises:
        TypeError: If any argument is not hashable.
    """
    args_for_key = list(args)
    kwargs_for_key = kwargs.copy()
    for i, arg in enumerate(args):
        if type(arg) is list:
            arg = tuple(sorted(arg))
        elif type(arg) is paradigms.Paradigm:
                # Paradigm objects are not hashable, so use their name
            arg = arg.name
            args_for_key[i] = arg
        if not isinstance(arg, (str, int, float, bool)):
            raise TypeError
    for key, value in kwargs.items():
        if type(value) is list:
            value = tuple(sorted(value))
            kwargs_for_key[key] = value
        if type(value) is paradigms.Paradigm:
                # Paradigm objects are not hashable, so use their name
            kwargs_for_key[key] = value.name
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError
    args_str = str(args_for_key)+str(kwargs_for_key)
    return args_str

def fst_cache(current_file: str, cache_dir=".cache/") -> pynini.Fst:
    """
    Arguments:
        current_file:  The file path of the current module.
        cache_dir:     Directory to store cached FST files.
    Returns:
        f:              FST loaded from cache or generated by the decorated function.
    
    Decorator that caches the output of an FST-generating function.

    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            os.makedirs(cache_dir, exist_ok=True)
            try:
                args_str = get_hashable_args_str(args, kwargs)
            except TypeError as e:
                # if args are not hashable, skip caching
                print(
                    f"Building FST for function {func.__name__} "+\
                    f"with args {args} and kwargs {kwargs} without caching (unhashable args): {e}"
                )
                f = func(*args, **kwargs)
                return f
            cache_key = hashlib.md5((func.__name__ + args_str).encode()).hexdigest()
            cache_path = os.path.join(
                cache_dir,
                f"{cache_key}.fst"
            )
            if cache_is_updated(current_file, cache_path):
                print(
                    f"Loaded FST for function {func.__name__} "+\
                    f"with args {args_str} from cache {cache_path}"
                )
                f = pynini.Fst.read(cache_path)
            else:
                print(
                    f"Building FST for function {func.__name__} "+\
                    f"with args {args_str} and cache {cache_path}"
                )
                f = func(*args, **kwargs)
                f.write(cache_path)
            return f
        return wrapper
    return decorator

def output_cache(current_file: str, cache_dir=".cache/") -> Any:
    """
    Arguments:
        current_file:  The file path of the current module.
        cache_dir:     Directory to store cached output files.
    Returns:
        out:             Python object loaded from cache or generated by the decorated function.
    
    Decorator that caches the output of a function returning any Python object.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            os.makedirs(cache_dir, exist_ok=True)
            try:
                args_str = get_hashable_args_str(args, kwargs)
            except TypeError as e:
                # if args are not hashable, skip caching
                print(
                    f"Building output for function {func.__name__} "+\
                    f"with args {args} and kwargs {kwargs} without caching (unhashable args): {e}"
                )
                out = func(*args, **kwargs)
                return out
            cache_key = hashlib.md5((func.__name__ + args_str).encode()).hexdigest()
            cache_path = os.path.join(
                cache_dir,
                f"{cache_key}.output"
            )
            if cache_is_updated(current_file, cache_path):
                with open(cache_path, 'rb') as f:
                    print(
                        f"Loaded output for function {func.__name__} "+\
                        f"with args {args_str} from cache {cache_path}"
                    )
                    out = pickle.load(f)
            else:
                print(
                    f"Building output for function {func.__name__} "+\
                    f"with args {args_str} and cache {cache_path}"
                )
                out = func(*args, **kwargs)
                with open(cache_path, 'wb') as f:
                    pickle.dump(out, f)
            return out
        return wrapper
    return decorator