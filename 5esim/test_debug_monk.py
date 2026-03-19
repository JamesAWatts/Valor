#!/usr/bin/env python
"""Debug test to understand monk rules flow"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules

# Test the exact function behavior
monk_profile = {
    'class': 'monk',
    'weapon': 'unarmed',
    'armor': 10,
    'armor_name': 'unarmored',
    'proficiency': 1,
    'attack_count': 2,
    'level': 1,
}

print("Testing apply_monk_rules directly:")
print(f"Input: {monk_profile}")
print()

print(f"Before: attack_count = {monk_profile.get('attack_count')}")
print(f"Before: base_attack_count = {monk_profile.get('base_attack_count')}")
print(f"Before: class = {monk_profile.get('class')}")
print(f"Before: weapon = {monk_profile.get('weapon')}")
print()

result = apply_monk_rules(monk_profile)

print(f"After: attack_count = {result.get('attack_count')}")
print(f"After: base_attack_count = {result.get('base_attack_count')}")
print()
print(f"Full result: {result}")
