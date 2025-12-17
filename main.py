from __future__ import annotations

from queue import Empty

import pygame

from network import TcpLineClient
from protocol import Message
from scenes import AfterMatchScene, ConnectScene, GameScene, LobbyScene
from state import AppState, H, SceneId, W, log_err, log_rx, toast


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("UPS – Rock Paper Scissors")

    clock = pygame.time.Clock()

    # Fonty
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
        dt = clock.tick(60) / 1000.0  # Uplynulý čas v sekundách (důležité pro časovače)

        # Zpracování zpráv ze serveru
        while True:
            try:
                msg: Message = client.inbox.get_nowait()
                log_rx(state, msg)
                nxt = scenes[state.scene].on_message(msg)
                if nxt:
                    state.scene = nxt
            except Empty:
                break

        # Zpracování chyb sítě (odpojení atd.)
        while True:
            try:
                err = client.errors.get_nowait()
                log_err(state, err)

                # Pokud dojde k odpojení během hry nebo lobby
                if "Disconnected" in err or "Send failed" in err:
                    client.close()
                    toast(state, "Connection lost! Attempting auto-reconnect...", 5.0)

                    # Pokus o okamžité znovupřipojení na pozadí
                    try:
                        client.connect()  # Zkusí otevřít socket
                        if client.connected and state.username:
                            # Pokud se spojení povedlo, hned pošleme LOGIN
                            client.send("REQ_LOGIN", state.username)
                            log_sys(state, f"Auto-reconnecting as {state.username}...")
                        else:
                            # Pokud se nepovedlo (kabel je stále venku), jdeme do CONNECT scény
                            state.scene = SceneId.CONNECT
                            state.user_id = ""
                    except Exception as e:
                        log_err(state, f"Auto-reconnect failed: {e}")
                        state.scene = SceneId.CONNECT
                    break
            except Empty:
                break

        # Zpracování událostí
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            # Toggle Debug
            if e.type == pygame.KEYDOWN and e.key == pygame.K_BACKQUOTE:
                state.debug_visible = not state.debug_visible

            scenes[state.scene].handle_event(e)

        # LOGIKA PRO ODPOČTY (časovače)

        # Odpočet toastu
        if state.toast_ttl > 0:
            state.toast_ttl -= dt
            if state.toast_ttl <= 0:
                state.toast = ""

        # Odpočet zobrazení výsledku kola (pouze ve scéně GAME)
        if state.scene == SceneId.GAME and state.round_result_visible:
            state.round_result_ttl -= dt
            if state.round_result_ttl <= 0:
                state.round_result_visible = False
                state.last_round = ""

        # Vykreslení
        scenes[state.scene].draw(screen)
        pygame.display.flip()

    client.close()
    pygame.quit()


if __name__ == "__main__":
    main()
