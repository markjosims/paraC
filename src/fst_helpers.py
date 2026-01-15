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
    str_no_brackets = nfkd_norm.replace('[', '').replace(']', '')
    str_w_word_boundaries = str_no_brackets.replace(' ', WORD_BOUNDARY_STR)
    tokenized_str = " ".join(str_w_word_boundaries)
    str_w_collapsed_tokens = collapse_multichar_tokens(tokenized_str)
    str_w_tone_symbols = tone2symbol(str_w_collapsed_tokens)
    return str_w_tone_symbols

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

def priority_union(
        fst_list: List[pynini.Fst],
        sigma_star: pynini.Fst,
    ) -> pynini.Fst:
    """
    Creates a priority union of the input FSTs, i.e.
    the first FST has highest priority, the second FST
    has second highest priority, etc.
    Adapted from Gorman and Sproat (2021).

    Arguments:
        fst_list:   List of FSTs to combine
    Returns:
        f:          FST representing priority union of input FSTs

    """
    if len(fst_list) < 2:
        raise ValueError("Need at least two FSTs for priority union.")

    # base case, just two FSTs
    if len(fst_list) == 2:
        f1, f2 = fst_list
        f1_input = pynini.project(f1, project_type='input')
        f2_not_f1 = (sigma_star - f1_input) @  f2
        return f1 | f2_not_f1

    # recursive case
    f_first = fst_list[0]
    f_rest = priority_union(fst_list[1:], sigma_star=sigma_star)
    f_first_input = pynini.project(f_first, project_type='input')
    f_rest_not_first = (sigma_star - f_first_input) @ f_rest
    return f_first | f_rest_not_first  

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

def vectorize_feature_dict(
        feature_dict: Dict[str, str],
        specify_unmarked: bool = True,
) -> Tuple[features.FeatureVector, features.FeatureVector]:
    """
    Arguments:
        feature_dict:   Dict mapping feature names to feature values
        specify_unmarked: Whether to include 'unmarked' features in the output FeatureVectors
    Returns:
        lexeme_vector:          FeatureVector containing lexeme-specific features
        lexical_flag_vector:    FeatureVector containing lexical flags
    Expects `feature_dict` to contain a "part_of_speech" key to determine the category.
    Splits features into lexeme-specific features and lexical flags and returns
    as two FeatureVectors.
    """
    part_of_speech = feature_dict["part_of_speech"]
    category = POS2CATEGORY[part_of_speech]
    lexeme_features = []
    lexical_flags = []

    if category is None:
        lexeme_vector = None
    else:
        for feature in category.features:
            feature_value = feature_dict.get(feature.name, 'unmarked')
            if feature_value == 'unmarked' and not specify_unmarked:
                continue
            feature_str = f"{feature.name}={feature_value}"
            lexeme_features.append(feature_str)
        lexeme_vector = features.FeatureVector(category, *lexeme_features)
    for feature in LEXEME.features:
        if feature.name == 'aux' and part_of_speech == 'verb':
            # special handling for 'aux' feature in verbs
            # if verb belongs to an Aux-taking TAMD value and user did not specify aux,
            # default to 'true'
            tam = feature_dict['tam']
            deixis = feature_dict.get('deixis', 'unmarked')
            if (tam == 'imperfective') or (tam == 'perfective' and deixis == 'itive'):
                feature_value = feature_dict.get(feature.name, 'true')
            else:
                feature_value = feature_dict.get(feature.name, 'unmarked')
        else:
            feature_value = feature_dict.get(feature.name, 'unmarked')
        if feature_value == 'unmarked' and not specify_unmarked:
            continue
        feature_str = f"{feature.name}={feature_value}"
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
        feature_value = lexeme_features.get(feature.name, 'unmarked')
        if feature_value == 'unmarked':
            continue
        feature_str = f"{feature.name}={feature_value}"
        feature_strs.append(feature_str)
    feature_str = " ".join(feature_strs)
    return feature_str

