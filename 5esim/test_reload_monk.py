#!/usr/bin/env python
"""Re-import and test to rule out caching"""
import sys
import os

# Clear any cached modules
if 'players.player' in sys.modules:
    del sys.modules['players.player']
if 'players.leveler' in sys.modules:
    del sys.modules['players.leveler']

sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules

# Test directly
monk_profile = {
    'class': 'monk',
    'weapon': 'unarmed',
    'armor': 10,
    'armor_name': 'unarmored',
    'proficiency': 1,
    'attack_count': 2,
    'level': 1,
}

print("TEST 1 - Direct call:")
print(f"  Before:  attack_count={monk_profile['attack_count']}, base_attack_count={monk_profile.get('base_attack_count')}")

# Debug the function logic
print(f"  weapon='{monk_profile.get('weapon')}'")
print(f"  weapon.lower()='{monk_profile.get('weapon', '').lower()}'")
weapon = monk_profile.get('weapon', '').lower()
print(f"  weapon in ('unarmed') = {weapon in ('unarmed')}")
print(f"  weapon in ('unarmed',) = {weapon in ('unarmed',)}")

result = apply_monk_rules(monk_profile)
print(f"  After:   attack_count={monk_profile['attack_count']}, base_attack_count={monk_profile.get('base_attack_count')}")
print()

# Now test the same thing from the comprehensive test setup
print("TEST 2 - Trying to replicate comprehensive test exactly:")
monk_profile2 = {
    'class': 'monk',
    'weapon': 'unarmed',
    'armor': 10,
    'armor_name': 'unarmored',
    'proficiency': 1,
    'attack_count': 2,  # From player_classes.json
    'level': 1,
    'xp': 0,
    'hp': 9,
    'base_hp': 9,
}

print(f"  Profile: {monk_profile2}")
print(f"  Before:  attack_count={monk_profile2['attack_count']}")

apply_monk_rules(monk_profile2)
print(f"  After:   attack_count={monk_profile2['attack_count']}")
print(f"  base_attack_count={monk_profile2.get('base_attack_count')}")
