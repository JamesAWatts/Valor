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
    def save_game(slot, party):
        SaveManager.ensure_save_dir()
        path = SaveManager.get_save_path(slot)
        
        # Ensure it's a list
        if not isinstance(party, list):
            party = [party]

        lead = party[0] if party else {}
        save_data = {
            "is_party_save": True,
            "party": party,
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
    def load_game(slot):
        path = SaveManager.get_save_path(slot)
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Check for new party format
                if isinstance(data, dict) and data.get("is_party_save"):
                    return data.get("party", [])
                # Old single-player save (directly a dict)
                elif isinstance(data, dict):
                    return [data]
                return None
        except Exception as e:
            print(f"Error loading game: {e}")
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
