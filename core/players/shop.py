import json
import os
from .player import load_weapons, load_armor, load_trinkets, load_shields, apply_weapon_to_player, apply_armor_to_player, apply_trinket_to_player, apply_shield_to_player, load_consumables
from .player_inventory import spend_gold, add_item

def visit_shop(player_data, inventory):
    weapons_data = load_weapons().get('weapon_list', {})
    armor_data = load_armor()
    consumables_data = load_consumables()
    trinkets_data = load_trinkets()
    shields_data = load_shields()

    while True:
        print("\n=== THE DRAGON'S HOARD SHOP ===")
        print(f"Your Gold: {inventory.get('gold', 0)}")
        print("1. Buy Weapons")
        print("2. Buy Armor")
        print("3. Buy Shields")
        print("4. Buy Consumables")
        print("5. Buy Trinkets")
        print("6. Sell Junk (varies by rarity)")
        print("7. Exit Shop")
        
        choice = input("What would you like to do? ").strip()

        if choice == '1':
            buy_items(player_data, inventory, weapons_data, 'weapon')
        elif choice == '2':
            buy_items(player_data, inventory, armor_data, 'armor')
        elif choice == '3':
            buy_items(player_data, inventory, shields_data, 'shield')
        elif choice == '4':
            buy_items(player_data, inventory, consumables_data, 'consumable')
        elif choice == '5':
            buy_items(player_data, inventory, trinkets_data, 'trinket')
        elif choice == '6':
            sell_junk(inventory)
        elif choice == '7' or choice.lower() == 'exit':
            break
        else:
            print("Invalid choice.")

def buy_items(player_data, inventory, item_list, item_type):
    # Only show items where in_shop is True (defaults to True if not present)
    available = {k: v for k, v in item_list.items() if v.get('cost', 0) > 0 and v.get('in_shop', True)}
    
    if item_type == 'armor':
        from .player import can_equip_armor
        available = {k: v for k, v in available.items() if can_equip_armor(player_data, k)}
        # none > light > medium > heavy > robe
        type_order = {'none': 0, 'light': 1, 'medium': 2, 'heavy': 3, 'robe': 4}
        names = sorted(available.keys(), key=lambda k: (type_order.get(available[k].get('type', 'none'), 99), available[k].get('cost', 0)))
    elif item_type == 'weapon':
        # melee > ranged
        type_order = {'melee': 0, 'ranged': 1}
        names = sorted(available.keys(), key=lambda k: (type_order.get(available[k].get('type', 'melee'), 99), available[k].get('cost', 0)))
    else:
        names = sorted(available.keys(), key=lambda k: available[k].get('cost', 0))

    print(f"\n--- Available {item_type.title()} ---")
    for i, name in enumerate(names, 1):
        item = available[name]
        cost = item['cost']
        if item_type == 'weapon':
            stats = f"(d{item['die']}, {item.get('on_hit_effect', 'no effect')})"
        elif item_type == 'armor':
            stats = f"(AC {item['ac']})"
        elif item_type == 'shield':
            stats = f"(AC +{item['ac']})"
        else:
            stats = f"({item.get('description', '')})"
            
        display_name = item.get('name', name.replace('_', ' ')).title()
        print(f"{i}. {display_name}: {cost} gold {stats}")
    print(f"{len(names) + 1}. Back")

    choice = input(f"Select a {item_type} to buy: ").strip()
    if not choice.isdigit():
        return
    
    idx = int(choice) - 1
    if idx == len(names):
        return
    
    if 0 <= idx < len(names):
        item_key = names[idx]
        item = available[item_key]
        cost = item['cost']
        item_name = item.get('name', item_key.replace('_', ' '))
        
        # You can own multiple consumables
        if item_type != 'consumable' and item_key in inventory.get(item_type, {}):
            print(f"You already own a {item_name}!")
            return

        if spend_gold(inventory, cost, player_profile=player_data):
            # 1. Add to inventory
            add_item(inventory, item_key, item_type)
            print(f"Successfully bought {item_name}!")
            
            # 2. Optionally equip
            if item_type in ['weapon', 'armor', 'trinket', 'shield']:
                confirm = input(f"Equip {item_name} now? (y/n): ").strip().lower()
                if confirm in ('y', 'yes'):
                    from .player_inventory import remove_item
                    
                    if item_type == 'weapon':
                        # Swap
                        old = player_data.get('weapon', 'unarmed')
                        if old and old != 'unarmed': add_item(inventory, old, 'weapon')
                        remove_item(inventory, item_key, 'weapon')
                        
                        player_data['weapon'] = item_key
                        apply_weapon_to_player(player_data)
                    elif item_type == 'armor':
                        from .player import can_equip_armor
                        if can_equip_armor(player_data, item_key):
                            # Swap
                            old = player_data.get('armor', 'unarmored')
                            if old and old != 'unarmored': add_item(inventory, old, 'armor')
                            remove_item(inventory, item_key, 'armor')
                            
                            player_data['armor'] = item_key
                            apply_armor_to_player(player_data)
                        else:
                            print(f"You are not proficient with {item_name}! It has been added to your inventory.")
                            return
                    elif item_type == 'trinket':
                        # Swap
                        old = player_data.get('trinket', 'none')
                        if old and old != 'none': add_item(inventory, old, 'trinket')
                        remove_item(inventory, item_key, 'trinket')
                        
                        player_data['trinket'] = item_key
                        apply_trinket_to_player(player_data)
                    elif item_type == 'shield':
                        # Swap
                        old = player_data.get('shield', 'none')
                        if old and old != 'none': add_item(inventory, old, 'shield')
                        remove_item(inventory, item_key, 'shield')
                        
                        player_data['shield'] = item_key
                        apply_shield_to_player(player_data)
                    print(f"Equipped {item_name}.")
        else:
            print("You don't have enough gold!")

def sell_junk(inventory):
    junk_category = inventory.get('junk', {})
    if not junk_category:
        print("You have no junk to sell.")
        return
    
    print("=== SELL_JUNK DEBUG START ===")
    print(f"Junk category: {junk_category}")
    
    from core.game_rules.path_utils import get_resource_path
    import json
    
    junk_data = {}
    try:
        junk_file = get_resource_path(os.path.join('data', 'items', 'junk.json'))
        print(f"Looking for junk file at: {junk_file}")
        print(f"File exists: {os.path.exists(junk_file)}")
        with open(junk_file, 'r') as f:
            junk_data = json.load(f)
        print(f"Successfully loaded junk data with keys: {list(junk_data.keys())}")
    except Exception as e:
        print(f"ERROR: Could not load junk data: {e}")
        print("This is why items are selling for 1 gold!")

    print(f"DEBUG: junk_category = {junk_category}")
    print(f"DEBUG: junk_data keys = {list(junk_data.keys())}")
    
    total_gold = 0
    for item_name, count in junk_category.items():
        val = junk_data.get('junk_list', {}).get(item_name, {}).get('cost', 1)
        print(f"DEBUG: Looking up '{item_name}' in junk_list...")
        print(f"DEBUG: Found cost: {val} (default was 1)")
        print(f"DEBUG: {item_name} x{count} = {val} gold each")
        total_gold += val * count

    inventory['gold'] += total_gold
    inventory['junk'] = {}
    print(f"=== SELL_JUNK DEBUG END: Sold for {total_gold} gold ===")
    print(f"Sold all junk for {total_gold} gold.")
