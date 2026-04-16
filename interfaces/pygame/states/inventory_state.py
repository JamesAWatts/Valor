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
    def __init__(self, game, font, player=None):
        super().__init__(game, font)
        
        # Use provided player or default to the main hero
        self.player = player if player else game.player
        
        self.background = BackgroundManager.get_hub_bg(self.player)
        self.dialogue = DialogueBox(self.font)
        self.message_queue = []
        
        # Mapping to remember original keys for display names
        self.item_map = {}

        self.inventory = self.player.get("inventory_ref", {})
        if not self.inventory:
            self.inventory = self.player.get("inventory", {})

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

        # EQUIP TO / USE ON MENU
        elif len(self.menus) == 3:
            if option == "Back":
                self.menus.pop()
                return
            
            # Retrieve item from previous menu selection
            prev_menu = self.menus[1]
            item_display = prev_menu.options[prev_menu.selected]
            item_key = self.item_map.get(item_display, item_display.split(" (")[0])
            
            # Find target character
            target_char = next((p for p in self.game.party if p.get('name') == option), None)
            if not target_char: return

            result_text = self.handle_item_action(item_key, target_char)

            if result_text:
                self.queue_message(result_text)
                self.start_next_message()

                # If successful (Equipped or Used), return to root or item list
                if "cannot be equipped" not in result_text and "not proficient" not in result_text:
                    root = self.menus[0]
                    self.menus = [root]
                # Else: Stay in menu 3 (Equip to) so they can try someone else
    
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
                display_name = get_weapon_display_name(self.player, item_key)
            elif category == "armor":
                display_name = get_armor_display_name(self.player, item_key)
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

        # Use raw_pos for cascading (Base 800x600)
        x = self.menus[-1].raw_pos[0] + 200
        y = self.menus[-1].raw_pos[1]

        new_menu = Menu(options, self.font, pos=(x, y), header=category.title(), descriptions=descriptions)
        self.menus.append(new_menu)

    def open_confirm_menu(self, item_key):
        category = self.menus[0].options[self.menus[0].selected].lower()

        action = "Use on" if category == "consumables" else "Equip to"
        party_names = [p.get('name', 'Adventurer') for p in self.game.party]

        x = self.menus[-1].raw_pos[0] + 200
        y = self.menus[-1].raw_pos[1]

        confirm_menu = Menu(
            party_names + ["Back"],
            self.font,
            pos=(x, y),
            header=f"{action}?"
        )

        self.menus.append(confirm_menu)
    
    def handle_item_action(self, item_key, target_char):
        category = self.menus[0].options[self.menus[0].selected].lower()

        if category == "weapons":
            return self.equip_weapon(item_key, target_char)
        elif category == "armor":
            return self.equip_armor(item_key, target_char)
        elif category == "shields":
            return self.equip_shield(item_key, target_char)
        elif category == "trinkets":
            return self.equip_trinket(item_key, target_char)
        elif category == "consumables":
            return self.use_consumable(item_key, target_char)
        return None

    def equip_weapon(self, item_key, target_char):
        from core.players.player import can_equip_weapon
        if not can_equip_weapon(target_char, item_key):
            return f"{target_char['name']} is not proficient with {item_key.replace('_', ' ').title()}!"

        target_char["weapon"] = item_key
        apply_weapon_to_player(target_char)
        # Shared inventory equipment sync if necessary
        return f"Equipped {item_key.replace('_', ' ').title()} to {target_char['name']}."

    def equip_armor(self, item_key, target_char):
        if not can_equip_armor(target_char, item_key):
            return f"{target_char['name']} is not proficient with {item_key.replace('_', ' ').title()}!"
            
        target_char["armor"] = item_key
        apply_armor_to_player(target_char)
        return f"Equipped {item_key.replace('_', ' ').title()} to {target_char['name']}."

    def equip_shield(self, item_key, target_char):
        target_char["shield"] = item_key
        apply_shield_to_player(target_char)
        return f"Equipped {item_key.replace('_', ' ').title()} to {target_char['name']}."

    def equip_trinket(self, item_key, target_char):
        target_char["trinket"] = item_key
        apply_trinket_to_player(target_char)
        return f"Equipped {item_key.replace('_', ' ').title()} to {target_char['name']}."

    def use_consumable(self, item_key, target_char):
        from core.combat.combat_engine import CombatEngine
        consumables_db = load_consumables()
        item_data = consumables_db.get(item_key)
        
        if not item_data:
            return f"{item_key.replace('_', ' ').title()} not found."

        res = CombatEngine.resolve_item(item_data, target_char)
        if res['hp_gain'] > 0:
            target_char['current_hp'] = min(target_char.get('max_hp', 20), target_char.get('current_hp', 0) + res['hp_gain'])
            target_char['hp'] = target_char['current_hp']
        
        from core.players.player_inventory import remove_item
        remove_item(self.inventory, item_key, 'consumable')

        return f"Used on {target_char['name']}. {res['msg']}"

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
