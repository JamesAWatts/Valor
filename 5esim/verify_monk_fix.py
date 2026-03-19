#!/usr/bin/env python
"""Final verification that monk rules are fixed"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules, apply_armor_to_player, apply_weapon_to_player
from players.leveler import load_levels, update_xp_and_level
import json

# Load monk class
with open(os.path.join(os.path.dirname(__file__), 'players', 'player_classes.json')) as f:
    classes = json.load(f)

monk_data = classes['monk'].copy()
monk_data['class'] = 'monk'
monk_data.setdefault('level', 1)
monk_data.setdefault('xp', 0)
monk_data.setdefault('base_hp', monk_data.get('hp', 0))

print("=" * 60)
print("MONK RULES VERIFICATION TEST")
print("=" * 60)
print()

# Initial setup
print(f"Initial attack_count from player_classes.json: {monk_data['attack_count']}")
apply_weapon_to_player(monk_data)
apply_armor_to_player(monk_data)
apply_monk_rules(monk_data)
print(f"After initial apply_monk_rules: attack_count = {monk_data['attack_count']}")
print()

# Simulate multiple combats
print("Simulating 3 combats without leveling up:")
for i in range(1, 4):
    apply_monk_rules(monk_data)
    result = "PASS" if monk_data['attack_count'] == 3 else "FAIL"
    print(f"  Combat {i}: attack_count = {monk_data['attack_count']} [{result}]")

print()

# Level up
print(f"Leveling up from level {monk_data['level']}...")
level_data = load_levels()
update_xp_and_level(monk_data, 300, level_data, base_hp=monk_data['base_hp'])
print(f"After leveling: level = {monk_data['level']}, attack_count = {monk_data['attack_count']}")
result = "PASS" if monk_data['attack_count'] == 3 else "FAIL"
print(f"  Attack count after level up: [{result}]")
print()

# Continue combats after level up
print("Continuing combats after level up:")
for i in range(4, 7):
    apply_monk_rules(monk_data)
    result = "PASS" if monk_data['attack_count'] == 3 else "FAIL"
    print(f"  Combat {i}: attack_count = {monk_data['attack_count']} [{result}]")

print()
print("=" * 60)
if all(monk_data['attack_count'] == 3 for _ in range(1)):
    print("✓ VERIFICATION COMPLETE - Monk rules are working correctly!")
else:
    print(f"✗ VERIFICATION FAILED - attack_count = {monk_data['attack_count']}")
print("=" * 60)
