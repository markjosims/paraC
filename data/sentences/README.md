
# tira_morph
Dataset of unique Tira sentences for purposes of training morphological segmentation.
Uses same textnorm steps as `tira_asr`. Contains 12334 unique sentences for
a total of 33906 words (9589 unique words) averaging
2.7489865412680397 words per sentence.

## Files
- sentences.csv: final dataset of unique Tira sentences with associated glosses and translations
- char_replacements.json: dictionary of character replacements used in text normalization
- tira_asr_unique_chars.json: list of all expected characters in Tira IPA transcriptions
- english_words.txt: list of all English words detected and removed during text normalization
- tira_words.txt: list of all Tira words detected in the dataset before text normalization
- tira_words_normalized.txt: list of all Tira words found in the dataset with text normalization applied

## Preprocessing log
- 29007 non-NaN transcriptions in dataset
- 13148 non-duplicate transcriptions in dataset
- 11121 valid rows after dropping unannotated and ASR-generated transcriptions
- added 1929 rows from excel data
- removed 72 ungrammatical rows
- applied NFKD unicode normalization to text, set to lowercase and removed punctuation
- removed 398 rows with no tone marked, 12580 rows remaining
- removed 246 rows with English words, 12334 rows remaining
- saved all detected English words to data/elan/english_words and Tira words to data/elan/tira_words.txt
- removed tone words (e.g. HLL, LHL, LLHH) from transcription, 14 rows affected
- Checked that only expected IPA chars are found in dataset, as defined by JSON file tira_asr_unique_chars.json