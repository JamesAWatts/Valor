#!/usr/bin/env python
"""Comprehensive test for monk rules through leveling"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules
from players.leveler import load_levels, update_xp_and_level

# Simulate a monk player profile from class data
def test_monk_multiple_combats():
    print("Testing monk attack_count consistency through multiple combats and level ups\n")
    
    # Simulate monk profile after initial setup
    monk_profile = {
        'class': 'monk',
        'weapon': 'unarmored',
        'armor': 10,
        'armor_name': 'unarmored',
        'proficiency': 1,
        'attack_count': 2,  # From player_classes.json
        'level': 1,
        'xp': 0,
        'hp': 9,
        'base_hp': 9,
    }
    
    level_data = load_levels()
    
    print(f"Initial state (level 1): attack_count = {monk_profile['attack_count']}")
    print(f"  class: {monk_profile.get('class')}, weapon: {monk_profile.get('weapon')}")
    print(f"  Calling apply_monk_rules...")
    apply_monk_rules(monk_profile)
    print(f"After apply_monk_rules: attack_count = {monk_profile['attack_count']}")
    print(f"  base_attack_count: {monk_profile.get('base_attack_count')}")
    print()
    
    test_results = []
    
    # Simulate multiple combats with no level up
    print("Combat 1 (no level up):")
    apply_monk_rules(monk_profile)
    result = "PASS" if monk_profile['attack_count'] == 3 else "FAIL"
    test_results.append(("Combat 1", result))
    print(f"  attack_count = {monk_profile['attack_count']} [{result}]\n")
    
    print("Combat 2 (no level up):")
    apply_monk_rules(monk_profile)
    result = "PASS" if monk_profile['attack_count'] == 3 else "FAIL"
    test_results.append(("Combat 2", result))
    print(f"  attack_count = {monk_profile['attack_count']} [{result}]\n")
    
    # Simulate gaining XP and leveling up
    print("Gaining 30 XP (leveling up to level 2):")
    print(f"  Before update_xp_and_level: level={monk_profile['level']}, attack_count={monk_profile['attack_count']}")
    update_xp_and_level(monk_profile, 30, level_data, base_hp=monk_profile['base_hp'])
    print(f"  After update_xp_and_level: level={monk_profile['level']}, attack_count={monk_profile['attack_count']}")
    print(f"  base_attack_count: {monk_profile.get('base_attack_count')}")
    result = "PASS" if monk_profile['attack_count'] == 3 else "FAIL"
    test_results.append(("After level up to 2", result))
    print(f"  [{result}]\n")
    
    # Combat after level up
    print("Combat 3 (after level up):")
    apply_monk_rules(monk_profile)
    result = "PASS" if monk_profile['attack_count'] == 3 else "FAIL"
    test_results.append(("Combat 3", result))
    print(f"  attack_count = {monk_profile['attack_count']} [{result}]\n")
    
    # Level up to level 4 (should change damage die)
    print("Gaining 60 XP (leveling up to level 4):")
    update_xp_and_level(monk_profile, 60, level_data, base_hp=monk_profile['base_hp'])
    print(f"  Level: {monk_profile['level']}")
    print(f"  attack_count = {monk_profile['attack_count']}")
    print(f"  damage_die = {monk_profile.get('damage_die', 'N/A')}")
    result = "PASS" if monk_profile['attack_count'] == 3 else "FAIL"
    test_results.append(("After level up to 4", result))
    print(f"  [{result}]\n")
    
    # Combat after reaching level 4
    print("Combat 4 (after damage die scaling):")
    apply_monk_rules(monk_profile)
    result = "PASS" if monk_profile['attack_count'] == 3 else "FAIL"
    test_results.append(("Combat 4", result))
    print(f"  attack_count = {monk_profile['attack_count']} [{result}]\n")
    
    # Summary
    print("=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    all_passed = all(r == "PASS" for _, r in test_results)
    for test_name, result in test_results:
        symbol = "✓" if result == "PASS" else "✗"
        print(f"{symbol} {test_name}: {result}")
    
    print("\n" + ("="*50))
    if all_passed:
        print("✓ ALL TESTS PASSED - Monk rules are consistent!")
    else:
        print("✗ SOME TESTS FAILED - Monk rules are not consistent!")

if __name__ == '__main__':
    test_monk_multiple_combats()
