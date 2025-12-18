from queue import Empty

import pygame

from network import TcpLineClient
from scenes import AfterMatchScene, ConnectScene, GameScene, LobbyScene
from state import AppState, H, SceneId, W, log_err, log_rx, log_sys, toast


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("UPS – Rock Paper Scissors")
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

    # Cooldown pro reconnect (v sekundách)
    reconnect_cooldown = 0.0

    # Keepalive pro heartbeat
    pong_keepalive = 0.0

    scenes = {
        SceneId.CONNECT: ConnectScene(client, state, fonts),
        SceneId.LOBBY: LobbyScene(client, state, fonts),
        SceneId.GAME: GameScene(client, state, fonts),
        SceneId.AFTER_MATCH: AfterMatchScene(client, state, fonts),
    }

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # --- Timery (UI state) ---
        if state.toast_ttl > 0:
            state.toast_ttl = max(0.0, state.toast_ttl - dt)
            if state.toast_ttl <= 0:
                state.toast = ""

        # Round result overlay timer
        if state.round_result_visible and state.round_result_ttl > 0:
            state.round_result_ttl = max(0.0, state.round_result_ttl - dt)
            if state.round_result_ttl <= 0:
                state.round_result_visible = False
                if state.pending_scene is not None:
                    state.scene = state.pending_scene
                    state.pending_scene = None

        if reconnect_cooldown > 0:
            reconnect_cooldown = max(0.0, reconnect_cooldown - dt)

        # --- Client keepalive ---
        if client.connected and (state.in_game or state.in_lobby):
            pong_keepalive += dt
            if pong_keepalive >= 1.5:
                try:
                    client.send("REQ_PONG", "0")
                except Exception:
                    pass
                pong_keepalive = 0.0
        else:
            pong_keepalive = 0.0

        # 1) Zpracování příchozích zpráv
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

        # 2) Watchdog (detekce ticha ze strany serveru)
        if client.connected and state.last_server_contact > 0:
            # Sjednocený timeout pro všechny herní fáze (Lobby, Game, AfterMatch)
            if pygame.time.get_ticks() - state.last_server_contact > 20000:
                log_err(state, "No data from server for 20s. Disconnecting.")
                client.close()
                state.last_server_contact = 0

        # 3) Reconnect logika
        # FIX: Povolujeme automatický reconnect v GAME i AFTER_MATCH fázích.
        if (not client.connected) and state.username:
            if state.scene in (SceneId.GAME, SceneId.AFTER_MATCH):
                if reconnect_cooldown <= 0:
                    try:
                        log_sys(
                            state, "Attempting to restore socket (Session Reconnect)..."
                        )
                        client.connect()
                        if client.connected:
                            state.last_server_contact = pygame.time.get_ticks()
                            client.send("REQ_LOGIN", state.username)
                        reconnect_cooldown = 2.0
                    except Exception:
                        reconnect_cooldown = 2.0
            else:
                # Pokud jsme v lobby nebo menu a ztratíme spojení, jdeme na login
                log_sys(state, "Connection lost. Returning to menu.")
                state.scene = SceneId.CONNECT
                state.username = ""
                state.in_lobby = False
                state.in_game = False

        # 4) Zpracování chyb sítě
        while True:
            try:
                err = client.errors.get_nowait()
                log_err(state, f"Network error: {err}")
                client.close()

                # FIX: Pokud nastane chyba (např. WinError 10038) v AFTER_MATCH,
                # neresetujeme scénu ani jméno, aby mohl proběhnout reconnect.
                if state.scene not in (SceneId.GAME, SceneId.AFTER_MATCH):
                    state.scene = SceneId.CONNECT
                    state.username = ""
            except Empty:
                break

        # 5) Události Pygame + Vykreslování
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
