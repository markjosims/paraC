import os

VERB_ROOTS_PATH = 'data/verb_roots_final.csv'
INFLECTED_VERBS_PATH = 'data/inflected_verb_forms.csv'

FST_DIR = "fst/"
ROOT2GLOSS_FST_PATH = os.path.join(FST_DIR, "root2gloss.fst")
ROOT2FV_FST_PATH = os.path.join(FST_DIR, "root2fv.fst")