import pygame
import json
import os
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.dialogue_box import DialogueBox
from core.players.player import apply_weapon_to_player, apply_armor_to_player, apply_trinket_to_player, apply_shield_to_player, load_weapons, load_armor, load_trinkets, load_shields, can_equip_armor, get_weapon_display_name, get_armor_display_name, load_consumables
from core.players.shop import visit_shop

class InventoryState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_hub_bg(game.player)
        self.dialogue = DialogueBox(self.font)
        self.message_queue = []
        
        # Mapping to remember original keys for display names
        self.item_map = {}

        self.inventory = game.player.get("inventory_ref", {})
        if not self.inventory:
            self.inventory = game.player.get("inventory", {})

        self.menus = []
        root_menu = Menu(
            ["Weapons", "Armor", "Shields", "Trinkets", "Consumables", "Back"],
            self.font,
            pos=(150, 150)
            )   
        self.menus.append(root_menu)

    def queue_message(self, text):
        self.message_queue.append(text)

    def start_next_message(self):
        if self.message_queue:
            self.dialogue.set_messages([self.message_queue.pop(0)])

    def handle_selection(self, option):
        # ROOT
        if len(self.menus) == 1:
            if option == "Back":
                from interfaces.pygame.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))
                return

            self.open_item_menu(option.lower())

        # ITEM LIST
        elif len(self.menus) == 2:
            if option == "Back":
                self.menus.pop()
                return

            # Retrieve original key from map
            item_key = self.item_map.get(option, option.split(" (")[0])
            self.open_confirm_menu(item_key)

        # CONFIRM MENU
        elif len(self.menus) == 3:
            if option == "No":
                self.menus.pop()
                return
            if option == "Yes":
                item_display = self.menus[1].options[self.menus[1].selected]
                item_key = self.item_map.get(item_display, item_display.split(" (")[0])

                result_text = self.handle_item_action(item_key)

                if result_text:
                    self.queue_message(result_text)
                    self.start_next_message()

                root = self.menus[0]
                self.menus = [root]
    
    def open_item_menu(self, category):
        if category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif category == "armor":
            data = load_armor()
        elif category == "shields":
            data = load_shields()
        elif category == "trinkets":
            data = load_trinkets()
        elif category == "consumables":
            data = load_consumables()
        else:
            return

        inv_key = category[:-1] if category.endswith('s') else category
        category_data = self.inventory.get(inv_key, {})
        
        items = sorted(category_data.keys())

        options = []
        descriptions = {}
        for item_key in items:
            if category == "weapons":
                display_name = get_weapon_display_name(self.game.player, item_key)
            elif category == "armor":
                display_name = get_armor_display_name(self.game.player, item_key)
            else:
                display_name = item_key.replace('_', ' ').title()
                
            count = category_data[item_key]
            
            if item_key in data:
                item = data[item_key]
                full_display = f"{display_name} (x{count})"
                
                # Format description
                if category == "weapons":
                    desc = f"{item.get('description', '')} (D{item.get('die', 4)}, {item.get('on_hit_effect', 'none').title()})"
                elif category == "armor":
                    desc = f"{item.get('description', '')} (AC: {item.get('ac', 10)}, {item.get('type', 'light').title()})"
                elif category == "shields":
                    desc = f"{item.get('description', '')} (AC: +{item.get('ac', 0)})"
                elif category == "trinkets":
                    desc = item.get('description', '')
                else:
                    desc = item.get('description', '')
                descriptions[full_display] = desc
            else:
                full_display = f"{display_name} (x{count})"
                
            options.append(full_display)
            self.item_map[full_display] = item_key

        options.append("Back")

        x = self.menus[-1].pos[0] + 250
        y = self.menus[-1].pos[1]

        new_menu = Menu(options, self.font, pos=(x, y), header=category.title(), descriptions=descriptions)
        self.menus.append(new_menu)

    def open_confirm_menu(self, item_key):
        display_name = item_key.replace('_', ' ').title()
        category = self.menus[0].options[self.menus[0].selected].lower()

        if category == "consumables":
            action = "Use"
        else:
            action = "Equip"

        x = self.menus[-1].pos[0] + 250
        y = self.menus[-1].pos[1]

        confirm_menu = Menu(
            ["Yes", "No"],
            self.font,
            pos=(x, y),
            header=f"{action} {display_name}?"
        )

        self.menus.append(confirm_menu)
    
    def handle_item_action(self, item_key):
        category = self.menus[0].options[self.menus[0].selected].lower()

        if category == "weapons":
            return self.equip_weapon(item_key)
        elif category == "armor":
            return self.equip_armor(item_key)
        elif category == "shields":
            return self.equip_shield(item_key)
        elif category == "trinkets":
            return self.equip_trinket(item_key)
        elif category == "consumables":
            return self.use_consumable(item_key)
        return None

    def equip_weapon(self, item_key):
        self.game.player["weapon"] = item_key
        apply_weapon_to_player(self.game.player)
        if "equipped" in self.inventory:
            self.inventory["equipped"]["weapon"] = item_key
        return f"Equipped {item_key.replace('_', ' ').title()}."

    def equip_armor(self, item_key):
        if not can_equip_armor(self.game.player, item_key):
            return f"You are not proficient with {item_key.replace('_', ' ').title()}!"
            
        self.game.player["armor"] = item_key
        apply_armor_to_player(self.game.player)
        if "equipped" in self.inventory:
            self.inventory["equipped"]["armor"] = item_key
        return f"Equipped {item_key.replace('_', ' ').title()}."

    def equip_shield(self, item_key):
        self.game.player["shield"] = item_key
        apply_shield_to_player(self.game.player)
        if "equipped" in self.inventory:
            self.inventory["equipped"]["shield"] = item_key
        return f"Equipped {item_key.replace('_', ' ').title()}."

    def equip_trinket(self, item_key):
        self.game.player["trinket"] = item_key
        apply_trinket_to_player(self.game.player)
        if "equipped" in self.inventory:
            self.inventory["equipped"]["trinket"] = item_key
        return f"Equipped {item_key.replace('_', ' ').title()}."

    def use_consumable(self, item_key):
        from core.combat.combat_engine import CombatEngine
        consumables_db = load_consumables()
        item_data = consumables_db.get(item_key)
        
        if not item_data:
            return f"{item_key.replace('_', ' ').title()} not found."

        res = CombatEngine.resolve_item(item_data, self.game.player)
        p = self.game.player
        if res['hp_gain'] > 0:
            p['hp'] = min(p.get('max_hp', 20), p['hp'] + res['hp_gain'])
        
        from core.players.player_inventory import remove_item
        remove_item(self.inventory, item_key, 'consumable')

        return res['msg']

    def update(self, events):
        if self.dialogue.current_message:
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)
                    if not was_typing and not self.dialogue.current_message:
                        if self.message_queue:
                            self.start_next_message()
            return

        active_menu = self.menus[-1]
        for event in events:
            result = active_menu.handle_event(event)
            if result:
                if result == "BACK" and len(self.menus) > 1:
                    self.menus.pop()
                elif result == "BACK" and len(self.menus) == 1:
                    from interfaces.pygame.states.hub import HubState
                    self.game.change_state(HubState(self.game, self.font))
                else:
                    self.handle_selection(result)

    def draw(self, screen):
        if self.background:
            screen.blit(self.background, (0, 0))
        else:
            screen.fill((30, 30, 30))

        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import SCREEN_WIDTH
        
        title_text = "Inventory"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255, 255, 255), (SCREEN_WIDTH // 2) - (tw // 2), 50)
        
        for menu in self.menus:
            menu.draw(screen)
        
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
