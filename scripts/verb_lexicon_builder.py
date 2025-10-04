"""
Load lexical data from Excel spreadsheets and save as `.csv` files
containing data for a lexeme's root, principal parts/inflection class, and gloss.
"""

import pandas as pd
import os
from dataset_builder import DATA_DIR, EXCEL_VERBS_PATH, EXCEL_SHEET_NAME

ROOTS_OUTPATH = os.path.join(DATA_DIR, "verb_roots.csv")
ROOTS_INPATH = os.path.join(DATA_DIR, "verb_roots_new.csv")
ROOTS_FINAL_OUTPATH = os.path.join(DATA_DIR, "verb_roots_final.csv")

OLD_ROOT_COL = 'Root'
OLD_SENSE_COL = 'Translation'
OLD_FV_COL = 'Inflection class'

ROOT_COL = 'verb_root'
SENSE_COL = 'root_sense'
FV_COL = 'root_fv'

def get_roots_from_excel() -> int:
    """
    Creates a `.csv` file from Excel data containing a single row for each unique verb root
    along with all senses and inflection classes associated with that root.
    """
    df = pd.read_excel(EXCEL_VERBS_PATH, sheet_name=EXCEL_SHEET_NAME)
    get_translation_and_class = lambda row: f"{row[OLD_SENSE_COL]} ({row[OLD_FV_COL]})"
    df['old_sense']=df.apply(get_translation_and_class, axis=1)
    group_by_root = df.groupby(by=OLD_ROOT_COL)
    root2unique_senses = group_by_root['old_sense'].apply(set).apply("; ".join)
    root2unique_senses['new_sense']=''
    root2unique_senses['merge_with']=''
    root2unique_senses.to_csv(ROOTS_OUTPATH, index_label='root')

    return 0

def apply_roots_to_excel() -> int:
    """
    Loads data from `ROOTS_INPATH` and updates `root_sense` and `root_fv_class` columns
    in Excel data.
    """
    excel_df = pd.read_excel(EXCEL_VERBS_PATH, sheet_name=EXCEL_SHEET_NAME)
    roots_df = pd.read_csv(ROOTS_INPATH)

    rows_to_merge = ~roots_df['merge_with'].isna()
    root2merge = {}
    roots_df[rows_to_merge].apply(
        lambda row: root2merge.update({row['root']: row['merge_with']}),
        axis=1,
    )
    roots_df[~rows_to_merge].apply(
        lambda row: root2merge.update({row['root']: row['root']}),
        axis=1,
    )
    root2sense = {}
    root2fv = {}
    roots_df[~rows_to_merge].apply(
        lambda row: root2sense.update({row['root']: row['new_sense']}),
        axis=1,
    )
    roots_df[~rows_to_merge].apply(
        lambda row: root2fv.update({row['root']: row['inflection_class']}),
        axis=1,
    )
    
    print("Merging roots in Excel data...")
    excel_df[ROOT_COL]=excel_df[OLD_ROOT_COL].map(root2merge)
    print("Adding senses and FV labels to Excel data...")
    excel_df[SENSE_COL]=excel_df[ROOT_COL].map(root2sense)
    excel_df[FV_COL]=excel_df[ROOT_COL].map(root2fv)

    excel_df.to_excel(EXCEL_VERBS_PATH, sheet_name=EXCEL_SHEET_NAME, index=False)

    roots_final_df = excel_df[[ROOT_COL, SENSE_COL, FV_COL]]
    roots_final_df = roots_final_df.drop_duplicates().dropna()
    roots_final_df.to_csv(ROOTS_FINAL_OUTPATH, index=False)


    return 0

if __name__ == '__main__':
    # get_roots_from_excel()
    apply_roots_to_excel()