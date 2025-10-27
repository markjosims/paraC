from typing import *
from tira_elan_scraper import LIST_PATH
import os
import pandas as pd
import string
import json
import unicodedata
from unidecode import unidecode
import wordfreq
from tqdm import tqdm

VERSION = "0.1.0"
DATA_DIR = os.environ.get(
    'TIRA_MORPH_DATA_DIR',
    os.path.join(os.getcwd(), 'data')
)
ELAN_DIR = os.path.join(DATA_DIR, 'elan')
EXCEL_DIR = os.path.join(DATA_DIR, 'excel')
SENTENCES_DIR = os.path.join(DATA_DIR, 'sentences')

EXCEL_VERBS_PATH = os.environ.get(
    'TIRA_VERBS_EXCEL',
    os.path.join(EXCEL_DIR, 'verb_paradigms.xlsx')
)
EXCEL_SHEET_NAME = 'Verbs'

IPA_REP_PATH = os.path.join(SENTENCES_DIR, 'char_replacements.json')
with open(IPA_REP_PATH, encoding='utf8') as f:
    IPA_REP_DICT = json.load(f)
IPA_REP_DICT = {k: v['target'] for k, v in IPA_REP_DICT.items()}


README_HEADER = string.Template(
"""
# tira_morph
Dataset of unique Tira sentences for purposes of training morphological segmentation.
Uses same textnorm steps as `tira_asr`. Contains $num_sentences unique sentences for
a total of $num_words words ($num_word_unique unique words) averaging
$mean_sentence_len words per sentence. 

## Files
- sentences.csv: final dataset of unique Tira sentences with associated glosses and translations
- char_replacements.json: dictionary of character replacements used in text normalization
- tira_asr_unique_chars.json: list of all expected characters in Tira IPA transcriptions
- english_words.txt: list of all English words detected and removed during text normalization
- tira_words.txt: list of all Tira words detected in the dataset before text normalization
- tira_words_normalized.txt: list of all Tira words found in the dataset with text normalization applied

## Preprocessing log
"""
)
PREPROCESSING_STEPS = []

verb_cols = [
    "IMP.AND", 
    "IMP.VEN", 
    "PFV.VEN", 
    "PFV.AND", 
    "IPFV.AND", 
    "IPFV.VEN", 
    "PRS.PROG.AND",
    "PRS.PROG.VEN", 
    "Infinitive (NOM)",
    "Infinitive (ACC)", 
    "PROH.AND", 
    "PROH.VEN",
    "Dependent AND", 
    "Dependent VEN",
    "Hort.ITV",
    "Hort.VEN",
    "PST.PROG? 'were doing X, used to do X'",
    "PST.PRF? AND",
    "PST.PRF? VEN",
    "FUT?",
    "FUT.PROG?.AND 'will be doing X'",
    "FUT.PROG?.VEN 'will be doing X'",
    "FUT.PRF?.AND 'will have done X' (also: 'would have done' in a conditional or counterfactual)",
    "FUT.PRF?.VEN  'will have done X' (also: 'would have done' in a conditional or counterfactual)",
    "should, can X ",
    "Let X do Y (dependent)",
    "Passive",
]
source_cols = ["Source file"] + [f"Source file.{i}" for i in range(1, len(verb_cols))]

# -------------- #
# string helpers #
# -------------- #

TONE_DIACS = ['grave', 'macrn', 'acute', 'circm', 'caron',]

COMBINING = {
    'grave': "\u0300",
    'macrn': "\u0304",
    'acute': "\u0301",
    'circm': "\u0302",
    'caron': "\u030C",
    'tilde': "\u0303",
    'bridge': "\u032A",
}

def strip_punct(f):
    def g(s):
        return f(s.strip(string.punctuation))
    return g


def remove_punct(text: str, keep: Optional[Union[str, Sequence[str]]] = None) -> str:
    for p in string.punctuation:
        if keep and p in keep:
            continue
        text = text.replace(p, '')
    return text

