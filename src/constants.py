import os

# filepaths
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        __file__
    )
)

CONFIG_ROOT = os.path.join(PROJECT_ROOT, "config")
EXAMPLE_CONFIG_DIR = os.path.join(CONFIG_ROOT, "example")
TIRA_CONFIG_DIR = os.path.join(CONFIG_ROOT, "tira")
SCHEMA_DIR = os.path.join(PROJECT_ROOT, 'schemas')

# pynini constants

# copied from https://github.com/kylebgorman/pynini/blob/27ce19048193358cd362a4de6b157cb43ab6e2eb/extensions/stringcompile.h#L69
# a bit hacky: since ... TODO check if we really need to include EOS/BOS in symbol table
BOS_INDEX = 0xF8FE
EOS_INDEX = 0xF8FF