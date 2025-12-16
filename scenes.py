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
    log_rx,
    log_sys,
    log_tx,
    toast,
)
from ui_components import HUDButton, InputField, MoveButton

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
    screen: pygame.Surface, font: pygame.font.Font, state: AppState, W: int, H: int
) -> None:
    if not state.debug_visible:
        return
    dbg = pygame.Rect(W - 380, H - 210, 360, 180)
    ov = pygame.Surface((dbg.width, dbg.height), pygame.SRCALPHA)
    pygame.draw.rect(ov, (10, 10, 12, 210), ov.get_rect(), border_radius=14)
    pygame.draw.rect(ov, (120, 120, 150, 180), ov.get_rect(), width=1, border_radius=14)
    screen.blit(ov, (dbg.x, dbg.y))

    head = font.render("DEBUG CONSOLE (toggle: `)", True, (220, 220, 235))
    screen.blit(head, (dbg.x + 12, dbg.y + 10))

    lines = state.log[-7:]
    y = dbg.y + 36
    for ln in lines:
        s = font.render(ln[:70], True, (190, 190, 210))
        screen.blit(s, (dbg.x + 12, y))
        y += font.get_height() + 2


def draw_waiting_screen(
    screen: pygame.Surface,
    card_rect_data: Tuple[int, int, int, int],
    my_move: str,
    font_xl: pygame.font.Font,
    font_b: pygame.font.Font,
    font_move: pygame.font.Font,
) -> None:
    card_rect = pygame.Rect(card_rect_data)
    mid_x = card_rect.centerx
    left_rect = pygame.Rect(
        card_rect.x, card_rect.y + 60, card_rect.width // 2 - 10, card_rect.height - 60
    )
    right_rect = pygame.Rect(
        mid_x + 10, card_rect.y + 60, card_rect.width // 2 - 10, card_rect.height - 60
    )

    my_label = font_b.render("Your Move", True, (180, 220, 180))
    screen.blit(
        my_label, my_label.get_rect(center=(left_rect.centerx, left_rect.y + 20))
    )

    move_names = {"R": "ROCK", "P": "PAPER", "S": "SCISSORS"}
    move_display = move_names.get(my_move, my_move)

    move_letter = font_xl.render(my_move, True, (200, 255, 200))
    screen.blit(
        move_letter,
        move_letter.get_rect(center=(left_rect.centerx, left_rect.centery - 20)),
    )

    move_name = font_b.render(move_display, True, (180, 220, 180))
    screen.blit(
        move_name,
        move_name.get_rect(center=(left_rect.centerx, left_rect.centery + 30)),
    )

    pygame.draw.line(
        screen,
        (120, 120, 150),
        (mid_x, card_rect.y + 70),
        (mid_x, card_rect.bottom - 20),
        2,
    )

    opp_label = font_b.render("Opponent", True, (220, 180, 180))
    screen.blit(
        opp_label, opp_label.get_rect(center=(right_rect.centerx, right_rect.y + 20))
    )

    waiting_text = font_xl.render("?", True, (255, 200, 200))
    screen.blit(
        waiting_text,
        waiting_text.get_rect(center=(right_rect.centerx, right_rect.centery - 20)),
    )

    waiting_label = font_move.render("Waiting...", True, (220, 180, 180))
    screen.blit(
        waiting_label,
        waiting_label.get_rect(center=(right_rect.centerx, right_rect.centery + 30)),
    )


