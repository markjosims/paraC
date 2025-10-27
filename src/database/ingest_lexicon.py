from src.constants import NOUN_FEATURE_ABBREVIATIONS
from src.lexicon import NOUNS_DF, VERBS_DF, ADJECTIVES_DF, UNINFLECTED_WORDS_DF
from src.database.database import engine, SessionLocal, Base
from tqdm import tqdm
import pandas as pd
from src.database.models import Lexeme
from sqlalchemy.orm import Session

def ingest_verbs(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_verb = db.query(Lexeme).filter(
            Lexeme.root == row['verb_root'],
            Lexeme.part_of_speech == 'verb',
        ).first()
        if existing_verb:
            continue

        new_lexeme = Lexeme(
            root=row['verb_root'],
            part_of_speech='verb',
            gloss=row['root_sense'],
            lexical_info={"fv_class": row['root_fv']}
        )
        db.add(new_lexeme)
        num_added += 1
        db.flush()
    db.commit()
    print(f"{num_added} verbs added successfully")

def ingest_nouns(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_noun = db.query(Lexeme).filter(
            Lexeme.root == row['lemma'],
            Lexeme.part_of_speech == 'noun',
        ).first()
        if existing_noun:
            continue

        noun_features = {abbr: row[abbr] for abbr in NOUN_FEATURE_ABBREVIATIONS if row[abbr]!=''}
        new_lexeme = Lexeme(
            root=row['lemma'],
            part_of_speech='noun',
            gloss=row['gloss'],
            lexical_info=noun_features,
        )
        db.add(new_lexeme)
        num_added += 1
        db.flush()
    db.commit()
    print(f"{num_added} nouns added successfully")

def ingest_adjectives(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_adj = db.query(Lexeme).filter(
            Lexeme.root == row['root'],
            Lexeme.part_of_speech == 'adjective',
        ).first()
        if existing_adj:
            continue

        new_lexeme = Lexeme(
            root=row['root'],
            part_of_speech='adjective',
            gloss=row['gloss'],
            lexical_info={},
        )
        db.add(new_lexeme)
        num_added += 1
        db.flush()
    db.commit()
    print(f"{num_added} adjectives added successfully")

def ingest_uninflected_words(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_lexeme = db.query(Lexeme).filter(
            Lexeme.root == row['word'],
            Lexeme.part_of_speech == row['part_of_speech'],
        ).first()
        if existing_lexeme:
            continue

        new_lexeme = Lexeme(
            root=row['word'],
            part_of_speech=row['part_of_speech'],
            gloss=row['gloss'],
            lexical_info={},
        )
        db.add(new_lexeme)
        num_added += 1
        db.flush()
    db.commit()
    print(f"{num_added} uninflected words added successfully")

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print(f"Ingesting verb lexical data...")
        ingest_verbs(VERBS_DF, db)

        print(f"Ingesting noun lexical data...")
        ingest_nouns(NOUNS_DF, db)

        print(f"Ingesting adjective lexical data...")
        ingest_adjectives(ADJECTIVES_DF, db)

        print(f"Ingesting uninflected word lexical data...")
        ingest_uninflected_words(UNINFLECTED_WORDS_DF, db)

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Rolling back changes to database.")
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    main()