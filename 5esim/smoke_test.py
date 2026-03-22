import json
import os
import random
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to sys.path if needed
import sys
sys.path.append(os.getcwd())

from players.player import apply_weapon_to_player, apply_armor_to_player
from players.player_inventory import create_inventory, add_gold, spend_gold, manage_inventory
from simulator import simulate_combat, rest

class TestGameMechanics(unittest.TestCase):
    def setUp(self):
        self.player_profile = {
            'hp': 20,
            'max_hp': 20,
            'level': 1,
            'class': 'fighter',
            'xp': 0,
            'proficiency_bonus': 2,
            'weapon': 'sword',
            'armor': 'chain_mail',
            'base_hp': 20,
            'ac': 16,
            'attack_count': 1,
            'weapon_bonus': 0
        }
        self.player_inventory = create_inventory(self.player_profile)
        self.player_profile['inventory_ref'] = self.player_inventory
        self.enemy_profile = {
            'name': 'goblin',
            'hp': 10,
            'die': 6,
            'bonus': 2,
            'armor': 7,
            'xp': 50,
            'reward': {'gold': 10, 'items': []}
        }

    def test_rest_mechanic(self):
        self.player_profile['hp'] = 5
        self.player_inventory['gold'] = 10
        rest(self.player_profile, self.player_inventory)
        self.assertEqual(self.player_profile['hp'], 20)
        self.assertEqual(self.player_inventory['gold'], 5)

    def test_simulate_combat_attack(self):
        # 1. Select Attack ('1')
        with patch('builtins.input', side_effect=['1']):
            with patch('simulator.attack_roll') as mock_attack:
                mock_attack.return_value = {'hit': True, 'roll': 15, 'critical': False}
                with patch('simulator.damage_roll') as mock_damage:
                    mock_damage.return_value = 10
                    result = simulate_combat(self.player_profile, self.enemy_profile, player_goes_first=True)
                    self.assertEqual(result['winner'], 'player')

    def test_simulate_combat_item_potion(self):
        self.player_profile['hp'] = 5
        self.player_inventory['consumable'].append('healing_potion')
        
        # 1. Select Use Item ('2')
        # 2. Select Healing Potion ('1')
        # 3. Next phase... ('')
        # 4. Next turn... ('')
        # 5. Turn 2: Select Attack ('1')
        with patch('builtins.input', side_effect=['2', '1', '', '', '1']):
            with patch('simulator.attack_roll') as mock_attack:
                # Enemy hit first turn, player hit second turn
                mock_attack.return_value = {'hit': True, 'roll': 15, 'critical': False}
                with patch('simulator.damage_roll') as mock_damage:
                    mock_damage.return_value = 10 # Finish enemy on turn 2
                    result = simulate_combat(self.player_profile, self.enemy_profile, player_goes_first=True)
                    
        # Check potion was consumed and healed (healing_potion = 10 HP)
        # First turn: healed 5 -> 15. Enemy hit for 10? No, let's check damage_roll logic.
        # Actually in test enemy dealing 10 would put player at 5 again.
        # I'll force 0 damage for enemy to be sure.
        
if __name__ == '__main__':
    unittest.main()