def vectorize_lexeme_string(lexeme_str: str, specify_unmarked: bool = True) -> features.FeatureVector:
    """
    Arguments:
        lexeme_str:     String representation of lexeme-specific features
    Returns:
        lexeme_vector:  FeatureVector containing lexeme-specific features
    """
    feature_dict = {}
    for feature_str in lexeme_str.split():
        feature, value = feature_str.split('=')
        feature_dict[feature] = value
    feature_strs = []
    for feature in LEXEME.features:
        feature_value = feature_dict.get(feature.name, 'unmarked')
        if feature_value == 'unmarked' and not specify_unmarked:
            continue
        elif feature == 'part_of_speech' and feature_value not in POS2CATEGORY:
            # assume uninflected if invalid part_of_speech tag
            feature_value = 'uninflected'
        feature_str = f"{feature.name}={feature_value}"
        feature_strs.append(feature_str)
    lexeme_vector = features.FeatureVector(LEXEME, *feature_strs)
    return lexeme_vector

def get_gloss_str_from_dict(
        analysis: Dict[str, str],
        verbose: bool = False,
        include_form: bool = False,
) -> str:
    """
    Arguments:
        analysis:       Dict mapping feature names to feature values
        verbose:        Whether to include full feature names in the gloss string
        include_form:   Whether to prepend the analyzed form to the gloss string
    Returns:
        gloss_str:      String representation of the analysis in gloss format
    """
    analysis_subset = analysis.copy()
    gloss = analysis_subset.pop('gloss')

    ignored_keys = [
        'root', 'part_of_speech', 'analyzed_form',
        'weight', 'form', 'fv',
    ]
    # drop ummarked and ignored keys
    # if not verbose, modify certain values for conciseness
    for key, value in analysis.items():
        if key in ignored_keys or value == 'unmarked':
            analysis_subset.pop(key, None)
        elif key == 'class' and not verbose:
            # Prepend 'CL' to class value
            analysis_subset[key] = f"CL{analysis_subset['class']}"
        elif key == 'subject' and not verbose:
            analysis_subset[key]+='.sbj'
        elif key == 'object' and not verbose:
            analysis_subset[key]+='.obj'
        elif value == 'true' and not verbose:
            analysis_subset[key]=key

    person_keys = [k for k in analysis_subset.keys() if k in ['subject', 'object', 'possessor']]
    lexical_keys = [k for k in analysis_subset.keys() if k in LEXICAL_FEATURE_VALUES]
    inflectional_keys = [k for k in analysis_subset.keys() if k not in person_keys+lexical_keys]
    keys = sorted(inflectional_keys) + sorted(person_keys) + sorted(lexical_keys)

    if verbose:
        other_parts = [f'[{key}={analysis_subset[key]}]' for key in keys]
        gloss_str = gloss + ''.join(other_parts)
    else:
        for key in inflectional_keys+person_keys:
            part = analysis_subset[key]
            part_abbr = FEATURE2ABBREVIATION.get(part, part.upper())
            analysis_subset[key] = part_abbr
        other_parts = [analysis_subset[key] for key in keys]
        gloss_str = '-'.join([gloss] + other_parts)

    if include_form and 'analyzed_form' in analysis:
        gloss_str = analysis['analyzed_form'] + ' ' + gloss_str
    if include_form and 'form' in analysis:
        gloss_str = analysis['form'] + ' ' + gloss_str

    return gloss_str

def get_features_fsa(
        features: Union[str, Dict[str,str], Tuple[features.FeatureVector, features.FeatureVector]],
) -> pynini.Fst:
    """
    Arguments:
        features:   Lexeme features and lexical flags as a string, dict, or tuple of FeatureVectors
    Returns:
        fsa:       Finite state acceptor representing the features
    """
    if isinstance(features, str):
        features = vectorize_lexeme_string(features)
    elif isinstance(features, dict):
        features = vectorize_feature_dict(features)
    lexeme_vector, lexical_flag_vector = features
    if lexeme_vector is None:
        # uninflected words have no feature tags
        fsa = lexical_flag_vector.acceptor
    else:
        fsa = lexeme_vector.acceptor + lexical_flag_vector.acceptor
    return fsa

