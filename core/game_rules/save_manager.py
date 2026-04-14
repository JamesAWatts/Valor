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
    def save_game(slot, player_data):
        SaveManager.ensure_save_dir()
        path = SaveManager.get_save_path(slot)
        
        # Create a copy to avoid modifying the active player data
        save_data = player_data.copy()
        
        # Remove non-serializable objects if any (like inventory_ref might be an object in some versions, 
        # but here it's a dict according to player_inventory.py)
        # However, BackgroundManager might have added a background object or path.
        # Let's ensure we only save what's necessary.
        
        # We should also handle the inventory_ref carefully if it's not a dict.
        # In this project, it seems to be a dict.
        
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
                return json.load(f)
        except Exception as e:
            print(f"Error loading game: {e}")
            return None

    @staticmethod
    def get_slot_info(slot):
        data = SaveManager.load_game(slot)
        if not data:
            return "Empty Slot"
        
        name = data.get('name', 'Unknown')
        level = data.get('level', 1)
        return f"{name}, Level {level}"

    @staticmethod
    def delete_save(slot):
        path = SaveManager.get_save_path(slot)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
