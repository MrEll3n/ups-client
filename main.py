# main.py
from queue import Empty

import pygame

from network import TcpLineClient
from protocol import Message
from scenes import AfterMatchScene, ConnectScene, GameScene, LobbyScene
from state import AppState, H, SceneId, W, log_err, log_rx, log_sys


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    fonts = (
        pygame.font.SysFont("Segoe UI", 18),
        pygame.font.SysFont("Segoe UI", 22, bold=True),
        pygame.font.SysFont("Segoe UI", 34, bold=True),
        pygame.font.SysFont("Segoe UI", 26, bold=True),
    )

    client = TcpLineClient("127.0.0.1", 10000)
    state = AppState()
    state.last_server_contact = pygame.time.get_ticks()

    # Časovač pro neblokující pokusy o spojení
    reconnect_cooldown = 0.0

    # Client-side keepalive: send REQ_PONG periodically even if we miss RES_PING.
    # Server accepts REQ_PONG in all phases and only uses it to refresh last_pong.
    pong_keepalive = 0.0

    scenes = {
        SceneId.CONNECT: ConnectScene(client, state, fonts),
        SceneId.LOBBY: LobbyScene(client, state, fonts),
        SceneId.GAME: GameScene(client, state, fonts),
        SceneId.AFTER_MATCH: AfterMatchScene(client, state, fonts),
    }

    running = True
    while running:
        # dt v sekundách
        dt = clock.tick(60) / 1000.0
        if reconnect_cooldown > 0:
            reconnect_cooldown -= dt

        # --- UI TIMERS (fix: round-result overlay must expire) ---
        # These attributes are expected to exist in AppState; guard with hasattr for safety.
        if hasattr(state, "toast_ttl") and state.toast_ttl > 0:
            state.toast_ttl = max(0.0, state.toast_ttl - dt)
            if state.toast_ttl == 0.0 and hasattr(state, "toast"):
                state.toast = ""

        if hasattr(state, "round_result_visible") and state.round_result_visible:
            if hasattr(state, "round_result_ttl"):
                state.round_result_ttl = max(0.0, state.round_result_ttl - dt)
                if state.round_result_ttl == 0.0:
                    state.round_result_visible = False
                    if hasattr(state, "last_round"):
                        state.last_round = ""
        # ---------------------------------------------------------

        # 0. CLIENT KEEPALIVE (prevents server heartbeat timeout even if RES_PING is missed)
        if client.connected:
            pong_keepalive += dt
            if pong_keepalive >= 1.5:
                try:
                    # Nonce is currently not validated by the server; keep a placeholder.
                    client.send("REQ_PONG", "0")
                except Exception:
                    # Errors are handled via client.errors / reconnect logic.
                    pass
                pong_keepalive = 0.0

        # 1. OKAMŽITÉ ZPRACOVÁNÍ SÍTĚ (Priorita č. 1)
        while True:
            try:
                msg = client.inbox.get_nowait()
                state.last_server_contact = pygame.time.get_ticks()
                log_rx(state, msg)
                nxt = scenes[state.scene].on_message(msg)
                if nxt:
                    state.scene = nxt
            except Empty:
                break

        # 2. MONITORING SPOJENÍ (Local Watchdog)
        # Avoid aggressive timeouts: server may be idle if heartbeat is disabled.
        # We only drop the socket if we've been connected, actively in a session,
        # and received nothing for a longer interval.
        if (
            client.connected
            and (state.in_game or state.in_lobby)
            and state.last_server_contact > 0
        ):
            if pygame.time.get_ticks() - state.last_server_contact > 20000:
                log_err(state, "No data from server for 20s. Disconnecting.")
                client.close()
                state.last_server_contact = 0

        # 3. NEBLOKUJÍCÍ RECONNECT LOGIKA
        if (
            not client.connected
            and state.username
            and (state.in_game or state.in_lobby)
        ):
            if reconnect_cooldown <= 0:
                try:
                    log_sys(state, "Attempting to restore socket...")
                    client.connect()
                    if client.connected:
                        state.last_server_contact = pygame.time.get_ticks()
                        client.send("REQ_LOGIN", state.username)
                    reconnect_cooldown = 2.0  # Zkusíme znovu až za 2s při selhání
                except:
                    reconnect_cooldown = 2.0

        # 4. CHYBY ZE SÍTĚ
        while True:
            try:
                err = client.errors.get_nowait()
                if "Disconnected" in err or "failed" in err:
                    log_err(state, f"Network error: {err}")
                    client.close()
            except Empty:
                break

        # 5. PYGAME UDÁLOSTI A VYKRESLOVÁNÍ
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            scenes[state.scene].handle_event(e)

        scenes[state.scene].draw(screen)
        pygame.display.flip()

    client.close()
    pygame.quit()


if __name__ == "__main__":
    main()
