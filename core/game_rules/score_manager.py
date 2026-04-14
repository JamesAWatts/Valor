import json
import os
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from core.game_rules.path_utils import get_writeable_path

class ScoreManager:
    HIGH_SCORES_FILE = os.path.join(get_writeable_path("saves"), "high_scores.json")

    @staticmethod
    def calculate_score(player_data, retired=False):
        """
        Calculates the final score based on player data.
        """
        kills = player_data.get('kill_count', 0)
        level = player_data.get('level', 1)
        gold_spent = player_data.get('total_gold_spent', 0)
        current_gold = player_data.get('inventory_ref', {}).get('gold', 0)
        
        score_breakdown = {
            'Kills': kills * 1,
            'Level Bonus': level * 100,
            'Gold Spent': gold_spent * 2,
            'Gold Held': current_gold * 1,
            'Retirement Bonus': (level * 200) if retired else 0
        }
        
        total_score = sum(score_breakdown.values())
        return total_score, score_breakdown

    @staticmethod
    def save_high_score(name, score):
        """
        Saves a score to the top 10 list.
        """
        scores = ScoreManager.load_high_scores()
        scores.append({'name': name, 'score': score})
        
        # Sort by score descending and keep top 10
        scores.sort(key=lambda x: x['score'], reverse=True)
        scores = scores[:10]
        
        os.makedirs(os.path.dirname(ScoreManager.HIGH_SCORES_FILE), exist_ok=True)
        try:
            with open(ScoreManager.HIGH_SCORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(scores, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving high scores: {e}")
            return False

    @staticmethod
    def load_high_scores():
        if not os.path.exists(ScoreManager.HIGH_SCORES_FILE):
            return []
        
        try:
            with open(ScoreManager.HIGH_SCORES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading high scores: {e}")
            return []
