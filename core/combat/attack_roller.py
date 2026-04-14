import random
import re


def roll_dice(dice_str):
    """
    Parses a dice string like '1d8', '3d6+4', '2d10-2' and returns the result.
    If parsing fails, returns 0.
    """
    if not dice_str:
        return 0
    
    # Clean string and match pattern
    s = dice_str.lower().replace(" ", "")
    match = re.match(r"(\d+)d(\d+)([+-]\d+)?", s)
    
    if not match:
        # Check if it's just a number
        if s.isdigit():
            return int(s)
        return 0
        
    num, sides, bonus = match.groups()
    num = int(num)
    sides = int(sides)
    
    total = sum(random.randint(1, sides) for _ in range(num))
    
    if bonus:
        total += int(bonus)
        
    return total


def roll_d20(advantage=0):
    """Roll d20. advantage=1: advantage, -1: disadvantage, 0: normal."""
    rolls = [random.randint(1, 20) for _ in range(2 if advantage != 0 else 1)]
    if advantage > 0:
        return max(rolls), rolls
    if advantage < 0:
        return min(rolls), rolls
    return rolls[0], rolls


def attack_roll(attack_bonus, enemy_ac, crit_range=(20,), advantage=0):
    attack_value, rolls = roll_d20(advantage)
    hit = False
    is_critical = attack_value in crit_range

    if attack_value == 1:
        # automatic miss
        hit = False
    elif is_critical:
        hit = True
    elif attack_value + attack_bonus >= enemy_ac:
        hit = True

    return {
        'roll': attack_value,
        'raw_rolls': rolls,
        'total': attack_value + attack_bonus,
        'hit': hit,
        'critical': is_critical,
        'enemy_ac': enemy_ac,
    }


def damage_roll(damage_die, attack_bonus, critical=False, player_data=None):
    """
    Calculate damage based on player class and stats.
    Returns (damage_amount, dice_string).
    """
    player_class = player_data.get('class', '') if player_data else ''
    eq_bonus = int(player_data.get('equipment_dmg_bonus', 0)) if player_data else 0
    total_bonus = attack_bonus + eq_bonus

    if player_class in ('sorcerer', 'wizard', 'druid', 'alchemist'):
        cantrip_dice_rolled = player_data.get('cantrip_dice_rolled', 1)
        dice_str = f"{cantrip_dice_rolled}d{damage_die}"
        if total_bonus != 0:
            dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
        
        base = sum(random.randint(1, damage_die) for _ in range(cantrip_dice_rolled)) + total_bonus
        if critical:
            dice_str += f" + 1d{damage_die} (CRIT)"
            return base + random.randint(1, damage_die), dice_str
        return base, dice_str

    else:
        dice_str = f"1d{damage_die}"
        if total_bonus != 0:
            dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
            
        base = random.randint(1, damage_die) + total_bonus
        if critical:
            dice_str += f" + 1d{damage_die} (CRIT)"
            return base + random.randint(1, damage_die), dice_str
        return base, dice_str


def combat_round(enemy_ac, attack_count, damage_die, attack_bonus, crit_on_19=False):     
    crit_range = (19, 20) if crit_on_19 else (20,)
    total_damage = 0
    results = []

    for i in range(attack_count):
        print(f"Attack {i+1}:")
        result = attack_roll(attack_bonus, enemy_ac, crit_range)
        if result['hit']:
            # damage_roll now returns (damage, dice_str)
            dmg, _ = damage_roll(damage_die, attack_bonus, critical=result['critical'])      
            total_damage += dmg
            status = 'CRITICAL HIT' if result['critical'] else 'HIT'
            print(f"  {status}! d20={result['roll']} (total {result['total']}), damage={dmg}")
        else:
            print(f"  MISS. d20={result['roll']} (total {result['total']})")
        results.append(result)

    print(f"Total damage this round: {total_damage}\n")
    return total_damage, results


def main():
    enemy_ac = int(input('Enter enemy armor class: '))
    attack_count = int(input('How many attacks this turn? '))
    damage_die = int(input('Damage die (4/6/8/10/12): '))
    proficiency = int(input('Proficiency bonus: '))
    weapon_mod = int(input('Weapon attack/damage modifier: '))
    attack_bonus = proficiency + weapon_mod
    crit_on_19 = input('Can crit on 19 (y/n)? ').strip().lower() in ('y', 'yes')

    print(f"Attack bonus: +{attack_bonus}\n")

    total_damage, _ = combat_round(enemy_ac, attack_count, damage_die, attack_bonus, crit_on_19)
    print(f"Final result: you dealt {total_damage} points of damage.")


if __name__ == '__main__':
    main()
