#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules, apply_armor_to_player, apply_weapon_to_player
import json

with open(os.path.join(os.path.dirname(__file__), 'players', 'player_classes.json')) as f:
    classes = json.load(f)

monk_data = classes['monk'].copy()
monk_data['class'] = 'monk'

print("Initial state:")
print(f"  weapon: {monk_data.get('weapon')}")
print(f"  attack_count: {monk_data.get('attack_count')}")
print()

print("After apply_weapon_to_player:")
apply_weapon_to_player(monk_data)
print(f"  weapon: {monk_data.get('weapon')}")
print(f"  attack_count: {monk_data.get('attack_count')}")
print()

print("After apply_armor_to_player:")
apply_armor_to_player(monk_data)
print(f"  armor_name: {monk_data.get('armor_name')}")
print(f"  attack_count: {monk_data.get('attack_count')}")
print()

print("About to call apply_monk_rules with:")
print(f"  class: {monk_data.get('class')}")
print(f"  weapon: {monk_data.get('weapon')}")
print(f"  armor_name: {monk_data.get('armor_name')}")
print(f"  attack_count BEFORE: {monk_data.get('attack_count')}")
print()

apply_monk_rules(monk_data)

print("After apply_monk_rules:")
print(f"  attack_count AFTER: {monk_data.get('attack_count')}")
print(f"  base_attack_count: {monk_data.get('base_attack_count')}")
