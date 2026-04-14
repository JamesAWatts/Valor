import pygame
from core.game_rules.constants import scale_y, scale_x, COLOR_ROYAL_BLUE, COLOR_GOLD
from interfaces.pygame.ui.panel import Panel

class Menu:
    def __init__(self, options, font, pos=(0, 0), header=None, disabled_indices=None, bg_color=(30, 30, 50), border_color=COLOR_GOLD, alpha=220, width = 100, descriptions=None):
        self.font = font
        self.pos = pos # Raw screen coordinates (e.g. 1280x720)
        self.header = header
        self.disabled_indices = disabled_indices if disabled_indices is not None else []
        self.bg_color = bg_color
        self.border_color = border_color
        self.alpha = alpha
        self.width = width
        self.descriptions = descriptions # Dictionary mapping option text to description string
        self.set_options(options)
        self.option_rects = []

    def get_width(self):
        """Returns the SCALED width of the menu."""
        from core.game_rules.constants import SCALE_X
        return self.get_raw_width() * SCALE_X

    def get_raw_width(self):
        """Returns the RAW (unscaled) width needed for the menu."""
        from core.game_rules.constants import SCALE_X
        max_text_width = 0
        if self.header:
            hw, _ = self.font.size(self.header)
            max_text_width = hw

        for option in self.options:
            text = "> " + str(option)
            w, _ = self.font.size(text)
            max_text_width = max(max_text_width, w)
            
        raw_text_w = max_text_width / SCALE_X
        return max(raw_text_w + 40, self.width)

    def set_options(self, options):
        self.options = options
        self.selected = 0

    def is_disabled(self, index):
        return index in self.disabled_indices

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                return self.options[self.selected]
            elif event.key == pygame.K_BACKSPACE:
                return "BACK"
        return None

    def handle_mouse(self, mouse_pos, mouse_click):
        if not self.option_rects:
            return None

        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected = i  
                if mouse_click:
                    return i 
        return None

    def draw(self, screen, center_x=None, start_y=None, force_bottom_desc=False):
        from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y, scale_y, scale_x
        
        # passed values are screen-space (1280x720)
        if center_x is None: center_x = self.pos[0]
        if start_y is None: start_y = self.pos[1]
        
        # --- CALCULATE DIMENSIONS ---
        line_h = self.font.get_height()
        spacing = line_h + scale_y(5)
        
        header_h = (line_h + scale_y(15)) if self.header else 0
        top_pad = scale_y(15)
        bottom_pad = scale_y(25)
        
        # get_width() returns scaled width
        w = self.get_width()
        h = header_h + (len(self.options) * spacing) + top_pad + bottom_pad

        # Anchor Logic (Screen Space)
        panel_x = center_x - w // 2
        panel_y = start_y - top_pad

        # --- CLAMPING (Screen Space) ---
        if panel_x < scale_x(5): panel_x = scale_x(5)
        if panel_x + w > SCREEN_WIDTH - scale_x(5): panel_x = SCREEN_WIDTH - scale_x(5) - w
        if panel_y < scale_y(5): panel_y = scale_y(5)
        if panel_y + h > SCREEN_HEIGHT - scale_y(5): panel_y = SCREEN_HEIGHT - scale_y(5) - h

        # Draw Panel (Panel expects raw, but we'll bypass scaling by passing 1.0 or modifying Panel)
        # Better: Update Panel to accept 'is_scaled' or just pass raw values by dividing.
        # But for now, let's keep it simple and just use raw values for Panel input.
        raw_w = w / SCALE_X
        raw_h = h / SCALE_Y
        raw_x = panel_x / SCALE_X
        raw_y = panel_y / SCALE_Y

        panel = Panel(
            raw_x, raw_y, raw_w, raw_h,
            bg_color=self.bg_color, border_color=self.border_color,
            border_width=3, centered=False, border_radius=15, alpha=self.alpha
        )
        rect = panel.draw(screen) 
        
        self.option_rects = []
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        # Draw Content (Screen Space)
        draw_center_x = rect.centerx
        current_y = rect.y + top_pad
        
        if self.header:
            tw, th = self.font.size(self.header)
            draw_text_outlined(screen, self.header, self.font, COLOR_GOLD, draw_center_x - tw // 2, current_y)
            current_y += (line_h + scale_y(10))
            
            line_y = current_y - scale_y(5)
            pygame.draw.line(screen, self.border_color, (rect.x + scale_x(10), line_y), (rect.right - scale_x(10), line_y), 2)

        for i, option in enumerate(self.options):
            color = (255, 255, 0) if i == self.selected else (255, 255, 255)
            if self.is_disabled(i): color = (150, 150, 150)

            text_str = ("> " if i == self.selected else "  ") + str(option)
            tw, th = self.font.size(text_str)
            text_x = draw_center_x - tw // 2
            text_y = current_y + i * spacing
            self.option_rects.append(draw_text_outlined(screen, text_str, self.font, color, text_x, text_y))

        # --- Tooltip ---
        if self.descriptions:
            selected_option = str(self.options[self.selected])
            desc_text = self.descriptions.get(selected_option)
            if desc_text:
                if force_bottom_desc:
                    self.draw_description(screen, draw_center_x, rect.bottom + 10 * SCALE_Y, raw_w, desc_text, centered=True)
                elif draw_center_x < SCREEN_WIDTH // 2:
                    self.draw_description(screen, rect.right + 5 * SCALE_X, rect.y, 250, desc_text, centered=False)
                else:
                    self.draw_description(screen, draw_center_x, rect.bottom + 10 * SCALE_Y, raw_w, desc_text, centered=True)

    def draw_description(self, screen, x, y, raw_w, text, centered=True):
        from core.game_rules.constants import SCALE_X, SCALE_Y, scale_y, scale_x
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        scaled_w = raw_w * SCALE_X
        words = str(text).split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            tw, th = self.font.size(test_line)
            if tw > scaled_w - 20 * SCALE_X:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        lines.append(' '.join(current_line))
        
        raw_line_h = self.font.get_height() / SCALE_Y
        raw_spacing = raw_line_h + 2
        raw_h = (len(lines) * raw_spacing) + 30
        
        raw_x = x / SCALE_X if not centered else (x / SCALE_X) - raw_w // 2
        raw_y = y / SCALE_Y
        
        # Clamp Tooltip (Raw 800x600)
        if raw_x < 5: raw_x = 5
        if raw_x + raw_w > 795: raw_x = 795 - raw_w
        if raw_y + raw_h > 595: raw_y = 595 - raw_h
        
        panel = Panel(
            raw_x, raw_y, raw_w, raw_h,
            bg_color=(20, 20, 40), border_color=COLOR_GOLD, border_width=2,
            centered=False, border_radius=10, alpha=230
        )
        rect = panel.draw(screen)
        
        spacing = raw_spacing * SCALE_Y
        for i, line in enumerate(lines):
            lw, lh = self.font.size(line)
            draw_text_outlined(screen, line, self.font, (220, 220, 220), rect.centerx - lw // 2, rect.y + 15 * SCALE_Y + i * spacing)
