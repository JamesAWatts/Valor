import pygame
import random
from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.panel import Panel, draw_text_outlined
from interfaces.pygame.ui.inventory_panel import InventoryPanel
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE
from core.players.player import load_weapons, load_armor, load_trinkets, load_shields, validate_player_data

class HubState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)

        # Ensure player data is valid and stats are recalculated
        validate_player_data(game.player)

        # Get persistent hub background from manager
        self.background = BackgroundManager.get_hub_bg(game.player)

        self.base_options = ["Fight", "Shop", "Blacksmith", "Rest", "Save Game", "Inventory", "Settings", "Retire"]
        options = list(self.base_options)
        if game.god_mode:
            options += ["Level Up", "Invincible"]

        self.menu = Menu(options, font, width = 50)
        
        # --- Cheat Code Setup ---
        self.cheat_code = [pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN, 
                           pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT]
        self.current_input_sequence = []
        
        self.sub_menu = None
        self.menu_state = "MAIN"
        self.active_menu = self.menu
        
        # Load data for inventory panel
        weapons_db = load_weapons().get('weapon_list', {})
        armor_db = load_armor()
        shields_db = load_shields()
        trinkets_db = load_trinkets()
        
        self.inventory_panel = InventoryPanel(font, weapons_db, armor_db, shields_db, trinkets_db)

    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)
        elif self.menu_state == "DEV":
            self.handle_dev_menu(option)

    def update(self, events):
        # Check for cheat code keys
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                    self.current_input_sequence.append(event.key)
                    # Keep only the last N keys where N is the length of the cheat code
                    if len(self.current_input_sequence) > len(self.cheat_code):
                        self.current_input_sequence.pop(0)
                    
                    # Check for match
                    if self.current_input_sequence == self.cheat_code:
                        if "Dev Tools" not in self.menu.options:
                            print("DEV: Dev Tools Unlocked!")
                            new_options = list(self.menu.options)
                            new_options.append("Dev Tools")
                            self.menu.set_options(new_options)
                            self.current_input_sequence = [] # Reset after success
                else:
                    # Any other key resets the sequence
                    self.current_input_sequence = []

        super().update(events)

    def handle_main_menu(self, option):
        if option == "Fight":
            from core.creatures.enemies import load_enemy_data, get_scaled_enemies
            enemy_data = load_enemy_data()
            enemies = get_scaled_enemies(enemy_data, self.game.player.get('level', 1))

            self.game.enemies = enemies

            from .combat import CombatState
            self.game.change_state(CombatState(self.game, self.font))
        elif option == "Shop":
            from .shop_state import ShopState
            self.game.change_state(ShopState(self.game, self.font))

        elif option == "Blacksmith":
            from .blacksmith_state import BlacksmithState
            self.game.change_state(BlacksmithState(self.game, self.font))

        elif option == "Inventory":
            from .inventory_state import InventoryState
            self.game.change_state(InventoryState(self.game, self.font))

        elif option == "Save Game":
            from .save_state import SaveState
            self.game.change_state(SaveState(self.game, self.font, mode="SAVE"))

        elif option == "Retire":
            from .game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font, retired=True))

        elif option == "Settings":
            from .settings_state import SettingsState
            self.game.change_state(SettingsState(self.game, self.font, previous_state=self))

        elif option == "Rest":
            p = self.game.player
            if "inventory_ref" not in p: return
            inv = p["inventory_ref"]
            cost = 5 + p.get("rest_count", 0)

            if self.game.god_mode or inv.get("gold", 0) >= cost:
                if not self.game.god_mode: inv["gold"] -= cost
                p["current_hp"] = p.get("max_hp", 10)
                p["current_mp"] = p.get("max_mp", 0)
                p["current_sp"] = p.get("max_sp", 0)
                p["rest_count"] = p.get("rest_count", 0) + 1
                validate_player_data(p)
            else:
                print("DEBUG: Not enough gold to rest")

        elif option == "Dev Tools":
            dev_options = ["1,000 HP", "10,000 Gold", "Level Up", "Restart Game", "Back"]
            self.sub_menu = Menu(dev_options, self.font, header="Dev Tools")
            self.menu_state = "DEV"
            self.active_menu = self.sub_menu

    def handle_dev_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.menu
        else:
            from interfaces.pygame.Dev_Mode import DevTools
            msg = DevTools.apply_dev_action(option, self.game)
            if msg:
                print(f"DEV: {msg}")
            
            if option != "Restart Game":
                pass

    def draw(self, screen):
        # --- Draw background FIRST ---
        self.draw_background(screen)

        width, height = screen.get_size()
        p = self.game.player

        # --- Title ---
        title_str = "Adventure Hub"
        tw, th = self.font.size(title_str)
        title_y = scale_y(40)
        draw_text_outlined(
            screen,
            title_str,
            self.font,
            (255, 255, 255),
            width // 2 - tw // 2,
            title_y
        )
        
        # --- Gold (Under Title) ---
        gold_val = p.get('inventory_ref', {}).get('gold', 0)
        gold_str = f"Gold: {gold_val}"
        gw, gh = self.font.size(gold_str)
        gold_y = title_y + th + scale_y(5)
        draw_text_outlined(screen, gold_str, self.font, COLOR_GOLD, width // 2 - gw // 2, gold_y)

        # --- Player Info Panel ---
        self.inventory_panel.draw(screen, p)

        # --- Player Bars (Top Center - Shifted Down) ---
        from interfaces.pygame.ui.bars import draw_bar

        if p:
            # Shifted down to accommodate title and gold
            bx = width // 2 - scale_x(100)
            by = gold_y + gh + scale_y(15)

            cur_hp = min(p.get("max_hp", 10), p.get("current_hp", p.get("hp", 10)))
            draw_bar(screen, bx, by, scale_x(200), scale_y(25),
                     cur_hp, p.get("max_hp", 10), (200, 50, 50), self.font)

            if p.get("max_mp", 0) > 0:
                cur_mp = min(p.get("max_mp", 0), p.get("current_mp", 0))
                draw_bar(screen, bx, by + scale_y(30), scale_x(200), scale_y(25),
                         cur_mp, p.get("max_mp", 0), (50, 100, 200), self.font)
            
            if p.get("max_sp", 0) > 0:
                y_off = scale_y(60) if p.get("max_mp", 0) > 0 else scale_y(30)
                cur_sp = min(p.get("max_sp", 0), p.get("current_sp", 0))
                draw_bar(screen, bx, by + y_off, scale_x(200), scale_y(25),
                         cur_sp, p.get("max_sp", 0), (255, 200, 0), self.font)

        # --- MENU (Left Aligned) ---
        if self.active_menu:
            menu_width = self.active_menu.get_width()
            
            # Precisely calculate menu height to match Menu.py's internal layout
            line_h = self.font.get_height()
            spacing = line_h + scale_y(5)
            header_h = (line_h + scale_y(15)) if self.active_menu.header else 0
            # Total height from the 'start_y' parameter to the bottom of the panel
            menu_height_below_start = header_h + (len(self.active_menu.options) * spacing) + scale_y(25)
            
            # Align to the left side with 20px padding
            menu_center_x = (menu_width // 2) + scale_x(20)
            
            # Align bottom with player panel (which ends at height - scale_y(40))
            menu_start_y = (height - scale_y(40)) - menu_height_below_start
            
            self.active_menu.draw(screen, menu_center_x, menu_start_y)
            
        # --- Tooltip (Draw LAST) ---
        self.inventory_panel.draw_tooltip(screen)

    # REMOVE OLD DRAWING METHODS
