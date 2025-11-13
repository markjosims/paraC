"""
For every sentence in the database, drop all associated parses and re-generate them.
Preserve parses that have been manually set by users.
"""

from src.database.init_database import engine, SessionLocal, Base
from src.database.models import Sentence, Wordform, SentenceWord, Parse, Lexeme
from src.database.ingest_elan import add_parses_for_word
from sqlalchemy.orm import Session
from tqdm import tqdm
import traceback
import math
from typing import *

BATCH_SIZE = 100

def update_parses_for_sentence(db: Session, sentence: Sentence, chosen_parses: Set[int]):
    sentence_words = db.query(SentenceWord).filter(SentenceWord.sentence_id == sentence.id).all()
    for sentence_word in sentence_words:
        wordform_id = sentence_word.wordform_id
        existing_parses = db.query(Parse).filter(Parse.wordform_id == wordform_id).all()
        for parse in existing_parses:
            if parse.id not in chosen_parses:
                db.delete(parse)

        wordform = db.query(Wordform).filter(Wordform.id == sentence_word.wordform_id).first()
        if not wordform:
            print(f"Warning: Wordform not found for SentenceWord ID {sentence_word.id}")
            continue

        add_parses_for_word(db, wordform.text, wordform)

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("Starting parse update...")
        sentences = db.query(Sentence).all()
        chosen_parses = db.query(
            SentenceWord.chosen_parse_id
        ).filter(
            SentenceWord.chosen_parse_id.isnot(None)
        ).all()
        # get id from tuple and cast to set
        chosen_parses = {parse[0] for parse in chosen_parses}
        num_batches = math.ceil(len(sentences) / BATCH_SIZE)
        for batch_i in tqdm(range(num_batches), desc="Ingesting batches"):
            start_idx = batch_i * BATCH_SIZE
            end_idx = min((batch_i + 1) * BATCH_SIZE, len(sentences))
            batch_sentences = sentences[start_idx:end_idx]
            for sentence in tqdm(batch_sentences, desc=f"Processing batch {batch_i+1}/{num_batches}"):
                update_parses_for_sentence(db, sentence, chosen_parses)
            db.commit()
        print("Parse update successful")

    except Exception as e:
        print("Error updating parses:")
        traceback.print_exc()
        print("Rolling back changes to database...")
        return
    finally:
        db.close()

if __name__ == "__main__":
    main()