def normalize_str(
        text: str,
        keep_punct: Optional[Union[str, Sequence[str]]] = None 
    ) -> str:
    """
    perform NFKD unicode normalization, convert string lower
    and remove any punctuation not specified in `keep_punct`
    """
    if not text:
        return text
    text = text.lower()
    text = text.strip()
    text = unicodedata.normalize('NFKD', text)
    text = remove_punct(text, keep=keep_punct)
    return text

def normalize_ipa(ipa_str: str):
    if not ipa_str:
        return ipa_str
    normalized_ipa_str = make_replacements(ipa_str, IPA_REP_DICT)
    return normalized_ipa_str

def unicode_description(char: str):
    unicode_name = unicodedata.name(char, 'No unicode name found')
    unicode_point = str(hex(ord(char)))
    return {
        'unicode_name': unicode_name,
        'unicode_point': unicode_point,
    }

def has_diac(text: str, tone_only: bool = False) -> str:
    text = normalize_str(text)
    for diac_name, diac in COMBINING.items():
        if tone_only and diac_name not in TONE_DIACS:
            continue
        if diac in text:
            return True
    return False

@strip_punct
def has_unicode(s):
    return unidecode(s) != s
@strip_punct
def is_en_word(w: str, expect_ascii: bool = True, threshold=1e-9) -> bool:
    """
    Returns True if a word is detected as English, False otherwise.
    Default behavior is to return True if word is recognized by `wordfreq`.
    Frequency must be greater than `threshold` value to prevent ultra
    low-frequency words from slipping through. If `expect_ascii=True`,
    return False if non-ascii unicode characters are detected, regardless
    of `wordfreq` search.
    """
    if expect_ascii and has_unicode(w):
        return False
    return wordfreq.word_frequency(w, 'en')>threshold

def max_ord_in_str(text: str) -> int:
    return max(ord(c) for c in text)

def make_replacements(text: str, reps: Dict[str, str]) -> str:
    """
    Makes all replacements specified by `reps`, a dict whose keys are intabs
    and values are outtabs to replace them.
    Avoids transitivity by first replacing intabs to a unique char not found in the original string.
    """
    max_ord_str = max_ord_in_str(text)
    max_ord_reps = max_ord_in_str(''.join([*reps.keys(), *reps.values()]))
    max_ord = max(max_ord_str, max_ord_reps)
    intab2unique = {
        k: chr(max_ord+i+1) for i, k in enumerate(reps.keys())
    }
    unique2outtab = {
        intab2unique[k]: v for k, v in reps.items()
    }

    # sort intabs so that longest sequences come first
    intabs = sorted(reps.keys(), key=len, reverse=True)

    for intab in intabs:
        sentinel = intab2unique[intab]
        text = text.replace(intab, sentinel)
    for sentinel, outtab in unique2outtab.items():
        text = text.replace(sentinel, outtab)
    return text

# --------------------------- #
# text normalization pipeline #
# --------------------------- #

