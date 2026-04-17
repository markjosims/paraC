from dataclasses import dataclass, field
from typing import Literal
from src.config_utils.schema_validation import ConfigKindType

@dataclass
class EditorState:
    path: str
    kind: ConfigKindType
    data: dict = field(default_factory=dict)