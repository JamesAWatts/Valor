import random
import json
import os
from .attack_roller import attack_roll, damage_roll, roll_dice, roll_d20

# Load combat effects for descriptions
EFFECTS_DATA = {}
try:
    # Adjust path to reach data/combat/combat_effects.json from core/combat/
    effects_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'combat', 'combat_effects.json')
    if os.path.exists(effects_path):
        with open(effects_path, 'r') as f:
            EFFECTS_DATA = json.load(f)
except Exception:
    pass

def get_effect_desc(effect_name):
    effect_name = effect_name.lower()
    # Check Conditions first
    conds = EFFECTS_DATA.get("Conditions", {})
    if effect_name in conds:
        return conds[effect_name]
    # Check Weapon effects
    weap = EFFECTS_DATA.get("Weapon_effefts", {}) # Note: typo in JSON 'Weapon_effefts'
    if effect_name in weap:
        return weap[effect_name]
    return ""

class CombatEngine:
    @staticmethod
    def resolve_attack(attacker, target, advantage=0, debug=None, float_mgr=None, extra_damage=0):
        """
        Resolves a single attack from attacker to target.
        attacker: dict containing proficiency_bonus, weapon_bonus, damage_die, on_hit_effect, etc.
        target: dict containing ac.
        advantage: 1 for advantage, -1 for disadvantage, 0 for normal.
        """
        prof = int(attacker.get('proficiency_bonus', 0))
        w_bonus = int(attacker.get('weapon_bonus', 0))
        attack_bonus = prof + w_bonus
        
        target_ac = int(target.get('ac', 10))
        target_pos = target.get('screen_pos', (400, 300))
        
        attacker_name = attacker.get('name', 'Attacker')
        target_name = target.get('name', 'Target')
        
        # Determine crit range
        crit_range = [20]
        if attacker.get('crit_on_18'):
            crit_range = [18, 19, 20]
        elif attacker.get('crit_on_19'):
            crit_range = [19, 20]

        res = attack_roll(attack_bonus, target_ac, crit_range=tuple(crit_range), advantage=advantage)
        
        damage = 0
        effects = []
        messages = []
        
        status = "HIT" if res['hit'] else "MISS"
        if res['critical']: status = "CRITICAL HIT"
        
        messages.append(f"{attacker_name} attacks {target_name}, and rolled a {res['roll']}. > {status}")

        if debug:
            debug.set("Last Attack Roll", res['roll'])
            debug.set("Target AC", target_ac)
            debug.set("Attack Bonus", attack_bonus)

        if res['hit']:
            damage, dice_str = damage_roll(attacker.get('damage_die', 4), w_bonus, critical=res['critical'], player_data=attacker)
            
            if extra_damage > 0:
                damage += extra_damage
                dice_str += f" + {extra_damage} (Bonus)"

            messages.append(f"{attacker_name} rolls {dice_str}, dealing {damage} damage to {target_name}.")

            if float_mgr:
                if res['critical']:
                    float_mgr.add("CRIT!", target_pos, "crit", rise_speed=2.0)
                else:
                    float_mgr.add("HIT", target_pos, "hit")
                
                if damage > 0:
                    float_mgr.add(f"-{damage}", target_pos, "damage", rise_speed=1.5)

            if debug:
                debug.set("Last Damage", damage)
                debug.log(f"Hit! Roll: {res['roll']} vs AC {target_ac}")
            
            # Handle standard on-hit effects
            effect_type = attacker.get('on_hit_effect', '').lower()
            if effect_type == 'vex':
                effects.append(('player_advantage', 1))
                messages.append(f"{target_name} now has Vex, {get_effect_desc('vex')}")
            elif effect_type == 'sap':
                effects.append(('enemy_advantage', -1))
                messages.append(f"{target_name} now has Sap, {get_effect_desc('sap')}")
            elif effect_type == 'poison':
                effects.append(('msg', "Poisoned!"))
                messages.append(f"{target_name} now has Poison, {get_effect_desc('poisoned')}")
                if float_mgr: float_mgr.add("POISON", target_pos, "effect")
                
            # Handle weapon enchantments
            enchant = attacker.get('weapon_enchantment')
            if enchant == 'lifesteal':
                heal_amt = max(1, damage // 2)
                effects.append(('heal_attacker', heal_amt))
                messages.append(f"Lifesteal: {attacker_name} heals for {heal_amt} HP.")
            elif enchant == 'fire':
                fire_dmg = random.randint(1, 4)
                damage += fire_dmg
                messages.append(f"Fire deals +{fire_dmg} damage!")
                if float_mgr: float_mgr.add(f"-{fire_dmg}", target_pos, (255, 128, 0))
            elif enchant == 'frost':
                effects.append(('enemy_advantage', -1)) # Slow effect
                messages.append(f"Frost chills {target_name}! {get_effect_desc('slow')}")
                if float_mgr: float_mgr.add("CHILLED", target_pos, (100, 200, 255))
            elif enchant == 'silence':
                # DC 12 Silence save
                save_roll, _ = roll_d20()
                if save_roll < 12:
                    effects.append(('silence', 1))
                    messages.append(f"{target_name} is Silenced! {get_effect_desc('incapacitated')}")
                    if float_mgr: float_mgr.add("SILENCED", target_pos, "effect")
                else:
                    messages.append(f"{target_name} resisted Silence.")

        else:
            if float_mgr:
                float_mgr.add("MISS", target_pos, "miss")
            if debug:
                debug.log(f"Missed! Roll: {res['roll']} vs AC {target_ac}")
            # Handle miss effects (like Graze)
            effect_type = attacker.get('on_hit_effect', '').lower()
            if effect_type == 'graze':
                graze_dmg = prof
                damage = graze_dmg
                messages.append(f"Graze dealt {graze_dmg} damage to {target_name}.")
                effects.append(('msg', f"Graze dealt {graze_dmg} damage"))
                if float_mgr: float_mgr.add(f"-{graze_dmg}", target_pos, "damage")

        return {
            'hit': res['hit'],
            'damage': damage,
            'critical': res['critical'],
            'roll': res['roll'],
            'effects': effects,
            'msg': messages
        }

    @staticmethod
    def compute_spell_dc(caster):
        """
        Calculates Spell DC: 8 + proficiency + bonus from items.
        If 'spell_dc' is already defined (e.g. for enemies), use that as the base.
        Clamped between 0 and 20.
        """
        base_dc = caster.get('spell_dc')
        if base_dc is not None:
            return max(0, min(20, int(base_dc)))

        prof = int(caster.get('proficiency_bonus', 0))
        # 'spell_save' is currently used in player_data for equipment bonus
        item_bonus = int(caster.get('spell_save', 0))
        
        dc = 8 + prof + item_bonus
        return max(0, min(20, dc))

    @staticmethod
    def compute_spell_resist(target):
        """
        Calculates Spell Resist. For players, it comes from items. For enemies, it's a base value.
        Clamped between 0 and 20.
        """
        resist = int(target.get('spell_resist', 0))
        return max(0, min(20, resist))

    @staticmethod
    def resolve_ability(ability_data, caster, targets, debug=None, float_mgr=None, skip_cost=False):
        """
        Resolves a single iteration of an ability (skill or spell) cast against one or more targets.
        targets: can be a single target dict or a list of target dicts.
        skip_cost: if True, returns 0 mana_cost (for multi-hit abilities where cost is paid upfront).
        """
        # Ensure targets is a list
        if not isinstance(targets, list):
            targets = [targets]
            
        is_aoe = ability_data.get('aoe', False)
        # If not AOE, we only hit the first target in the list
        active_targets = targets if is_aoe else [targets[0]]

        # Check 'cost' (skills) first, then 'level' (spells)
        mana_cost = 0 if skip_cost else ability_data.get('cost', ability_data.get('level', 0))
        
        total_damage = 0
        total_healing = 0
        all_effects = []
        msg_parts = []
        
        caster_name = caster.get('name', 'Caster')
        target_names = ", ".join([t.get('name', 'Target') for t in active_targets])
        
        name = ability_data.get('name', 'Ability')
        resource_type = ability_data.get('resource', 'mp')
        
        if debug:
            debug.set("Last Ability", name)

        # Only show "uses/casts" message if it's the first time (cost paid)
        if not skip_cost:
            if resource_type == 'sp':
                msg_parts.append(f"{caster_name} uses {name}!")
            else:
                msg_parts.append(f"{caster_name} casts {name}!")

        spell_type = ability_data.get('type', 'attack')
        dice_str = ability_data.get('dice', '')
        
        hits_by_target = {id(t): 0 for t in active_targets}
        damage_by_target = {id(t): 0 for t in active_targets}
        failed_saves_by_target = {id(t): 0 for t in active_targets}

        for target in active_targets:
            target_pos = target.get('screen_pos', (400, 300))
            target_name = target.get('name', 'Target')
            # Determine Dice
            current_dice = dice_str
            if ability_data.get('use_sneak_dice'):
                num_dice = caster.get('sneak_attack_rolls', 1)
                multiplier = ability_data.get('multiplier', 1)
                current_dice = f"{num_dice * multiplier}d6"
                w_bonus = caster.get('weapon_bonus', 0)
                if w_bonus > 0:
                    current_dice += f"+{w_bonus}"
            elif ability_data.get('use_damage_die'):
                # Monk-style damage die scaling
                die = caster.get('damage_die', 4)
                current_dice = f"1d{die}"
                w_bonus = caster.get('weapon_bonus', 0)
                if w_bonus > 0:
                    current_dice += f"+{w_bonus}"
            
            # Resolve by Type
            if spell_type == "attack":
                roll, _ = roll_d20()
                if debug:
                    debug.set("Last Ability Roll", roll)
                
                status = "HIT" if roll >= 6 else "MISS"
                msg_parts.append(f"{caster_name} attacks {target_name}, and rolled a {roll}. > {status}")

                if roll >= 6: # 75% hit chance
                    dmg = roll_dice(current_dice) if current_dice else 0
                    dmg *= ability_data.get('multiplier', 1)
                    damage_by_target[id(target)] += dmg
                    hits_by_target[id(target)] += 1
                    failed_saves_by_target[id(target)] += 1 # Auto-pass save gate for attack types
                    
                    if current_dice:
                        msg_parts.append(f"{caster_name} rolls {current_dice}, dealing {dmg} damage to {target_name}.")
                    
                    if float_mgr:
                        float_mgr.add(f"-{dmg}", target_pos, "damage")
                    if debug:
                        debug.log(f"Hit with {name}! Damage: {dmg}")
                else:
                    if float_mgr:
                        float_mgr.add("MISS", target_pos, "miss")
            
            elif spell_type == "save":
                roll, _ = roll_d20()
                
                spell_dc = CombatEngine.compute_spell_dc(caster)
                spell_resist = CombatEngine.compute_spell_resist(target)
                
                difficulty = max(0, min(20, spell_dc - spell_resist))

                if debug:
                    debug.set("Last Roll", roll)
                    debug.set("Spell DC", spell_dc)
                    debug.set("Spell Resist", spell_resist)
                    debug.set("Difficulty", difficulty)

                if roll < difficulty:
                    # Target FAILED the save (Full Damage + Effects)
                    dmg = roll_dice(current_dice) if current_dice else 0
                    dmg *= ability_data.get('multiplier', 1)
                    damage_by_target[id(target)] += dmg
                    hits_by_target[id(target)] += 1
                    failed_saves_by_target[id(target)] += 1
                    
                    msg_parts.append(f"{target_name} failed save ({roll} < {difficulty})!")
                    if current_dice:
                        msg_parts.append(f"{caster_name} rolls {current_dice}, dealing {dmg} damage to {target_name}.")

                    if float_mgr:
                        float_mgr.add("FAIL", target_pos, "fail")
                        if dmg > 0:
                            float_mgr.add(f"-{dmg}", target_pos, "damage")
                    if debug:
                        debug.log(f"FAIL: {roll} < {difficulty} (Dmg: {dmg})")
                else:
                    # Target PASSED the save (Half Damage, No Effects)
                    dmg = (roll_dice(current_dice) // 2) if current_dice else 0
                    dmg *= ability_data.get('multiplier', 1)
                    damage_by_target[id(target)] += dmg
                    hits_by_target[id(target)] += 1
                    
                    msg_parts.append(f"{target_name} resisted ({roll} >= {difficulty})!")
                    if current_dice:
                        msg_parts.append(f"{caster_name} rolls {current_dice} (half), dealing {dmg} damage to {target_name}.")

                    if float_mgr:
                        float_mgr.add("SAVE", target_pos, "save")
                        if dmg > 0:
                            float_mgr.add(f"-{dmg}", target_pos, "damage")
                    if debug:
                        debug.log(f"RESIST: {roll} >= {difficulty} (Dmg: {dmg})")
                    
            elif spell_type == "auto":
                dmg = roll_dice(current_dice) if current_dice else 0
                dmg *= ability_data.get('multiplier', 1)
                damage_by_target[id(target)] += dmg
                hits_by_target[id(target)] += 1
                failed_saves_by_target[id(target)] += 1
                
                threshold = ability_data.get('hp_threshold')
                if threshold and target.get('current_hp', target.get('hp', 999)) > threshold:
                    damage_by_target[id(target)] = 0
                    hits_by_target[id(target)] = 0
                    failed_saves_by_target[id(target)] = 0
                    msg_parts.append(f"{target_name} HP above threshold!")
                else:
                    if current_dice:
                        msg_parts.append(f"{caster_name} rolls {current_dice}, dealing {dmg} damage to {target_name}.")
                    if float_mgr:
                        float_mgr.add(f"-{dmg}", target_pos, "damage")
            
            elif spell_type == "heal":
                heal_amt = roll_dice(current_dice) if current_dice else 0
                heal_amt *= ability_data.get('multiplier', 1)
                total_healing += heal_amt
                hits_by_target[id(target)] += 1
                failed_saves_by_target[id(target)] += 1
                
                if current_dice:
                    msg_parts.append(f"{caster_name} rolls {current_dice}, healing {target_name} for {heal_amt} HP.")
                
                if float_mgr:
                    float_mgr.add(f"+{heal_amt}", target_pos, "heal")
            
            elif spell_type == "buff":
                hits_by_target[id(target)] += 1
                failed_saves_by_target[id(target)] += 1

        # Consolidate results
        total_hits = sum(hits_by_target.values())
        total_damage = sum(damage_by_target.values())
        total_failed_saves = sum(failed_saves_by_target.values())

        if total_hits == 0 and spell_type in ("attack", "save"):
            msg_parts.append("It missed!")

        # Apply Effects (only if at least one hit landed and save failed)
        if total_failed_saves > 0:
            # Gather all effect keys
            effect_keys = ['effect', 'effect2', 'effect3']
            duration = ability_data.get('duration', 1)
            for e_key in effect_keys:
                effect_name = ability_data.get(e_key)
                if effect_name:
                    power = ability_data.get('power', 0)
                    all_effects.append((effect_name, power if power else duration))
                    
                    desc = get_effect_desc(effect_name)
                    verb = "have" if is_aoe else "has"
                    msg_parts.append(f"{target_names} now {verb} {effect_name.title()}, {desc}")
                    
                    if float_mgr:
                        # Find the first valid target position for effect display
                        target_pos = active_targets[0].get('screen_pos', (400, 300))
                        float_mgr.add(effect_name.upper(), target_pos, "effect")

            
            # Handle DOT/HOT
            if ability_data.get('dot'):
                dot_dice = ability_data.get('dot_dice', '1d6')
                dot_duration = ability_data.get('duration', 3)
                effect_type = 'hot' if ability_data.get('type') == 'heal' else 'dot'
                
                # Store DOT info in effects to be handled by combat state
                all_effects.append((effect_type, (dot_dice, dot_duration)))
                
                if effect_type == 'hot':
                    msg_parts.append("Regeneration effect applied!")
                else:
                    msg_parts.append("Lingering damage applied!")
            
        return {
            'mana_cost': mana_cost,
            'damage': total_damage,
            'healing': total_healing,
            'damage_by_target': damage_by_target, # Map of id(target) -> damage
            'effects': all_effects,
            'hit': total_hits > 0,
            'msg': msg_parts
        }

    @staticmethod
    def resolve_item(item_data, user):
        """
        Resolves item usage.
        item_data: dict from consumables.json
        user: player/creature data
        """
        hp_gain = item_data.get('hp_gain', 0)
        mana_gain = item_data.get('mana_gain', 0)
        bonus_gain = item_data.get('bonus_gain', 0)
        attack_gain = item_data.get('attack_gain', 0)
        extra_damage = item_data.get('extra_damage', 0)
        
        # Map effect_type/value if they exist
        e_type = item_data.get('effect_type')
        val = item_data.get('value', 0)
        if e_type == 'heal': hp_gain = val
        elif e_type == 'restore_mana': mana_gain = val
        elif e_type == 'buff_bonus': bonus_gain = val
        elif e_type == 'buff_attacks': attack_gain = val
        elif e_type == 'extra_damage': extra_damage = val

        display_name = item_data.get('name', 'Item').replace('_', ' ').title()
        msg = f"Used {display_name}. {item_data.get('description', '')}"
        
        return {
            'hp_gain': hp_gain,
            'mana_gain': mana_gain,
            'bonus_gain': bonus_gain,
            'attack_gain': attack_gain,
            'extra_damage': extra_damage,
            'msg': msg
        }

    @staticmethod
    def generate_loot(enemies):
        """
        Generates loot after defeating enemies.
        """
        total_gold = 0
        items = []
        messages = []
        
        for enemy in enemies:
            # Gold based on enemy HP/level
            gold = random.randint(5, 15) + (enemy.get('hp', 10) // 5)
            total_gold += gold
            
            # Chance for item
            if random.random() < 0.3:
                # Randomly pick a category and item (simplified)
                item_types = ['consumable', 'junk']
                t = random.choice(item_types)
                if t == 'consumable':
                    item_name = random.choice(['healing_potion', 'mana_potion'])
                else:
                    item_name = 'goblin_ear'
                items.append((t, item_name))
                messages.append(f"Found {item_name.replace('_', ' ').title()}!")

        messages.append(f"Gained {total_gold} gold!")
        
        return {
            'gold': total_gold,
            'items': items,
            'messages': messages
        }
