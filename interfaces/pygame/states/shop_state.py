import pygame
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.dialogue_box import DialogueBox
from core.players.player import (
    load_weapons, load_armor, load_trinkets, load_shields, 
    apply_weapon_to_player, apply_armor_to_player, apply_shield_to_player, apply_trinket_to_player
)
from core.players.shop import load_consumables
from core.combat.combat_engine import CombatEngine

class ShopState(BaseState):
    def __init__(self, game, font, player=None):
        super().__init__(game, font)
        self.background = BackgroundManager.get_shop_bg()
        self.dialogue = DialogueBox(font)

        self.player = player if player else game.player
        self.inventory = self.player.get("inventory_ref", {})
        if not self.inventory:
             self.inventory = self.player.get("inventory", {})

        self.mode = "MAIN"
        self.item_map = {}
        self.buy_category = None
        self.current_page = 0
        self.items_per_page = 10
        
        self.purchased_item_key = None
        self.purchased_item_cat = None
        self.purchased_item_data = None

        self.main_menu = Menu(["Buy", "Sell", "Blacksmith", "Back"], font, width=100, header="The Dragon's Hoard")
        self.active_menu = self.main_menu

    def refresh_buy_menu(self):
        options = ["Weapons", "Armor", "Shields", "Consumables", "Trinkets", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="What are you looking for?")

    def refresh_weapon_categories(self):
        options = ["Simple", "Martial", "Caster", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="Weapon Class?")

    def refresh_armor_categories(self):
        options = ["Robes", "Light", "Medium", "Heavy", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="Armor Type?")

    def open_buy_category(self, category, sub_category=None):
        if category == "weapons":
            data = load_weapons().get("weapon_list", {})
            if sub_category:
                data = {k: v for k, v in data.items() if v.get('weapon_class', 'simple').lower() == sub_category.lower()}
        elif category == "armor":
            data = load_armor()
            if sub_category:
                # Handle Robes separately or as a type
                # Looking at player.py: 'none', 'light', 'medium', 'heavy', 'robe'
                target_type = sub_category.lower()
                if target_type == "robes": target_type = "robe"
                data = {k: v for k, v in data.items() if v.get('type', 'none').lower() == target_type}
        elif category == "shields":
            data = load_shields()
        elif category == "consumables":
            data = load_consumables()
        elif category == "trinkets":
            data = load_trinkets()
        else:
            return

        available = {k: v for k, v in data.items() if v.get('cost', 0) > 0}
        
        # REMOVED class-based filtering here per request
        
        if category == "armor":
            # none > light > medium > heavy > robe
            type_order = {'none': 0, 'light': 1, 'medium': 2, 'heavy': 3, 'robe': 4}
            all_keys = sorted(available.keys(), key=lambda k: (type_order.get(available[k].get('type', 'none'), 99), available[k].get('cost', 0)))
        else:
            all_keys = sorted(available.keys(), key=lambda k: available[k].get('cost', 0))
        
        total_pages = (len(all_keys) + self.items_per_page - 1) // self.items_per_page
        if self.current_page >= total_pages: self.current_page = 0
        if self.current_page < 0: self.current_page = total_pages - 1

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_keys = all_keys[start_idx:end_idx]

        options = []
        descriptions = {}
        self.item_map = {}
        for k in page_keys:
            item = available[k]
            display_name = item.get('name', k.replace('_', ' ')).title()
            full_display = f"{display_name} ({item['cost']}g)"
            options.append(full_display)
            self.item_map[full_display] = k
            
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

        # Add Pagination/Footer options
        if total_pages > 1:
            options.append("Next Page")
            options.append("Previous Page")
        
        options.append("Return")
        
        sub_header = f" - {sub_category.title()}" if sub_category else ""
        header = f"{category.title()}{sub_header} (Page {self.current_page + 1}/{total_pages})"
        self.active_menu = Menu(options, self.font, width=200, header=header, descriptions=descriptions)

    def refresh_sell_menu(self):
        options = ["Weapons", "Armor", "Shields", "Consumables", "Trinkets", "Junk", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="What would you like to sell?")

    def open_sell_category(self, category):
        inv_key = category[:-1] if category.endswith('s') else category
        items_dict = self.inventory.get(inv_key, {})
        
        if not items_dict:
            self.dialogue.set_messages([f"You have no {category} to sell."])
            self.refresh_sell_menu()
            return

        # Load price data
        if category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif category == "armor":
            data = load_armor()
        elif category == "shields":
            data = load_shields()
        elif category == "consumables":
            data = load_consumables()
        elif category == "trinkets":
            data = load_trinkets()
        else: # Junk
            data = {}

        equipped = self.inventory.get('equipped', {})
        options = []
        descriptions = {}
        self.item_map = {}
        
        # Sort keys
        all_keys = sorted(items_dict.keys())
        
        for k in all_keys:
            # Skip if equipped
            if k == equipped.get(inv_key):
                # If we only have 1 of this item and it's equipped, skip it
                if items_dict[k] <= 1:
                    continue
            
            count = items_dict[k]
            # Equipped check for items with multiple counts
            sellable_count = count
            if k == equipped.get(inv_key):
                sellable_count -= 1

            if sellable_count <= 0:
                continue

            item_data = data.get(k, {})
            # Junk sells for 1g, others for 50% cost
            price = item_data.get('cost', 2) // 2 if category != "junk" else 1
            if price < 1: price = 1
            
            display_name = item_data.get('name', k.replace('_', ' ')).title()
            full_display = f"{display_name} x{sellable_count} ({price}g)"
            options.append(full_display)
            self.item_map[full_display] = (k, price, inv_key)
            descriptions[full_display] = item_data.get('description', 'A miscellaneous item.')

        if not options:
            self.dialogue.set_messages([f"You have no unequipped {category} to sell."])
            self.refresh_sell_menu()
            return

        options.append("Back")
        self.active_menu = Menu(options, self.font, width=200, header=f"Sell {category.title()}", descriptions=descriptions)

    def on_select(self, option):
        if self.mode == "MAIN":
            if option == "Buy":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            elif option == "Sell":
                self.mode = "SELL_CAT"
                self.refresh_sell_menu()
            elif option == "Blacksmith":
                from .blacksmith_state import BlacksmithState
                self.game.change_state(BlacksmithState(self.game, self.font, player=self.player))
            elif option == "Back":
                from interfaces.pygame.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))

        elif self.mode == "BUY_CAT":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            elif option == "Weapons":
                self.mode = "BUY_WEAPON_CAT"
                self.refresh_weapon_categories()
            elif option == "Armor":
                self.mode = "BUY_ARMOR_CAT"
                self.refresh_armor_categories()
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = option.lower()
                self.buy_sub_category = None
                self.current_page = 0
                self.open_buy_category(self.buy_category)

        elif self.mode == "BUY_WEAPON_CAT":
            if option == "Back":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = "weapons"
                self.buy_sub_category = option.lower()
                self.current_page = 0
                self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif self.mode == "BUY_ARMOR_CAT":
            if option == "Back":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = "armor"
                self.buy_sub_category = option.lower()
                self.current_page = 0
                self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif self.mode == "SELL_CAT":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                self.mode = "SELL_ITEMS"
                self.sell_category = option.lower()
                self.open_sell_category(self.sell_category)

        elif self.mode == "BUY_ITEMS":
            if option == "Return":
                if self.buy_category == "weapons":
                    self.mode = "BUY_WEAPON_CAT"
                    self.refresh_weapon_categories()
                elif self.buy_category == "armor":
                    self.mode = "BUY_ARMOR_CAT"
                    self.refresh_armor_categories()
                else:
                    self.mode = "BUY_CAT"
                    self.refresh_buy_menu()
            elif option == "Next Page":
                self.current_page += 1
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            elif option == "Previous Page":
                self.current_page -= 1
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.handle_buy(option)

        elif self.mode == "SELL_ITEMS":
            if option == "Back":
                self.mode = "SELL_CAT"
                self.refresh_sell_menu()
            else:
                self.handle_sell(option)

        elif self.mode == "CONFIRM_ACTION":
            if option == "Yes":
                self.execute_action()
            else:
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category)

        elif self.mode == "SELL": # Cleanup old mode if hit
            self.mode = "SELL_CAT"
            self.refresh_sell_menu()

    def handle_sell(self, display_name):
        mapped = self.item_map.get(display_name)
        if not mapped: return
        
        item_key, price, inv_key = mapped
        
        # Verify we still have it
        category = self.inventory.get(inv_key, {})
        if category.get(item_key, 0) <= 0:
            self.dialogue.set_messages(["You no longer have this item."])
            self.open_sell_category(self.sell_category)
            return

        # Double check equipped
        equipped = self.inventory.get('equipped', {})
        if item_key == equipped.get(inv_key) and category.get(item_key, 0) <= 1:
            self.dialogue.set_messages(["Cannot sell equipped items!"])
            self.open_sell_category(self.sell_category)
            return

        # Remove item and add gold
        from core.players.player_inventory import remove_item
        if remove_item(self.inventory, item_key, inv_key):
            self.inventory['gold'] = self.inventory.get('gold', 0) + price
            self.dialogue.set_messages([f"Sold {item_key.replace('_',' ').title()} for {price} gold."])
        
        # Refresh the current sell category view
        self.open_sell_category(self.sell_category)

    def handle_buy(self, display_name):
        item_key = self.item_map.get(display_name)
        if not item_key: return

        if self.buy_category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif self.buy_category == "armor":
            data = load_armor()
        elif self.buy_category == "shields":
            data = load_shields()
        elif self.buy_category == "trinkets":
            data = load_trinkets()
        else:
            data = load_consumables()

        item = data[item_key]
        cost = item['cost']
        
        # Check gold (use party inventory gold)
        inv = self.game.player['inventory_ref']
        if self.game.god_mode or inv.get('gold', 0) >= cost:
            if not self.game.god_mode:
                inv['gold'] -= cost
            
            from core.players.player_inventory import add_item
            # Mapping Buy Categories to inventory keys
            inv_key = self.buy_category[:-1] if self.buy_category.endswith('s') else self.buy_category
            add_item(inv, item_key, inv_key)
            
            # Store for confirmation
            self.purchased_item_key = item_key
            self.purchased_item_cat = inv_key
            self.purchased_item_data = item
            
            # --- New "Equip to" Menu ---
            self.mode = "CONFIRM_ACTION"
            action_verb = "Use on" if inv_key == "consumable" else "Equip to"
            party_names = [p.get('name', 'Adventurer') for p in self.game.party]
            self.active_menu = Menu(party_names + ["Back"], self.font, header=f"{action_verb}?")
        else:
            self.dialogue.set_messages(["Not enough gold!"])

    def execute_action(self, character_name):
        # Find the character
        target_char = next((p for p in self.game.party if p.get('name') == character_name), None)
        if not target_char: return

        key = self.purchased_item_key
        cat = self.purchased_item_cat
        item = self.purchased_item_data
        inv = self.game.player['inventory_ref']
        
        # Ensure equipped dict exists
        if 'equipped' not in inv:
            inv['equipped'] = {}

        if cat == "weapon":
            from core.players.player import can_equip_weapon
            if can_equip_weapon(target_char, key):
                apply_weapon_to_player(target_char, key)
                # Note: Inventory system handles equipment per character name if needed, 
                # but currently seems to use one shared 'equipped' slot or shared inv.
                # Assuming target_char['weapon'] update is enough for Hub to show.
                self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.dialogue.set_messages([f"{item.get('name', key.replace('_',' ')).title()} cannot be equipped by {character_name}."])
                # Stay in CONFIRM_ACTION to allow picking someone else
        
        elif cat == "armor":
            from core.players.player import can_equip_armor
            if can_equip_armor(target_char, key):
                target_char['armor'] = key
                apply_armor_to_player(target_char)
                self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.dialogue.set_messages([f"{item.get('name', key.replace('_',' ')).title()} cannot be equipped by {character_name}."])

        elif cat == "shield":
            apply_shield_to_player(target_char, key)
            self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif cat == "trinket":
            apply_trinket_to_player(target_char, key)
            self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif cat == "consumable":
            # Use logic
            res = CombatEngine.resolve_item(item, target_char)
            if res.get('hp_gain', 0) > 0:
                target_char['current_hp'] = min(target_char.get('max_hp', 10), target_char.get('current_hp', 10) + res['hp_gain'])
            if res.get('mana_gain', 0) > 0:
                target_char['current_mp'] = min(target_char.get('max_mp', 0), target_char.get('current_mp', 0) + res['mana_gain'])
            
            # Remove from shared inventory
            from core.players.player_inventory import remove_item
            remove_item(inv, key, "consumable")
            
            self.dialogue.set_messages([f"Used on {character_name}. {res.get('msg', '')}"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

    def update(self, events):
        if self.dialogue.current_message:
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN:
                    self.dialogue.handle_event(event)
            return
            
        super().update(events)

    def draw(self, screen):
        # --- Draw background FIRST ---
        self.draw_background(screen)

        from core.game_rules.constants import scale_y, SCREEN_WIDTH, COLOR_GOLD
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        # Show Gold at the top
        gold_text = f"Gold: {self.inventory.get('gold', 0)}"
        gw, gh = self.font.size(gold_text)
        draw_text_outlined(screen, gold_text, self.font, COLOR_GOLD, (SCREEN_WIDTH // 2) - (gw // 2), scale_y(40))

        # --- MENU (Left Aligned, Vertically Centered in Base 800x600) ---
        if self.active_menu and not self.dialogue.current_message:
            # Position at x=150, y=300 in Base space
            self.active_menu.draw(screen, 150, 300)
            
        self.dialogue.draw(screen)
