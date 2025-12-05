from src.search import rewrite_sentence
from src.parser import get_main_parser
from scripts.dataset_builder import normalize_str, normalize_ipa
from datasets import load_from_disk
import os

data_dir = os.environ.get('DATASETS')
tira_asr_dir = os.path.join(data_dir, 'tira_asr')

if __name__ == '__main__':
    dataset = load_from_disk(tira_asr_dir)
    main_lemmatizer, main_analyzer, _ = get_main_parser()
    rewritten_dataset = dataset.map(
        lambda example: {
            'rewritten_transcript': rewrite_sentence(
                normalize_str(
                    normalize_ipa(
                        example['transcription']
                    )
                ),
                main_lemmatizer=main_lemmatizer,
                main_analyzer=main_analyzer,
            )
        }
    )
    rewritten_dataset.save_to_disk(tira_asr_dir + '_rewritten')