def perform_textnorm(
        df: pd.DataFrame,
        preproc_steps: List[str],
        norm_col: str = 'text',
        keep_punct: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, List[str]]:

    # drop ungrammatical rows
    ungrammatical_mask = df[norm_col].str.contains('*', regex=False)
    df = df[~ungrammatical_mask]
    ungrammatical_str = f"- removed {int(ungrammatical_mask.sum())} ungrammatical rows"
    print(ungrammatical_str)
    preproc_steps.append(ungrammatical_str)

    # basic string normalization
    print("String normalization...")
    df[norm_col] = df[norm_col].apply(lambda s: normalize_str(s, keep_punct=keep_punct))
    nfkd_str = f"- applied NFKD unicode normalization to text, set to lowercase and removed punctuation"
    print(nfkd_str)
    preproc_steps.append(nfkd_str)

    # skip all toneless entries
    print("Dropping rows with no tone diacritics")
    has_tone_mask = df[norm_col].apply(lambda s: has_diac(s, tone_only=True))
    prev_len = len(df)
    df = df[has_tone_mask]
    toneless_row_num = prev_len-len(df)
    toneless_str = f"- removed {toneless_row_num} rows with no tone marked, {len(df)} rows remaining"
    print(toneless_str)
    preproc_steps.append(toneless_str)


    # remove all rows with English words
    print("Removing rows with English")
    en_words = set()
    tira_words = set()
    def detect_en_words(sentence):
        has_en_word = False
        for word in sentence.split():
            if is_en_word(word) and (len(word)>1) or word in ['downstep']:
                en_words.add(word)
                has_en_word=True
            else:
                tira_words.add(word)
        return has_en_word

    has_en_mask = df[norm_col].apply(detect_en_words)

    # save detected words for manual verification
    en_words_path = os.path.join(SENTENCES_DIR, "english_words.txt")
    tira_words_path = os.path.join(SENTENCES_DIR, "tira_words.txt")
    with open(en_words_path, 'w', encoding='utf8') as f:
        f.writelines(['\n'.join(en_words)])
    with open(tira_words_path, 'w', encoding='utf8') as f:
        f.writelines(['\n'.join(tira_words)])

    prev_len = len(df)
    df = df[~has_en_mask]
    en_row_num = prev_len-len(df)
    no_en_str = f"- removed {en_row_num} rows with English words, {len(df)} rows remaining"
    unique_words_str = "- saved all detected English words to $TIRA_ASR_CLIPS/english_words "+\
        "and Tira words to $TIRA_ASR_CLIPS/tira_words.txt"
    print(no_en_str)
    print(unique_words_str)
    preproc_steps.append(no_en_str)
    preproc_steps.append(unique_words_str)

    # remove tone words (e.g. HLL, LHL,...)
    print("Removing tone words from transcriptions...")
    is_tone_word = lambda s: all(c in 'hml' for c in s)
    has_tone_word = lambda s: any(is_tone_word(w) for w in s.split())
    remove_tone_word = lambda s: ' '.join(word for word in s.split() if not is_tone_word(word))
    has_tone_word_mask = df[norm_col].apply(has_tone_word)
    df[norm_col] = df[norm_col].apply(remove_tone_word)
    remove_tone_word_str = f"- removed tone words (e.g. HLL, LHL, LLHH) from transcription, {int(has_tone_word_mask.sum())} rows affected"
    print(remove_tone_word_str)
    preproc_steps.append(remove_tone_word_str)

    # normalize IPA charset
    print("Normalizing IPA character set...")
    # # Uncomment to overwrite `char_rep_json`
    # unique_chars = set()
    # df[norm_col].apply(unique_chars.update)
    # rep_dict = {
    #     char: {
    #         'target': char,
    #         'comment': '',
    #         **unicode_description(char)
    #     } for char in unique_chars
    # }
    # with open(char_rep_json_path, 'w', encoding='utf8') as f:
    #     json.dump(rep_dict, f, ensure_ascii=True, indent=2)
    # apply twice since some diacritics may interfere with replacing digraphs
    df[norm_col]=df[norm_col].apply(normalize_ipa)
    df[norm_col]=df[norm_col].apply(normalize_ipa)

    print("Checking only expected chars are found in dataset...")
    expected_chars_basename = 'tira_asr_unique_chars.json'
    expected_chars_path = os.path.join(SENTENCES_DIR, expected_chars_basename)
    with open(expected_chars_path, encoding='utf8') as f:
        expected_ipa_chars = json.load(f)
    if keep_punct:
        expected_ipa_chars.extend([p for p in keep_punct])
    unexpected_chars = set()
    def find_unexpected_chars(sentence):
        found_unexpected_char = False
        for c in sentence:
            if c not in expected_ipa_chars:
                unexpected_chars.add(c)
                found_unexpected_char=True
        return found_unexpected_char

    unexpected_chars_mask = df[norm_col].apply(find_unexpected_chars)
    if (unexpected_chars_mask).sum()>0:
        raise ValueError(f"Found unexpected chars after normalizing IPA. Inspect {norm_col} col in dataframe.")
    expected_char_str = "- Checked that only expected IPA chars are found in dataset, "+\
        f"as defined by JSON file {expected_chars_basename}"
    print(expected_char_str)
    preproc_steps.append(expected_char_str)

    tira_words_normalized = set()
    df['text'].str.split().apply(tira_words_normalized.update)

    tira_words_nmzd_path = os.path.join(DATA_DIR, "tira_words_normalized.txt")
    with open(tira_words_nmzd_path, 'w', encoding='utf8') as f:
        f.writelines(['\n'.join(tira_words_normalized)])

    return df, preproc_steps

