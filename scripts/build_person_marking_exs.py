import pandas as pd
from dataset_builder import normalize_ipa

PERSON_MARKING_EXCEL_PATH = 'data/excel/tira_person_marking.xlsx'
EXCEL_TABS = [
    'Ventive Perfective',
    'Ventive Imperfective',
    'Andative Perfective',
    'Andative Imperfective',
]
LABEL_MAP = {
    '1SG': '1sg',
    '2SG': '2sg',
    '3SG (human)': '3sg',
    '1DUAL': '1du.incl',
    '1INCPL': '1pl.incl',
    '1EXCLPL': '1pl.excl',
    '2PL': '2pl',
    '3PL (human)': '3pl',
}
CSV_PATH = 'data/test_cases/gold_person_marking.csv'

def get_forms_for_tam(df: pd.DataFrame, tamd: str) -> pd.DataFrame:
    tamd = tamd.lower()
    examples = []
    features = {}
    if 'perfective' in tamd:
        features['tam'] = 'perfective'
    elif 'imperfective' in tamd:
        features['tam'] = 'imperfective'
    if 'ventive' in tamd:
        features['deixis'] = 'ventive'
    elif 'andative' in tamd:
        features['deixis'] = 'itive'
    for _, row in df.iterrows():
        subj = row['SUBJ/OBJ']
        if subj not in LABEL_MAP:
            continue
        for obj in LABEL_MAP.keys():
            cell = row[obj]
            if pd.isna(cell) or 'reflexive' in cell.lower() or 'impossible' in cell.lower():
                continue
            form = normalize_ipa(cell.strip())
            example_features = features.copy()
            if 'c' in form:
                example_features['root']='ɲɛlac'
                example_features['gloss']='tickle'
            else:
                example_features['root']='vəlɛð'
                example_features['gloss']='pull'
            example_features['subj'] = LABEL_MAP[subj]
            example_features['obj'] = LABEL_MAP[obj]
            example_features['form'] = form
            examples.append(example_features)
    return pd.DataFrame(examples)


def main():
    all_examples = []
    for tab in EXCEL_TABS:
        df = pd.read_excel(PERSON_MARKING_EXCEL_PATH, sheet_name=tab)
        processed_df = get_forms_for_tam(df, tamd=tab)
        all_examples.append(processed_df)
    final_df = pd.concat(all_examples, ignore_index=True)
    final_df.to_csv(CSV_PATH, index=False)

if __name__ == '__main__':
    main()