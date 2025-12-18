from typing import Optional, Tuple

import pygame

from network import TcpLineClient
from protocol import Message
from state import (
    BOTTOM_HINT,
    CENTER_CARD,
    TOPBAR,
    AppState,
    H,
    SceneId,
    W,
    log_err,
    log_sys,
    log_tx,
    toast,
)
from ui_components import HUDButton, InputField, MoveButton

# =============================
# Helpers
# =============================


def move_letter_to_name(letter: str) -> str:
    l = (letter or "").strip().upper()
    if l == "R":
        return "Rock"
    if l == "P":
        return "Paper"
    if l == "S":
        return "Scissors"
    return ""


def safe_first_char(s: Optional[str], fallback: str = "?") -> str:
    if not s:
        return fallback
    return s[0]


def winner_label(state: AppState, winner_id_str: str) -> str:
    """
    Map winner id (string) to a UI label.
    If server provided p1Id/p2Id + names, show name; else show raw id.
    """
    try:
        wid = int(winner_id_str)
    except Exception:
        return winner_id_str or "?"

    # Prefer names if available
    if getattr(state, "p1_id", 0) == wid and getattr(state, "p1_name", ""):
        return state.p1_name
    if getattr(state, "p2_id", 0) == wid and getattr(state, "p2_name", ""):
        return state.p2_name

    # If id matches none (or names missing), fall back to id
    return str(wid)


def player_label(state: AppState, idx: int) -> str:
    """
    idx: 1 or 2
    """
    if idx == 1:
        return state.p1_name or "P1"
    if idx == 2:
        return state.p2_name or "P2"
    return "P?"


# =============================
# Rendering helpers
# =============================


def draw_background(surf: pygame.Surface) -> None:
    w, h = surf.get_size()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(10 + 10 * t)
        g = int(10 + 12 * t)
        b = int(18 + 22 * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))

    vignette = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(vignette, (0, 0, 0, 120), pygame.Rect(0, 0, w, h))
    pygame.draw.rect(
        vignette,
        (0, 0, 0, 0),
        pygame.Rect(40, 40, w - 80, h - 80),
        border_radius=30,
    )
    surf.blit(vignette, (0, 0))


def draw_panel(
    surf: pygame.Surface,
    rect_data: Tuple[int, int, int, int],
    title: str,
    font_title: pygame.font.Font,
) -> None:
    rect = pygame.Rect(rect_data)
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (18, 18, 24, 220), panel.get_rect(), border_radius=18)
    pygame.draw.rect(
        panel, (120, 120, 150, 180), panel.get_rect(), width=1, border_radius=18
    )
    surf.blit(panel, (rect.x, rect.y))

    t = font_title.render(title, True, (245, 245, 255))
    surf.blit(t, (rect.x + 16, rect.y + 12))


def draw_toast(
    screen: pygame.Surface,
    rect_parent_data: Tuple[int, int, int, int],
    font: pygame.font.Font,
    state: AppState,
) -> None:
    if not state.toast:
        return

    rect_parent = pygame.Rect(rect_parent_data)

    x_pos = rect_parent.x + 10
    y_pos = rect_parent.y + rect_parent.height + 6
    w_pos = rect_parent.width - 20
    h_pos = 36

    toast_rect = pygame.Rect(x_pos, y_pos, w_pos, h_pos)

    overlay = pygame.Surface((toast_rect.width, toast_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (18, 18, 22, 220), overlay.get_rect(), border_radius=12)
    pygame.draw.rect(
        overlay, (160, 160, 190, 180), overlay.get_rect(), width=1, border_radius=12
    )
    screen.blit(overlay, (toast_rect.x, toast_rect.y))

    t = font.render(state.toast, True, (245, 245, 255))
    screen.blit(t, t.get_rect(center=toast_rect.center))


def draw_debug(
    screen: pygame.Surface, font: pygame.font.Font, state: AppState, w: int, h: int
) -> None:
    if not state.debug_visible:
        return

    r = pygame.Rect(22, 95, w - 44, h - 125)
    overlay = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (0, 0, 0, 200), overlay.get_rect(), border_radius=18)
    pygame.draw.rect(
        overlay, (140, 140, 170, 160), overlay.get_rect(), width=1, border_radius=18
    )
    screen.blit(overlay, (r.x, r.y))

    lines = state.log[-28:]
    y = r.y + 14
    for ln in lines:
        t = font.render(ln, True, (230, 230, 240))
        screen.blit(t, (r.x + 14, y))
        y += 18