def associate_tiers(
        df: pd.DataFrame,
        transription_tier: str = 'IPA Transcription',
        annotation_tiers: List[str] = ['Gloss', 'Translation', 'Word']
    ) -> pd.DataFrame:
    """
    For each unique transcription in `transcription_tier`, look for any
    annotations for each tier in `annotation_tiers`. Return a dataframe whose
    columns correspond to `transcription_tier` and the various `annotation_tiers`
    with one row for each unique transcription on `transcription_tier`.
    """
    transcription_tier_mask = df['tier']==transription_tier
    unique_transcriptions = df.loc[transcription_tier_mask, 'text'].unique().tolist()
    annotation_dict = {transription_tier: unique_transcriptions}
    tier_masks = {}
    for tier in annotation_tiers:
        tier_mask = df['tier']==tier
        tier_masks[tier]=tier_mask
        annotation_dict[tier]=list()
    for transcription in tqdm(unique_transcriptions):
        transcription_mask = get_transcription_mask(df, transcription, transcription_tier_mask)
        for tier in annotation_tiers:
            annotation_mask = tier_masks[tier]
            annotation = get_annotation_for_transcription(df, transcription_mask, annotation_mask)
            annotation_dict[tier].append(annotation)
    
    annotation_df = pd.DataFrame(data=annotation_dict)
    return annotation_df

def get_annotation_for_transcription(
        df: pd.DataFrame,
        transcription_mask: pd.Series,
        annotation_mask: pd.Series,
) -> str:
    """
    Given a mask corresponding to all rows coinciding with a given transcription
    return the longest non-zero annotation, if any, on the respective annotation tier.
    """
    masked_df = df[transcription_mask&annotation_mask]
    if len(masked_df)==0:
        return ''
    sorted_annotations = masked_df['text'].sort_values(ascending=False)
    longest_annotation = sorted_annotations.iloc[0]
    return longest_annotation

def get_transcription_mask(
        df: pd.DataFrame,
        transcription: str,
        transcription_tier_mask: pd.Series,
) -> pd.Series:
    """
    Given a string indicating a particular transcription value,
    return a mask over all rows in the dataset that coincide with the
    timestamp and source file of one of the instances of that transcription value.
    """
    running_mask = pd.Series([False]*len(df))
    transcription_text_mask = (df['text']==transcription)&transcription_tier_mask
    for _, row in df[transcription_text_mask].iterrows():
        start, end = row['start'], row['end']
        eaf_basename = row['eaf_basename']
        
        start_mask = df['start']==start
        end_mask = df['end']==end
        basename_mask = df['eaf_basename']==eaf_basename

        mask_for_interval = start_mask&end_mask&basename_mask&~transcription_tier_mask
        running_mask = running_mask | mask_for_interval
    return running_mask

