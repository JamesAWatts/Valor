import pygame
import random
from core.game_rules.constants import scale_x, scale_y

class FloatingText:
    def __init__(self, text, pos, color=(255, 255, 255), lifetime=60, rise_speed=1.0, font_size=24):
        # Initialize font if not already done
        if not pygame.font.get_init():
            pygame.font.init()
            
        try:
            self.font = pygame.font.SysFont("consolas", scale_y(font_size), bold=True)
        except:
            self.font = pygame.font.SysFont(None, scale_y(font_size), bold=True)
            
        self.text = text
        self.x, self.y = pos
        
        # Add slight horizontal randomness (juice)
        self.x += random.randint(scale_x(-20), scale_x(20))
        
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        
        self.rise_speed = rise_speed * scale_y(1)
        self.alpha = 255

    def update(self):
        self.y -= self.rise_speed
        self.rise_speed += 0.02 # Slight acceleration
        self.lifetime -= 1
        
        # Fade out
        self.alpha = int(255 * (self.lifetime / self.max_lifetime))

    def draw(self, surface):
        if self.alpha <= 0:
            return
            
        surf = self.font.render(self.text, True, self.color)
        
        # Create a copy with alpha support for fading
        temp_surf = surf.convert_alpha()
        temp_surf.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
        
        surface.blit(temp_surf, (self.x, self.y))

    def is_alive(self):
        return self.lifetime > 0


class FloatingTextManager:
    def __init__(self):
        self.texts = []
        self.COLORS = {
            "hit": (255, 255, 255),
            "miss": (180, 180, 180),
            "fail": (255, 80, 80),       # failed save
            "save": (80, 160, 255),      # resisted
            "crit": (255, 215, 0),       # gold
            "damage": (255, 50, 50),
            "heal": (50, 255, 100),
            "effect": (200, 100, 255),
            "mana": (100, 150, 255),
            "stamina": (255, 220, 100)
        }

    def add(self, text, pos, color_key="hit", lifetime=60, rise_speed=1.2):
        color = self.COLORS.get(color_key, (255, 255, 255))
        # Support passing direct color tuples too
        if isinstance(color_key, tuple):
            color = color_key
            
        self.texts.append(FloatingText(text, pos, color, lifetime, rise_speed))

    def update(self):
        for t in self.texts:
            t.update()
        self.texts = [t for t in self.texts if t.is_alive()]

    def draw(self, surface):
        for t in self.texts:
            t.draw(surface)