def draw_round_result(
    screen: pygame.Surface,
    card_rect_data: Tuple[int, int, int, int],
    result_str: str,
    font_xl: pygame.font.Font,
    font_b: pygame.font.Font,
    state: AppState,
) -> None:
    card_rect = pygame.Rect(card_rect_data)

    # 1. Tmavé pozadí overlaye
    overlay = pygame.Surface((card_rect.width, card_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (10, 10, 14, 235), overlay.get_rect(), border_radius=18)

    # Okraj (barva se určí podle výsledku)
    border_color = (100, 100, 120)

    # 2. Parsování výsledku
    parts = result_str.split(" | ")

    title_text = "RESULT"
    title_color = (255, 255, 255)

    my_move_display = "?"
    opp_move_display = "?"

    move_map = {"R": "ROCK", "P": "PAPER", "S": "SCISSORS", "NONE": "-"}

    if len(parts) == 3:
        winner_id_str, p1_move, p2_move = parts

        try:
            winner_id = int(winner_id_str)
            my_id = int(state.user_id) if state.user_id.isdigit() else -1
        except ValueError:
            winner_id = -1
            my_id = -2

        # Logika: Kdo vyhrál?
        if winner_id == 0:
            title_text = "DRAW"
            title_color = (255, 230, 80)  # Žlutá
            border_color = (200, 180, 50)
        elif winner_id == my_id:
            title_text = "VICTORY!"
            title_color = (80, 255, 80)  # Zelená
            border_color = (50, 200, 50)
        else:
            title_text = "DEFEAT"
            title_color = (255, 80, 80)  # Červená
            border_color = (200, 50, 50)

        # Logika: Který tah byl můj?
        # Snažíme se porovnat s tím, co jsme si uložili do state.last_move
        # Pokud je remíza, tahy jsou stejné, takže je to jedno.
        if p1_move == p2_move:
            my_real_move = p1_move
            opp_real_move = p2_move
        elif state.last_move == p1_move:
            my_real_move = p1_move
            opp_real_move = p2_move
        else:
            # Pokud můj tah není p1, tak musí být p2 (nebo došlo k chybě, ale předpokládáme p2)
            my_real_move = p2_move
            opp_real_move = p1_move

        my_move_display = move_map.get(my_real_move, my_real_move)
        opp_move_display = move_map.get(opp_real_move, opp_real_move)

    # Vykreslení rámečku
    pygame.draw.rect(
        overlay, border_color, overlay.get_rect(), width=2, border_radius=18
    )
    screen.blit(overlay, (card_rect.x, card_rect.y))

    # --- HEADER (VÝSLEDEK) ---
    title_surf = font_xl.render(title_text, True, title_color)
    # Stín pod textem
    title_shadow = font_xl.render(title_text, True, (0, 0, 0))
    screen.blit(
        title_shadow,
        title_shadow.get_rect(center=(card_rect.centerx + 2, card_rect.y + 52)),
    )
    screen.blit(
        title_surf, title_surf.get_rect(center=(card_rect.centerx, card_rect.y + 50))
    )

    # --- ROZDĚLENÍ OBRAZOVKY ---
    mid_y = card_rect.centery + 10
    left_center = (card_rect.x + card_rect.width // 4, mid_y)
    right_center = (card_rect.x + 3 * card_rect.width // 4, mid_y)

    # Čára uprostřed
    pygame.draw.line(
        screen,
        (80, 80, 100),
        (card_rect.centerx, card_rect.y + 90),
        (card_rect.centerx, card_rect.bottom - 60),
        2,
    )

    # --- LEVÁ STRANA (JA) ---
    lbl_you = font_b.render("YOU", True, (200, 200, 200))
    screen.blit(lbl_you, lbl_you.get_rect(center=(left_center[0], card_rect.y + 110)))

    my_move_display = my_move_display or "?"

    opp_move_display = opp_move_display or "??"

    move_you = font_xl.render(
        my_move_display[0], True, (255, 255, 255)
    )  # První písmeno velké
    screen.blit(move_you, move_you.get_rect(center=(left_center[0], mid_y)))

    full_you = font_b.render(my_move_display, True, (150, 150, 170))
    screen.blit(full_you, full_you.get_rect(center=(left_center[0], mid_y + 40)))

    # --- PRAVÁ STRANA (SOUPEŘ) ---
    lbl_opp = font_b.render("OPPONENT", True, (200, 200, 200))
    screen.blit(lbl_opp, lbl_opp.get_rect(center=(right_center[0], card_rect.y + 110)))

    move_opp = font_xl.render(opp_move_display[0], True, (255, 255, 255))
    screen.blit(move_opp, move_opp.get_rect(center=(right_center[0], mid_y)))

    full_opp = font_b.render(opp_move_display, True, (150, 150, 170))
    screen.blit(full_opp, full_opp.get_rect(center=(right_center[0], mid_y + 40)))

    # --- FOOTER (TIMER) ---
    ttl = int(state.round_result_ttl + 0.9)
    hint = font_b.render(f"Next round in {ttl}...", True, (120, 120, 140))
    screen.blit(hint, hint.get_rect(center=(card_rect.centerx, card_rect.bottom - 30)))


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

    # Bezpečné odesílání (oprava z minula)
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

    # TATO METODA VÁM CHYBĚLA:
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


def draw(self, screen: pygame.Surface):
    draw_background(screen)
    draw_panel(screen, TOPBAR, "GAME", self.font_b)
    draw_panel(screen, CENTER_CARD, "ROCK · PAPER · SCISSORS", self.font_b)

    mouse = pygame.mouse.get_pos()

    # --- ZDE BYLA CHYBA ---
    if self.reconnect_wait:
        # 1. NEJDŘÍVE PŘEVÉST TUPLE NA RECT
        cc_rect = pygame.Rect(CENTER_CARD)

        # 2. TEĎ POUŽÍVÁME cc_rect (NE CENTER_CARD) PRO PŘÍSTUP K .width A .height
        overlay = pygame.Surface((cc_rect.width, cc_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 200), overlay.get_rect(), border_radius=18)

        # Používáme cc_rect pro souřadnice
        screen.blit(overlay, (cc_rect.x, cc_rect.y))

        txt = self.font_b.render("OPPONENT DISCONNECTED", True, (255, 100, 100))
        screen.blit(txt, txt.get_rect(center=(cc_rect.centerx, cc_rect.centery - 20)))

        sub = self.font.render("Waiting for reconnection...", True, (200, 200, 200))
        screen.blit(sub, sub.get_rect(center=(cc_rect.centerx, cc_rect.centery + 20)))

        draw_toast(screen, TOPBAR, self.font, self.state)
        draw_debug(screen, self.font, self.state, W, H)
        return
    # ----------------------

    if self.state.round_result_visible:
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


class LobbyScene:
    def __init__(self, client: TcpLineClient, state: AppState, fonts):
        self.client = client
        self.state = state
        self.font, self.font_b, self.font_xl, self.font_move = fonts

        cc_rect = pygame.Rect(CENTER_CARD)
        top_rect = pygame.Rect(TOPBAR)

        # --- LAYOUT PRO VÝBĚR LOBBY ---
        content_width = 360
        input_height = 46
        btn_height = 48
        gap = 14

        start_x = cc_rect.centerx - (content_width // 2)
        input_y = cc_rect.centery - 40

        # Input Field
        self.inp_lobby = InputField(
            pygame.Rect(start_x, input_y, content_width, input_height), "Lobby Name"
        )

        # Tlačítka Create / Join
        btn_w = (content_width - gap) // 2
        btns_y = input_y + input_height + gap + 10

        self.btn_create = HUDButton(
            pygame.Rect(start_x, btns_y, btn_w, btn_height), "CREATE"
        )
        self.btn_join = HUDButton(
            pygame.Rect(start_x + btn_w + gap, btns_y, btn_w, btn_height), "JOIN"
        )

        # --- TLAČÍTKO LOGOUT (TOP BAR) ---
        logout_w = 110
        logout_h = 32
        logout_x = top_rect.right - logout_w - 12
        logout_y = top_rect.centery - (logout_h // 2)

        self.btn_logout = HUDButton(
            pygame.Rect(logout_x, logout_y, logout_w, logout_h), "LOGOUT"
        )

        # --- NOVÉ: TLAČÍTKO LEAVE LOBBY (PRO ČEKACÍ OBRAZOVKU) ---
        # Umístíme ho do spodní části středové karty
        leave_w = 180
        leave_h = 44
        leave_x = cc_rect.centerx - (leave_w // 2)
        leave_y = cc_rect.bottom - 80

        self.btn_leave_lobby = HUDButton(
            pygame.Rect(leave_x, leave_y, leave_w, leave_h), "LEAVE LOBBY"
        )

    def _send(self, type_desc: str, *params: str) -> None:
        try:
            self.client.send(type_desc, *params)
            log_tx(self.state, type_desc, *params)
        except Exception as ex:
            log_err(self.state, f"Send failed: {ex}")

    def handle_event(self, e: pygame.event.Event) -> None:
        # Input funguje jen když NEJSME v lobby
        if not self.state.in_lobby:
            self.inp_lobby.handle(e)

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            # Akce pro Lobby Selection
            if not self.state.in_lobby:
                if self.btn_create.hit(e.pos):
                    name = self.inp_lobby.text.strip()
                    if not name:
                        toast(self.state, "Enter lobby name first.", 2.0)
                        return
                    self.state.lobby_name = name
                    self._send("REQ_CREATE_LOBBY", name)

                elif self.btn_join.hit(e.pos):
                    name = self.inp_lobby.text.strip()
                    if not name:
                        toast(self.state, "Enter lobby name first.", 2.0)
                        return
                    self.state.lobby_name = name
                    self._send("REQ_JOIN_LOBBY", name)

            # Akce pro Waiting Room (Leave Lobby)
            else:
                if self.btn_leave_lobby.hit(e.pos):
                    self._send("REQ_LEAVE_LOBBY")

            # Logout funguje vždy (pokud jsme v lobby, server nás nejprve vyhodí z lobby)
            if self.btn_logout.hit(e.pos):
                if self.state.in_lobby:
                    self._send("REQ_LEAVE_LOBBY")
                    # Můžeme poslat i logout hned za tím, nebo počkat na potvrzení
                    # Pro jednoduchost zde jen odejdeme z lobby
                else:
                    self._send("REQ_LOGOUT")

    def on_message(self, msg: Message) -> Optional[SceneId]:
        t = msg.type_desc
        p = msg.params

        if t == "RES_PING":
            if p:
                self._send("REQ_PONG", p[0])
            return None

        if t == "RES_LOBBY_CREATED":
            self.state.in_lobby = True
            lobby_id = p[0] if p else ""
            toast(self.state, f"Lobby created (ID: {lobby_id})", 3.0)
            return None

        if t == "RES_LOBBY_JOINED":
            self.state.in_lobby = True
            lobby_name = p[0] if p else (self.state.lobby_name or "")
            toast(self.state, f"Joined lobby: {lobby_name}", 3.0)
            return None

        if t == "RES_LOBBY_LEFT":
            self.state.in_lobby = False
            self.state.lobby_name = ""
            toast(self.state, "Left lobby.", 2.0)
            return None

        if t == "RES_GAME_STARTED":
            self.state.in_game = True
            self.state.last_move = ""
            self.state.waiting_for_opponent = False
            self.state.last_round = ""
            self.state.last_match = ""
            self.state.round_result_visible = False
            self.state.round_result_ttl = 0.0
            self.state.waiting_for_rematch = False

            toast(self.state, "Game started!", 2.5)
            self.state.scene = SceneId.GAME
            return SceneId.GAME

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
            # POJISTKA: Pokud chceme odejít, ale server říká error (např. že tam nejsme),
            # tak násilně přepneme klienta do stavu "Nejsem v lobby".
            # Tím se odblokuje UI.
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

        # --- HORNÍ LIŠTA ---
        draw_panel(screen, TOPBAR, "UPS – Rock Paper Scissors", self.font_b)

        # Nick
        nick_text = self.state.username if self.state.username else "Guest"
        nick_surf = self.font_b.render(nick_text, True, (150, 255, 150))
        nick_rect = nick_surf.get_rect(
            midright=(self.btn_logout.rect.left - 15, self.btn_logout.rect.centery)
        )
        screen.blit(nick_surf, nick_rect)

        # Logout button
        mouse = pygame.mouse.get_pos()
        # Text na tlačítku nahoře upravíme podle kontextu
        if self.state.in_lobby:
            self.btn_logout.text = "EXIT"
        else:
            self.btn_logout.text = "LOGOUT"
        self.btn_logout.draw(screen, self.font_b, mouse)

        # --- HLAVNÍ KARTA ---
        panel_title = "WAITING ROOM" if self.state.in_lobby else "LOBBY SELECTION"
        draw_panel(screen, CENTER_CARD, panel_title, self.font_b)

        draw_panel(screen, BOTTOM_HINT, "STATUS", self.font_b)

        # --- OBSAH KARTY ---

        if self.state.in_lobby:
            # === WAITING ROOM ===

            title = self.font_xl.render(self.state.lobby_name, True, (100, 255, 100))
            screen.blit(title, title.get_rect(center=(cc_rect.centerx, cc_rect.y + 80)))

            info = self.font_b.render("Waiting for opponent...", True, (200, 200, 220))
            screen.blit(info, info.get_rect(center=(cc_rect.centerx, cc_rect.y + 130)))

            dots = "." * (int(pygame.time.get_ticks() / 500) % 4)
            loading = self.font_xl.render(dots, True, (255, 255, 255))
            screen.blit(
                loading, loading.get_rect(center=(cc_rect.centerx, cc_rect.y + 160))
            )

            # NOVÉ: Tlačítko Leave Lobby uprostřed
            self.btn_leave_lobby.draw(screen, self.font_b, mouse)

        else:
            # === LOBBY SELECTION ===

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

        # Status Bar
        if self.state.in_lobby:
            status_txt = "Status: WAITING FOR PLAYER 2"
        else:
            status_txt = "Status: BROWSING LOBBIES"

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

        # Herní tlačítka
        x = cc_rect.x + 28
        w = cc_rect.width - 56
        y0 = cc_rect.y + 96

        self.move_r = MoveButton(pygame.Rect(x, y0, w, 72), "R", "Rock")
        self.move_p = MoveButton(pygame.Rect(x, y0 + 88, w, 72), "P", "Paper")
        self.move_s = MoveButton(pygame.Rect(x, y0 + 176, w, 72), "S", "Scissors")

        self.reconnect_wait = False

        # --- NOVÉ: TLAČÍTKO FORFEIT (V TOP BARU) ---
        # Stejná pozice jako Logout v Lobby
        forfeit_w = 110
        forfeit_h = 32
        forfeit_x = top_rect.right - forfeit_w - 12
        forfeit_y = top_rect.centery - (forfeit_h // 2)

        # Červený nádech tlačítka vyřešíme tím, že se jmenuje FORFEIT
        # (HUDButton nemá vlastní barvu v konstruktoru, ale to nevadí)
        self.btn_forfeit = HUDButton(
            pygame.Rect(forfeit_x, forfeit_y, forfeit_w, forfeit_h), "FORFEIT"
        )

    def _send(self, type_desc: str, *params: str):
        try:
            self.client.send(type_desc, *params)
            log_tx(self.state, type_desc, *params)
        except Exception as ex:
            log_err(self.state, f"Send failed: {ex}")

    def _choose(self, move: str):
        if self.state.waiting_for_opponent or self.state.round_result_visible:
            return
        self.state.last_move = move
        self.state.waiting_for_opponent = True
        self._send("REQ_MOVE", move)

    def handle_event(self, e: pygame.event.Event):
        if self.state.round_result_visible or self.reconnect_wait:
            return

        # Kliknutí na Forfeit (funguje vždy, když je aktivní input)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_forfeit.hit(e.pos):
                # Odesláním LEAVE_LOBBY během hry se hra vzdává
                self._send("REQ_LEAVE_LOBBY")
                return

        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self._choose("R")
            elif e.key == pygame.K_p:
                self._choose("P")
            elif e.key == pygame.K_s:
                self._choose("S")

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.move_r.hit(e.pos):
                self._choose("R")
            elif self.move_p.hit(e.pos):
                self._choose("P")
            elif self.move_s.hit(e.pos):
                self._choose("S")

    def on_message(self, msg: Message) -> Optional[SceneId]:
        if msg.type_desc == "RES_PING":
            if msg.params:
                self._send("REQ_PONG", msg.params[0])
            return None

        if msg.type_desc == "RES_ROUND_RESULT":
            self.state.last_round = " | ".join(msg.params)
            self.state.waiting_for_opponent = False
            self.state.round_result_visible = True
            self.state.round_result_ttl = 3.0
            return None

        if msg.type_desc == "RES_MATCH_RESULT":
            p = msg.params
            self.state.last_match_winner_id = int(p[0])
            self.state.last_match_p1wins = int(p[1])
            self.state.last_match_p2wins = int(p[2])
            self.state.round_result_visible = False
            self.state.scene = SceneId.AFTER_MATCH
            self.state.waiting_for_rematch = False
            self.reconnect_wait = False
            return SceneId.AFTER_MATCH

        if msg.type_desc == "RES_OPPONENT_DISCONNECTED":
            ttl = msg.params[0]
            toast(self.state, f"Opponent disconnected. Waiting {ttl}s...", float(ttl))
            self.reconnect_wait = True
            return None

        if msg.type_desc == "RES_GAME_RESUMED":
            toast(self.state, "Opponent reconnected! Play again!", 2.0)
            self.reconnect_wait = False
            self.state.waiting_for_opponent = False
            self.state.last_move = ""
            return None

        if msg.type_desc == "RES_GAME_STARTED":
            self.reconnect_wait = False
            self.state.waiting_for_opponent = False
            self.state.last_move = ""
            return None

        if msg.type_desc == "RES_GAME_CANNOT_CONTINUE":
            reason = msg.params[0] if msg.params else "Game ended"
            toast(self.state, f"{reason}", 3.0)
            return None

        if msg.type_desc == "RES_LOBBY_LEFT":
            self.state.in_game = False
            self.state.in_lobby = False
            self.state.lobby_name = ""
            self.state.waiting_for_rematch = False

            toast(self.state, "Left match.", 2.5)
            self.state.scene = SceneId.LOBBY
            return SceneId.LOBBY

        if msg.type_desc == "RES_ERROR":
            toast(
                self.state,
                " | ".join(msg.params) if msg.params else "Server error",
                4.0,
            )
            return None

        return None

    def draw(self, screen: pygame.Surface):
        draw_background(screen)
        draw_panel(screen, TOPBAR, "GAME", self.font_b)
        draw_panel(screen, CENTER_CARD, "ROCK · PAPER · SCISSORS", self.font_b)

        mouse = pygame.mouse.get_pos()

        # --- TOP BAR (FORFEIT TLAČÍTKO) ---
        # Vykreslíme tlačítko Forfeit vpravo nahoře
        self.btn_forfeit.draw(screen, self.font_b, mouse)

        # Nick hráče vedle tlačítka (volitelné, pro konzistenci s lobby)
        nick_text = self.state.username if self.state.username else "Guest"
        nick_surf = self.font_b.render(nick_text, True, (150, 255, 150))
        nick_rect = nick_surf.get_rect(
            midright=(self.btn_forfeit.rect.left - 15, self.btn_forfeit.rect.centery)
        )
        screen.blit(nick_surf, nick_rect)
        # ----------------------------------

        if self.reconnect_wait:
            cc_rect = pygame.Rect(CENTER_CARD)
            overlay = pygame.Surface((cc_rect.width, cc_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(
                overlay, (0, 0, 0, 200), overlay.get_rect(), border_radius=18
            )
            screen.blit(overlay, (cc_rect.x, cc_rect.y))

            txt = self.font_b.render("OPPONENT DISCONNECTED", True, (255, 100, 100))
            screen.blit(
                txt, txt.get_rect(center=(cc_rect.centerx, cc_rect.centery - 20))
            )

            sub = self.font.render("Waiting for reconnection...", True, (200, 200, 200))
            screen.blit(
                sub, sub.get_rect(center=(cc_rect.centerx, cc_rect.centery + 20))
            )

            draw_toast(screen, TOPBAR, self.font, self.state)
            draw_debug(screen, self.font, self.state, W, H)
            return

        if self.state.round_result_visible:
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
        # Pokud už čekáme na rematch, ignorujeme vstupy na Rematch
        if self.state.waiting_for_rematch:
            # Povolit EXIT i během čekání
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.btn_exit.hit(e.pos):
                    self._send("REQ_LEAVE_LOBBY")
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_rematch.hit(e.pos):
                self._send("REQ_REMATCH")
                # Ihned zamkneme tlačítko, aby nešlo poslat 2x
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
            self.state.scene = SceneId.GAME
            return SceneId.GAME

        if msg.type_desc == "RES_GAME_CANNOT_CONTINUE":
            reason = msg.params[0] if msg.params else "Game ended"
            toast(self.state, f"{reason}", 3.0)
            self.state.waiting_for_rematch = False
            return None

        # --- ZDE BYLA CHYBA: Musíme resetovat in_lobby na False ---
        if msg.type_desc == "RES_LOBBY_LEFT":
            self.state.in_game = False
            self.state.in_lobby = False  # <--- TOTO CHYBĚLO
            self.state.lobby_name = ""  # Vyčistíme název lobby
            self.state.waiting_for_rematch = False

            toast(self.state, "Left match, back in menu.", 2.5)
            self.state.scene = SceneId.LOBBY
            return SceneId.LOBBY
        # ----------------------------------------------------------

        if msg.type_desc == "RES_ERROR":
            # Pokud nastane chyba (např. Rematch failed), zrušíme čekání
            if self.state.waiting_for_rematch:
                self.state.waiting_for_rematch = False

            toast(
                self.state,
                " | ".join(msg.params) if msg.params else "Server error",
                4.0,
            )
            return None

        return None

    def draw(self, screen: pygame.Surface):
        draw_background(screen)
        draw_panel(screen, TOPBAR, "MATCH RESULT", self.font_b)
        draw_panel(screen, CENTER_CARD, "RESULT", self.font_b)

        cc_rect = pygame.Rect(CENTER_CARD)
        winner = self.state.last_match_winner_id

        try:
            me = int(self.state.user_id)
        except ValueError:
            me = -1

        # Vykreslení výsledku (WIN / LOSE / TIE)
        if winner == me:
            txt = self.font_xl.render("YOU WIN!", True, (120, 255, 120))
        elif winner == 0:
            txt = self.font_xl.render("TIE!", True, (255, 255, 120))
        else:
            txt = self.font_xl.render("YOU LOSE", True, (255, 120, 120))

        screen.blit(txt, txt.get_rect(center=(cc_rect.centerx, cc_rect.y + 110)))

        score = self.font_b.render(
            f"Score: {self.state.last_match_p1wins} : {self.state.last_match_p2wins}",
            True,
            (200, 200, 220),
        )
        screen.blit(score, score.get_rect(center=(cc_rect.centerx, cc_rect.y + 150)))

        mouse = pygame.mouse.get_pos()

        if self.state.waiting_for_rematch:
            wait_text = self.font_b.render(
                "Waiting for opponent...", True, (180, 180, 200)
            )
            screen.blit(
                wait_text,
                wait_text.get_rect(
                    center=(
                        self.btn_rematch.rect.centerx,
                        self.btn_rematch.rect.centery,
                    )
                ),
            )
        else:
            self.btn_rematch.draw(screen, self.font_b, mouse)

        self.btn_exit.draw(screen, self.font_b, mouse)

        draw_toast(screen, TOPBAR, self.font, self.state)
        draw_debug(screen, self.font, self.state, W, H)
