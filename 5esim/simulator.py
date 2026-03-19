import json
import os
import random

from players.player import choose_player_class, classes as player_classes, apply_weapon_to_player, apply_armor_to_player, apply_monk_rules
from players.player_inventory import create_inventory, award_loot
from players.leveler import load_levels, update_xp_and_level, xp_to_next_level
from combat.attack_roller import attack_roll, damage_roll


def load_enemy_data():
    # enemies JSON in creatures folder
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, 'creatures', 'enemies.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def choose_enemy(enemy_data, player_level=1):
    # choose an enemy at random constrained by player level
    enemy_names = list(enemy_data.keys())

    if player_level <= 4:
        max_index = min(4, len(enemy_names) - 1)
    elif player_level <= 10:
        max_index = min(10, len(enemy_names) - 1)
    else:
        max_index = len(enemy_names) - 1

    if max_index < 0:
        raise ValueError('Enemy data is empty')

    selected_names = enemy_names[0:max_index + 1]
    enemy_name = random.choice(selected_names)

    print(f"You encountered {enemy_name.title()}!")
    input('Press Enter to Roll initiative!\n')
    return enemy_name, enemy_data[enemy_name]



def simulate_combat(player_data, enemy_data, player_goes_first=True):
    # copy dicts so we don't mutate original
    player = player_data.copy()
    enemy = enemy_data.copy()

    player_hp = int(player.get('hp', 1))
    enemy_hp = int(enemy.get('hp', 1))

    player_attack_count = int(player.get('attack_count', 1))
    enemy_attack_count = int(enemy.get('attack_count', 1))

    player_die = int(player.get('die', 8))
    player_bonus = int(player.get('bonus', 0))
    player_armor = int(player.get('armor', 10))

    enemy_die = int(enemy.get('die', 6))
    enemy_bonus = int(enemy.get('bonus', 0))
    enemy_armor = int(enemy.get('armor', 10))

    turn = 1
    print(f"Combat start: player hp={player_hp}, enemy hp={enemy_hp}\n")

    while player_hp > 0 and enemy_hp > 0:
        print(f"--- Turn {turn} ---")

        def player_phase():
            nonlocal enemy_hp
            total_damage = 0
            for _ in range(player_attack_count):
                attack = attack_roll(player_bonus, enemy_armor)
                if attack['hit']:
                    dmg = damage_roll(player_die, player_bonus, attack['critical'])
                    total_damage += dmg
                    print(f"Player hits for {dmg} (roll {attack['roll']})")
                else:
                    print(f"Player misses (roll {attack['roll']})")
            enemy_hp -= total_damage
            enemy_hp = max(enemy_hp, 0)
            print(f"Total player damage this turn: {total_damage}. Enemy HP now {enemy_hp}")

        def enemy_phase():
            nonlocal player_hp
            total_damage = 0
            for _ in range(enemy_attack_count):
                attack = attack_roll(enemy_bonus, player_armor)
                if attack['hit']:
                    dmg = damage_roll(enemy_die, enemy_bonus, attack['critical'])
                    total_damage += dmg
                    print(f"Enemy hits for {dmg} (roll {attack['roll']})")
                else:
                    print(f"Enemy misses (roll {attack['roll']})")
            player_hp -= total_damage
            player_hp = max(player_hp, 0)
            print(f"Total enemy damage this turn: {total_damage}. Player HP now {player_hp}\n")

        if player_goes_first:
            player_phase()
            if enemy_hp <= 0:
                print('Enemy defeated!')
                break
            input('Press Enter to continue to the enemy turn...\n')

            enemy_phase()
            if player_hp <= 0:
                print('Player has been defeated!')
                break

        else:
            enemy_phase()
            if player_hp <= 0:
                print('Player has been defeated!')
                break
            input('Press Enter to continue to the player turn...\n')

            player_phase()
            if enemy_hp <= 0:
                print('Enemy defeated!')
                break

        input('Press Enter to continue to the next turn...\n')
        turn += 1

    winner = 'player' if player_hp > 0 else 'enemy'
    print(f"Combat ends: {winner} wins")
    return {
        'winner': winner,
        'player_hp': player_hp,
        'enemy_hp': enemy_hp,
        'turns': turn,
    }


def main():
    enemy_data = load_enemy_data()

    player_name, player_profile = choose_player_class(player_classes)
    player_profile.setdefault('xp', 0)
    player_profile.setdefault('level', 1)
    player_profile.setdefault('base_hp', player_profile.get('hp', 0))

    # ensure weapon stats are in place
    apply_weapon_to_player(player_profile)
    apply_armor_to_player(player_profile)
    apply_monk_rules(player_profile)

    # inventory starts with player's weapon and zero gold
    player_inventory = create_inventory(player_profile)

    level_data = load_levels()

    print(f"Player chosen: {player_name.title()} with {player_profile['hp']} HP.")

    continue_fighting = True
    enemies_defeated = 0

    while continue_fighting and player_profile['hp'] > 0:
        enemy_name, enemy_profile = choose_enemy(enemy_data, player_profile.get('level', 1))
        print(f"Starting fight against {enemy_name.title()}...")

        # Reapply monk rules before each combat to ensure they're in effect
        apply_monk_rules(player_profile)

        # initiative
        player_init_roll = random.randint(1, 20) + player_profile.get('proficiency_bonus', 0)
        enemy_init_roll = random.randint(1, 20) + enemy_profile.get('bonus', 0)
        print(f"Player initiative: {player_init_roll} (roll + prof)")
        print(f"Enemy initiative: {enemy_init_roll} (roll + bonus)")

        player_first = player_init_roll >= enemy_init_roll
        if player_first:
            print('Player goes first!')
        else:
            print('Enemy goes first!')

        result = simulate_combat(player_profile, enemy_profile, player_goes_first=player_first)

        if result['winner'] == 'player':
            enemies_defeated += 1
            xp_gain = enemy_profile.get('xp', 0)
            update_xp_and_level(player_profile, xp_gain, level_data, base_hp=player_profile['base_hp'])
            print(f"You gained {xp_gain} XP for defeating {enemy_name}.")

            loot_message = award_loot(player_inventory, enemy_profile.get('reward', {}))
            if loot_message:
                print(loot_message)
            else:
                print('No loot dropped.')

            next_xp = xp_to_next_level(player_profile['xp'], level_data)
            print(f"Total XP: {player_profile['xp']}, Level: {player_profile['level']} (HP: {player_profile['hp']})")
            print(f"Inventory: gold={player_inventory['gold']}, items={player_inventory['items']}, equipped={player_inventory['equipped_weapon']}")
            if next_xp is None:
                print('You have reached max level.')
            else:
                print(f"XP to next level: {next_xp}")

            again = input('Do you want another fight? (y/n): \n').strip().lower()
            if again not in ('y', 'yes'):
                continue_fighting = False

        else:
            print('You were defeated and cannot continue.')
            total_score = player_profile.get('xp', 0) + enemies_defeated
            print(f"Total score: XP {player_profile.get('xp', 0)} + enemies defeated {enemies_defeated} = {total_score}")
            break

    print('\nFinal player state:')
    print(player_profile)
    print('Final inventory:')
    print(player_inventory)


if __name__ == '__main__':
    main()
