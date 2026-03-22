import json

filepath = r"D:\GitHub\python_games\5esim\players\player_classes.json"

with open(filepath, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# Define spell progressions
spells_map = {
    "sorcerer": {
        "1": ["magic_missile"],
        "3": ["scorching_ray"],
        "5": ["lightning_bolt"],
        "7": ["wall_of_fire"],
        "9": ["cone_of_cold"],
        "11": ["disintegrate"],
        "13": ["finger_of_death"],
        "15": ["sunburst"],
        "17": ["power_word_kill"]
    },
    "wizard": {
        "1": ["magic_missile"],
        "3": ["hold_person"],
        "5": ["fireball"],
        "7": ["blight"],
        "9": ["hold_monster"],
        "11": ["chain_lightning"],
        "13": ["prismatic_spray"],
        "15": ["power_word_stun"],
        "17": ["meteor_swarm"]
    },
    "druid": {
        "1": ["cure_wounds"],
        "3": ["hold_person"],
        "5": ["haste"],
        "7": ["wall_of_fire"],
        "9": ["hold_monster"],
        "11": ["sunburst"],
        "13": ["finger_of_death"],
        "15": ["power_word_stun"],
        "17": ["meteor_swarm"]
    },
    "alchemist": {
        "1": ["cure_wounds"],
        "3": ["scorching_ray"],
        "5": ["haste"],
        "7": ["blight"],
        "9": ["cone_of_cold"],
        "11": ["disintegrate"],
        "13": ["prismatic_spray"],
        "15": ["sunburst"],
        "17": ["meteor_swarm"]
    }
}

for cls, prog in spells_map.items():
    if cls in data:
        # Ensure base spell list exists
        if "spells" not in data[cls]:
            data[cls]["spells"] = []
            
        levels = data[cls]["levels"]
        
        for lvl, new_spells in prog.items():
            if lvl in levels:
                levels[lvl]["spells"] = new_spells
            else:
                levels[lvl] = {"spells": new_spells}

with open(filepath, 'w', encoding='utf-8-sig') as f:
    json.dump(data, f, indent=4)
