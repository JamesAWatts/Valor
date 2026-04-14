
UPGRADE_COSTS = {
    1: 250,
    2: 500,
    3: 1000
}

ENCHANTMENTS = {
    "lifesteal": {
        "cost": 300,
        "description": "Heal for 50% of damage dealt."
    },
    "critical": {
        "cost": 400,
        "description": "Increases critical hit range (19-20)."
    },
    "extra_critical": {
        "cost": 800,
        "description": "Massively increases critical hit range (18-20)."
    },
    "focusing_lens": {
        "cost": 500,
        "description": "Improves Spell Save DC by 1."
    },
    "silence": {
        "cost": 600,
        "description": "On hit: DC 12 save or enemy cannot cast spells."
    },
    "fire": {
        "cost": 250,
        "description": "Adds 1d4 fire damage to attacks."
    },
    "frost": {
        "cost": 250,
        "description": "Slows enemy on hit."
    }
}

def get_weapon_upgrade_info(player, weapon_name):
    upgrades = player.get('weapon_upgrades', {})
    info = upgrades.get(weapon_name, {'level': 0, 'enchantment': None})
    return info

def can_upgrade(player, weapon_name):
    info = get_weapon_upgrade_info(player, weapon_name)
    current_level = info['level']
    if current_level >= 3:
        return False, "Max level reached."
    
    next_level = current_level + 1
    cost = UPGRADE_COSTS[next_level]
    
    inventory = player.get('inventory_ref', {})
    if inventory.get('gold', 0) < cost:
        return False, f"Not enough gold ({cost}g required)."
    
    return True, cost

def upgrade_weapon(player, weapon_name):
    allowed, result = can_upgrade(player, weapon_name)
    if not allowed:
        return False, result
    
    cost = result
    inventory = player.get('inventory_ref', {})
    inventory['gold'] -= cost
    
    upgrades = player.setdefault('weapon_upgrades', {})
    info = upgrades.setdefault(weapon_name, {'level': 0, 'enchantment': None})
    info['level'] += 1
    
    # Re-apply stats if it's the equipped weapon
    if player.get('weapon') == weapon_name:
        from core.players.player import apply_weapon_to_player
        apply_weapon_to_player(player)
        
    from core.players.player import get_weapon_display_name
    display_name = get_weapon_display_name(player, weapon_name)
    return True, f"Upgraded weapon to {display_name}!"

def can_enchant(player, weapon_name, enchantment_key):
    if enchantment_key not in ENCHANTMENTS:
        return False, "Invalid enchantment."
    
    cost = ENCHANTMENTS[enchantment_key]['cost']
    inventory = player.get('inventory_ref', {})
    if inventory.get('gold', 0) < cost:
        return False, f"Not enough gold ({cost}g required)."
    
    return True, cost

def enchant_weapon(player, weapon_name, enchantment_key):
    allowed, result = can_enchant(player, weapon_name, enchantment_key)
    if not allowed:
        return False, result
    
    cost = result
    inventory = player.get('inventory_ref', {})
    inventory['gold'] -= cost
    
    upgrades = player.setdefault('weapon_upgrades', {})
    info = upgrades.setdefault(weapon_name, {'level': 0, 'enchantment': None})
    info['enchantment'] = enchantment_key
    
    # Re-apply stats if it's the equipped weapon
    if player.get('weapon') == weapon_name:
        from core.players.player import apply_weapon_to_player
        apply_weapon_to_player(player)
        
    from core.players.player import get_weapon_display_name
    display_name = get_weapon_display_name(player, weapon_name)
    return True, f"Enchanted weapon to {display_name}!"