def draw_waiting_screen(
    screen: pygame.Surface,
    rect_data: Tuple[int, int, int, int],
    move: str,
    font_xl: pygame.font.Font,
    font_b: pygame.font.Font,
    font_move: pygame.font.Font,
) -> None:
    rect = pygame.Rect(rect_data)

    title = font_b.render("Waiting for opponent...", True, (245, 245, 255))
    screen.blit(title, title.get_rect(center=(rect.centerx, rect.y + 70)))

    if move:
        # Big letter
        m = font_xl.render(move, True, (255, 255, 255))
        screen.blit(m, m.get_rect(center=(rect.centerx, rect.centery - 6)))

        # Name under it
        mv_name = move_letter_to_name(move) or "Your move"
        sub = font_move.render(mv_name, True, (180, 180, 200))
        screen.blit(sub, sub.get_rect(center=(rect.centerx, rect.centery + 48)))


def draw_round_result(
    screen: pygame.Surface,
    rect_data: Tuple[int, int, int, int],
    round_str: str,
    font_xl: pygame.font.Font,
    font_b: pygame.font.Font,
    state: AppState,
) -> None:
    rect = pygame.Rect(rect_data)

    parts = round_str.split("|")
    # expected: winner_id|p1Move|p2Move
    winner_id = parts[0].strip() if len(parts) >= 1 else "?"
    p1m = parts[1].strip() if len(parts) >= 2 else "-"
    p2m = parts[2].strip() if len(parts) >= 3 else "-"

    title = font_b.render("ROUND RESULT", True, (245, 245, 255))
    screen.blit(title, title.get_rect(center=(rect.centerx, rect.y + 60)))

    # Winner line (prefer name if known)
    w_label = winner_label(state, winner_id)
    winner = font_b.render(f"Winner: {w_label}", True, (200, 200, 220))
    screen.blit(winner, winner.get_rect(center=(rect.centerx, rect.y + 110)))

    mid_y = rect.centery + 10
    left_center = (rect.x + rect.width // 4, mid_y)
    right_center = (rect.x + 3 * rect.width // 4, mid_y)

    pygame.draw.line(
        screen,
        (80, 80, 100),
        (rect.centerx, rect.y + 90),
        (rect.centerx, rect.bottom - 60),
        2,
    )

    # Left (P1)
    lbl_p1 = font_b.render(player_label(state, 1), True, (200, 200, 200))
    screen.blit(lbl_p1, lbl_p1.get_rect(center=(left_center[0], rect.y + 110)))

    mv1 = font_xl.render(safe_first_char(p1m), True, (255, 255, 255))
    screen.blit(mv1, mv1.get_rect(center=(left_center[0], mid_y)))

    full1 = font_b.render(
        move_letter_to_name(p1m) or (p1m or "-"), True, (150, 150, 170)
    )
    screen.blit(full1, full1.get_rect(center=(left_center[0], mid_y + 40)))

    # Right (P2)
    lbl_p2 = font_b.render(player_label(state, 2), True, (200, 200, 200))
    screen.blit(lbl_p2, lbl_p2.get_rect(center=(right_center[0], rect.y + 110)))

    mv2 = font_xl.render(safe_first_char(p2m), True, (255, 255, 255))
    screen.blit(mv2, mv2.get_rect(center=(right_center[0], mid_y)))

    full2 = font_b.render(
        move_letter_to_name(p2m) or (p2m or "-"), True, (150, 150, 170)
    )
    screen.blit(full2, full2.get_rect(center=(right_center[0], mid_y + 40)))

    ttl = int(state.round_result_ttl + 0.9)
    hint = font_b.render(f"Next screen in {ttl}...", True, (120, 120, 140))
    screen.blit(hint, hint.get_rect(center=(rect.centerx, rect.bottom - 30)))


# =============================
# Scenes
# =============================


class ConnectScene:
    def __init__(self, client: TcpLineClient, state: AppState, fonts):
        self.client = client
        self.state = state
        self.font, self.font_b, self.font_xl, self.font_move = fonts

        cc_rect = pygame.Rect(CENTER_CARD)
        x = cc_rect.x + 28
        w = cc_rect.width - 56
        y0 = cc_rect.y + 96

        self.inp_host = InputField(pygame.Rect(x, y0, w, 42), "IP / Host")
        self.inp_port = InputField(pygame.Rect(x, y0 + 54, w, 42), "Port")
        self.inp_name = InputField(pygame.Rect(x, y0 + 108, w, 42), "Nickname")

        self.inp_host.text = self.client.host
        self.inp_port.text = str(self.client.port)

        self.btn_connect = HUDButton(pygame.Rect(x, y0 + 168, w, 48), "CONNECT")

    def _send(self, type_desc: str, *params: str) -> None:
        try:
            self.client.send(type_desc, *params)
            log_tx(self.state, type_desc, *params)
        except Exception as ex:
            log_err(self.state, f"Send failed: {ex}")

    def _connect_and_autologin(self) -> None:
        host = self.inp_host.text.strip() or "127.0.0.1"
        port_txt = self.inp_port.text.strip() or "10000"
        nickname = self.inp_name.text.strip()

        if not nickname:
            toast(self.state, "Enter nickname first.", 2.5)
            return

        try:
            port = int(port_txt)
        except ValueError:
            toast(self.state, "Port must be a number.", 2.5)
            return

        try:
            self.client.host = host
            self.client.port = port
            if not self.client.connected:
                self.client.connect()
                log_sys(self.state, f"Connected to {host}:{port}")
                toast(self.state, f"Connected to {host}:{port}", 2.0)

            self.state.username = nickname
            self._send("REQ_LOGIN", nickname)
            toast(self.state, "Logging in…", 2.0)

        except Exception as ex:
            log_err(self.state, f"Connect/Login failed: {ex}")
            toast(self.state, f"Connect/Login failed: {ex}", 4.0)

    def handle_event(self, e: pygame.event.Event) -> None:
        self.inp_host.handle(e)
        self.inp_port.handle(e)
        self.inp_name.handle(e)

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_connect.hit(e.pos):
                self._connect_and_autologin()

    def on_message(self, msg: Message) -> Optional[SceneId]:
        if msg.type_desc == "RES_LOGIN_OK":
            self.state.user_id = msg.params[0] if msg.params else ""
            toast(self.state, f"Logged in (id={self.state.user_id})", 2.5)
            self.state.scene = SceneId.LOBBY
            return SceneId.LOBBY

        if msg.type_desc == "RES_LOGIN_FAIL":
            toast(self.state, "Login failed.", 3.0)
            return None

        if msg.type_desc == "RES_PING":
            if msg.params:
                nonce = msg.params[0]
                self._send("REQ_PONG", nonce)
            return None

        if msg.type_desc == "RES_ERROR":
            toast(
                self.state,
                " | ".join(msg.params) if msg.params else "Server error",
                4.0,
            )
            return None

        return None

    def draw(self, screen: pygame.Surface) -> None:
        draw_background(screen)

        cc_rect = pygame.Rect(CENTER_CARD)
        draw_panel(screen, TOPBAR, "UPS – Rock Paper Scissors", self.font_b)
        draw_panel(screen, CENTER_CARD, "CONNECT", self.font_b)
        draw_panel(screen, BOTTOM_HINT, "INFO", self.font_b)

        mouse = pygame.mouse.get_pos()

        title = self.font_xl.render("Connect to server", True, (245, 245, 255))
        screen.blit(title, title.get_rect(center=(cc_rect.centerx, cc_rect.y + 52)))

        self.inp_host.draw(screen, self.font)
        self.inp_port.draw(screen, self.font)
        self.inp_name.draw(screen, self.font)

        self.btn_connect.enabled = True
        self.btn_connect.draw(screen, self.font_b, mouse)

        hint = self.font.render(
            "CONNECT will connect and immediately send REQ_LOGIN|nickname|",
            True,
            (180, 180, 200),
        )
        bh_rect = pygame.Rect(BOTTOM_HINT)
        screen.blit(hint, hint.get_rect(center=(bh_rect.centerx, bh_rect.centery)))

        draw_toast(screen, TOPBAR, self.font, self.state)
        draw_debug(screen, self.font, self.state, W, H)


class LobbyScene:
    def __init__(self, client: TcpLineClient, state: AppState, fonts):
        self.client = client
        self.state = state
        self.font, self.font_b, self.font_xl, self.font_move = fonts

        cc_rect = pygame.Rect(CENTER_CARD)
        top_rect = pygame.Rect(TOPBAR)

        content_width = 360
        input_height = 46
        btn_height = 48
        gap = 14

        start_x = cc_rect.centerx - (content_width // 2)
        input_y = cc_rect.centery - 40

        self.inp_lobby = InputField(
            pygame.Rect(start_x, input_y, content_width, input_height), "Lobby Name"
        )

        btn_w = (content_width - gap) // 2
        btns_y = input_y + input_height + gap + 10

        self.btn_create = HUDButton(
            pygame.Rect(start_x, btns_y, btn_w, btn_height), "CREATE"
        )
        self.btn_join = HUDButton(
            pygame.Rect(start_x + btn_w + gap, btns_y, btn_w, btn_height), "JOIN"
        )

        logout_w = 110
        logout_h = 32
        logout_x = top_rect.right - logout_w - 12
        logout_y = top_rect.centery - (logout_h // 2)

        self.btn_logout = HUDButton(
            pygame.Rect(logout_x, logout_y, logout_w, logout_h), "LOGOUT"
        )

        leave_w = 180
        leave_h = 44
        leave_x = cc_rect.centerx - (leave_w // 2)
        leave_y = cc_rect.bottom - 80

        self.btn_leave_lobby = HUDButton(
            pygame.Rect(leave_x, leave_y, leave_w, leave_h), "LEAVE LOBBY"
        )

    def _send(self, type_desc: str, *params: str):
        try:
            self.client.send(type_desc, *params)
            log_tx(self.state, type_desc, *params)
        except Exception as e:
            log_err(self.state, f"Send failed: {e}")

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F1:
                self.state.debug_visible = not self.state.debug_visible

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_logout.hit(e.pos):
                if self.state.in_lobby:
                    self._send("REQ_LEAVE_LOBBY")
                else:
                    self._send("REQ_LOGOUT")

            if self.state.in_lobby:
                if self.btn_leave_lobby.hit(e.pos):
                    self._send("REQ_LEAVE_LOBBY")
            else:
                if self.btn_create.hit(e.pos):
                    name = self.inp_lobby.text.strip()
                    if name:
                        self._send("REQ_CREATE_LOBBY", name)

                if self.btn_join.hit(e.pos):
                    name = self.inp_lobby.text.strip()
                    if name:
                        self._send("REQ_JOIN_LOBBY", name)

        if not self.state.in_lobby:
            self.inp_lobby.handle(e)

    def on_message(self, msg: Message) -> Optional[SceneId]:
        t = msg.type_desc
        p = msg.params

        if t == "RES_PING":
            if p:
                self._send("REQ_PONG", p[0])
            return None

        if t == "RES_LOBBY_CREATED":
            self.state.in_lobby = True
            self.state.in_game = False
            self.state.lobby_name = self.inp_lobby.text.strip()
            toast(self.state, f"Lobby created: {self.state.lobby_name}", 2.0)
            return None

        if t == "RES_LOBBY_JOINED":
            self.state.in_lobby = True
            self.state.in_game = False
            self.state.lobby_name = p[0] if p else self.inp_lobby.text.strip()
            toast(self.state, f"Joined lobby: {self.state.lobby_name}", 2.0)
            return None

        if t == "RES_GAME_STARTED":
            self.state.in_game = True
            self.state.in_lobby = True
            self.state.last_move = ""
            self.state.waiting_for_opponent = False
            self.state.round_result_visible = False
            self.state.round_result_ttl = 0.0
            toast(self.state, "Game started!", 2.0)
            return SceneId.GAME

        if t == "RES_LOBBY_LEFT":
            self.state.in_game = False
            self.state.in_lobby = False
            self.state.lobby_name = ""
            toast(self.state, "Left lobby.", 2.0)
            return None

        if t == "RES_LOGOUT_OK":
            self.state.user_id = ""
            self.state.username = ""
            self.state.lobby_name = ""
            self.state.in_lobby = False
            self.state.in_game = False
            toast(self.state, "Logged out.", 2.5)
            self.state.scene = SceneId.CONNECT
            return SceneId.CONNECT

        if t == "RES_ERROR":
            if self.state.in_lobby and ("Unexpected" in str(p) or "state" in str(p)):
                self.state.in_lobby = False
                self.state.lobby_name = ""
                toast(self.state, "Sync error: Resetting view.", 2.0)
                return None

            toast(self.state, " | ".join(p) if p else "Server error", 4.0)
            return None

        return None

    def draw(self, screen: pygame.Surface) -> None:
        draw_background(screen)

        cc_rect = pygame.Rect(CENTER_CARD)
        top_rect = pygame.Rect(TOPBAR)

        draw_panel(screen, TOPBAR, "UPS – Rock Paper Scissors", self.font_b)

        nick_text = self.state.username if self.state.username else "Guest"
        nick_surf = self.font_b.render(nick_text, True, (150, 255, 150))
        nick_rect = nick_surf.get_rect(
            midright=(self.btn_logout.rect.left - 15, self.btn_logout.rect.centery)
        )
        screen.blit(nick_surf, nick_rect)

        mouse = pygame.mouse.get_pos()
        self.btn_logout.label = "EXIT" if self.state.in_lobby else "LOGOUT"
        self.btn_logout.draw(screen, self.font_b, mouse)

        panel_title = "WAITING ROOM" if self.state.in_lobby else "LOBBY SELECTION"
        draw_panel(screen, CENTER_CARD, panel_title, self.font_b)
        draw_panel(screen, BOTTOM_HINT, "STATUS", self.font_b)

        if self.state.in_lobby:
            title = self.font_xl.render(self.state.lobby_name, True, (100, 255, 100))
            screen.blit(title, title.get_rect(center=(cc_rect.centerx, cc_rect.y + 80)))

            info = self.font_b.render("Waiting for opponent...", True, (200, 200, 220))
            screen.blit(info, info.get_rect(center=(cc_rect.centerx, cc_rect.y + 130)))

            dots = "." * (int(pygame.time.get_ticks() / 500) % 4)
            loading = self.font_xl.render(dots, True, (255, 255, 255))
            screen.blit(
                loading, loading.get_rect(center=(cc_rect.centerx, cc_rect.y + 160))
            )

            self.btn_leave_lobby.draw(screen, self.font_b, mouse)

        else:
            lbl = self.font_b.render("Enter Lobby Name:", True, (180, 180, 200))
            screen.blit(
                lbl,
                lbl.get_rect(
                    center=(self.inp_lobby.rect.centerx, self.inp_lobby.rect.y - 18)
                ),
            )

            self.inp_lobby.draw(screen, self.font)
            self.btn_create.draw(screen, self.font_b, mouse)
            self.btn_join.draw(screen, self.font_b, mouse)

        status_txt = (
            "Status: WAITING FOR PLAYER 2"
            if self.state.in_lobby
            else "Status: BROWSING LOBBIES"
        )
        status = self.font.render(status_txt, True, (180, 180, 200))
        bh_rect = pygame.Rect(BOTTOM_HINT)
        screen.blit(status, status.get_rect(center=(bh_rect.centerx, bh_rect.centery)))

        draw_toast(screen, TOPBAR, self.font, self.state)
        draw_debug(screen, self.font, self.state, W, H)


class GameScene:
    def __init__(self, client: TcpLineClient, state: AppState, fonts):
        self.client = client
        self.state = state
        self.font, self.font_b, self.font_xl, self.font_move = fonts

        cc_rect = pygame.Rect(CENTER_CARD)
        top_rect = pygame.Rect(TOPBAR)

        x, w, y0 = cc_rect.x + 28, cc_rect.width - 56, cc_rect.y + 96
        self.move_r = MoveButton(pygame.Rect(x, y0, w, 72), "R", "Rock")
        self.move_p = MoveButton(pygame.Rect(x, y0 + 88, w, 72), "P", "Paper")
        self.move_s = MoveButton(pygame.Rect(x, y0 + 176, w, 72), "S", "Scissors")

        self.reconnect_wait = False
        self.btn_forfeit = HUDButton(
            pygame.Rect(top_rect.right - 122, top_rect.y + 12, 110, 32), "FORFEIT"
        )

    def _send(self, type_desc: str, *params: str):
        try:
            self.client.send(type_desc, *params)
            log_tx(self.state, type_desc, *params)
        except Exception as e:
            log_err(self.state, f"Send failed: {e}")

    def _choose(self, move: str):
        if self.state.waiting_for_opponent or self.state.round_result_visible:
            return
        self.state.last_move = move
        self.state.waiting_for_opponent = True
        self._send("REQ_MOVE", move)

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F1:
                self.state.debug_visible = not self.state.debug_visible

        if self.state.round_result_visible or self.reconnect_wait:
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_forfeit.hit(e.pos):
                self._send("REQ_LEAVE_LOBBY")
                return

            if not self.state.waiting_for_opponent:
                if self.move_r.hit(e.pos):
                    self._choose("R")
                elif self.move_p.hit(e.pos):
                    self._choose("P")
                elif self.move_s.hit(e.pos):
                    self._choose("S")

        if e.type == pygame.KEYDOWN and not self.state.waiting_for_opponent:
            if e.key == pygame.K_r:
                self._choose("R")
            elif e.key == pygame.K_p:
                self._choose("P")
            elif e.key == pygame.K_s:
                self._choose("S")

    def on_message(self, msg: Message) -> Optional[SceneId]:
        self.state.last_server_contact = pygame.time.get_ticks()

        if msg.type_desc == "RES_PING":
            if msg.params:
                self._send("REQ_PONG", msg.params[0])
            return None

        if msg.type_desc == "RES_STATE":
            # Example: score=1:2;hasMoved=true;lastMove=R;phase=InGame;p1Id=1;p1Name=Alice;p2Id=2;p2Name=Bob;
            if msg.params:
                p_dict = {}
                for part in msg.params[0].split(";"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        p_dict[k.strip()] = v.strip()

                # score
                if "score" in p_dict:
                    try:
                        s1, s2 = p_dict["score"].split(":")
                        self.state.p1_wins, self.state.p2_wins = int(s1), int(s2)
                    except Exception:
                        pass

                # identities (optional)
                if "p1Id" in p_dict:
                    try:
                        self.state.p1_id = int(p_dict["p1Id"])
                    except Exception:
                        pass
                if "p2Id" in p_dict:
                    try:
                        self.state.p2_id = int(p_dict["p2Id"])
                    except Exception:
                        pass
                if "p1Name" in p_dict:
                    self.state.p1_name = p_dict["p1Name"]
                if "p2Name" in p_dict:
                    self.state.p2_name = p_dict["p2Name"]

                # hasMoved -> restore waiting UI
                if "hasMoved" in p_dict:
                    has_moved = p_dict["hasMoved"].lower() == "true"
                    self.state.waiting_for_opponent = has_moved
                    if not has_moved:
                        self.state.last_move = ""

                # lastMove -> restore the shown letter
                if "lastMove" in p_dict:
                    mv = p_dict["lastMove"].strip().upper()
                    if mv in ("R", "P", "S"):
                        self.state.last_move = mv

            return None

        if msg.type_desc == "RES_GAME_STARTED":
            self.state.in_game = True
            self.state.waiting_for_opponent = False
            self.state.last_move = ""
            self.state.round_result_visible = False
            self.state.round_result_ttl = 0.0
            self.reconnect_wait = False
            toast(self.state, "Game started!", 2.0)
            return None

        if msg.type_desc == "RES_GAME_RESUMED":
            log_sys(self.state, "SESSION: Gameplay active/resumed.")
            self.reconnect_wait = False
            return None

        # ---- Round result (now includes score) ----
        if msg.type_desc == "RES_ROUND_RESULT":
            # msg.params: [winner_id, p1_move, p2_move, p1_wins, p2_wins]
            p = msg.params
            if len(p) >= 5:
                winner_id, p1m, p2m, s1, s2 = p[0], p[1], p[2], p[3], p[4]
                try:
                    self.state.p1_wins = int(s1)
                    self.state.p2_wins = int(s2)
                except ValueError:
                    pass
                self.state.last_round = f"{winner_id}|{p1m}|{p2m}"
            else:
                # Backward compatible: [winner_id, p1_move, p2_move]
                self.state.last_round = " | ".join(p)

            self.state.waiting_for_opponent = False
            self.state.round_result_visible = True
            self.state.round_result_ttl = 2.8
            self.state.last_move = ""
            log_sys(self.state, f"GAME: Round result: {self.state.last_round}")
            return None

        # ---- Match result: defer switch until last round overlay finishes ----
        if msg.type_desc == "RES_MATCH_RESULT":
            p = msg.params
            try:
                self.state.last_match_winner_id = int(p[0])
                self.state.last_match_p1wins = int(p[1])
                self.state.last_match_p2wins = int(p[2])
            except Exception:
                self.state.last_match_winner_id = 0
                self.state.last_match_p1wins = 0
                self.state.last_match_p2wins = 0

            log_sys(
                self.state, f"GAME: Match finished. Winner ID: {p[0] if p else '?'}"
            )

            if self.state.round_result_visible and self.state.round_result_ttl > 0:
                self.state.pending_scene = SceneId.AFTER_MATCH
                return None

            return SceneId.AFTER_MATCH

        if msg.type_desc == "RES_OPPONENT_DISCONNECTED":
            self.reconnect_wait = True
            wait_s = msg.params[0] if msg.params else "?"
            log_err(
                self.state, f"REMOTE: Opponent lost connection. Wait limit: {wait_s}s"
            )
            return None

        if msg.type_desc == "RES_GAME_CANNOT_CONTINUE":
            reason = msg.params[0] if msg.params else "Game ended"
            toast(self.state, f"{reason}", 3.0)
            self.state.in_game = False
            self.state.waiting_for_opponent = False
            self.state.last_move = ""
            self.state.round_result_visible = False
            self.state.round_result_ttl = 0.0
            return SceneId.LOBBY

        if msg.type_desc == "RES_LOBBY_LEFT":
            self.state.in_game = False
            self.state.in_lobby = False
            self.state.lobby_name = ""
            return SceneId.LOBBY

        return None

    def draw(self, screen: pygame.Surface):
        draw_background(screen)

        score_txt = f"SCORE: {self.state.p1_wins} - {self.state.p2_wins}"
        draw_panel(screen, TOPBAR, f"GAME | {score_txt}", self.font_b)
        draw_panel(screen, CENTER_CARD, "ROCK · PAPER · SCISSORS", self.font_b)

        cc = pygame.Rect(CENTER_CARD)
        mouse = pygame.mouse.get_pos()
        self.btn_forfeit.draw(screen, self.font_b, mouse)

        is_local_timeout = (
            pygame.time.get_ticks() - self.state.last_server_contact > 5000
        )

        if self.reconnect_wait or is_local_timeout:
            overlay = pygame.Surface((cc.width, cc.height), pygame.SRCALPHA)
            pygame.draw.rect(
                overlay, (0, 0, 0, 210), overlay.get_rect(), border_radius=18
            )
            screen.blit(overlay, (cc.x, cc.y))

            txt = (
                "CONNECTION INTERRUPTED"
                if is_local_timeout
                else "OPPONENT DISCONNECTED"
            )
            t_surf = self.font_b.render(txt, True, (255, 100, 100))
            screen.blit(t_surf, t_surf.get_rect(center=(cc.centerx, cc.centery)))

        elif self.state.round_result_visible:
            draw_round_result(
                screen,
                CENTER_CARD,
                self.state.last_round,
                self.font_xl,
                self.font_b,
                self.state,
            )

        elif self.state.waiting_for_opponent:
            draw_waiting_screen(
                screen,
                CENTER_CARD,
                self.state.last_move,
                self.font_xl,
                self.font_b,
                self.font_move,
            )

        else:
            for b in (self.move_r, self.move_p, self.move_s):
                b.enabled = True
                b.draw(screen, self.font_move, self.font, mouse)

        draw_toast(screen, TOPBAR, self.font, self.state)
        draw_debug(screen, self.font, self.state, W, H)


class AfterMatchScene:
    def __init__(self, client: TcpLineClient, state: AppState, fonts):
        self.client = client
        self.state = state
        self.font, self.font_b, self.font_xl, _ = fonts

        cc_rect = pygame.Rect(CENTER_CARD)
        x = cc_rect.x + 28
        w = cc_rect.width - 56
        y = cc_rect.y + 180

        self.btn_rematch = HUDButton(pygame.Rect(x, y, w, 48), "REMATCH")
        self.btn_exit = HUDButton(pygame.Rect(x, y + 60, w, 48), "EXIT TO MENU")

    def _send(self, type_desc: str, *params: str):
        try:
            self.client.send(type_desc, *params)
            log_tx(self.state, type_desc, *params)
        except Exception as ex:
            log_err(self.state, f"Send failed: {ex}")

    def handle_event(self, e: pygame.event.Event):
        if self.state.waiting_for_rematch:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.btn_exit.hit(e.pos):
                    self._send("REQ_LEAVE_LOBBY")
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_rematch.hit(e.pos):
                self._send("REQ_REMATCH")
                self.state.waiting_for_rematch = True
            elif self.btn_exit.hit(e.pos):
                self._send("REQ_LEAVE_LOBBY")

    def on_message(self, msg: Message) -> Optional[SceneId]:
        if msg.type_desc == "RES_PING":
            if msg.params:
                self._send("REQ_PONG", msg.params[0])
            return None

        if msg.type_desc == "RES_REMATCH_READY":
            self.state.waiting_for_rematch = True
            return None

        if msg.type_desc == "RES_GAME_STARTED":
            self.state.last_move = ""
            self.state.waiting_for_opponent = False
            self.state.last_round = ""
            self.state.round_result_visible = False
            self.state.round_result_ttl = 0.0
            self.state.waiting_for_rematch = False

            toast(self.state, "Rematch started!", 2.5)
            return SceneId.GAME

        if msg.type_desc == "RES_GAME_CANNOT_CONTINUE":
            reason = msg.params[0] if msg.params else "Game ended"
            toast(self.state, f"{reason}", 3.0)

            self.state.in_game = False
            self.state.in_lobby = False
            self.state.lobby_name = ""
            self.state.waiting_for_opponent = False
            self.state.waiting_for_rematch = False

            return SceneId.LOBBY

        if msg.type_desc == "RES_LOBBY_LEFT":
            self.state.in_game = False
            self.state.in_lobby = False
            self.state.lobby_name = ""
            self.state.waiting_for_rematch = False
            toast(self.state, "Lobby closed by server.", 2.0)
            return SceneId.LOBBY

        return None

    def draw(self, screen: pygame.Surface) -> None:
        draw_background(screen)

        draw_panel(screen, TOPBAR, "AFTER MATCH", self.font_b)
        draw_panel(screen, CENTER_CARD, "RESULT", self.font_b)
        draw_panel(screen, BOTTOM_HINT, "INFO", self.font_b)

        cc = pygame.Rect(CENTER_CARD)
        mouse = pygame.mouse.get_pos()

        w_id = self.state.last_match_winner_id
        s1 = self.state.last_match_p1wins
        s2 = self.state.last_match_p2wins

        title = self.font_xl.render("Match finished", True, (245, 245, 255))
        screen.blit(title, title.get_rect(center=(cc.centerx, cc.y + 70)))

        score = self.font_b.render(f"Final score: {s1} - {s2}", True, (200, 200, 220))
        screen.blit(score, score.get_rect(center=(cc.centerx, cc.y + 120)))

        # Winner name if possible
        w_label = winner_label(self.state, str(w_id))
        winner = self.font_b.render(f"Winner: {w_label}", True, (150, 255, 150))
        screen.blit(winner, winner.get_rect(center=(cc.centerx, cc.y + 155)))

        self.btn_rematch.enabled = not self.state.waiting_for_rematch
        self.btn_rematch.draw(screen, self.font_b, mouse)
        self.btn_exit.enabled = True
        self.btn_exit.draw(screen, self.font_b, mouse)

        if self.state.waiting_for_rematch:
            hint = self.font_b.render("Waiting for opponent…", True, (180, 180, 200))
            bh = pygame.Rect(BOTTOM_HINT)
            screen.blit(hint, hint.get_rect(center=(bh.centerx, bh.centery)))

        draw_toast(screen, TOPBAR, self.font, self.state)
        draw_debug(screen, self.font, self.state, W, H)
