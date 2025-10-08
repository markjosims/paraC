from src.constants import NOUNS_PATH, VERB_ROOTS_PATH, NOUN_FEATURE_ABBREVIATIONS
from src.database import engine, SessionLocal, Base
from tqdm import tqdm
import pandas as pd
from src.models import Lexeme
from sqlalchemy.orm import Session

def ingest_verbs(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    for i, row in tqdm(df.iterrows(), total=num_rows):
        new_lexeme = Lexeme(
            root=row['verb_root'],
            part_of_speech='verb',
            gloss=row['root_sense'],
            lexical_info={"fv_class": row['root_fv']}
        )
        db.add(new_lexeme)
        db.flush()
    db.commit()
    print("Ingestion of verbs successful")

def ingest_nouns(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    for i, row in tqdm(df.iterrows(), total=num_rows):
        noun_features = {abbr: row[abbr] for abbr in NOUN_FEATURE_ABBREVIATIONS if row[abbr]!=''}
        new_lexeme = Lexeme(
            root=row['lemma'],
            part_of_speech='noun',
            gloss=row['gloss'],
            lexical_info=noun_features,
        )
        db.add(new_lexeme)
        db.flush()
    db.commit()
    print("Ingestion of nouns successful")

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print(f"Reading verb lexical data from {VERB_ROOTS_PATH}")
        verb_df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
        ingest_verbs(verb_df, db)

        print(f"Reading noun lexical data from {NOUNS_PATH}")
        noun_df = pd.read_csv(NOUNS_PATH, keep_default_na=False)
        ingest_nouns(noun_df, db)

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Rolling back changes to database.")
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    main()