import json
import os
import random
from core.game_rules.path_utils import get_resource_path

class EnemyAI:
    _skills_cache = None
    _spells_cache = None
    _enemy_abilities_cache = None

    @classmethod
    def _load_data(cls):
        if cls._skills_cache is not None:
            return

        # Load Player Skills (shared)
        skills_path = get_resource_path(os.path.join('data', 'players', 'skills.json'))
        with open(skills_path, 'r', encoding='utf-8-sig') as f:
            cls._skills_cache = json.load(f).get('skill_list', {})

        # Load Player Spells (shared)
        spells_path = get_resource_path(os.path.join('data', 'players', 'spells.json'))
        with open(spells_path, 'r', encoding='utf-8-sig') as f:
            cls._spells_cache = json.load(f).get('spell_list', {})

        # Load Exclusive Enemy Abilities
        enemy_path = get_resource_path(os.path.join('data', 'creatures', 'enemy_abilities.json'))
        with open(enemy_path, 'r', encoding='utf-8-sig') as f:
            cls._enemy_abilities_cache = json.load(f).get('ability_list', {})

    @classmethod
    def get_ability_data(cls, name):
        cls._load_data()
        # Check all three caches
        if name in cls._enemy_abilities_cache:
            return cls._enemy_abilities_cache[name]
        if name in cls._skills_cache:
            return cls._skills_cache[name]
        if name in cls._spells_cache:
            return cls._spells_cache[name]
        return None

    @classmethod
    def decide_action(cls, enemy):
        """
        New Planning Logic (Option 1):
        1. Heal Priority: Interrupts everything if HP < 50%.
        2. Plan Check: If no 'planned_ability', pick a random non-heal goal.
        3. Execution: If 'planned_ability' is affordable, use it.
        4. Saving: If not affordable, perform a basic attack.
        """
        hp_percent = enemy.get('current_hp', 0) / enemy.get('hp', 1)
        
        # --- 1. Heal Priority (Interrupt) ---
        if hp_percent < 0.5 and not enemy.get('has_healed', False):
            all_abilities = enemy.get('skills', []) + enemy.get('spells', [])
            for name in all_abilities:
                data = cls.get_ability_data(name)
                if data and data.get('type') == 'heal':
                    cost = data.get('cost', data.get('level', 0))
                    resource = data.get('resource', 'mp')
                    if enemy.get(f'current_{resource}', 0) >= cost:
                        enemy['has_healed'] = True
                        return {'type': 'ability', 'name': name, 'data': data}

        # --- 2. Plan Selection ---
        if not enemy.get('planned_ability'):
            # Combine non-heal abilities into a pool
            pool = []
            for name in enemy.get('skills', []) + enemy.get('spells', []):
                data = cls.get_ability_data(name)
                if data and data.get('type') != 'heal':
                    pool.append({'name': name, 'data': data})
            
            if pool:
                enemy['planned_ability'] = random.choice(pool)

        # --- 3. Plan Execution / Saving ---
        plan = enemy.get('planned_ability')
        if plan:
            data = plan['data']
            cost = data.get('cost', data.get('level', 0))
            resource = data.get('resource', 'mp')
            
            if enemy.get(f'current_{resource}', 0) >= cost:
                # Can afford! Execute and clear plan
                enemy['planned_ability'] = None
                return {'type': 'ability', 'name': plan['name'], 'data': data}
            else:
                # Saving up... Attack instead
                return {'type': 'attack'}

        # --- 4. Fallback ---
        return {'type': 'attack'}
