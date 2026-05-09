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

def get_advantage_desc(power):
    """Returns (type, duration_desc) for advantage/disadvantage."""
    duration = abs(int(power))
    adv_type = "Advantage" if int(power) > 0 else "Disadvantage"
    return adv_type, f"for {duration} round{'s' if duration > 1 else ''}"

class CombatEngine:
    @staticmethod
    def resolve_attack(attacker, target, advantage=0, debug=None, float_mgr=None, extra_damage=0, crit_range=[]):
        """
        Resolves a single attack from attacker to target.
        attacker: dict containing proficiency_bonus, weapon_bonus, damage_die, on_hit_effect, etc.
        target: dict containing ac.
        advantage: 1 for advantage, -1 for disadvantage, 0 for normal.
        """
        # Unified bonus calculation: Proficiency + Weapon/Item + Equipment + Feast
        prof = int(attacker.get('proficiency_bonus', 0))
        w_bonus = int(attacker.get('weapon_bonus', 0))
        eq_atk = int(attacker.get('equipment_atk_bonus', 0))
        f_bonus = int(attacker.get('feast_bonus', 0))
        attack_bonus = prof + w_bonus + eq_atk + f_bonus
        
        target_ac = int(target.get('ac', 10))
        target_pos = target.get('screen_pos', (400, 300))
        
        attacker_name = attacker.get('name', 'Attacker')
        target_name = target.get('name', 'Target')
        
        # Determine crit range (Merge with optional parameter)
        base_crit = [20]
        if attacker.get('crit_on_18'): base_crit = [18, 19, 20]
        elif attacker.get('crit_on_19'): base_crit = [19, 20]
        
        actual_crit = list(set(base_crit + list(crit_range)))

        res = attack_roll(attack_bonus, target_ac, crit_range=tuple(actual_crit), advantage=advantage)
        
        # --- Stunned Auto-Crit Trigger ---
        # If target is stunned and attacker is melee (type or range < 3), automatic critical hit.
        target_conds = target.get('conditions', {})
        if target_conds.get('stunned'):
            is_melee = False
            if attacker.get('weapon_type') == 'melee':
                is_melee = True
            # Use weapon_range (players) or attack_range (enemies)
            r_val = attacker.get('weapon_range', attacker.get('attack_range', 1))
            if r_val < 3:
                is_melee = True
            
            if is_melee:
                res['hit'] = True
                res['critical'] = True
        
        damage = 0
        effects = []
        messages = []
        
        status = "hit" if res['hit'] else "missed"
        if res['critical']: status = "CRITICAL hit"
        
        msg = f"{attacker_name} attacked {target_name} and {status}"

        if res['hit']:
            # For damage, we use weapon_bonus + Feast. 
            # For enemies (who lack weapon_bonus), proficiency_bonus acts as their primary modifier.
            primary_mod = w_bonus if w_bonus != 0 else prof
            dmg_mod = primary_mod + f_bonus
            
            # Fallback to 'die' if 'damage_die' is missing (for enemies)
            damage_die = attacker.get('damage_die', attacker.get('die', 4))
            damage, dice_str = damage_roll(damage_die, dmg_mod, critical=res['critical'], player_data=attacker)
            
            # Add bonus_dmg (used by summons)
            b_dmg = int(attacker.get('bonus_dmg', 0))
            if b_dmg > 0:
                damage += b_dmg
                dice_str += f" + {b_dmg} (Summon Bonus)"

            if extra_damage > 0:
                damage += extra_damage
                dice_str += f" + {extra_damage} (Bonus)"

            if damage > 0:
                msg += f", dealing {damage} damage."
            else:
                msg += "."

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
            duration = int(attacker.get('duration', 1))
            
            if effect_type == 'vex':
                effects.append(('vex', duration))
                msg += f" Vex applied to {attacker_name}."
            elif effect_type == 'sap':
                effects.append(('sap', duration))
                msg += f" Sap applied to {target_name}."
            elif effect_type == 'poison':
                effects.append(('poisoned', duration))
                msg += f" Poisoned applied to {target_name}."
                if float_mgr: float_mgr.add("POISONED", target_pos, "effect")
            elif effect_type == 'lifesteal':
                heal_amt = max(1, damage // 2)
                effects.append(('heal_attacker', heal_amt))
                msg += f" Lifesteal applied to {attacker_name}."
                
            # Handle weapon-based DOT
            if attacker.get('dot'):
                dot_val = attacker.get('dot_dice', 4)
                # Ensure it's a dice string
                if isinstance(dot_val, int): dot_val = f"1d{dot_val}"
                elif isinstance(dot_val, str) and 'd' not in dot_val: dot_val = f"1d{dot_val}"
                
                # DOT duration is handled separately in effects
                effects.append(('dot', (str(dot_val), duration)))
                msg += f" Lingering damage applied to {target_name}."

            # Handle weapon enchantments
            enchant = attacker.get('weapon_enchantment')
            if enchant == 'lifesteal':
                heal_amt = max(1, damage // 2)
                effects.append(('heal_attacker', heal_amt))
                msg += f" Lifesteal applied to {attacker_name}."
            elif enchant == 'fire':
                fire_dmg = random.randint(1, 4)
                effects.append(('extra_dmg', fire_dmg))
                msg += f" Fire applied to {target_name}."
                if float_mgr: float_mgr.add(f"-{fire_dmg}", target_pos, (255, 128, 0))
            elif enchant == 'frost':
                effects.append(('enemy_advantage', -1)) # Slow effect
                msg += f" Frost applied to {target_name}."
                if float_mgr: float_mgr.add("CHILLED", target_pos, (100, 200, 255))
            elif enchant == 'silence':
                # DC 12 Silence save
                save_roll, _ = roll_d20()
                if save_roll < 12:
                    effects.append(('silence', 1))
                    msg += f" Silence applied to {target_name}."
                    if float_mgr: float_mgr.add("SILENCED", target_pos, "effect")
                else:
                    msg += f" {target_name} resisted Silence."

        else:
            msg += "."
            if float_mgr:
                float_mgr.add("MISS", target_pos, "miss")
            if debug:
                debug.log(f"Missed! Roll: {res['roll']} vs AC {target_ac}")
            # Handle miss effects (like Graze)
            effect_type = attacker.get('on_hit_effect', '').lower()
            if effect_type == 'graze':
                graze_dmg = max(1, prof // 2)
                damage = graze_dmg
                msg += f" Graze applied to {target_name}, dealing {graze_dmg} damage."
                if float_mgr: float_mgr.add(f"-{graze_dmg}", target_pos, "damage")

        messages.append(msg)

        return {
            'hit': res['hit'],
            'damage': damage,
            'critical': res['critical'],
            'roll': res['roll'],
            'attack_bonus': attack_bonus,
            'total_roll': res['total'],
            'effects': effects,
            'msg': messages,
            'attacker_name': attacker_name,
            'target_name': target_name
        }

    @staticmethod
    def compute_spell_dc(caster, ability_bonus=0):
        """
        Calculates Spell DC: 8 + proficiency + bonus from items + feast bonus + optional ability bonus.
        If 'spell_dc' is already defined (e.g. for enemies), use that as the base.
        Clamped between 0 and 20.
        """
        base_dc = caster.get('spell_dc')
        if base_dc is not None:
            return max(0, min(20, int(base_dc) + ability_bonus))

        prof = int(caster.get('proficiency_bonus', 0))
        # 'spell_save' is currently used in player_data for equipment bonus
        item_bonus = int(caster.get('spell_save', 0))
        f_bonus = int(caster.get('feast_bonus', 0))
        
        dc = 8 + prof + item_bonus + f_bonus + ability_bonus
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
    def _resolve_math(input_str, placeholders):
        """Helper to replace placeholders and evaluate math in a string."""
        if not isinstance(input_str, str):
            return str(input_str)
            
        result = input_str
        
        # 0. Handle Nested Dice (e.g. 2d{damage_die} where damage_die is 2d10)
        # If {damage_die} placeholder is a dice string, "d{damage_die}" should become "*({damage_die})"
        dd_val = placeholders.get("{damage_die}")
        if dd_val and 'd' in str(dd_val):
             result = result.replace("d{damage_die}", f"*({dd_val})")

        # 1. Replace all named placeholders
        for ph, val in placeholders.items():
            result = result.replace(ph, str(val))
            
        import re
        # 2. Resolve all remaining {math} blocks explicitly
        def eval_block(match):
            expr = match.group(0).strip("{}")
            try:
                # Use a safe eval for the inner math
                return str(int(eval(expr, {"__builtins__": None}, {})))
            except:
                # If eval fails, maybe it's still a placeholder or complex string
                return match.group(0)
        
        result = re.sub(r"\{[^\}]+\}", eval_block, result)
        
        # 3. Handle dice strings and general arithmetic
        # We split by + and - to evaluate terms, but preserve 'd' for dice
        parts = re.split(r"(\+|-)", result)
        resolved_parts = []
        
        for part in parts:
            if not part or part in "+-":
                resolved_parts.append(part)
                continue
            
            if 'd' in part:
                # Handle dice notation XdY where X and Y might still be math like (4+1)
                d_match = re.split(r"(d)", part) # Split by 'd' but keep it
                sub_resolved = []
                for sub in d_match:
                    if sub == 'd' or not sub:
                        sub_resolved.append(sub)
                        continue
                    # Try to eval the count or side if it has math characters
                    if any(c in sub for c in "()*/"):
                        try:
                            # Sanitize sub for safety
                            cleaned = "".join(c for c in sub if c in "0123456789+-*/(). ")
                            val = str(int(eval(cleaned, {"__builtins__": None}, {})))
                            sub_resolved.append(val)
                        except:
                            sub_resolved.append(sub)
                    else:
                        sub_resolved.append(sub)
                resolved_parts.append("".join(sub_resolved))
            else:
                # Pure math part
                if any(c in part for c in "()*/"):
                    try:
                        cleaned = "".join(c for c in part if c in "0123456789+-*/(). ")
                        val = str(int(eval(cleaned, {"__builtins__": None}, {})))
                        resolved_parts.append(val)
                    except:
                        resolved_parts.append(part)
                else:
                    resolved_parts.append(part)
                    
        return "".join(resolved_parts)

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
        mana_cost_raw = 0 if skip_cost else ability_data.get('cost', ability_data.get('level', 0))
        
        # Prepare placeholders for all resolutions
        prof = int(caster.get('proficiency_bonus', 0))
        total_level = sum(caster.get('class_levels', {}).values()) if caster.get('class_levels') else caster.get('level', 1)
        
        # Snapshot-aware resource values
        mp_val = int(caster.get('standby_mp', caster.get('current_mp', 0)))
        sp_val = int(caster.get('standby_sp', caster.get('current_sp', 0)))

        placeholders = {
            "{damage_die}": str(caster.get('damage_die', caster.get('die', 4))),
            "{level}": str(total_level),
            "{level/2}": str(total_level // 2),
            "{level2}": str(total_level // 2),
            "{prof}": str(prof),
            "{current_mp}": str(mp_val),
            "{current_mp/2}": str(mp_val // 2),
            "{current_mp2}": str(mp_val // 2),
            "{current_sp}": str(sp_val),
            "{current_sp/2}": str(sp_val // 2),
            "{current_sp2}": str(sp_val // 2)
        }

        mana_cost = 0
        if mana_cost_raw:
            try:
                # Resolve math/placeholders in cost (e.g. "{prof}/2 + 1")
                resolved_cost = CombatEngine._resolve_math(str(mana_cost_raw), placeholders)
                if any(op in resolved_cost for op in "+-*/"):
                    mana_cost = int(eval(resolved_cost, {"__builtins__": None}, {}))
                else:
                    mana_cost = int(resolved_cost)
            except:
                # Fallback to 0 or raw int if possible
                mana_cost = int(mana_cost_raw) if str(mana_cost_raw).isdigit() else 0
        
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

        spell_type = ability_data.get('type', 'attack')
        dice_str = ability_data.get('dice', '')
        
        hits_by_target = {id(t): 0 for t in active_targets}
        damage_by_target = {id(t): 0 for t in active_targets}
        healing_by_target = {id(t): 0 for t in active_targets}
        failed_saves_by_target = {id(t): 0 for t in active_targets}
        rolls_by_target = {}
        saves_info = {} # Map of tid -> {'roll': int, 'success': bool, 'dc': int}

        for target in active_targets:
            tid = id(target)
            target_pos = target.get('screen_pos', (400, 300))
            
            # Determine Dice
            current_dice = dice_str
            if ability_data.get('use_damage_die'):
                # Monk-style damage die scaling
                die = caster.get('damage_die', caster.get('die', 4))
                current_dice = f"1d{die}"
                w_bonus = int(caster.get('weapon_bonus', 0))
                f_bonus = int(caster.get('feast_bonus', 0))
                total_bonus = w_bonus + prof + f_bonus
                
                # Level scaling: {damage_die} + {player_level / 2}
                if ability_data.get('bonus_per_level'):
                    level_bonus = total_level // 2
                    total_bonus += level_bonus
                
                if total_bonus != 0:
                    current_dice += f"{'+' if total_bonus > 0 else ''}{total_bonus}"

            # Resolve placeholders and math in the determined dice string
            if current_dice:
                current_dice = CombatEngine._resolve_math(current_dice, placeholders)

            # Resolve by Type
            f_bonus = int(caster.get('feast_bonus', 0))
            if spell_type == "attack":
                roll, _ = roll_d20()
                rolls_by_target[tid] = roll
                # Standard 75% hit chance (roll 6+), improved by Feast bonus
                threshold = max(2, 6 - f_bonus)
                if roll >= threshold:
                    dmg = roll_dice(current_dice) if current_dice else 0
                    dmg *= ability_data.get('multiplier', 1)
                    # Add feast bonus to damage if it's an attack ability
                    dmg += f_bonus
                    damage_by_target[tid] += dmg
                    hits_by_target[tid] += 1
                    failed_saves_by_target[tid] += 1
                    if float_mgr: float_mgr.add(f"-{dmg}", target_pos, "damage")
                else:
                    if float_mgr: float_mgr.add("MISS", target_pos, "miss")

            elif spell_type == "save":
                # Roll damage ONCE for all targets if there's a dice string
                damage_roll = roll_dice(current_dice) if current_dice else 0
                
                # Resolve ability-specific DC bonus
                ability_dc_bonus = ability_data.get('bonus_spell_save', 0)
                if ability_dc_bonus:
                    try:
                        ability_dc_bonus = int(CombatEngine._resolve_math(str(ability_dc_bonus), placeholders))
                    except:
                        ability_dc_bonus = 0
                
                spell_dc = CombatEngine.compute_spell_dc(caster, ability_bonus=int(ability_dc_bonus))
                
                for target in active_targets:
                    tid = id(target)
                    target_pos = target.get('screen_pos', (400, 300))
                    
                    roll, _ = roll_d20()
                    spell_resist = CombatEngine.compute_spell_resist(target)
                    difficulty = max(0, min(20, spell_dc - spell_resist))

                    failed = roll < difficulty
                    saves_info[tid] = {'roll': roll, 'success': not failed, 'dc': difficulty, 'damage_roll': damage_roll}

                    if failed:
                        dmg = damage_roll
                        dmg *= ability_data.get('multiplier', 1)
                        damage_by_target[tid] += dmg
                        hits_by_target[tid] += 1
                        failed_saves_by_target[tid] += 1
                        if float_mgr:
                            float_mgr.add("FAIL", target_pos, "fail")
                            if dmg > 0: float_mgr.add(f"-{dmg}", target_pos, "damage")
                    else:
                        dmg = damage_roll // 2
                        dmg *= ability_data.get('multiplier', 1)
                        damage_by_target[tid] += dmg
                        hits_by_target[tid] += 1
                        if float_mgr:
                            float_mgr.add("SAVE", target_pos, "save")
                            if dmg > 0: float_mgr.add(f"-{dmg}", target_pos, "damage")
                
                # End of target loop for save type
                continue

            elif spell_type == "auto":
                threshold = ability_data.get('hp_threshold')
                is_below = True
                if threshold and target.get('current_hp', target.get('hp', 999)) > threshold:
                    is_below = False

                if is_below:
                    dmg = ability_data.get('threshold_damage')
                    if dmg is None:
                        dmg = roll_dice(current_dice) if current_dice else 0
                    
                    damage_by_target[tid] += dmg * ability_data.get('multiplier', 1)
                    hits_by_target[tid] += 1
                    failed_saves_by_target[tid] += 1
                    if float_mgr and dmg > 0:
                        float_mgr.add(f"-{dmg}", target_pos, "damage")
                else:
                    dmg = ability_data.get('else_damage', 0)
                    if dmg > 0:
                        damage_by_target[tid] += dmg * ability_data.get('multiplier', 1)
                        hits_by_target[tid] += 1
                        # Do not increment failed_saves_by_target so effects don't apply if above threshold
                        if float_mgr:
                            float_mgr.add(f"-{dmg}", target_pos, "damage")
            
            elif spell_type == "heal":
                heal_amt = roll_dice(current_dice) if current_dice else 0
                heal_amt *= ability_data.get('multiplier', 1)
                total_healing += heal_amt
                healing_by_target[tid] += heal_amt
                hits_by_target[tid] += 1
                failed_saves_by_target[tid] += 1
                
                if float_mgr:
                    float_mgr.add(f"+{heal_amt}", target_pos, "heal")
            
            elif spell_type == "buff":
                hits_by_target[tid] += 1
                failed_saves_by_target[tid] += 1
            
            elif spell_type == "summon":
                hits_by_target[tid] += 1
                failed_saves_by_target[tid] += 1

        # Consolidate results
        total_hits = sum(hits_by_target.values())
        total_damage = sum(damage_by_target.values())
        total_failed_saves = sum(failed_saves_by_target.values())

        # Resolve duration and power placeholders
        duration_raw = ability_data.get('duration', 1)
        duration = 1
        try:
            resolved_dur = CombatEngine._resolve_math(str(duration_raw), placeholders)
            if any(op in resolved_dur for op in "+-*/"):
                duration = int(eval(resolved_dur, {"__builtins__": None}, {}))
            else:
                duration = int(resolved_dur)
        except:
            try: duration = int(duration_raw)
            except: duration = 1

        # Apply Effects (only if at least one hit landed and save failed)
        if total_failed_saves > 0:
            # Gather all effect keys
            effect_keys = ['effect', 'effect2', 'effect3']
            for e_key in effect_keys:
                effect_name = ability_data.get(e_key)
                if effect_name:
                    power_raw = ability_data.get('power', 0)
                    power = 0
                    try:
                        resolved_power = CombatEngine._resolve_math(str(power_raw), placeholders)
                        if any(op in resolved_power for op in "+-*/"):
                            power = int(eval(resolved_power, {"__builtins__": None}, {}))
                        else:
                            power = int(resolved_power)
                    except:
                        try: power = int(power_raw)
                        except: power = 0
                    
                    all_effects.append((effect_name, power if power else duration))
                    
                    if float_mgr:
                        # Find the first valid target position for effect display
                        target_pos = active_targets[0].get('screen_pos', (400, 300))
                        float_mgr.add(effect_name.upper(), target_pos, "effect")

            # Handle DOT/HOT
            has_dot = ability_data.get('dot')
            has_hot = ability_data.get('hot')

            if has_dot or has_hot:
                dot_duration_raw = ability_data.get('duration', 3)
                dot_duration = 3
                try:
                    resolved_dot_dur = CombatEngine._resolve_math(str(dot_duration_raw), placeholders)
                    if any(op in resolved_dot_dur for op in "+-*/"):
                        dot_duration = int(eval(resolved_dot_dur, {"__builtins__": None}, {}))
                    else:
                        dot_duration = int(resolved_dot_dur)
                except:
                    try: dot_duration = int(dot_duration_raw)
                    except: dot_duration = 3
                
                if has_hot or ability_data.get('type') == 'heal':
                    effect_type = 'hot'
                    dice = ability_data.get('hot_dice', ability_data.get('dot_dice', '1d6'))
                else:
                    effect_type = 'dot'
                    dice = ability_data.get('dot_dice', '1d6')
                
                # Resolve placeholders and math in dice string
                dice = CombatEngine._resolve_math(dice, placeholders)
                
                # Store info in effects to be handled by combat state
                all_effects.append((effect_type, (dice, dot_duration)))

        # Handle Lifesteal / on_hit_effect for abilities
        if total_damage > 0:
            if ability_data.get('on_hit_effect') == 'lifesteal':
                heal_amt = max(1, total_damage // 2)
                all_effects.append(('heal_attacker', heal_amt))

        # Build message
        status = "hit" if total_hits > 0 else "missed"
        msg = f"{caster_name} used {name} on {target_names} and {status}"
        if total_hits > 0:
            if total_damage > 0:
                msg += f", dealing {total_damage} damage."
            elif total_healing > 0:
                msg += f", restoring {total_healing} HP."
            else:
                msg += "."
            
            for effect, val in all_effects:
                # Simple logic for internal messages
                msg += f" {effect.replace('_', ' ').title()} applied."
        else:
            msg += "."
        msg_parts.append(msg)
            
        res_dict = {
            'mana_cost': mana_cost,
            'damage': total_damage,
            'healing': total_healing,
            'damage_by_target': damage_by_target, # Map of id(target) -> damage
            'healing_by_target': healing_by_target, # Map of id(target) -> healing
            'hits_by_target': hits_by_target, # Map of id(target) -> hits
            'failed_saves_by_target': failed_saves_by_target,
            'saves_info': saves_info,
            'effects': all_effects,
            'hit': total_hits > 0,
            'msg': msg_parts,
            'attacker_name': caster_name,
            'target_names': target_names,
            'ability_name': name
        }

        # For "attack" types, return the first roll for the UI to animate
        if spell_type == "attack" and rolls_by_target:
            first_tid = list(rolls_by_target.keys())[0]
            roll_val = rolls_by_target[first_tid]
            res_dict['roll'] = roll_val
            
            # Calculate total_bonus as requested: {item_bonus+proficiency+bonus+feast}
            # In our engine: proficiency_bonus + weapon_bonus + equipment_atk_bonus + feast_bonus
            w_bonus = int(caster.get('weapon_bonus', 0))
            eq_atk = int(caster.get('equipment_atk_bonus', 0))
            f_bonus = int(caster.get('feast_bonus', 0))
            total_bonus = prof + w_bonus + eq_atk + f_bonus
            res_dict['attack_bonus'] = total_bonus
            res_dict['total_roll'] = roll_val + total_bonus

        return res_dict

    @staticmethod
    def resolve_item(item_data, user):
        """
        Resolves item usage.
        item_data: dict from consumables.json
        user: player/creature data
        """
        hp_gain = item_data.get('hp_gain', 0)
        mana_gain = item_data.get('mana_gain', 0)
        stamina_gain = item_data.get('stamina_gain', 0)
        bonus_gain = item_data.get('bonus_gain', 0)
        attack_gain = item_data.get('attack_gain', 0)
        extra_damage = item_data.get('extra_damage', 0)
        
        # Map effect_type/value if they exist
        e_type = item_data.get('effect_type')
        val = item_data.get('value', 0)
        if e_type == 'heal': hp_gain = val
        elif e_type == 'restore_mana': mana_gain = val
        elif e_type == 'restore_stamina': stamina_gain = val
        elif e_type == 'buff_bonus': bonus_gain = val
        elif e_type == 'buff_attacks': attack_gain = val
        elif e_type == 'extra_damage': extra_damage = val
        elif e_type == 'temp_weapon_buff': bonus_gain = val

        display_name = item_data.get('name', 'Item').replace('_', ' ').title()
        msg = f"Used {display_name}. {item_data.get('description', '')}"
        
        return {
            'hp_gain': hp_gain,
            'mana_gain': mana_gain,
            'stamina_gain': stamina_gain,
            'bonus_gain': bonus_gain,
            'attack_gain': attack_gain,
            'extra_damage': extra_damage,
            'msg': msg
        }

    @staticmethod
    def generate_loot(enemies):
        """
        Generates loot after defeating enemies.
        Always drops reward gold + scaling bonus.
        50% chance per enemy to drop one of its reward items.
        """
        total_gold = 0
        items = []
        messages = []
        
        for enemy in enemies:
            # 1. Gold: Use defined reward gold + a scaling level bonus
            reward_data = enemy.get('reward', {})
            base_gold = reward_data.get('gold', 10)
            
            # Add some randomness and scaling to make it feel more frequent/rewarding
            scaling_bonus = random.randint(5, 15) + (enemy.get('level', 1) * 2)
            gold_dropped = base_gold + scaling_bonus
            total_gold += gold_dropped
            
            # 2. Items: 50/50 chance to drop one of the items in the reward list
            reward_items = reward_data.get('items', [])
            if reward_items and random.random() < 0.5:
                # Pick one item from the reward list
                item = random.choice(reward_items)
                
                if isinstance(item, dict):
                    i_name = item.get('name')
                    i_type = item.get('type', 'junk')
                    if i_name:
                        items.append((i_type, i_name))
                        messages.append(f"Found {i_name.replace('_', ' ').title()}!")
                else:
                    # Fallback for old string format
                    items.append(('junk', item))
                    messages.append(f"Found {item.replace('_', ' ').title()}!")
            
            # 3. Extra Chance for Potion (Bonus)
            if random.random() < 0.2:
                potion = random.choice(['healing_potion', 'mana_potion', 'stamina_potion'])
                items.append(('consumable', potion))
                messages.append(f"Found {potion.replace('_', ' ').title()}!")

        messages.append(f"Gained {total_gold} gold!")
        
        return {
            'gold': total_gold,
            'items': items,
            'messages': messages
        }
