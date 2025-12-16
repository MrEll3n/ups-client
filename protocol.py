from dataclasses import dataclass
from typing import List, Optional

# =============================
# Protocol config
# =============================

PROTOCOL_MAGIC = "MRLLN"

# =============================
# Protocol helpers
# =============================


@dataclass(frozen=True)
class Message:
    type_desc: str
    params: List[str]

    def __str__(self) -> str:
        return f"{PROTOCOL_MAGIC}|{self.type_desc}|{'|'.join(self.params)}|"


def encode(type_desc: str, *params: str) -> bytes:
    safe = [p.replace("\n", " ").replace("\r", " ") for p in params]
    line = f"{PROTOCOL_MAGIC}|{type_desc}|{'|'.join(safe)}|\n"
    return line.encode("utf-8")


def try_decode_line(line: str) -> Optional[Message]:
    line = line.strip("\r\n")
    if not line:
        return None

    parts = line.split("|")
    if parts and parts[-1] == "":
        parts = parts[:-1]

    if len(parts) < 2:
        return None

    magic = parts[0].strip()
    if magic != PROTOCOL_MAGIC:
        raise ValueError(f"Invalid protocol magic: {magic!r}")

    type_desc = parts[1].strip()
    if not type_desc:
        return None

    return Message(type_desc=type_desc, params=parts[2:])
