from typing import Tuple

import pygame

# =============================
# UI components
# =============================


class InputField:
    def __init__(self, rect: pygame.Rect, placeholder: str):
        self.rect = rect
        self.placeholder = placeholder
        self.text = ""
        self.active = False

    def handle(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(e.pos)

        if e.type == pygame.KEYDOWN and self.active:
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                pass
            else:
                if e.unicode and e.unicode.isprintable():
                    self.text += e.unicode

    def draw(self, surf: pygame.Surface, font: pygame.font.Font) -> None:
        bg = (30, 30, 38) if self.active else (24, 24, 30)
        pygame.draw.rect(surf, bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, (120, 120, 140), self.rect, width=1, border_radius=10)

        s = self.text if self.text else self.placeholder
        c = (235, 235, 245) if self.text else (150, 150, 165)
        txt = font.render(s, True, c)
        surf.blit(
            txt,
            (
                self.rect.x + 12,
                self.rect.y + (self.rect.height - txt.get_height()) // 2,
            ),
        )


class HUDButton:
    def __init__(self, rect: pygame.Rect, label: str):
        self.rect = rect
        self.label = label
        self.enabled = True

    def hit(self, pos: Tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(pos)

    def draw(
        self, surf: pygame.Surface, font: pygame.font.Font, mouse: Tuple[int, int]
    ) -> None:
        hover = self.enabled and self.rect.collidepoint(mouse)
        base = (55, 55, 70) if self.enabled else (35, 35, 45)
        if hover:
            base = (75, 75, 95)

        pygame.draw.rect(surf, base, self.rect, border_radius=14)
        pygame.draw.rect(surf, (160, 160, 190), self.rect, width=1, border_radius=14)

        txt = font.render(
            self.label,
            True,
            (245, 245, 255) if self.enabled else (160, 160, 175),
        )
        surf.blit(txt, txt.get_rect(center=self.rect.center))


class MoveButton:
    def __init__(self, rect: pygame.Rect, move: str, title: str):
        self.rect = rect
        self.move = move
        self.title = title
        self.enabled = True

    def hit(self, pos: Tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(pos)

    def draw(
        self,
        surf: pygame.Surface,
        font_big: pygame.font.Font,
        font: pygame.font.Font,
        mouse: Tuple[int, int],
    ) -> None:
        hover = self.enabled and self.rect.collidepoint(mouse)

        bg = (26, 26, 34) if self.enabled else (18, 18, 22)
        edge = (160, 160, 190) if hover else (110, 110, 135)
        glow = (90, 90, 120) if hover else (60, 60, 80)

        pygame.draw.rect(surf, bg, self.rect, border_radius=18)
        pygame.draw.rect(surf, edge, self.rect, width=2, border_radius=18)

        cx = self.rect.x + 46
        cy = self.rect.centery
        r = 26
        pygame.draw.circle(surf, glow, (cx, cy), r + 4)
        pygame.draw.circle(surf, (18, 18, 22), (cx, cy), r + 1)
        pygame.draw.circle(surf, edge, (cx, cy), r, width=2)

        letter = font_big.render(self.move, True, (245, 245, 255))
        surf.blit(letter, letter.get_rect(center=(cx, cy)))

        title = font.render(
            self.title, True, (235, 235, 245) if self.enabled else (160, 160, 175)
        )
        surf.blit(title, (self.rect.x + 86, self.rect.y + 18))

        hint = font.render("Click / press key", True, (160, 160, 175))
        surf.blit(hint, (self.rect.x + 86, self.rect.y + 42))
