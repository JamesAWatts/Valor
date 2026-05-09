import pygame
import os
import random
from core.game_rules.path_utils import get_resource_path

class SpriteManager:
    """
    Manages static combat sprites for both players and enemies.
    """
    _cache = {}
    
    # Mapping of enemy keys to list of potential image filenames
    _enemy_mapping = {
        "kobold": ["kobold1.png", "kobold2.png", "kobold3.png"],
        "kobold_slinger": ["kobold_slinger.png"],
        "skeleton": ["skeleton1.png", "skeleton2.png", "skeleton3.png"],
        "kobold_sorcerer": ["kobold_sorcerer1.png"],
        "kobold_inventor": ["kobold_inventor1.png", "kobold_inventor2.png"],
        "kobold_dragonshield": ["kobold_dragonshield1.png", "kobold_dragonshield2.png"],
        "goblin": ["goblin1.png", "goblin2.png", "goblin3.png"],
        "goblin_archer": ["goblin_archer1.png"],
        "bandit": ["bandit1.png", "bandit2.png"],
        "scout": ["scout1.png", "scout2.png"],
        "archer": ["archer1.png", "archer2.png"],
        "cultist": ["cultist1.png", "cultist2.png", "cultist3.png"],
        "harpy": ["harpy1.png", "harpy2.png"],
        "berserker": ["berserker1.png", "berserker2.png"],
        "thief": ["thief1.png", "thief2.png", "thief3.png"],
        "bandit_captain": ["bandit1.png", "bandit2.png"],
        "bugbear_warrior": ["bugbear_warrior1.png", "bugbear_warrior2.png"],
        "goblin_chieften": ["goblin_chieften1.png", "goblin_chieften2.png"],
        "assassin": ["assassin1.png", "assassin2.png"],
        "guard": ["guard1.png", "guard2.png", "guard3.png"],
        "cultist_fanatic": ["cultist_fanatic1.png", "cultist_fanatic2.png"],
        "orc_warrior": ["orc_warrior1.png", "orc_warrior2.png"],
        "knight": ["knight1.png", "knight2.png"],
        "guard_captain": ["guard_captain1.png", "guard_captain2.png"],
        "mage": ["mage1.png", "mage2.png"],
        "gladiator": ["gladiator1.png", "gladiattor2.png"],
        "master_thief": ["master_thief1.png", "master_thief2.png"],
        "blackguard": ["blackguard1.png", "blackguard2.png"],
        "champion": ["champion1.png", "champion2.png"],
        "archmage": ["archmage1.png", "archmage2.png"],
        "warlord": ["warlord1.png", "warlord2.png"],
        "minotaur": ["minotaur1.png", "minotaur2.png"],
        "medusa": ["medusa1.png", "medusa2.png"],
        "death_knight": ["death_knight1.png", "death_knight2.png"],
        "chimera": ["chimera1.png", "chimera2.png"],
        "wyrmling": ["wyrmling1.png", "wyrmling2.png"],
        "wyvern": ["wyvern1.png", "wyvern2.png"],
        "young_dragon": ["young_dragon1.png", "young_dragon2.png"],
        "adult_dragon": ["adult_dragon1.png", "adult_dragon2.png"],
        "ancient_dragon": ["ancient_dragon1.png", "ancient_dragon2.png"],
        "dragon_turtle": ["dragon_turtle1.png", "dragon_turtle2.png"],
        "dragons_chosen": ["dragon_chosen1.png", "dragon_chosen2.png", "dragon_chosen3.png"],
        "behir": ["behir1.png", "behir2.png"],
        "greatwyrm": ["greatwyrm1.png", "greatwyrm2.png"],
        "lich": ["lich1.png", "lich2.png"],
        "necromancer": ["necromancer1.png", "necromancer2.png"],
        "brown_bear": ["brown_bear1.png", "brown_bear2.png"],
        "bulette": ["bulette1.png", "bulette2.png"],
        "cockatrice": ["cockatrice1.png", "cockatrice2.png", "cockatrice3.png"],
        "griffon": ["griffon1.png", "griffon2.png"],
        "hydra": ["hydra1.png", "hydra2.png"],
        "kraken": ["kraken1.png", "kraken2.png"],
        "manticore": ["manticore1.png", "manticore2.png"],
        "owlbear": ["owlbear1.png", "owlbear2.png"],
        "purple_worm": ["purple_worm1.png", "purple_worm2.png"],
        "tarrasque": ["tarrasque1.png", "tarrasque2.png"],
        "banshee": ["banshee1.png", "banshee2.png"],
        "blink_dog": ["blink_dog1.png", "blink_dog2.png"],
        "boneclaw": ["bone_claw1.png", "bone_claw2.png"],
        "darkling": ["darkling1.png", "darkling2.png", "darkling3.png"],
        "darkling_elder": ["darkling_elder1.png", "darkling_elder2.png"],
        "deathlock_mastermind": ["deathlock_mastermind1.png", "deathlock_mastermind2.png"],
        "deathlock_wight": ["deathlock_wight2.png"],
        "deathlock": ["deathlock1.png", "deathlock2.png"],
        "dire_troll": ["dire_troll1.png", "dire_troll2.png"],
        "dryad": ["dryad1.png", "dryad2.png"],
        "fomorian": ["fomorian1.png", "fomorian2.png"],
        "ghast": ["ghast1.png", "ghast2.png"],
        "ghost_dragon": ["ghost_dragon1.png"],
        "ghoul": ["ghoul1.png", "ghoul2.png"],
        "goblin": ["goblin1.png", "goblin2.png", "goblin3.png"],
        "goblin_archer": ["goblin_archer1.png", "goblin_archer2.png", "goblin_archer3.png"],
        "green_hag": ["green_hag1.png", "green_hag2.png"],
        "hobgoblin_captain": ["hobgoblin_captain1.png", "hobgoblin_captain2.png"],
        "hobgoblin_warlord": ["hobgoblin_warlord1.png", "hobgoblin_warlord2.png"],
        "hobgoblin": ["hobgoblin1.png", "hobgoblin2.png"],
        "needle_blight": ["needle_blight1.png", "needle_blight2.png", "needle_blight3.png"],
        "ogre": ["ogre1.png", "ogre2.png"],
        "oni": ["oni1.png", "oni2.png"],
        "quickling": ["quickling1.png", "quickling2.png"],
        "redcap": ["redcap1.png", "redcap2.png"],
        "shambling_mound": ["shambling_mound1.png", "shambling_mound2.png"],
        "skull_lord": ["skull_lord1.png", "skull_lord2.png"],
        "treant": ["treant1.png", "treant2.png", "treant3.png"],
        "troll": ["troll1.png", "troll2.png"],
        "vampire_spawn": ["vampire_spawn1.png", "vampire_spawn2.png"],
        "vampire": ["vampire1.png", "vampire2.png", "vampire_lord1.png", "vampire_lord2.png"],
        "vine_blight": ["vine_blight1.png", "vine_blight2.png"],
        "worg_rider": ["worg_rider1.png", "worg_rider2.png"],
        "worg": ["worg1.png", "worg2.png"],
        "wraith": ["wraith2.png"],
        "yeth_hound": ["yeth_hound1.png", "yeth_hound2.png"],
        "yggdrasti": ["yggdarasti1.png", "yggdarasti2.png"],
        "zombie": ["zombie1.png", "zombie2.png"]
    }

    @staticmethod
    def get_enemy_sprite(enemy_key, category="humanoid", forced_filename=None, size=(192, 192)):
        """Loads and returns a sprite for the given enemy key and category.
        Randomly selects from available sprite variants for visual variance,
        unless forced_filename is provided (for combat persistence).
        """
        enemy_key = enemy_key.lower().replace(" ", "_")
        category = category.lower() if category else "humanoid"
        
        # Determine which file to use
        if forced_filename:
            filename = forced_filename
        else:
            filenames = SpriteManager._enemy_mapping.get(enemy_key, [])
            if not filenames:
                filenames = [f"{enemy_key}.png"]
            filename = random.choice(filenames)
        cache_key = ("enemy", filename, size)
        
        if cache_key in SpriteManager._cache:
            return SpriteManager._cache[cache_key]

        # Use get_resource_path for dynamic asset loading
        # Path: assets/sprites/enemy_images/{category}/{filename}
        sprite_path = get_resource_path(os.path.join("assets", "sprites", "enemy_images", category, filename))

        try:
            if not os.path.exists(sprite_path):
                # Try variations in the category folder
                images_dir = get_resource_path(os.path.join("assets", "sprites", "enemy_images", category))
                if os.path.exists(images_dir):
                    all_files = os.listdir(images_dir)
                    matches = [f for f in all_files if f.lower().startswith(enemy_key)]
                    if matches:
                        sprite_path = os.path.join(images_dir, matches[0])
                    else:
                        raise FileNotFoundError(f"No sprite found for {enemy_key} in {category}")
                else:
                    raise FileNotFoundError(f"Category folder {category} not found")

            sprite = pygame.image.load(sprite_path).convert_alpha()
            if size:
                sprite = pygame.transform.scale(sprite, size)
            
            SpriteManager._cache[cache_key] = sprite
            return sprite
        except Exception:
            placeholder = pygame.Surface(size if size else (192, 192), pygame.SRCALPHA)
            pygame.draw.rect(placeholder, (200, 0, 0), placeholder.get_rect(), 2)
            return placeholder

    @staticmethod
    def get_player_sprite(class_name, size=(192, 192)):
        """Loads and returns a sprite for the given player class."""
        class_name = class_name.lower()
        
        # Redirection for renamed class
        if class_name == "archer":
            class_name = "ranger"
            
        filename = f"{class_name}.png"
        
        cache_key = ("player", filename, size)
        if cache_key in SpriteManager._cache:
            return SpriteManager._cache[cache_key]

        # Use get_resource_path for dynamic asset loading
        sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", filename))

        try:
            if not os.path.exists(sprite_path):
                # Placeholder mapping for cleric
                if class_name == "cleric":
                    sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", "wizard2.png"))
                # Try webp fallback for special cases like kobold sorc if any
                elif class_name == "kobold_sorcerer":
                     sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", "Kobald_sorc.webp"))
                else:
                     raise FileNotFoundError(f"No player sprite found for {class_name}")

            sprite = pygame.image.load(sprite_path).convert_alpha()
            if size:
                sprite = pygame.transform.scale(sprite, size)
            
            SpriteManager._cache[cache_key] = sprite
            return sprite
        except Exception:
            placeholder = pygame.Surface(size if size else (192, 192), pygame.SRCALPHA)
            pygame.draw.rect(placeholder, (0, 0, 200), placeholder.get_rect(), 2)
            return placeholder
