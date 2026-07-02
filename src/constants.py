import os
from dotenv import load_dotenv

# filepaths
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        __file__
    )
)

SCHEMA_DIR = os.path.join(PROJECT_ROOT, 'schemas')

load_dotenv(os.path.join(PROJECT_ROOT, "parC.env"), override=True)


def get_yaml_dir():
    return os.environ.get("YAML_DIR") or os.path.join(PROJECT_ROOT, "yaml", "spanish-example")

# pynini constants


# copied from https://github.com/kylebgorman/pynini/blob/27ce19048193358cd362a4de6b157cb43ab6e2eb/extensions/stringcompile.h#L69
# a bit hacky: since ... TODO check if we really need to include EOS/BOS in symbol table
BOS_INDEX = 0xF8FE
EOS_INDEX = 0xF8FF
