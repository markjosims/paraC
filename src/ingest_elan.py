import pandas as pd
from src.database import engine, SessionLocal, Base
from src.constants import ANALYSES_PATH
from src.models import Sentence, Wordform, SentenceWord
from sqlalchemy.orm import Session
from tqdm import tqdm

def ingest_data(df: pd.DataFrame, db: Session):
    num_rows = len(df)

    wordform_cache = {}

    for i, row in tqdm(df.iterrows(), total=num_rows):
        text = row['text']
        new_sentence = Sentence(
            elan_sentence=text,
            updated_sentence=text,
            translation=row['Translation'],
            elan_gloss=row['Gloss'],
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
        print(f"Reading ELAN data from {ANALYSES_PATH}")
        df = pd.read_csv(ANALYSES_PATH, keep_default_na=False)
        elan_mask = df['source']=='elan'
        df=df[elan_mask]
        ingest_data(df, db)

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Rolling back changes to database.")
    finally:
        db.close()

    return 0

if __name__ == '__main__':
    main()