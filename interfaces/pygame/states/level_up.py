import os
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.inventory_panel import InventoryPanel
from core.players.leveler import load_player_classes, add_class_level
from core.players.player import load_weapons, load_armor, load_shields, load_trinkets
from core.game_rules.constants import COLOR_BG, COLOR_LIGHT_GRAY, SCREEN_WIDTH, scale_x, scale_y

class LevelUpState(BaseState):
    def __init__(self, game, font, player=None, is_dev_mode=False):
        super().__init__(game, font)
        self.is_dev_mode = is_dev_mode
        self.mode = "CLASS_SELECT"
        
        # Current player being leveled
        self.player = player if player else self.game.player

        # Use manager to pick random background
        self.background = BackgroundManager.get_levelup_bg()

        # Load data for inventory panel
        weapons_db = load_weapons().get('weapon_list', {})
        armor_db = load_armor()
        shields_db = load_shields()
        trinkets_db = load_trinkets()
        self.inventory_panel = InventoryPanel(font, weapons_db, armor_db, shields_db, trinkets_db)

        self.refresh_class_menu()

    def refresh_class_menu(self):
        self.class_names = [name.title() for name in load_player_classes().keys()]
        
        from core.players.leveler import get_level_up_benefits
        descriptions = {}
        for name in self.class_names:
            descriptions[name] = get_level_up_benefits(self.player, name)

        # 25% transparent means 75% opacity, alpha = 255 * 0.75 = 191
        self.menu = Menu(self.class_names, self.font, bg_color=COLOR_BG, border_color=COLOR_LIGHT_GRAY, alpha=191, width=200, descriptions=descriptions, pos=(150, 150))
        self.active_menu = self.menu

    def on_select(self, option):
        if self.mode == "CLASS_SELECT":
            add_class_level(self.player, option.lower())
            
            # If dev mode and not max level, ask to level up again
            if self.is_dev_mode and self.player.get('level', 1) < 20:
                self.mode = "AGAIN_PROMPT"
                self.active_menu = Menu(["Yes", "No"], self.font, header="Level up again?")
            else:
                self.finish_level_up()
                
        elif self.mode == "AGAIN_PROMPT":
            if option == "Yes":
                self.mode = "CLASS_SELECT"
                self.refresh_class_menu()
            else:
                self.finish_level_up()

    def finish_level_up(self):
        # Check if anyone else needs to level up
        from core.players.leveler import needs_level_up
        next_player = None
        for p in self.game.party:
            if needs_level_up(p):
                next_player = p
                break
        
        if next_player:
            # Re-init this state with the next player
            self.game.change_state(LevelUpState(self.game, self.font, player=next_player, is_dev_mode=self.is_dev_mode))
        else:
            from interfaces.pygame.states.hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    def draw(self, screen):
        # Draw background manually to avoid super().draw() centering the menu
        self.draw_background(screen)

        from interfaces.pygame.ui.panel import draw_text_outlined
        title_text = f"Level Up: {self.player.get('name', 'Adventurer')}!"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255, 255, 0), (SCREEN_WIDTH // 2) - (tw // 2), 50)

        # Position class selection menu on the left
        if self.active_menu:
            self.active_menu.draw(screen, 150, 150, force_bottom_desc=True)

        # Draw Player Info Panel (on the right)
        self.inventory_panel.draw(screen, self.player)
        self.inventory_panel.draw_tooltip(screen)

