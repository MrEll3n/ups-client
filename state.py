# state.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from protocol import PROTOCOL_MAGIC, Message


class SceneId(Enum):
    CONNECT = 1
    LOBBY = 2
    GAME = 3
    AFTER_MATCH = 4


@dataclass
class AppState:
    scene: SceneId = SceneId.CONNECT
    username: str = ""
    user_id: str = ""
    lobby_name: str = ""
    in_lobby: bool = False
    in_game: bool = False

    # Game state
    last_move: str = ""
    waiting_for_opponent: bool = False

    # NOVÉ: Pro Reconnect a synchronizaci
    p1_wins: int = 0
    p2_wins: int = 0
    last_server_contact: float = 0.0  # Čas posledního přijatého paketu

    round_result_visible: bool = False
    round_result_ttl: float = 0.0
    last_round: str = ""
    last_match: str = ""

    waiting_for_rematch: bool = False
    last_match_winner_id: int = 0
    last_match_p1wins: int = 0
    last_match_p2wins: int = 0

    toast: str = "Welcome."
    toast_ttl: float = 3.0
    debug_visible: bool = False
    log: List[str] = field(default_factory=list)


def toast(state: AppState, msg: str, ttl: float = 3.0) -> None:
    state.toast = msg
    state.toast_ttl = ttl


W, H = 1100, 700
M = 22
TOPBAR = (M, M, W - 2 * M, 56)
CENTER_CARD = ((W - 520) // 2, (H - 360) // 2, 520, 360)
BOTTOM_HINT = (M, H - 90, W - 2 * M, 68)


def wire_str(type_desc: str, *params: str) -> str:
    return f"{PROTOCOL_MAGIC}|{type_desc}|{'|'.join(params)}|"


def log_tx(state: AppState, type_desc: str, *params: str) -> None:
    line = f"[TX] {wire_str(type_desc, *params)}"
    state.log.append(line)


def log_rx(state: AppState, msg: Message) -> None:
    line = f"[RX] {msg}"
    state.log.append(line)


def log_sys(state: AppState, msg: str) -> None:
    state.log.append(f"[SYS] {msg}")


def log_err(state: AppState, msg: str) -> None:
    state.log.append(f"[ERR] {msg}")
