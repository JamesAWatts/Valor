#!/usr/bin/env python
import sys
import os

# Clear modules completely
for mod in list(sys.modules.keys()):
    if 'players' in mod or 'combat' in mod:
        del sys.modules[mod]

sys.path.insert(0, os.path.dirname(__file__))

from players.player import apply_monk_rules

def test():
    monk_profile = {
        'class': 'monk',
        'weapon': 'unarmed',
        'armor': 10,
        'armor_name': 'unarmored',
        'proficiency': 1,
        'attack_count': 2,
        'level': 1,
    }
    
    print(f"Before: attack_count={monk_profile['attack_count']}")
    print(f"  class={monk_profile.get('class')}, weapon={monk_profile.get('weapon')}")
    
    # Call the exact same way as comprehensive test
    apply_monk_rules(monk_profile)
    
    print(f"After: attack_count={monk_profile['attack_count']}")
    print(f"  base_attack_count={monk_profile.get('base_attack_count')}")
    
    if monk_profile['attack_count'] == 3:
        print("✓ PASS")
    else:
        print("✗ FAIL")

test()
