import json
import os
import random
import sys

# Add project root to path to allow absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.players.player import choose_player_class, classes as player_classes, apply_weapon_to_player, apply_armor_to_player, load_consumables, load_spells, load_skills
from core.creatures.enemies import load_enemy_data, get_scaled_enemies
from core.players.player_inventory import create_inventory, add_gold, add_item, display_inventory, manage_inventory, award_loot
from core.players.leveler import update_xp_and_level, xp_to_next_level, get_class_stats_at_level, load_player_classes, add_class_level
from core.combat.attack_roller import attack_roll, damage_roll
from core.combat.combat_engine import CombatEngine
from core.players.shop import visit_shop

def choose_enemies(enemy_data, player_level=1):
    enemies = get_scaled_enemies(enemy_data, player_level)
    names = ", ".join([e['name'].title() for e in enemies])
    print(f"You encountered {names}!")
    input('Press Enter to Roll initiative!\n')
    return enemies


def simulate_combat(player_data, enemy_list, player_goes_first=True):
    player = player_data # Reference to update HP/MP
    enemies = [e.copy() for e in enemy_list] # Work with copies

    # HP Tracking
    player_hp = int(player.get('hp', 1))
    player_max_hp = player.get('max_hp', player_hp)
    
    # Stats (Local modifiable versions for combat)
    p_attack_count = int(player.get('attack_count', 1))
    
    player_advantage = 0 
    enemy_advantage = 0
    extra_damage_once = 0 # From poisons, etc.

    # Condition tracking
    player_conditions = {}
    for e in enemies: e['conditions'] = {}

    consumables_db = load_consumables()
    spells_db = load_spells()
    skills_db = load_skills()

    turn = 1
    
    def get_alive_enemies():
        return [e for e in enemies if e.get('hp', 0) > 0]

    print(f"Combat start: player hp={player_hp}, enemies={len(enemies)}\n")

    while player_hp > 0 and len(get_alive_enemies()) > 0:
        print(f"--- Turn {turn} ---")

        def player_phase():
            nonlocal player_hp, player_advantage, enemy_advantage, p_attack_count, extra_damage_once
            
            if player_conditions.get('stunned', 0) > 0:
                print("You are stunned and skip your turn!")
                player_conditions['stunned'] -= 1
                return "ok"

            action_taken = False
            while not action_taken:
                alive_enemies = get_alive_enemies()
                if not alive_enemies: break

                status_str = f"\nPLAYER TURN (HP: {player_hp}/{player_max_hp}"
                if player.get('max_mp', 0) > 0:
                    status_str += f", MP: {player.get('current_mp', 0)}/{player.get('max_mp', 0)}"
                if player.get('max_sp', 0) > 0:
                    status_str += f", SP: {player.get('current_sp', 0)}/{player.get('max_sp', 0)}"
                status_str += ")"
                print(status_str)
                
                print("Enemies:")
                for i, e in enumerate(alive_enemies, 1):
                    cond_str = f" [{', '.join(e['conditions'].keys())}]" if e['conditions'] else ""
                    print(f"  {i}. {e['name'].title()} (HP: {e['hp']}){cond_str}")

                print("\n1. Attack")
                print("2. Use Item")
                print("3. Skills/Spells")
                print("4. Run")
                
                choice = input("Select an action: ").strip()
                
                if choice == '1':
                    # Select target
                    t_choice = input(f"Select target (1-{len(alive_enemies)}): ").strip()
                    if not (t_choice.isdigit() and 1 <= int(t_choice) <= len(alive_enemies)):
                        print("Invalid target.")
                        continue
                    
                    target = alive_enemies[int(t_choice) - 1]
                    total_damage = 0
                    for _ in range(p_attack_count):
                        res = CombatEngine.resolve_attack(player, target, advantage=player_advantage)
                        player_advantage = 0 
                        
                        if res['hit']:
                            dmg = res['damage']
                            if extra_damage_once > 0:
                                dmg += extra_damage_once
                                print(f"  Effect applied! +{extra_damage_once} damage.")
                                extra_damage_once = 0
                                
                            total_damage += dmg
                            print(f"Player hits {target['name']} for {dmg} (roll {res['roll']})")
                            
                            for effect, val in res['effects']:
                                if effect == 'player_advantage': player_advantage = val; print("  Vex: Advantage on next attack!")
                                elif effect == 'enemy_advantage': enemy_advantage = val; print("  Sap: Enemy disadvantage on next attack!")
                                elif effect == 'heal_attacker':
                                    player_hp = min(player_max_hp, player_hp + val)
                                    print(f"  Lifesteal: Healed for {val} HP!")
                                elif effect == 'stunned':
                                    target['conditions']['stunned'] = val
                                    print(f"  Effect: {target['name']} is stunned!")
                                elif effect == 'msg': print(f"  {val}")
                        else:
                            print(f"Player misses {target['name']} (roll {res['roll']})")
                    
                    target['hp'] = max(0, target['hp'] - total_damage)
                    print(f"Total damage to {target['name']}: {total_damage}. Remaining HP: {target['hp']}")
                    action_taken = True
                    
                elif choice == '2':
                    items = player_data.get('inventory_ref', {}).get('consumable', [])
                    if not items:
                        print("You have no consumables!")
                        continue
                    
                    print("\n--- Consumables ---")
                    for i, item in enumerate(items, 1):
                        print(f"{i}. {item.replace('_', ' ').title()}")
                    print(f"{len(items) + 1}. Back")
                    
                    item_choice = input("Select an item to use: ").strip()
                    if item_choice.isdigit() and 1 <= int(item_choice) <= len(items):
                        item_key = items[int(item_choice) - 1].lower().replace(' ', '_')
                        item_data = consumables_db.get(item_key)
                        
                        if item_data:
                            res = CombatEngine.resolve_item(item_data, player)
                            print(res['msg'])
                            
                            if res['hp_gain'] > 0:
                                player_hp = min(player_max_hp, player_hp + res['hp_gain'])
                                print(f"Healed for {res['hp_gain']} HP! (Current: {player_hp}/{player_max_hp})")
                            if res['bonus_gain'] > 0:
                                player['weapon_bonus'] = player.get('weapon_bonus', 0) + res['bonus_gain']
                                print(f"Attack/Damage bonus increased by {res['bonus_gain']}!")
                            if res['attack_gain'] > 0:
                                p_attack_count += res['attack_gain']
                                print(f"Attack count increased by {res['attack_gain']}!")
                            if res['extra_damage'] > 0:
                                extra_damage_once += res['extra_damage']
                                print(f"Next hit will deal +{res['extra_damage']} damage!")
                            
                            items.pop(int(item_choice) - 1)
                            action_taken = True
                    else:
                        continue

                elif choice == '3':
                    skills = player.get('skills', [])
                    spells = player.get('spells', [])
                    all_abilities = skills + spells
                    
                    if not all_abilities:
                        print("You have no skills or spells yet!")
                        continue
                    
                    print("\n--- Skills & Spells ---")
                    for i, ability in enumerate(all_abilities, 1):
                        print(f"{i}. {ability.title()}")
                    print(f"{len(all_abilities) + 1}. Back")
                    
                    s_choice = input("Select an ability: ").strip()
                    if s_choice.isdigit() and 1 <= int(s_choice) <= len(all_abilities):
                        ability_name = all_abilities[int(s_choice) - 1]
                        ability_key = ability_name.lower().replace(' ', '_')
                        ability_data = skills_db.get(ability_key) or spells_db.get(ability_key)
                        
                        if ability_data:
                            cost = ability_data.get('cost', ability_data.get('level', 0))
                            resource_type = ability_data.get('resource', 'mp')
                            resource_key = 'current_mp' if resource_type == 'mp' else 'current_sp'
                            current_resource = player.get(resource_key, 0)
                            
                            if current_resource < cost:
                                print(f"Not enough {resource_type.upper()}! (Need {cost}, have {current_resource})")
                                continue

                            # Target selection for non-AOE
                            targets = alive_enemies
                            if not ability_data.get('aoe'):
                                t_choice = input(f"Select target (1-{len(alive_enemies)}): ").strip()
                                if not (t_choice.isdigit() and 1 <= int(t_choice) <= len(alive_enemies)):
                                    print("Invalid target.")
                                    continue
                                targets = [alive_enemies[int(t_choice) - 1]]

                            res = CombatEngine.resolve_ability(ability_data, player, targets)
                            print(res['msg'])
                            player[resource_key] = current_resource - res.get('mana_cost', cost)
                            
                            # Apply damage to targets
                            dmg_map = res.get('damage_by_target', {})
                            for target in targets:
                                dmg = dmg_map.get(id(target), 0)
                                if dmg > 0:
                                    target['hp'] = max(0, target['hp'] - dmg)
                                    print(f"  {target['name']} took {dmg} damage! (HP: {target['hp']})")
                            
                            if res['healing'] > 0:
                                player_hp = min(player_max_hp, player_hp + res['healing'])
                                print(f"Ability healed you for {res['healing']} HP!")
                                
                            for effect, val in res['effects']:
                                if effect == 'enemy_advantage':
                                    enemy_advantage = val
                                    print("Enemies are disadvantaged!")
                                elif effect == 'extra_damage':
                                    extra_damage_once += val
                                    print(f"Effect: Next hit will deal +{val} damage!")
                                elif effect == 'heal_attacker':
                                    player_hp = min(player_max_hp, player_hp + val)
                                    print(f"Effect: Healed for {val} HP!")
                                elif effect == 'stunned':
                                    for target in targets:
                                        target['conditions']['stunned'] = val
                                        print(f"Effect: {target['name']} is stunned!")
                                
                            action_taken = True
                        else:
                            print(f"You used {ability_name.title()}!")
                            action_taken = True
                    else:
                        continue

                elif choice == '4':
                    if random.random() < 0.4:
                        print("You successfully ran away!")
                        return "ran"
                    else:
                        print("You failed to run away!")
                        action_taken = True
                else:
                    print("Invalid selection.")
            
            return "ok"

        def enemy_phase():
            nonlocal player_hp, enemy_advantage
            total_damage = 0
            alive_enemies = get_alive_enemies()
            
            for enemy in alive_enemies:
                if enemy['conditions'].get('stunned', 0) > 0:
                    print(f"{enemy['name'].title()} is stunned and skips their turn!")
                    enemy['conditions']['stunned'] -= 1
                    continue

                e_attack_count = int(enemy.get('attack_count', 1))
                print(f"{enemy['name'].title()} attacks!")
                
                for _ in range(e_attack_count):
                    res = CombatEngine.resolve_attack(enemy, player, advantage=enemy_advantage)
                    enemy_advantage = 0 
                    
                    if res['hit']:
                        dmg = res['damage']
                        total_damage += dmg
                        print(f"  Hits for {dmg} (roll {res['roll']})")
                        
                        for effect, val in res['effects']:
                            if effect == 'heal_attacker':
                                enemy['hp'] = min(enemy.get('max_hp', enemy['hp']), enemy['hp'] + val)
                                print(f"  {enemy['name']} heals for {val} HP!")
                            elif effect == 'stunned':
                                player_conditions['stunned'] = val
                                print("  Effect: You are stunned!")
                    else:
                        print(f"  Misses (roll {res['roll']})")

            player_hp = max(0, player_hp - total_damage)
            print(f"Total damage received: {total_damage}. Player HP: {player_hp}\n")

        if player_goes_first:
            res = player_phase()
            if res == "ran": return {'winner': 'none', 'player_hp': player_hp, 'turns': turn}
            if not get_alive_enemies(): break
            input('Next phase...')
            enemy_phase()
        else:
            enemy_phase()
            if player_hp <= 0: break
            input('Next phase...')
            res = player_phase()
            if res == "ran": return {'winner': 'none', 'player_hp': player_hp, 'turns': turn}

        if player_hp <= 0 or not get_alive_enemies(): break
        input('Next turn...')
        turn += 1

    winner = 'player' if player_hp > 0 else 'enemy'
    print(f"Combat ends: {winner.upper()} wins")
    player['hp'] = player_hp 
    return {'winner': winner, 'player_hp': player_hp, 'turns': turn}


