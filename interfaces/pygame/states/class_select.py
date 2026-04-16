import pygame
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from core.players.player import classes

class ClassSelectState(BaseState):
    def __init__(self, game, font, hiring=False):
        super().__init__(game, font)
        # Use manager to pick a random rest/selection background
        self.background = BackgroundManager.get_rest_bg()

        self.class_names = list(classes.keys())
        self.menu = Menu(self.class_names, font, width=250)
        self.active_menu = self.menu
        self.sprite_cache = {}
        self.hiring = hiring

    def get_class_sprite(self, class_name):
        class_name = class_name.lower()
        if class_name in self.sprite_cache:
            return self.sprite_cache[class_name]

        import os
        from core.game_rules.constants import scale_x, scale_y
        from core.game_rules.path_utils import get_resource_path

        # Use get_resource_path to find the sprites dynamically
        sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", f"{class_name}.png"))

        # Handle .webp for Kobold Sorcerer if needed, or other extensions
        if not os.path.exists(sprite_path):
            sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", f"{class_name}.webp"))
        try:
            sprite = pygame.image.load(sprite_path).convert_alpha()
            # Scale sprite to a reasonable size (e.g., 200x200 raw)
            scaled_sprite = pygame.transform.scale(sprite, (scale_x(200), scale_y(200)))
            self.sprite_cache[class_name] = scaled_sprite
            return scaled_sprite
        except Exception as e:
            print(f"DEBUG: Could not load sprite for {class_name}: {e}")
            return None

    def on_select(self, option):
        new_player = self.create_player(option)
        
        if self.hiring:
            self.game.party.append(new_player)
            from .tavern import TavernState
            self.game.change_state(TavernState(self.game, self.font))
        else:
            self.game.player = new_player
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    def create_player(self, class_name):
        from core.players.player import apply_weapon_to_player, apply_armor_to_player
        from core.players.leveler import load_player_classes, get_class_stats_at_level
        from core.players.player_inventory import create_inventory

        # 1. Get initial class data from player_classes.json
        player_classes_data = load_player_classes()
        # Class names in the menu are likely capitalized, but keys in json might be lowercase
        class_key = class_name.lower()
        player_profile = get_class_stats_at_level(class_key, 1, player_classes_data)

        # 2. Set base attributes
        player_profile['class'] = class_key
        
        # Use game.party_member_name if hiring, else game.player_name
        if self.hiring:
            player_profile['name'] = getattr(self.game, 'party_member_name', 'Mercenary')
        else:
            player_profile['name'] = getattr(self.game, 'player_name', 'Adventurer')
            
        player_profile['xp'] = 0
        player_profile['level'] = 1
        player_profile['kill_count'] = 0
        player_profile['total_gold_spent'] = 0
        player_profile['max_hp'] = player_profile.get('hp', 10)
        player_profile['hp'] = player_profile['max_hp'] # Compatibility with simulator
        player_profile['current_hp'] = player_profile['max_hp'] # Compatibility with Hub/Combat
        player_profile['base_hp'] = player_profile['max_hp']

        # Mana/MP for casters
        caster_classes = ["wizard", "druid", "alchemist", "sorcerer", "cleric"]
        if class_key in caster_classes:
            player_profile['max_mp'] = 1
            player_profile['current_mp'] = 1
        else:
            player_profile['max_mp'] = 0
            player_profile['current_mp'] = 0
        
        # Stamina/SP for martial classes
        martial_classes = ["fighter", "monk", "archer", "rogue"]
        if class_key in martial_classes:
            player_profile['max_sp'] = 1
            player_profile['current_sp'] = 1
        else:
            player_profile['max_sp'] = 0
            player_profile['current_sp'] = 0
        
        # Initialize skills/spells from the class definition at level 1
        class_lvl1 = player_classes_data.get(class_key, {}).get('levels', {}).get('1', {})
        player_profile['skills'] = class_lvl1.get('skills', [])
        player_profile['spells'] = class_lvl1.get('spells', [])

        # Track class levels for multiclassing support (used by leveler)
        player_profile['class_levels'] = {class_key: 1}

        # 3. Recalculate stats to ensure all keys (spells, mp, sp, etc) are correctly populated
        from core.players.leveler import recalculate_stats
        recalculate_stats(player_profile)

        # 4. Apply equipment stats
        apply_weapon_to_player(player_profile)
        apply_armor_to_player(player_profile)

        # 5. Initialize inventory
        # Hiring characters might share gold or have their own.
        # Usually gold is shared in these games.
        if self.hiring:
            # Mercenary uses the same inventory as the lead?
            # Let's check how create_inventory works.
            player_inventory = self.game.player['inventory_ref']
        else:
            player_inventory = create_inventory(player_profile)
            
        player_profile['inventory_ref'] = player_inventory
        
        # 6. Initialize weapon upgrades
        player_profile['weapon_upgrades'] = {}
        
        # 7. Initialize other tracking stats
        player_profile['rest_count'] = 0

        return player_profile

    def draw(self, screen):
        self.draw_background(screen)
        width, height = screen.get_size()
        self.active_menu.draw(screen, width//2, height//4)


        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import scale_y
        
        title_str = "Choose Your Class"
        tw, th = self.font.size(title_str)
        draw_text_outlined(screen, title_str, self.font, (255, 255, 255), width // 2 - tw // 2, 50)

        # Draw current class sprite
        current_class = self.menu.options[self.menu.selected]
        sprite = self.get_class_sprite(current_class)
        if sprite:
            sw, sh = sprite.get_size()
            # Position at bottom center
            screen.blit(sprite, (width // 2 - sw // 2, height - sh - scale_y(20)))
