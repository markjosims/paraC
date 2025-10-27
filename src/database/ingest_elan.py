import pandas as pd
from src.database.database import engine, SessionLocal, Base
from src.constants import SENTENCES_PATH
from src.database.models import Sentence, Wordform, SentenceWord, Parse, Lexeme
from sqlalchemy.orm import Session
from tqdm import tqdm
from src.search import search_parse
import traceback
from random import choice
import math

ANNOTATORS = ['mark', 'jenny', 'gordon', 'james']
BATCH_SIZE = 100

def ingest_data(df: pd.DataFrame, db: Session):
    num_rows = len(df)

    wordform_cache = {}

    for _, row in tqdm(df.iterrows(), total=num_rows):
        text = row['text']
        annotator = choice(ANNOTATORS)
        existing_sentence = db.query(Sentence).filter(Sentence.elan_sentence == text).first()
        if existing_sentence:
            continue

        new_sentence = Sentence(
            elan_sentence=text,
            updated_sentence=text,
            translation=row['Translation'],
            elan_gloss=row['Gloss'],
            assigned_to=annotator,
        )
        db.add(new_sentence)
        db.flush()

        words = text.strip().split()
        for word_i, word_str in enumerate(words):
            if word_str in wordform_cache:
                wordform = wordform_cache[word_str]
            else:
                wordform = db.query(Wordform).filter(
                    Wordform.text == word_str
                ).first()
                if not wordform:
                    wordform = Wordform(text=word_str)
                    db.add(wordform)
                    db.flush()
                wordform_cache[word_str] = wordform

                parses = search_parse(word_str)
                for parse, weight in parses:
                    part_of_speech = parse['part_of_speech']
                    lexeme = db.query(Lexeme).filter(
                        Lexeme.root == parse['root'],
                        Lexeme.part_of_speech == part_of_speech,
                    ).first()
                    if not lexeme:
                        raise ValueError(f"Lexeme not found for root {parse['root']} and part_of_speech {part_of_speech}")

                    new_parse = Parse(
                        wordform_id=wordform.id,
                        lexeme_id=lexeme.id,
                        updated_form=parse['form'],
                        analysis={k: v for k, v in parse.items() if k !='form'},
                        edits=weight,
                    )
                    db.add(new_parse)
                db.flush()
        
            sentence_word_link = SentenceWord(
                sentence_id=new_sentence.id,
                wordform_id=wordform.id,
                position=word_i,
            )
            db.add(sentence_word_link)
    db.commit()
    print("Data ingestion successful")


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print(f"Reading ELAN data from {SENTENCES_PATH}")
        df = pd.read_csv(SENTENCES_PATH, keep_default_na=False)
        elan_mask = df['source']=='elan'
        df = df[elan_mask]
        df = df.drop_duplicates(subset=['text'])
        num_batches = math.ceil(len(df) / BATCH_SIZE)
        for batch_i in tqdm(range(num_batches), desc="Ingesting batches"):
            start_idx = batch_i * BATCH_SIZE
            end_idx = min((batch_i + 1) * BATCH_SIZE, len(df))
            batch_df = df.iloc[start_idx:end_idx]
            ingest_data(batch_df, db)
        elan_mask = df['source']=='elan'
        df=df[elan_mask]
        ingest_data(df, db)

    except Exception as e:
        print(f"Error occurred: {e}")
        traceback.print_exc()
        print("Rolling back changes to database.")
    finally:
        db.close()

    return 0

if __name__ == '__main__':
    main()