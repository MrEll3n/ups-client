from queue import Empty

import pygame

from network import TcpLineClient
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

    # Non-blocking reconnect cooldown (seconds)
    reconnect_cooldown = 0.0

    # Client-side keepalive: send REQ_PONG periodically even if we miss RES_PING.
    # This prevents heartbeat timeouts caused by UI / OS stalls.
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

        # --- Timers (UI state) ---
        if state.toast_ttl > 0:
            state.toast_ttl = max(0.0, state.toast_ttl - dt)
            if state.toast_ttl <= 0:
                state.toast = ""

        # Round result overlay timer (this was the main "client stuck" cause)
        if state.round_result_visible and state.round_result_ttl > 0:
            state.round_result_ttl = max(0.0, state.round_result_ttl - dt)
            if state.round_result_ttl <= 0:
                state.round_result_visible = False
                # Deferred transition (e.g., AFTER_MATCH) once the last round overlay is done
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

        # 1) Process network inbox (priority)
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

        # 2) Local watchdog (avoid aggressive disconnects; server can be idle)
        if (
            client.connected
            and (state.in_game or state.in_lobby)
            and state.last_server_contact > 0
        ):
            if pygame.time.get_ticks() - state.last_server_contact > 20000:
                log_err(state, "No data from server for 20s. Disconnecting.")
                client.close()
                state.last_server_contact = 0

        if client.connected and state.scene == SceneId.AFTER_MATCH:
            if pygame.time.get_ticks() - state.last_server_contact > 10000:  # 10s ticha
                state.scene = SceneId.LOBBY
                client.close()
                log_sys(state, "Connection timed out")

        # 3) Non-blocking reconnect logic
        if (
            (not client.connected)
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
                    reconnect_cooldown = 2.0
                except Exception:
                    reconnect_cooldown = 2.0

        # 4) Network errors
        while True:
            try:
                err = client.errors.get_nowait()
                if "Disconnected" in err or "failed" in err:
                    log_err(state, f"Network error: {err}")
                    client.close()
            except Empty:
                break

        # 5) Pygame events + rendering
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
