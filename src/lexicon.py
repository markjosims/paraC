from loguru import logger

from src.launcher import YAML_DIR
from src.yaml_utils.yaml_server import get_yaml_data_safe
import pandas as pd
import os
import numpy as np


def load_lexicon_df(lexicon_basename: str) -> pd.DataFrame:
    lexicon_dir = os.path.join(YAML_DIR, "Lexicon", "Wordlists")
    lexicon_stem = os.path.splitext(lexicon_basename.removeprefix("$"))[0]

    csv_path = os.path.join(lexicon_dir, lexicon_stem + ".csv")
    xlsx_path = os.path.join(lexicon_dir, lexicon_stem + ".xlsx")

    if os.path.exists(xlsx_path):
        return pd.read_excel(xlsx_path, keep_default_na=False)
    elif os.path.exists(csv_path):
        return pd.read_csv(csv_path, keep_default_na=False)
    else:
        return init_lexicon(xlsx_path)


def init_lexicon(lexicon_path: str) -> pd.DataFrame:
    part_of_speech = get_yaml_data_safe(yaml_basename=lexicon_path, kind="PartOfSpeech")
    lexical_features = part_of_speech.get("lexical_features", [])
    principal_parts = part_of_speech.get("principal_parts", [])
    df = pd.DataFrame(columns=["root", "gloss"] + lexical_features + principal_parts)
    df.to_excel(lexicon_path, index=False)
    return lexicon_path


def get_roots(lexicon_basename: str) -> list[str]:
    lexicon_df = load_lexicon_df(lexicon_basename)
    return lexicon_df["root"].tolist()


def get_roots_with_lexical_features(
    lexicon_basename: str, lexical_features: list[tuple[str, str]]
) -> list[str]:
    df = load_lexicon_df(lexicon_basename)
    filter = pd.Series([True] * len(df), index=df.index)
    for feature, value in lexical_features:
        filter &= df[feature] == value

    filtered_df = df[filter]
    return filtered_df["root"].tolist()


def get_features_for_root(
    lexicon_basename: str, root: str
) -> tuple[tuple[str, str], ...]:
    df = load_lexicon_df(lexicon_basename)
    part_of_speech = get_yaml_data_safe(yaml_basename=lexicon_basename, kind="PartOfSpeech")
    lexical_features = part_of_speech.get("lexical_features", [])
    row = df[df["root"] == root]
    if not row.empty:
        return tuple(row.iloc[0][lexical_features].items())
    return {}


def get_principle_part_for_root(
    lexicon_basename: str,
    root: str,
    principal_part: str,
    fallback_to_root: bool = True,
) -> str | None:
    df = load_lexicon_df(lexicon_basename)
    row = df[df["root"] == root]
    if not row.empty:
        principle_part = row.iloc[0][principal_part]
        if not principle_part and fallback_to_root:
            return root
        return principle_part
    logger.exception(f"Root not found: {root} in lexicon: {lexicon_basename}")
    return None


def get_principle_part_for_all_roots(
    lexicon_basename: str, principal_part: str, fallback_to_root: bool = True
) -> list[str]:
    df = load_lexicon_df(lexicon_basename)
    if fallback_to_root:
        return (
            df[principal_part]
            .replace("", np.nan)
            .fillna(df["root"])
            .tolist()
        )
    return df[principal_part].tolist()

def get_gloss_for_root(lexicon_basename: str, root: str) -> str | None:
    df = load_lexicon_df(lexicon_basename)
    row = df[df["root"] == root]
    if not row.empty:
        return row.iloc[0]["gloss"]
    return None