import pandas as pd
from dataset_builder import normalize_str, normalize_ipa, is_en_word

NOUN_EXCEL_PATH = 'data/excel/nouns_excel_raw.csv'
NOUN_CSV_PATH = 'data/lexicon/nouns.csv'

FORM_COLMAPPER = {
    'SG subject form': 'nom.sg',
    'PL subject form': 'nom.pl',
    'SG object form': 'acc.sg',
    'PL object form': 'acc.pl',
}
GLOSS_COLMAPPER = {
    'Translation equivalent': 'translation',
    'Gloss': 'gloss',
    'Noun class (based on agreement)': 'noun_class',
}
COLMAPPER = {**FORM_COLMAPPER, **GLOSS_COLMAPPER}

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
    df = pd.read_csv(NOUN_EXCEL_PATH)
    df = df[COLMAPPER.keys()]
    forms_df = df[FORM_COLMAPPER.keys()]
    forms_df = forms_df.dropna(how='all')
    has_forms_idcs = forms_df.index
    df = df.loc[has_forms_idcs]
    df = df.fillna('')
    
    has_eng=pd.Series([False]*len(df))
    for col in FORM_COLMAPPER.keys():
        df[col]=df[col].apply(remove_english)
        df[col]=df[col].apply(normalize_str)
        df[col]=df[col].apply(normalize_ipa)
        col_has_eng = df[col].str.split().apply(lambda l: any(is_en_word(word) for word in l))
        has_eng=has_eng|col_has_eng

    assert ~has_eng.all()
    df=df.rename(columns=COLMAPPER)
    df['lemma']=df['nom.sg']
    for feature in ['acc.sg', 'nom.pl', 'acc.pl']:
        no_lemma = df['lemma']==''
        df.loc[no_lemma, 'lemma']=df.loc[no_lemma, feature]
    # where lemma has multiple forms, take the first one
    df['lemma']=df['lemma'].str.split().apply(lambda l: l[0])

    df.to_csv(NOUN_CSV_PATH, index=False)
    return 0

if __name__ == '__main__':
    main()