def hub_menu(player_profile, player_inventory):
    while True:
        print("\n--- ADVENTURE HUB ---")
        print(f"Level {player_profile['level']} {player_profile['class'].title()}")
        print(f"HP: {player_profile['hp']} / {player_profile.get('max_hp', player_profile['hp'])}")
        print(f"Gold: {player_inventory['gold']}")
        
        rest_cost = 5 + player_profile.get('rest_count', 0)
        
        print("1. Next Fight")
        print("2. Visit Shop")
        print(f"3. Rest (Restores full HP, costs {rest_cost} gold)")
        print("4. View Inventory/Stats")
        print("5. Exit Game")
        
        choice = input("What would you like to do? ").strip()
        
        if choice == '1':
            return True
        elif choice == '2':
            visit_shop(player_profile, player_inventory)
        elif choice == '3':
            rest(player_profile, player_inventory)
        elif choice == '4':
            manage_inventory(player_profile, player_inventory)
        elif choice == '5':
            return False
        else:
            print("Invalid selection.")

def rest(player_profile, player_inventory):
    cost = 5 + player_profile.get('rest_count', 0)
    if player_inventory['gold'] >= cost:
        player_inventory['gold'] -= cost
        player_profile['hp'] = player_profile.get('max_hp', player_profile['hp'])
        player_profile['rest_count'] = player_profile.get('rest_count', 0) + 1
        print(f"You rested for {cost} gold. HP fully restored to {player_profile['hp']}!")
        print(f"Your next rest will cost {5 + player_profile['rest_count']} gold.")
    else:
        print(f"You don't have enough gold! You need {cost} gold to rest.")