def ingress_excel_verbs() -> pd.DataFrame:
    """
    Load excel data on Tira verb paradigms and shape into dataframe with gloss column
    populated by stem translation plus verb gloss as indicated by column label
    in original excel spreadsheet.
    """
    excel_df = pd.read_excel(EXCEL_VERBS_PATH, keep_default_na=False, sheet_name=EXCEL_SHEET_NAME)
    analyses = []
    def add_verb_columns(row):
        translation = row['Translation']
        for verb_col, source_col in zip(verb_cols, source_cols):
            if not row[verb_col]:
                continue
            gloss = translation + ' ' + verb_col
            analyses.append({
                "text": row[verb_col],
                "eaf_basename": row.get(source_col, None),
                "gloss": gloss,
                "form": verb_col,
            })
    excel_df.apply(add_verb_columns, axis=1)
    analyses_df = pd.DataFrame(data=analyses)
    return analyses_df

def main() -> int:
    df = pd.read_csv(LIST_PATH, keep_default_na=False)
    print(len(df))

    annotations_path = os.path.join(ELAN_DIR, 'annotations.csv')
    if not os.path.exists(annotations_path):
        print("Associating annotations to transcriptions...")
        annotation_df = associate_tiers(df)
        annotation_df.to_csv(annotations_path, index_label='index')
    else:
        print("Loading annotations...")
        annotation_df = pd.read_csv(annotations_path, index_col='index')
    annotation_df = annotation_df.rename(columns={'IPA Transcription': 'text'})

    # only interested in 'IPA Transcription', no other tiers
    print("Dropping non-transcription annotations...")
    ipa_mask = df['tier'] == 'IPA Transcription'
    df=df[ipa_mask]
    df=df.drop(columns=['tier'])
    print(len(df))

    # drop na rows
    df=df.dropna()
    nan_str = f"- {len(df)} non-NaN transcriptions in dataset"
    print(nan_str)
    PREPROCESSING_STEPS.append(nan_str)

    # drop duplicates
    df = df.drop_duplicates(subset='text')
    dedup_str = f"- {len(df)} non-duplicate transcriptions in dataset"
    print(dedup_str)
    PREPROCESSING_STEPS.append(dedup_str)

    print("Merging annotations into dataframe...")
    df = pd.merge(df, annotation_df, how='left', on='text')

    # drop non-annotated rows and model output rows
    model_mask = df['eaf_basename'].str.lower().str.contains('model')
    no_gloss_mask = df['Gloss']==''
    no_translation_mask = df['Translation']==''
    rows_to_drop = model_mask|no_gloss_mask|no_translation_mask
    df=df[~rows_to_drop]
    invalid_row_str = f"- {len(df)} valid rows after dropping unannotated and ASR-generated transcriptions"
    print(invalid_row_str)
    PREPROCESSING_STEPS.append(invalid_row_str)

    prev_len = len(df)
    excel_df = ingress_excel_verbs()
    df['source']='elan'
    excel_df['source']='excel'
    df = pd.concat([df, excel_df])
    rows_added = len(df)-prev_len
    excel_str = f"- added {rows_added} rows from excel data"
    PREPROCESSING_STEPS.append(excel_str)
    print(excel_str)

    df, _ = perform_textnorm(df, PREPROCESSING_STEPS)

    words_per_row = df['text'].str.split()
    num_words_per_row = words_per_row.apply(len)
    num_words = num_words_per_row.sum()
    mean_sentence_len = num_words/len(df)
    all_words = set()
    words_per_row.apply(all_words.update)
    

    readme_header_str = README_HEADER.substitute(
        num_sentences=len(df),
        num_words=num_words,
        num_word_unique=len(all_words),
        mean_sentence_len=mean_sentence_len,
        num_analyses=None,
        num_word_analyzed=None,
        num_morphs=None,
    )
    readme_out = os.path.join(SENTENCES_DIR, 'README.md')
    with open(readme_out, 'w', encoding='utf8') as f:
        f.write(readme_header_str+'\n')
        f.write('\n'.join(PREPROCESSING_STEPS))

    transcriptions_path = os.path.join(SENTENCES_DIR, 'sentences.csv')
    df.to_csv(transcriptions_path, index_label='index')

if __name__ == '__main__':
    main()