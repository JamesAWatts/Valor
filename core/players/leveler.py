import json
import os
from core.game_rules.path_utils import get_resource_path

def load_player_classes(path=None):
    """Load player class definitions."""
    if path is None:
        path = get_resource_path(os.path.join('data', 'players', 'player_classes.json'))
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def load_xp_table():
    """Load unified XP table."""
    path = get_resource_path(os.path.join('data', 'players', 'xp_table.json'))
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def get_total_level_for_xp(total_xp):
    """Determine total character level from XP."""
    xp_table = load_xp_table()
    current_level = 1
    for lvl in range(1, 21):
        lvl_str = str(lvl)
        if lvl_str in xp_table:
            if total_xp >= xp_table[lvl_str]:
                current_level = lvl
            else:
                break
    return current_level

def get_class_stats_at_level(class_name, level, player_classes=None):
    """
    Get class stats at a specific level, merging base stats with level-specific overrides.
    """
    if player_classes is None:
        player_classes = load_player_classes()
    
    class_name = class_name.lower()
    if class_name not in player_classes:
        return {}
    
    class_def = player_classes[class_name]
    stats = {k: v for k, v in class_def.items() if k != 'levels'}
    
    for k, v in stats.items():
        if isinstance(v, list):
            stats[k] = list(v)

    levels_def = class_def.get('levels', {})
    for lvl in range(1, level + 1):
        lvl_str = str(lvl)
        if lvl_str in levels_def:
            level_data = levels_def[lvl_str]
            for key, value in level_data.items():
                if isinstance(value, list):
                    if key not in stats:
                        stats[key] = []
                    stats[key].extend([item for item in value if item not in stats[key]])
                else:
                    stats[key] = value
    return stats

def xp_to_next_level(total_xp):
    """Calculate XP needed for next character level."""
    xp_table = load_xp_table()
    current_level = get_total_level_for_xp(total_xp)
    next_level = current_level + 1
    if str(next_level) in xp_table:
        return xp_table[str(next_level)] - total_xp
    return None