def parse_lattice_outputs(
        lattice: pynini.Fst,
        word_key: str='form',
        nshortest: Optional[int]=None,
        include_input_strs: bool=False,
        input_str_key: str='input_str',
        strip_eos: bool = True,
    ) -> List[Dict[str, Any]]:
    """
    Arguments:
        lattice:    pynini.Fst with multiple output strings.
        word_key:   key to use for decoded string in feature dicts
        nshortest:  (Optional) int indicating number of shortest paths to
                    consider before decoding (default None, i.e. all paths).
        include_input_strs:  (Optional) bool indicating whether to include
                            input strings in output dicts (default False).
        input_str_key:       (Optional) key to use for input strings in output dicts
        strip_eos:           (Optional) bool indicating whether to strip EOS symbol
                            from output strings (default True).
    Returns:
        decoded_outputs:    List of decoded feature dicts from the lattice.
    Wraps `get_lattice_strs_and_weights` and converts output strings to feature dicts.
    """
    if not include_input_strs:
        decoded_outputs = get_lattice_strs_and_weights(
            lattice,
            project_type='output',
            nshortest=nshortest,
            strip_eos=strip_eos,
        )
    else:
        decoded_outputs = get_lattice_input_output_strs_and_weights(
            lattice,
            nshortest=nshortest,
            strip_eos=strip_eos,
        )
    feature_dicts = []
    for output in decoded_outputs:
        feature_dict = {}
        if include_input_strs:
            output_str, input_str, weight = output
            feature_dict[input_str_key] = input_str
        else:
            output_str, weight = output

        parts = output_str.split('[')
        wordform = parts[0]
        feature_dict[word_key] = wordform
        feature_dict['weight'] = weight
        for feature_part in parts[1:]:
            feature_part = feature_part.rstrip(']')
            feature, value = feature_part.split('=')
            feature_dict[feature] = value
        feature_dicts.append(feature_dict)
    return feature_dicts

def vectorize_lattice_outputs(
        lattice: pynini.Fst,
        nshortest: Optional[int]=None,
        strip_eos: bool = True,
    ) -> List[Tuple[str, features.FeatureVector, features.FeatureVector, float]]:
    """
    Arguments:
        lattice:    pynini.Fst with multiple output strings.
        nshortest:  (Optional) int indicating number of shortest paths to
                    consider before decoding (default None, i.e. all paths).
        strip_eos:  (Optional) bool indicating whether to strip EOS symbol
                    from output strings (default True).
    Returns:
        decoded_outputs:    List of tuples of the shape
                            `(decoded_string, lexeme_vector, lexical_flag_vector, weight)`.
    Wraps `parse_lattice_outputs` and converts output strings to feature vectors.
    """
    decoded_outputs = parse_lattice_outputs(
        lattice,
        word_key='form',
        nshortest=nshortest,
        strip_eos=strip_eos,
    )
    output_tuples = []
    for output_dict in decoded_outputs:
        wordform = output_dict.pop('form', '')
        lexeme_vector = vectorize_lexeme_string(wordform)
        lexical_flag_vector = vectorize_lexeme_string(wordform, specify_unmarked=False)
        weight = output_dict.pop('weight', 0.0)
        output_tuples.append(
            (wordform, lexeme_vector, lexical_flag_vector, weight)
        )
    return output_tuples

def get_lattice_strs(
        lattice: pynini.Fst,
        project_type: Literal['input', 'output']='output',
        nshortest: Optional[int]=None,
        strip_eos: bool = True,
    ) -> List[str]:
    """
    Arguments:
        lattice:        pynini.Fst with multiple output strings.
        project_type:   'input' or 'output' indicating which side to project
                        before decoding (default 'output').
                        (default True).
        nshortest:      (Optional) int indicating number of shortest paths to
                        consider before decoding (default None, i.e. all paths).
        strip_eos:      (Optional) bool indicating whether to strip EOS symbol
                        from output strings (default True).
    Returns:
        decoded_outputs:    List of decoded strings from the lattice.

    Wraps `get_lattice_strs_and_weights` and returns only the decoded strings.

    Returns a list of decoded strings.
    """
    decoded_outputs = get_lattice_strs_and_weights(
        lattice,
        project_type=project_type,
        nshortest=nshortest,
        strip_eos=strip_eos,
    )
    return [output for output, _ in decoded_outputs]


