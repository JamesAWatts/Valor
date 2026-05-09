import pygame

def draw_bar(screen, x, y, w, h, current, max_val, color, font=None, border_radius=8, show_numbers=True):
    from core.game_rules.constants import COLOR_GRAY, COLOR_BLACK
    ratio = min(1.0, current / max_val) if max_val > 0 else 0

    # Background (Darker grey/black)
    pygame.draw.rect(screen, (40, 40, 40), (x, y, w, h), border_radius=border_radius)

    # Fill
    if ratio > 0:
        fill_w = int(w * ratio)
        # Ensure fill doesn't look weird when very small with large radius
        # But for simplicity, we'll just draw it with the same radius
        pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=border_radius)

    # Gold Border
    from core.game_rules.constants import COLOR_GOLD
    pygame.draw.rect(screen, COLOR_GOLD, (x, y, w, h), 2, border_radius=border_radius)

    if font and show_numbers:
        from interfaces.pygame.ui.panel import draw_text_outlined
        text_str = f"{int(current)} / {int(max_val)}"
        tw, th = font.size(text_str)
        tx = x + w // 2 - tw // 2
        ty = y + h // 2 - th // 2
        draw_text_outlined(screen, text_str, font, (255, 255, 255), tx, ty)