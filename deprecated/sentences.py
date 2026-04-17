from src.constants import SENTENCES_PATH
import pandas as pd
from typing import *

ANALYSES_DF = pd.read_csv(SENTENCES_PATH, keep_default_na=False)

def get_elan_analyses() -> List[Tuple[str,str]]:
    """
    Returns:
        A list of tuples containing transcriptions, translations, and glosses from ELAN files.

    Get all analyses from the dataframe that come from ELAN files.
    """
    elan_mask = ANALYSES_DF['source']=='elan'
    transcriptions = ANALYSES_DF.loc[elan_mask, 'text'].tolist()
    translations = ANALYSES_DF.loc[elan_mask, 'Translation'].tolist()
    gloss = ANALYSES_DF.loc[elan_mask, 'Gloss'].tolist()
    return list(zip(transcriptions, translations, gloss))