import pynini
from pynini.lib import pynutil, rewrite, features
from src.constants import *
from typing import *
import pydot
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
    raise DeprecationWarning

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
        input_string: Union[str, Sequence[str]],
    ) -> Union[str, List[str]]:
    raise DeprecationWarning

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

def get_feature_fsa(feature_dict: Dict[str, str]) -> pynini.Fst:
    """
    Arguments:
        feature_dict:   Dict mapping feature names to feature values
    Returns:
        f:              FSA accepting the feature string encoded from `feature_dict`
    
    Creates an FSA accepting the feature string encoded from `feature_dict`.
    Resulting FSA accepts a language of the shape "feature1=value1 feature2=value2 ...".
    The features are sorted so that lexeme-specific features come first, then lexical
    flags.
    """
    lexeme_vector, lexical_flag_vector = vectorize_feature_dict(feature_dict)
    acceptor = lexeme_vector.acceptor + lexical_flag_vector.acceptor
    return acceptor

def vectorize_feature_dict(
        feature_dict: Dict[str, str],
        specify_unmarked: bool = False,
) -> Tuple[features.FeatureVector, features.FeatureVector]:
    """
    Arguments:
        feature_dict:   Dict mapping feature names to feature values
    Returns:
        lexeme_vector:          FeatureVector containing lexeme-specific features
        lexical_flag_vector:    FeatureVector containing lexical flags
    Expects `feature_dict` to contain a "part_of_speech" key to determine the category.
    Splits features into lexeme-specific features and lexical flags and returns
    as two FeatureVectors.
    """
    pos = feature_dict["part_of_speech"]
    category = POS2CATEGORY[pos]
    lexeme_features = []
    lexical_flags = []

    if category is None:
        lexeme_vector = None
    else:
        for feature in category.features:
            feature_value = feature_dict.get(feature.name, 'unmarked')
            if feature_value == 'unmarked' and not specify_unmarked:
                continue
            feature_str = f"[{feature.name}={feature_value}]"
            lexeme_features.append(feature_str)
        lexeme_vector = features.FeatureVector(category, *lexeme_features)
    for feature in LEXEME.features:
        feature_value = feature_dict.get(feature.name, 'unmarked')
        if feature_value == 'unmarked' and not specify_unmarked:
            continue
        feature_str = f"[{feature.name}={feature_value}]"
        lexical_flags.append(feature_str)
    
    lexical_flag_vector = features.FeatureVector(LEXEME, *lexical_flags)
    return lexeme_vector, lexical_flag_vector

def stringify_lexeme_features(
        lexeme_features: Union[features.FeatureVector, Dict[str,str]]
    ) -> str:
    """
    Arguments:
        lexeme_features:  dict or FeatureVector containing lexeme-specific features
    Returns:
        feature_str:    String representation of the features in `lexeme_features`

    Converts the features in `lexeme_features` to a string of the shape
    "feature1=value1 feature2=value2 ...".
    """
    feature_strs = []
    if type(lexeme_features) is features.FeatureVector:
        lexeme_features = lexeme_features.values
    for feature in LEXEME.features:
        feature_value = lexeme_features.values[feature.name]
        if feature_value == 'unmarked':
            continue
        feature_str = f"{feature.name}={feature_value}"
        feature_strs.append(feature_str)
    feature_str = " ".join(feature_strs)
    return feature_str

def vectorize_lexeme_string(lexeme_str: str) -> features.FeatureVector:
    """
    Arguments:
        lexeme_str:     String representation of lexeme-specific features
    Returns:
        lexeme_vector:  FeatureVector containing lexeme-specific features
    """
    features = {}
    for feature_str in lexeme_str.split():
        feature, value = feature_str.split('=')
        features[feature] = value
    features_strs = []
    for feature in LEXEME.features:
        feature_value = features.get(feature.name, 'unmarked')
        feature_str = f"[{feature.name}={feature_value}]"
        features_strs.append(feature_str)
    lexeme_vector = features.FeatureVector(LEXEME, *features_strs)
    return lexeme_vector

