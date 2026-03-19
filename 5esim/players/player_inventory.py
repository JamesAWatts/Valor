import random


def create_inventory(selected_player):
    """Initialize player inventory using chosen class weapon."""
    starting_weapon = selected_player.get('weapon', 'unarmed')
    inventory = {
        'gold': 0,
        'items': [],
        'equipped_weapon': starting_weapon,
    }

    if starting_weapon and starting_weapon not in inventory['items']:
        inventory['items'].append(starting_weapon)

    return inventory


def add_gold(inventory, amount):
    inventory['gold'] = inventory.get('gold', 0) + int(amount)
    return inventory['gold']


def add_item(inventory, item_name):
    if not item_name:
        return None
    items = inventory.setdefault('items', [])
    if item_name not in items:
        items.append(item_name)
    return item_name


def choose_loot(enemy_reward):
    """Randomly choose gold or an item from enemy reward."""
    if not enemy_reward:
        return None

    gold = enemy_reward.get('gold', 0)
    items = enemy_reward.get('items', [])
    if isinstance(items, str):
        items = [items]

    possibilities = []
    if gold > 0:
        possibilities.append('gold')
    if items:
        possibilities.append('item')

    if not possibilities:
        return None

    choice = random.choice(possibilities)

    if choice == 'gold':
        return {'type': 'gold', 'amount': gold}

    dropped_item = random.choice(items)
    return {'type': 'item', 'name': dropped_item}


def award_loot(inventory, enemy_reward):
    """Process one loot drop and update inventory."""
    drop = choose_loot(enemy_reward)
    if not drop:
        return None

    if drop['type'] == 'gold':
        add_gold(inventory, drop['amount'])
        return f"Loot: +{drop['amount']} gold. Total gold now {inventory['gold']}"

    if drop['type'] == 'item':
        add_item(inventory, drop['name'])
        return f"Loot: {drop['name']} added to inventory. Items now: {inventory['items']}"

    return None
