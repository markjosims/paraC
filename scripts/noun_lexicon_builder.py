import pandas as pd
from dataset_builder import normalize_str, normalize_ipa, is_en_word

NOUN_EXCEL_PATH = 'data/nouns.xlsx'
NOUN_CSV_PATH = 'data/nouns.csv'

EXCEL_SHEET_NAME = 'Nouns'
COL_MAPPER = {
    'SG subject form': 'nom.sg',
    'PL subject form': 'nom.pl',
    'SG object form': 'acc.sg',
    'PL object form': 'acc.pl',
}
TRANSLATION_COLNAME = 'Translation equivalent'
GLOSS_COLNAME = 'gloss'

ENGLISH_SPANS = [
    'no number distinction',
    'his mother',
    'or',
    'in HH20220714',
]

def remove_english(text: str):
    for sentence in ENGLISH_SPANS:
        text = text.replace(sentence, '')
    return text

def main() -> int:
    df = pd.read_excel(NOUN_EXCEL_PATH, sheet_name=EXCEL_SHEET_NAME)
    translation = df[TRANSLATION_COLNAME]
    df = df[COL_MAPPER.keys()]
    df = df.dropna(how='all')
    df = df.fillna('')
    
    has_eng=pd.Series([False]*len(df))
    for col in COL_MAPPER.keys():
        if col == 'Translation equivalent':
            continue
        df[col]=df[col].apply(remove_english)
        df[col]=df[col].apply(normalize_str)
        df[col]=df[col].apply(normalize_ipa)
        col_has_eng = df[col].str.split().apply(lambda l: any(is_en_word(word) for word in l))
        has_eng=has_eng|col_has_eng

    assert ~has_eng.all()
    df=df.rename(columns=COL_MAPPER)
    df[GLOSS_COLNAME]=translation

    df.to_csv(NOUN_CSV_PATH, index=False)
    return 0

if __name__ == '__main__':
    main()