def decode_fst_lattice(
        lattice: pynini.Fst,
        project_type: Literal['input', 'output']='output',
        unique_only: bool=True,
        nshortest: Optional[int]=None,
        strings_only: bool=False,
        to_feature_vectors: bool=False,
    ) -> List[
        Union[
            Dict[str,str],
            str,
            Tuple[
                str, features.FeatureVector, features.FeatureVector
            ],
        ]
    ]:
    """
    Arguments:
        lattice:        pynini.Fst with multiple output strings.
        project_type:   'input' or 'output' indicating which side to project
                        before decoding (default 'output').
        unique_only:    bool indicating whether to return only unique strings
                        (default True).
        nshortest:      (Optional) int indicating number of shortest paths to
                        consider before decoding (default None, i.e. all paths).
        strings_only:   bool indicating whether to return only decoded strings
                        (default False).
        to_feature_vectors:  bool indicating whether to return feature dicts
                            as FeatureVectors (default False).
    Returns:
        decoded_outputs:    List of decoded strings and feature dicts/vectors
                            from the lattice.

    Decodes all strings from the given `lattice` FST.
    Code based off `Paradigm._parse_lattice` in `pynini.lib.paradigms`.
    If `nshortest` is passed, call `rewrite.lattice_to_nshortest` first.

    By default, return a list of tuples of dicts where the 'form' key
    corresponds to the decoded string and other keys correspond to features.
    If `strings_only=True`, return only the decoded strings.
    If `to_feature_vectors=True`, convert the feature dicts to FeatureVectors
    and return tuples of (string, lexeme_vector, lexical_flag_vector).
    """
    lattice = pynini.project(lattice, project_type=project_type)
    if nshortest is not None:
        lattice = rewrite.lattice_to_nshortest(lattice, nshortest=nshortest)

    decoded_outputs = []

    # to track unique words and features
    decoded_words = []
    decoded_features = []

    path_iter = lattice.paths()
    while not path_iter.done():
        word = ''
        feature_dict = {}
        for label in path_iter.olabels():
            if label == 0:
                # epsilon, skip
                continue
            elif label < TIRA_NUM_SYMBOLS:
                symbol = TIRA_SYMBOL_TABLE.find(label)
                char = TIRA_SYMBOL_TO_CHAR.get(symbol, symbol)
                word += char
            elif chr(label) in '[]' and strings_only:
                word += chr(label)
            elif chr(label) in '[]':
                continue
            elif strings_only:
                feature_str = GENERATED_SYMBOLS.find(label)
                word += feature_str
            else:
                feature_str = GENERATED_SYMBOLS.find(label)
                feature, value = feature_str.split('=')
                if value == 'unmarked':
                    continue
                feature_dict[feature] = value
        
        path_iter.next()
        if unique_only and word in decoded_words and feature_dict in decoded_features:
            continue
        if to_feature_vectors:
            feature_vecs = vectorize_feature_dict(feature_dict)
            decoded_outputs.append((word, *feature_vecs))
        elif strings_only:
            decoded_outputs.append(word)
        else:
            feature_dict[word_key]=word
            decoded_outputs.append(feature_dict)
        decoded_words.append(word)
        decoded_features.append(feature_dict)

    return decoded_outputs

def decode_feature_label_rewriter(
        lattice: pynini.Fst,
):
    """
    Arguments:
        lattice: FST corresponding Paradigm.feature_label_rewriter
    Returns:
        decoded_strs: List of decoded strings from the output side of `lattice`
    `feature_label_rewriter` maps doesn't use GENERATED_SYMBOLS, so we need a
    custom decoder here.
    """
    strings = rewrite.lattice_to_strings(lattice)
    decoded_strs = []
    for lattice_output in strings:
        parts = lattice_output.split('[')
        wordform = parts[0]
        wordform = decode_byte_str(wordform)
        features = {'wordform': wordform}
        for feature_part in parts[1:]:
            feature_part = feature_part.rstrip(']')
            feature, value = feature_part.split('=')
            features[feature] = value
        decoded_strs.append(features)
    return decoded_strs

def decode_byte_str(byte_str: str) -> str:
    decoded_str = ''
    for token in byte_str:
        i = ord(token)
        char = TIRA_SYMBOL_TABLE.find(i)
        decoded_str += TIRA_SYMBOL_TO_CHAR.get(char, char)
    return decoded_str

def draw_svg(
    fst: pynini.Fst, filepath: str = 'tmp/tmp.svg',
    title: Optional[str]=None,
    use_union_table: bool=True,
):
    """
    Saves .dot and .svg representations of `fst`, with an optionally specified `title`
    (defaults to `filepath`).
    """
    stem = os.path.splitext(filepath)[0]
    fst = set_symbols(fst)
    dotfile = stem+'.dot'
    input_table = UNION_TABLE if use_union_table else fst.input_symbols()
    output_table = UNION_TABLE if use_union_table else fst.output_symbols()
    fst.draw(
        source=dotfile,
        show_weight_one=True,
        isymbols=input_table,
        osymbols=output_table,
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
