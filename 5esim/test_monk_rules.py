#!/usr/bin/env python
"""Test script to verify apply_monk_rules is working correctly"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules

# Simulate a monk player profile
def test_apply_monk_rules():
    print("Testing apply_monk_rules()...\n")
    
    # Test 1: Initial monk with unarmed weapon
    monk_profile = {
        'class': 'monk',
        'weapon': 'unarmed',
        'armor': 10,  # Already converted by apply_armor_to_player
        'armor_name': 'unarmored',
        'proficiency': 1,
        'attack_count': 2,  # From player_classes.json
        'level': 1,
    }
    
    print(f"Before apply_monk_rules: attack_count = {monk_profile['attack_count']}")
    apply_monk_rules(monk_profile)
    print(f"After apply_monk_rules:  attack_count = {monk_profile['attack_count']}")
    
    expected_attack_count = 3  # 2 + 1
    actual_attack_count = monk_profile['attack_count']
    
    if actual_attack_count == expected_attack_count:
        print(f"✓ PASS: attack_count correctly increased to {actual_attack_count}\n")
    else:
        print(f"✗ FAIL: Expected {expected_attack_count}, got {actual_attack_count}\n")
    
    # Test 2: Apply monk rules multiple times (should stay at 3, not keep incrementing)
    print("Testing idempotency (calling apply_monk_rules again)...")
    initial_count = monk_profile['attack_count']
    apply_monk_rules(monk_profile)
    print(f"After 2nd apply_monk_rules: attack_count = {monk_profile['attack_count']}")
    
    if monk_profile['attack_count'] == 3:
        print(f"✓ PASS: attack_count remains at 3 (idempotent)\n")
    else:
        print(f"✗ FAIL: attack_count changed to {monk_profile['attack_count']}, expected 3\n")
    
    # Test 3: Level up and reapply
    print("Testing after level up...")
    monk_profile['level'] = 5
    apply_monk_rules(monk_profile)
    print(f"After level 5, apply_monk_rules: attack_count = {monk_profile['attack_count']}")
    print(f"After level 5, apply_monk_rules: damage_die = {monk_profile.get('damage_die', 'N/A')}")
    
    # At level 5, the damage die should be scaled
    # base_die = 4, scale_count = (5-1)//4 = 1
    # scaled_die = 4 + (2*1) = 6
    expected_die = 6
    actual_die = monk_profile.get('damage_die', 0)
    
    if actual_die == expected_die:
        print(f"✓ PASS: damage_die correctly scaled to d{actual_die}\n")
    else:
        print(f"✗ FAIL: Expected d{expected_die}, got d{actual_die}\n")

if __name__ == '__main__':
    test_apply_monk_rules()
