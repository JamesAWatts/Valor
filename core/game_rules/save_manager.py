import json
import os
from core.game_rules.path_utils import get_writeable_path

class SaveManager:
    SAVE_DIR = get_writeable_path("saves")

    @staticmethod
    def ensure_save_dir():
        if not os.path.exists(SaveManager.SAVE_DIR):
            os.makedirs(SaveManager.SAVE_DIR)

    @staticmethod
    def get_save_path(slot):
        return os.path.join(SaveManager.SAVE_DIR, f"save_slot_{slot}.json")

    @staticmethod
    def save_game(slot, party, inventory=None, battle_counter=0, bestiary_rp=None):
        SaveManager.ensure_save_dir()
        path = SaveManager.get_save_path(slot)
        
        # Ensure it's a list
        if not isinstance(party, list):
            party = [party]

        lead = party[0] if party else {}
        
        # If inventory is not provided, try to get it from the lead's ref
        if inventory is None and lead:
            inventory = lead.get('inventory_ref', {})

        save_data = {
            "is_party_save": True,
            "party": party,
            "inventory": inventory, # Global Inventory
            "battle_counter": battle_counter,
            "bestiary_rp": bestiary_rp or {},
            "name": lead.get('name', 'Unknown'),
            "level": lead.get('level', 1)
        }
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving game: {e}")
            return False

    @staticmethod
    def load_game_data(slot):
        """Returns the full save dictionary or None."""
        path = SaveManager.get_save_path(slot)
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading game: {e}")
            return None

    @staticmethod
    def load_game(slot):
        data = SaveManager.load_game_data(slot)
        if not data:
            return None
            
        # Check for new party format
        if isinstance(data, dict) and data.get("is_party_save"):
            party = data.get("party", [])
            # Fallback to lead player's inventory_ref if global inventory is missing
            inventory = data.get("inventory")
            if inventory is None and party:
                inventory = party[0].get('inventory_ref', {})
            
            if inventory is None:
                inventory = {
                    'gold': 0, 'weapon': {}, 'armor': {}, 'shield': {},
                    'trinket': {}, 'consumable': {}, 'junk': {}, 'key_items': {}
                }

            # Sync all players to use the SAME inventory object
            for p in party:
                p['inventory_ref'] = inventory
            return party
        # Old single-player save (directly a dict)
        elif isinstance(data, dict):
            # For very old saves, the dict IS the player.
            inventory = data.get('inventory_ref', {
                'gold': 0, 'weapon': {}, 'armor': {}, 'shield': {},
                'trinket': {}, 'consumable': {}, 'junk': {}, 'key_items': {}
            })
            data['inventory_ref'] = inventory
            return [data]
        return None

    @staticmethod
    def get_slot_info(slot):
        # We need the raw data for slot info to be efficient, or just use load_game
        # load_game now returns a list of players
        party = SaveManager.load_game(slot)
        if not party:
            return "Empty Slot"
        
        lead = party[0] if party else {}
        name = lead.get('name', 'Unknown')
        level = lead.get('level', 1)
        party_size = len(party)
        size_str = f" (Party: {party_size})" if party_size > 1 else ""
        return f"{name}, Level {level}{size_str}"

    @staticmethod
    def delete_save(slot):
        path = SaveManager.get_save_path(slot)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
