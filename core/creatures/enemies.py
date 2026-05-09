import json
import os
import random
from core.game_rules.path_utils import get_resource_path

def load_enemy_data(category=None):
    """
    Loads enemy data. 
    If category is provided (e.g. 'undead'), loads that specific file.
    If None, can return all or handle as needed. 
    """
    if category:
        json_path = get_resource_path(os.path.join('data', 'creatures', f'{category}.json'))
    else:
        # Legacy fallback
        json_path = get_resource_path(os.path.join('data', 'creatures', 'enemies.json'))
        
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_scaled_enemies(player_level=1, battle_count=0, category=None):
    """
    Phased Budget Encounter System:
    PHASE 1: CATEGORY selection.
    PHASE 2: BUDGET determination.
    PHASE 3: LEADER selection (Every 5th battle).
    PHASE 4: MINION filling.
    """
    # PHASE 1: CATEGORY
    if category is None:
        category_map = {
            1: 'beast',
            2: 'dragon',
            3: 'fae',
            4: 'goblinoid',
            5: 'humanoid',
            6: 'undead'
        }
        cat_roll = random.randint(1, 6)
        category = category_map[cat_roll]
    
    enemy_data = load_enemy_data(category)
    if not enemy_data:
        # Fallback to humanoid if chosen cat is empty
        enemy_data = load_enemy_data('humanoid')
        category = 'humanoid'

    all_enemies = list(enemy_data.items())
    
    # PHASE 2: BUDGET
    budget = player_level
    encounter = []

    # Decide if this is a Boss Fight (Every 5th battle)
    is_boss_fight = (battle_count > 0 and battle_count % 5 == 0)

    if is_boss_fight:
        # PHASE 3: LEADER (Boss)
        # Rule: (2*budget)/3 to get leader_floor, then pick one between floor and budget
        leader_floor = (2 * budget) // 3
        eligible_leaders = [e for e in all_enemies if leader_floor <= e[1].get('level', 1) <= budget]
        
        if not eligible_leaders:
            eligible_leaders = sorted([e for e in all_enemies if e[1].get('level', 1) <= budget], 
                                     key=lambda x: x[1].get('level', 1), reverse=True)[:3]
            
        if not eligible_leaders:
            humanoid_data = load_enemy_data('humanoid')
            eligible_leaders = [list(humanoid_data.items())[0]]

        l_name, l_stats = random.choice(eligible_leaders)
        leader = l_stats.copy()
        leader['base_name'] = l_name
        leader['name'] = l_name.replace('_', ' ').title()
        leader['is_leader'] = True
        leader['category'] = category
        
        encounter.append(leader)
        current_budget = budget - leader.get('level', 1)
    else:
        # NO LEADER PHASE - Just Minions
        current_budget = budget

    # PHASE 4: MINIONS
    # Fill remaining budget with up to 7 more minions (max 8 total)
    max_enemies = 8
    while current_budget > 0 and len(encounter) < max_enemies:
        affordable = [e for e in all_enemies if e[1].get('level', 1) <= current_budget]
        if not affordable:
            break
            
        m_name, m_stats = random.choice(affordable)
        minion = m_stats.copy()
        minion['base_name'] = m_name
        minion['name'] = m_name.replace('_', ' ').title()
        minion['is_leader'] = False
        minion['category'] = category
        
        encounter.append(minion)
        current_budget -= m_stats.get('level', 1)

    # Safety check: if somehow empty, add at least one
    if not encounter:
        m_name, m_stats = all_enemies[0]
        minion = m_stats.copy()
        minion['base_name'] = m_name
        minion['name'] = m_name.replace('_', ' ').title()
        minion['is_leader'] = False
        minion['category'] = category
        encounter.append(minion)

    battle_type = "BOSS" if is_boss_fight else "STANDARD"
    print(f"[DEBUG] Generated {battle_type} encounter (Battle #{battle_count}) from '{category}' category. Budget: {budget}")
    return encounter
