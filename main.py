# main.py
from __future__ import annotations

from queue import Empty

import pygame

from network import TcpLineClient
from protocol import Message
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

    scenes = {
        SceneId.CONNECT: ConnectScene(client, state, fonts),
        SceneId.LOBBY: LobbyScene(client, state, fonts),
        SceneId.GAME: GameScene(client, state, fonts),
        SceneId.AFTER_MATCH: AfterMatchScene(client, state, fonts),
    }

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # 1. Kontrola lokálního timeoutu (detekce vlastního odpojení)
        if state.in_game and state.last_server_contact > 0:
            if (
                pygame.time.get_ticks() - state.last_server_contact > 7000
            ):  # 7 sekund bez PINGu
                log_err(state, "Server heartbeat lost.")
                client.errors.put("Disconnected: Server timeout")
                state.last_server_contact = 0

        # 2. Zpracování zpráv
        while True:
            try:
                msg: Message = client.inbox.get_nowait()
                log_rx(state, msg)
                nxt = scenes[state.scene].on_message(msg)
                if nxt:
                    state.scene = nxt
            except Empty:
                break

        # 3. AUTOMATICKÝ RECONNECT
        while True:
            try:
                err = client.errors.get_nowait()
                if "Disconnected" in err or "Send failed" in err:
                    client.close()
                    if state.username and state.in_game:
                        log_sys(state, "Connection lost. Retrying in 1s...")
                        pygame.time.wait(1000)
                        try:
                            client.connect()
                            if client.connected:
                                # DŮLEŽITÉ: Resetujeme čas kontaktu hned po připojení
                                state.last_server_contact = pygame.time.get_ticks()
                                client.send("REQ_LOGIN", state.username)
                                log_sys(
                                    state, f"Auto-reconnect sent for {state.username}"
                                )
                        except:
                            pass
                    else:
                        state.scene = SceneId.CONNECT
                    break
            except Empty:
                break

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_BACKQUOTE:
                state.debug_visible = not state.debug_visible
            scenes[state.scene].handle_event(e)

        # Timery (Toast, Round result)
        if state.toast_ttl > 0:
            state.toast_ttl -= dt
            if state.toast_ttl <= 0:
                state.toast = ""
        if state.scene == SceneId.GAME and state.round_result_visible:
            state.round_result_ttl -= dt
            if state.round_result_ttl <= 0:
                state.round_result_visible = False

        scenes[state.scene].draw(screen)
        pygame.display.flip()

    client.close()
    pygame.quit()


if __name__ == "__main__":
    main()
