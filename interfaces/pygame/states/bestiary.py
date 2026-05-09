import pygame
import os
import json
import random
from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.panel import Panel, draw_text_outlined
from interfaces.pygame.graphics.enemy_sprites import SpriteManager
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y, COLOR_GOLD, COLOR_WHITE, COLOR_GRAY

class BestiaryState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_hub_bg(game.player)
        
        self.menu_state = "CHAPTERS"
        self.creature_types = [f.replace('.json', '') for f in os.listdir(get_resource_path(os.path.join('data', 'creatures'))) if f.endswith('.json')]
        self.chapters_menu = Menu([t.title() for t in self.creature_types] + ["Back"], font, header="Creature Chapters", width=300)
        self.active_menu = self.chapters_menu
        
        self.selected_type = None
        self.creatures_list = []
        self.creatures_menu = None
        
        self.current_creature_idx = 0
        self.spec_nav_menu = Menu(["Previous", "Next", "Return"], font, width=150, pos=(100, 80))
        
        # UI Elements
        self.stat_panel = Panel(SCREEN_WIDTH - scale_x(320), scale_y(50), scale_x(300), scale_y(220), alpha=200)
        self.loot_panel = Panel(SCREEN_WIDTH - scale_x(320), scale_y(280), scale_x(300), scale_y(140), alpha=200)
        self.ability_panel = Panel(SCREEN_WIDTH - scale_x(320), scale_y(430), scale_x(300), scale_y(150), alpha=200)
        self.sprite_panel = Panel(scale_x(50), scale_y(150), scale_x(400), scale_y(400), alpha=150)

    def on_select(self, option):
        if self.menu_state == "CHAPTERS":
            if option == "Back":
                from .hub import HubState
                self.game.change_state(HubState(self.game, self.font))
            else:
                self.selected_type = option.lower()
                self.load_creatures_of_type(self.selected_type)
                self.menu_state = "CREATURES"
                self.active_menu = self.creatures_menu
        elif self.menu_state == "CREATURES":
            if option == "Back":
                self.menu_state = "CHAPTERS"
                self.active_menu = self.chapters_menu
            else:
                # Find index
                for i, c in enumerate(self.creatures_list):
                    if c['name'].replace('_', ' ').title() == option.split(" (Lv")[0]:
                        self.current_creature_idx = i
                        break
                self.menu_state = "SPEC_SHEET"
                self.active_menu = self.spec_nav_menu
        elif self.menu_state == "SPEC_SHEET":
            if option == "Previous":
                self.prev_creature()
            elif option == "Next":
                self.next_creature()
            elif option == "Return":
                self.menu_state = "CHAPTERS"
                self.active_menu = self.chapters_menu

    def load_creatures_of_type(self, c_type):
        path = get_resource_path(os.path.join('data', 'creatures', f"{c_type}.json"))
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                # Data is often a dict with 'enemies' or just a list?
                # Looking at enemies.py, it expects a list or dict of categories.
                # Actually data/creatures/*.json are dicts mapping internal name to stats.
                self.creatures_list = []
                for key, stats in data.items():
                    stats['internal_name'] = key
                    stats['category'] = c_type
                    self.creatures_list.append(stats)
                
                # Sort by level
                self.creatures_list.sort(key=lambda x: x.get('level', 1))
                
                options = [f"{c['name'].replace('_', ' ').title()} (Lv {c.get('level', 1)})" for c in self.creatures_list]
                self.creatures_menu = Menu(options + ["Back"], self.font, header=f"{c_type.title()} List", width=400)
        except Exception as e:
            print(f"Error loading bestiary category {c_type}: {e}")
            self.creatures_list = []

    def next_creature(self):
        if self.current_creature_idx < len(self.creatures_list) - 1:
            self.current_creature_idx += 1

    def prev_creature(self):
        if self.current_creature_idx > 0:
            self.current_creature_idx -= 1

    def update(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.menu_state == "SPEC_SHEET":
                        self.menu_state = "CHAPTERS"
                        self.active_menu = self.chapters_menu
                    elif self.menu_state == "CREATURES":
                        self.menu_state = "CHAPTERS"
                        self.active_menu = self.chapters_menu
                    else:
                        from .hub import HubState
                        self.game.change_state(HubState(self.game, self.font))
                    return
                
                if self.menu_state == "SPEC_SHEET":
                    if event.key == pygame.K_LEFT:
                        self.prev_creature()
                    elif event.key == pygame.K_RIGHT:
                        self.next_creature()
        
        super().update(events)

    def draw(self, screen):
        self.draw_background(screen)
        
        if self.menu_state in ["CHAPTERS", "CREATURES"]:
            if self.active_menu:
                self.active_menu.draw(screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        elif self.menu_state == "SPEC_SHEET":
            self.draw_spec_sheet(screen)

    def draw_spec_sheet(self, screen):
        creature = self.creatures_list[self.current_creature_idx]
        e_type = creature.get('internal_name', creature.get('name', 'enemy').lower().replace(' ', '_'))
        rp = self.game.bestiary_rp.get(e_type, 0)
        
        # 1. Navigation Menu
        self.spec_nav_menu.draw(screen, scale_x(100), scale_y(80))
        
        # 2. Sprite Panel
        self.sprite_panel.draw(screen)
        # Horizontally flipped sprite
        sz = scale_x(250)
        sprite = SpriteManager.get_enemy_sprite(e_type, category=creature.get('category'), size=(sz, sz))
        if sprite:
            sprite = pygame.transform.flip(sprite, True, False)
            screen.blit(sprite, (self.sprite_panel.rect.centerx - sz // 2, self.sprite_panel.rect.centery - sz // 2))
        
        # RP Display
        rp_text = f"Research Points: {rp}"
        tw, th = self.font.size(rp_text)
        draw_text_outlined(screen, rp_text, self.font, COLOR_GOLD, self.sprite_panel.rect.centerx - tw // 2, self.sprite_panel.rect.bottom - scale_y(40))
        
        # 3. Stat Block (Threshold 5 RP)
        self.stat_panel.draw(screen)
        name_str = f"{creature['name'].replace('_', ' ').title()}'s Stats"
        nw, nh = self.font.size(name_str)
        draw_text_outlined(screen, name_str, self.font, COLOR_GOLD, self.stat_panel.rect.centerx - nw // 2, self.stat_panel.rect.y + scale_y(10))
        
        stats_y = self.stat_panel.rect.y + scale_y(50)
        if rp >= 5:
            stats = [
                ("Level", creature.get('level', 1)),
                ("HP", creature.get('hp', 10) if rp >= 1 else "???"),
                ("AC", creature.get('ac', 10)),
                ("Proficiency", creature.get('proficiency_bonus', 0)),
                ("Attacks", creature.get('attack_count', 1)),
                ("Damage", f"d{creature.get('die', 4)}")
            ]
            for label, val in stats:
                draw_text_outlined(screen, f"{label}:", self.font, COLOR_WHITE, self.stat_panel.rect.x + scale_y(20), stats_y)
                draw_text_outlined(screen, str(val), self.font, COLOR_GOLD, self.stat_panel.rect.right - scale_x(100), stats_y)
                stats_y += scale_y(25)
        else:
            # Masked stats
            draw_text_outlined(screen, "Requires 5 RP to unlock", self.font, COLOR_GRAY, self.stat_panel.rect.x + scale_y(20), stats_y)

        # 4. Loot Drops Panel
        self.loot_panel.draw(screen)
        draw_text_outlined(screen, "Loot Drops", self.font, COLOR_GOLD, self.loot_panel.rect.x + scale_y(10), self.loot_panel.rect.y + scale_y(5))
        
        # Unlock at Party Level 31
        party_lvl = sum(p.get('level', 1) for p in self.game.party)
        if party_lvl >= 31:
            loot_data = creature.get('reward', {})
            gold_range = f"{loot_data.get('gold', 10)} - {loot_data.get('gold', 10) + creature.get('level', 1) * 5}"
            draw_text_outlined(screen, f"Gold: {gold_range}", self.font, COLOR_WHITE, self.loot_panel.rect.x + scale_y(20), self.loot_panel.rect.y + scale_y(40))
            
            items = loot_data.get('items', [])
            item_y = self.loot_panel.rect.y + scale_y(65)
            for i_data in items[:3]: 
                item_name = i_data[1].replace('_', ' ').title()
                draw_text_outlined(screen, f"- {item_name}", self.font, COLOR_WHITE, self.loot_panel.rect.x + scale_y(20), item_y)
                item_y += scale_y(25)
        else:
            draw_text_outlined(screen, "Requires Party Level 31", self.font, COLOR_GRAY, self.loot_panel.rect.x + scale_y(20), self.loot_panel.rect.y + scale_y(40))

        # 5. Abilities Panel (Threshold 10 RP)
        self.ability_panel.draw(screen)
        draw_text_outlined(screen, "Abilities", self.font, COLOR_GOLD, self.ability_panel.rect.x + scale_y(10), self.ability_panel.rect.y + scale_y(5))
        
        if rp >= 10:
            abilities = creature.get('skills', []) + creature.get('spells', [])
            # Filter non-healing if needed? User said "non-healing abilities"
            # For now listing all
            ability_y = self.ability_panel.rect.y + scale_y(40)
            from core.combat.enemy_ai import EnemyAI
            for a_name in abilities[:4]:
                data = EnemyAI.get_ability_data(a_name)
                if not data: continue
                if data.get('type') == 'heal': continue
                
                name_disp = a_name.replace('_', ' ').title()
                if rp >= 40:
                    # Show baked damage and description
                    # We need a dummy actor to resolve math? 
                    # Or just show the raw formula if it has placeholders
                    die = data.get('damage_die', data.get('die', ''))
                    desc = data.get('description', '')
                    draw_text_outlined(screen, f"{name_disp} ({die})", self.font, COLOR_GOLD, self.ability_panel.rect.x + scale_y(20), ability_y)
                    # Very simple wrap or just truncate for now
                    ability_y += scale_y(20)
                    draw_text_outlined(screen, desc[:35] + "...", self.font, COLOR_WHITE, self.ability_panel.rect.x + scale_y(40), ability_y, size=scale_y(16))
                    ability_y += scale_y(30)
                else:
                    draw_text_outlined(screen, name_disp, self.font, COLOR_WHITE, self.ability_panel.rect.x + scale_y(20), ability_y)
                    ability_y += scale_y(25)
        else:
            draw_text_outlined(screen, "Requires 10 RP to unlock", self.font, COLOR_GRAY, self.ability_panel.rect.x + scale_y(20), self.ability_panel.rect.y + scale_y(40))