def main():
    enemy_data = load_enemy_data()
    player_name, player_profile = choose_player_class(player_classes)
    player_profile['class'] = player_name
    player_profile.setdefault('xp', 0)
    player_profile.setdefault('level', 1)
    player_profile.setdefault('base_hp', player_profile.get('hp', 0))
    player_profile['max_hp'] = player_profile['hp']
    
    player_profile['rest_count'] = 0

    player_classes_data = load_player_classes()
    level1_stats = get_class_stats_at_level(player_name, 1, player_classes_data)
    for k, v in level1_stats.items(): player_profile[k] = v

    apply_weapon_to_player(player_profile)
    apply_armor_to_player(player_profile)
    player_inventory = create_inventory(player_profile)
    
    player_profile['inventory_ref'] = player_inventory

    print(f"Player: {player_name.title()} ({player_profile['hp']} HP)")

    continue_playing = True
    enemies_defeated = 0

    while continue_playing and player_profile['hp'] > 0:
        if not hub_menu(player_profile, player_inventory):
            break

        enemies = choose_enemies(enemy_data, player_profile.get('level', 1))
        
        p_init = random.randint(1, 20) + player_profile.get('proficiency_bonus', 0)
        # Initiative against the "first" enemy's bonus as a representative
        e_init = random.randint(1, 20) + enemies[0].get('bonus', 0)
        player_first = p_init >= e_init
        
        print(f"Initiative: Player {p_init} vs Enemies {e_init}")
        result = simulate_combat(player_profile, enemies, player_goes_first=player_first)

        if result['winner'] == 'player':
            enemies_defeated += len(enemies)
            # Sum XP from all enemies in the group
            total_xp = sum([e.get('xp', 0) for e in enemies])
            player_profile['hp'] = result['player_hp']
            
            level_up_available = update_xp_and_level(player_profile, total_xp)
            
            if level_up_available:
                from core.players.leveler import get_level_up_benefits
                benefits = get_level_up_benefits(player_profile, player_profile['class'])
                add_class_level(player_profile, player_profile['class'])
                print(f"\n*** LEVEL UP! ***")
                print(f"You are now level {player_profile['level']}.")
                print(f"{benefits}")
                print(f"Max HP: {player_profile['max_hp']}\n")

            # Loot from each enemy
            for e in enemies:
                loot_msg = award_loot(player_inventory, e.get('reward', {}))
                if loot_msg:
                    print(f"Loot from {e['name']}: {loot_msg}")
            
            print(f"Current HP: {player_profile['hp']}")
            next_xp_val = xp_to_next_level(player_profile['xp'])
            print(f"You gained {total_xp} xp, you are now {next_xp_val if next_xp_val is not None else 0} xp away from next level.")
        elif result['winner'] == 'none':
            print(f"You escaped.")
            player_profile['hp'] = result['player_hp']
        else:
            print(f"Game Over. Final Score: {player_profile['xp'] + enemies_defeated}")
            break

    final_score = player_profile['xp'] + enemies_defeated
    print(f"Final Score: {final_score} (XP: {player_profile['xp']}, Defeated: {enemies_defeated})")

if __name__ == '__main__':
    main()
