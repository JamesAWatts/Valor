import json
import os


def load_levels(path=None):
    base_dir = os.path.dirname(__file__)
    if path is None:
        path = os.path.join(base_dir, 'levels.json')

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    levels = {int(lvl): info for lvl, info in data.get('level', {}).items()}
    sorted_levels = dict(sorted(levels.items()))
    return sorted_levels


def get_level_for_xp(total_xp, levels=None):
    if levels is None:
        levels = load_levels()

    current_level = 1
    for lvl, info in levels.items():
        if total_xp >= info['xp_threshold']:
            current_level = lvl
        else:
            break

    return current_level


def xp_to_next_level(total_xp, levels=None):
    if levels is None:
        levels = load_levels()

    current_level = get_level_for_xp(total_xp, levels)
    next_level = current_level + 1

    if next_level not in levels:
        return None

    return levels[next_level]['xp_threshold'] - total_xp


def apply_level_up(player_data, old_level, new_level, base_hp=None):
    if new_level <= old_level:
        return player_data

    if base_hp is None:
        base_hp = player_data.get('base_hp', player_data.get('hp', 0))

    hp_increase = int(base_hp / 2)
    for _ in range(new_level - old_level):
        player_data['hp'] += hp_increase

    player_data['level'] = new_level
    return player_data


def update_xp_and_level(player_data, xp_gain, levels=None, base_hp=None):
    if levels is None:
        levels = load_levels()

    player_data.setdefault('xp', 0)
    player_data.setdefault('level', 1)
    player_data['xp'] += xp_gain

    old_level = player_data['level']
    new_level = get_level_for_xp(player_data['xp'], levels)

    if new_level > old_level:
        apply_level_up(player_data, old_level, new_level, base_hp=base_hp)

    level_info = levels[player_data['level']]
    player_data['proficiency_bonus'] = level_info['proficiency_bonus']
    if 'attack_count' in level_info:
        player_data['attack_count'] = level_info['attack_count']

    # Reapply monk rules after level changes to override attack_count if needed
    from players.player import apply_monk_rules
    apply_monk_rules(player_data)

    return player_data