def recalculate_stats(player_data):
    """
    Recalculate all stats based on class levels.
    """
    class_defs = load_player_classes()
    class_levels = player_data.get('class_levels', {})
    total_level = sum(class_levels.values())
    
    if not class_levels:
        return player_data

    # PROFICIENCY BONUS
    prof_bonus = 2 + (total_level - 1) // 4 
    player_data['proficiency_bonus'] = prof_bonus

    # BASE HP Calculation
    # First class taken gives 9 + full hit die, subsequent levels give (die/2)+1
    base_max_hp = 0
    first_class = True
    for class_name, level in class_levels.items():
        c_def = class_defs.get(class_name.lower(), {})
        hit_die = c_def.get('hp', 8)
        if first_class:
            # Rule: 9 + hit_die at level 1, then standard gain
            base_max_hp += 9 + hit_die + (level - 1) * ((hit_die // 2) + 1)
            first_class = False
        else:
            base_max_hp += level * ((hit_die // 2) + 1)
    
    player_data['max_hp_base'] = base_max_hp

    # MANA POOL (MP)
    caster_classes = ["wizard", "druid", "alchemist", "sorcerer", "cleric"]
    max_mp = 0
    for c_name, c_level in class_levels.items():
        if c_name.lower() in caster_classes:
            max_mp += c_level
    player_data['max_mp_base'] = max_mp

    # STAMINA POOL (SP)
    martial_classes = ["fighter", "monk", "archer", "rogue"]
    max_sp = 0
    for c_name, c_level in class_levels.items():
        if c_name.lower() in martial_classes:
            max_sp += c_level
    player_data['max_sp_base'] = max_sp

    # RESET ACCUMULATORS
    player_data['spells'] = []
    player_data['skills'] = []
    player_data['attack_count'] = 1
    player_data['sneak_attack_rolls'] = 0
    player_data['cantrip_dice_rolled'] = 1
    
    # Spell DC Base (equipment will add to this)
    player_data['spell_save_base'] = 8 + prof_bonus + (total_level // 4)
    
    for class_name, level in class_levels.items():
        c_def = class_defs.get(class_name.lower())
        if not c_def: continue
        
        for lvl in range(1, level + 1):
            lvl_str = str(lvl)
            lvl_data = c_def.get('levels', {}).get(lvl_str, {})
            
            if 'attack_count' in lvl_data:
                player_data['attack_count'] = max(player_data['attack_count'], lvl_data['attack_count'])
            if 'sneak_attack_rolls' in lvl_data:
                player_data['sneak_attack_rolls'] = max(player_data['sneak_attack_rolls'], lvl_data['sneak_attack_rolls'])
            if 'cantrip_dice_rolled' in lvl_data:
                player_data['cantrip_dice_rolled'] = max(player_data['cantrip_dice_rolled'], lvl_data['cantrip_dice_rolled'])
            if 'spells' in lvl_data:
                for s in lvl_data['spells']:
                    if s not in player_data['spells']: player_data['spells'].append(s)
            if 'skills' in lvl_data:
                for s in lvl_data['skills']:
                    if s not in player_data['skills']: player_data['skills'].append(s)
            if 'damage_die' in lvl_data:
                player_data['damage_die'] = max(player_data.get('damage_die', 0), lvl_data['damage_die'])

    return player_data

def get_level_up_benefits(player_data, class_name):
    """
    Returns a string summarizing the benefits of gaining a level in the specified class.
    """
    class_defs = load_player_classes()
    class_name_lower = class_name.lower()
    c_def = class_defs.get(class_name_lower)
    if not c_def:
        return "No benefits found."

    player_class_levels = player_data.get('class_levels', {})
    next_level = player_class_levels.get(class_name_lower, 0) + 1
    total_level = sum(player_class_levels.values()) + 1
    
    lvl_str = str(next_level)
    lvl_data = c_def.get('levels', {}).get(lvl_str, {})
    
    benefits = []
    
    # HP Gain
    hit_die = c_def.get('hp', 8)
    hp_gain = (hit_die // 2) + 1
    benefits.append(f"HP: +{hp_gain}")
    
    # Proficiency Bonus
    new_prof = 2 + (total_level - 1) // 4
    old_prof = 2 + (total_level - 2) // 4 if total_level > 1 else 2
    if new_prof > old_prof:
        benefits.append(f"Proficiency Bonus: +{new_prof}")
        
    # MP/SP
    caster_classes = ["wizard", "druid", "alchemist", "sorcerer", "cleric"]
    martial_classes = ["fighter", "monk", "archer", "rogue"]
    if class_name_lower in caster_classes:
        benefits.append("Mana: +1")
    if class_name_lower in martial_classes:
        benefits.append("Stamina: +1")
        
    # Level Data benefits
    if 'attack_count' in lvl_data:
        current_attack_count = player_data.get('attack_count', 1)
        if lvl_data['attack_count'] > current_attack_count:
            benefits.append(f"Attacks: {lvl_data['attack_count']}")

    # Skills/Spells in levels
    new_skills = list(lvl_data.get('skills', []))
    new_spells = list(lvl_data.get('spells', []))

    # At level 1, also check top-level skills/spells
    if next_level == 1:
        for s in c_def.get('skills', []):
            if s not in new_skills: new_skills.append(s)
        for s in c_def.get('spells', []):
            if s not in new_spells: new_spells.append(s)

    for skill in new_skills:
        benefits.append(f"Skill: {skill.replace('_', ' ').title()}")
    for spell in new_spells:
        benefits.append(f"Spell: {spell.replace('_', ' ').title()}")

    if 'sneak_attack_rolls' in lvl_data:
        current_sa = player_data.get('sneak_attack_rolls', 0)
        if lvl_data['sneak_attack_rolls'] > current_sa:
             benefits.append(f"Sneak Attack: {lvl_data['sneak_attack_rolls']}d6")
             
    if 'damage_die' in lvl_data:
        current_dd = player_data.get('damage_die', 0)
        if lvl_data['damage_die'] > current_dd:
            benefits.append(f"Unarmed Die: d{lvl_data['damage_die']}")

    if not benefits:
        return f"Level {next_level} {class_name.title()}"
        
    return f"Gains: " + ", ".join(benefits)

def add_class_level(player_data, class_name):
    """Add a level in a specific class and update stats."""
    player_data.setdefault('class_levels', {})
    class_name = class_name.lower()
    player_data['class_levels'][class_name] = player_data['class_levels'].get(class_name, 0) + 1
    
    player_data['level'] = sum(player_data['class_levels'].values())
    
    # Recalculate base stats
    recalculate_stats(player_data)
    
    # Synchronize with equipment and current HP
    from .player import validate_player_data
    validate_player_data(player_data)
    
    return player_data

def update_xp_and_level(player_data, xp_gain):
    """
    Update player XP and check if a level-up is available.
    Returns True if a level-up is pending.
    """
    player_data.setdefault('xp', 0)
    player_data.setdefault('level', 1)
    player_data['xp'] += xp_gain
    
    return needs_level_up(player_data)

def needs_level_up(player_data):
    """Check if player has enough XP to level up."""
    current_level = player_data.get('level', 1)
    total_xp = player_data.get('xp', 0)
    return get_total_level_for_xp(total_xp) > current_level
