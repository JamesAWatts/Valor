import json
import os
import random
from core.game_rules.path_utils import get_resource_path

def load_enemy_data():
    """Load enemy definitions from the JSON database."""
    json_path = get_resource_path(os.path.join('data', 'creatures', 'enemies.json'))
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_scaled_enemies(enemy_data, player_level=1):
    """
    Budget-based encounter system:
    Picks enemies until their total level matches the player_level.
    """
    budget = player_level
    encounter = []

    # Map enemies to names so we can copy them
    all_enemies = list(enemy_data.items())

    # Safety: Ensure we have at least level 1 enemies
    if not any(e[1].get('level', 1) <= player_level for e in all_enemies):
        # If no enemies are low enough, just pick the weakest one
        name, stats = all_enemies[0]
        enemy_instance = stats.copy()
        enemy_instance['name'] = name.replace('_', ' ').title()
        return [enemy_instance]

    while budget > 0 and len(encounter) < 4:
        # Filter enemies we can afford
        affordable = [e for e in all_enemies if e[1].get('level', 1) <= budget]

        if not affordable:
            break

        # Pick one
        name, stats = random.choice(affordable)

        # Create a deep copy
        enemy_instance = stats.copy()

        # Check if we already have this enemy type to add a suffix (A, B, C)
        count = sum(1 for e in encounter if e.get('base_name') == name)
        enemy_instance['base_name'] = name

        if count > 0:
            suffix = f" {chr(65 + count)}"
            enemy_instance['name'] = name.replace('_', ' ').title() + suffix
        else:
            enemy_instance['name'] = name.replace('_', ' ').title()

        encounter.append(enemy_instance)
        budget -= stats.get('level', 1)

    return encounter
