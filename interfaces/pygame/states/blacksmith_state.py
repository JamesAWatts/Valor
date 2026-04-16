import pygame
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from core.players.blacksmith import UPGRADE_COSTS, ENCHANTMENTS, get_weapon_upgrade_info, upgrade_weapon, enchant_weapon, can_upgrade, can_enchant
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, COLOR_GOLD, COLOR_WHITE

class BlacksmithState(BaseState):
    def __init__(self, game, font, player=None):
        super().__init__(game, font)
        # Use a specialized background if available, or fallback to shop/rest
        try:
            self.background = BackgroundManager.get_shop_bg()
        except:
            self.background = BackgroundManager.get_rest_bg()

        self.player = player if player else game.player
        self.inventory = self.player.get("inventory_ref", {})
        self.mode = "MAIN"
        self.selected_weapon = self.player.get('weapon', 'unarmed')
        
        self.main_menu = Menu(["Upgrade Weapon", "Enchant Weapon", "Back"], font, width=200, header="The Iron Anvil")
        self.active_menu = self.main_menu

    def refresh_upgrade_menu(self):
        weapons = self.inventory.get('weapon', {})
        options = []
        descriptions = {}
        
        # Always include currently equipped weapon even if not in inventory count
        equipped = self.player.get('weapon', 'unarmed')
        weapon_list = sorted(list(set(list(weapons.keys()) + [equipped])))
        
        for w in weapon_list:
            info = get_weapon_upgrade_info(self.player, w)
            level = info['level']
            display_name = f"{w.replace('_', ' ').title()} (+{level})"
            options.append(display_name)
            
            if level < 3:
                cost = UPGRADE_COSTS[level + 1]
                descriptions[display_name] = f"Upgrade to +{level+1} for {cost}g. Increases damage, accuracy, and Spell DC."
            else:
                descriptions[display_name] = "Max level reached."
                
        options.append("Back")
        self.active_menu = Menu(options, self.font, width=250, header="Select Weapon to Upgrade", descriptions=descriptions)

    def refresh_enchant_menu(self):
        options = []
        descriptions = {}
        
        for key, data in ENCHANTMENTS.items():
            display_name = f"{key.title()} ({data['cost']}g)"
            options.append(display_name)
            descriptions[display_name] = data['description']
            
        options.append("Back")
        self.active_menu = Menu(options, self.font, width=250, header=f"Enchant {self.selected_weapon.title()}", descriptions=descriptions)

    def on_select(self, option):
        if self.mode == "MAIN":
            if option == "Upgrade Weapon":
                self.mode = "UPGRADE"
                self.refresh_upgrade_menu()
            elif option == "Enchant Weapon":
                self.mode = "ENCHANT_SELECT_WEAPON"
                self.refresh_upgrade_menu() # Re-use weapon select logic
                self.active_menu.header = "Select Weapon to Enchant"
            elif option == "Back":
                from interfaces.pygame.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))

        elif self.mode == "UPGRADE":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                weapon_name = option.split(" (+")[0].replace(" ", "_").lower()
                success, msg = upgrade_weapon(self.player, weapon_name)
                print(f"BLACKSMITH: {msg}")
                self.refresh_upgrade_menu()

        elif self.mode == "ENCHANT_SELECT_WEAPON":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                self.selected_weapon = option.split(" (+")[0].replace(" ", "_").lower()
                self.mode = "ENCHANT"
                self.refresh_enchant_menu()

        elif self.mode == "ENCHANT":
            if option == "Back":
                self.mode = "ENCHANT_SELECT_WEAPON"
                self.refresh_upgrade_menu()
                self.active_menu.header = "Select Weapon to Enchant"
            else:
                enchant_key = option.split(" (")[0].lower()
                success, msg = enchant_weapon(self.player, self.selected_weapon, enchant_key)
                print(f"BLACKSMITH: {msg}")
                self.mode = "MAIN"
                self.active_menu = self.main_menu

    def draw(self, screen):
        self.draw_background(screen)
        
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        # Show Gold
        gold_text = f"Gold: {self.inventory.get('gold', 0)}"
        gw, gh = self.font.size(gold_text)
        draw_text_outlined(screen, gold_text, self.font, COLOR_GOLD, (SCREEN_WIDTH // 2) - (gw // 2), scale_y(40))

        if self.active_menu:
            # Center the menu (Base 400, 300)
            self.active_menu.draw(screen, 400, 300)
