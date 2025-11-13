from src.constants import NOUN_FEATURE_ABBREVIATIONS
from src.lexicon import (
    get_all_noun_data, get_all_verb_data,
    get_all_adjective_data, get_uninflected_word_data
)
from src.database.init_database import engine, SessionLocal, Base
from tqdm import tqdm
import pandas as pd
from src.database.models import Lexeme
from sqlalchemy.orm import Session

def ingest_verbs(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    num_existing = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_verb = db.query(Lexeme).filter(
            Lexeme.root == row['verb_root'],
            Lexeme.part_of_speech == 'verb',
        ).first()
        if existing_verb:
            num_existing += 1
            continue

        new_lexeme = Lexeme(
            root=row['verb_root'],
            part_of_speech='verb',
            gloss=row['gloss'],
            lexical_info={"fv_class": row['fv']}
        )
        db.add(new_lexeme)
        num_added += 1
    # special case: add TAMD aux
    existing_tamd = db.query(Lexeme).filter(
        Lexeme.root == 'ŋgá',
        Lexeme.part_of_speech == 'verb',
    ).first()
    if not existing_tamd:
        tamd_lexeme = Lexeme(
            root='ŋgá',
            part_of_speech='verb',
            gloss='aux',
            lexical_info={},
        )
        db.add(tamd_lexeme)
        num_added += 1
    else:
        num_existing += 1
    db.commit()
    print(f"{num_added} verbs added successfully, {num_existing} verbs already present")

def ingest_nouns(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    num_existing = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_noun = db.query(Lexeme).filter(
            Lexeme.root == row['lemma'],
            Lexeme.part_of_speech == 'noun',
        ).first()
        if existing_noun:
            num_existing += 1
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
    db.commit()
    print(f"{num_added} nouns added successfully, {num_existing} nouns already present")

def ingest_adjectives(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    num_existing = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_adj = db.query(Lexeme).filter(
            Lexeme.root == row['root'],
            Lexeme.part_of_speech == 'adjective',
        ).first()
        if existing_adj:
            num_existing += 1
            continue

        new_lexeme = Lexeme(
            root=row['root'],
            part_of_speech='adjective',
            gloss=row['gloss'],
            lexical_info={},
        )
        db.add(new_lexeme)
        num_added += 1
    db.commit()
    print(f"{num_added} adjectives added successfully, {num_existing} adjectives already present")

def ingest_uninflected_words(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    num_added = 0
    num_existing = 0
    for i, row in tqdm(df.iterrows(), total=num_rows):
        existing_lexeme = db.query(Lexeme).filter(
            Lexeme.root == row['word'],
            Lexeme.part_of_speech == row['part_of_speech'],
        ).first()
        if existing_lexeme:
            num_existing += 1
            continue

        new_lexeme = Lexeme(
            root=row['word'],
            part_of_speech=row['part_of_speech'],
            gloss=row['gloss'],
            lexical_info={},
        )
        db.add(new_lexeme)
        num_added += 1
    db.commit()
    print(f"{num_added} uninflected words added successfully, {num_existing} uninflected words already present")

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print(f"Ingesting verb lexical data...")
        ingest_verbs(get_all_verb_data(return_type=pd.DataFrame), db)

        print(f"Ingesting noun lexical data...")
        ingest_nouns(get_all_noun_data(return_type=pd.DataFrame), db)

        print(f"Ingesting adjective lexical data...")
        ingest_adjectives(get_all_adjective_data(return_type=pd.DataFrame), db)

        print(f"Ingesting uninflected word lexical data...")
        ingest_uninflected_words(get_uninflected_word_data(return_type=pd.DataFrame), db)

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Rolling back changes to database.")
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    main()