def get_lattice_strs_and_weights(
        lattice: pynini.Fst,
        project_type: Literal['input', 'output']='output',
        nshortest: Optional[int]=None,
        strip_eos: bool = True,
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
                        (default True).
        nshortest:      (Optional) int indicating number of shortest paths to
                        consider before decoding (default None, i.e. all paths).
        strip_eos:      (Optional) bool indicating whether to strip EOS symbol
                        from output strings (default True).
    Returns:
        decoded_outputs:    List of decoded strings and feature dicts/vectors
                            from the lattice.

    Decodes all strings from the given `lattice` FST.
    Code based off `Paradigm._parse_lattice` in `pynini.lib.paradigms`.
    If `nshortest` is passed, call `rewrite.lattice_to_nshortest` first.

    Returns a list of tuples of the shape `(decoded_string, path_weight)`.
    """
    lattice = pynini.project(lattice, project_type=project_type)
    if nshortest is not None:
        lattice = rewrite.lattice_to_nshortest(lattice, nshortest=nshortest)

    decoded_outputs = []

    path_iter = lattice.paths()
    while not path_iter.done():
        label_iter = path_iter.olabels()
        word = extract_word_from_labels(label_iter, strip_eos=strip_eos)
        weight = float(path_iter.weight())
        if (word, weight) not in  decoded_outputs:
            decoded_outputs.append((word, weight))
        path_iter.next()

    decoded_outputs.sort(key=lambda t:t[-1])
    return decoded_outputs

def extract_word_from_labels(label_iter, strip_eos: bool = True) -> str:
    """
    Arguments:
        label_iter:     An iterator over FST labels
        strip_eos:      (Optional) bool indicating whether to strip EOS symbol
                        from output strings (default True).
    Returns:
        word:           Decoded string from the labels

    Decodes a string from the given `label_iter`. Used in `get_lattice_strs_and_weights`.
    """
    word = ''
    for label in label_iter:
        if label == 0:
                # epsilon, skip
            continue
        elif label < TIRA_NUM_SYMBOLS:
            symbol = TIRA_SYMBOL_TABLE.find(label)
            char = TIRA_SYMBOL_TO_CHAR.get(symbol, symbol)
            word += char
        else:
            feature_str = '['+GENERATED_SYMBOL_TABLE.find(label)+']'
            word += feature_str
    if strip_eos:
        word = word.replace(EOS_STR, '')
    return word

def get_lattice_input_output_strs_and_weights(
        lattice: pynini.Fst,
        nshortest: Optional[int]=None,
    ) -> List[Tuple[str, str, float]]:
    """
    Arguments:
        lattice:        pynini.Fst with multiple output strings.
        nshortest:      (Optional) int indicating number of shortest paths to
                        consider before decoding (default None, i.e. all paths).
    Returns:
        decoded_outputs:    List of tuples of the shape
                            `(input_string, output_string, weight)`.
    Decodes all input and output strings from the given `lattice` FST.
    Code based off `Paradigm._parse_lattice` in `pynini.lib.paradigms`.
    If `nshortest` is passed, call `rewrite.lattice_to_nshortest` first.
    Returns a list of tuples of the shape `(input_string, output_string, path_weight)`.
    """
    if nshortest is not None:
        # can't call `rewrite.lattice_to_nshortest` on an FST with both input and output labels
        # compute nshortest on projected output FSA and compose back
        output_fsa = pynini.project(lattice, project_type='output')
        output_fsa = rewrite.lattice_to_nshortest(output_fsa, nshortest=nshortest)
        lattice = lattice @ output_fsa

    decoded_outputs = []

    path_iter = lattice.paths()
    while not path_iter.done():
        outlabel_iter = path_iter.olabels()
        inlabel_iter = path_iter.ilabels()
        in_word = extract_word_from_labels(inlabel_iter)
        out_word = extract_word_from_labels(outlabel_iter)
        weight = float(path_iter.weight())
        if (in_word, out_word, weight) not in  decoded_outputs:
            decoded_outputs.append((in_word, out_word, weight))
        path_iter.next()

    decoded_outputs.sort(key=lambda t:t[-1])
    return decoded_outputs


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
):
    """
    Saves .dot and .svg representations of `fst`, with an optionally specified `title`
    (defaults to `filepath`).
    """
    stem = os.path.splitext(filepath)[0]
    fst = set_symbols(fst)
    dotfile = stem+'.dot'
    input_table = fst.input_symbols()
    output_table = fst.output_symbols()
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
    ) -> List[Tuple[str, str, float]]:
    raise DeprecationWarning
