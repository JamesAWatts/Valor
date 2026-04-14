import pygame
import random
import os

from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.panel import Panel
from interfaces.pygame.ui.dialogue_box import DialogueBox
from interfaces.pygame.ui.bars import draw_bar
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y
from core.combat.attack_roller import attack_roll, damage_roll
from core.combat.combat_engine import CombatEngine
from core.players.player import load_consumables, load_spells, load_skills
from core.game_rules.mana_check import ManaCheck
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.graphics.enemy_sprites import SpriteManager
from interfaces.pygame.ui.floating_text import FloatingTextManager


class CombatState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_combat_bg()

        self.dialogue = DialogueBox(self.font)
        self.float_mgr = FloatingTextManager()

        self.player = game.player
        self.enemies = game.enemies
        
        # Player screen position (Centered over 256x256 sprite at x=0)
        self.player['screen_pos'] = (scale_x(128), SCREEN_HEIGHT // 2 - scale_y(80))

        # --- Format Enemy Names and set Screen Positions (Matching Sprite Layout) ---
        for i, e in enumerate(self.enemies):
            if "name" in e:
                e["name"] = e["name"].replace("_", " ").title()
            
            # Calculate grid position to match sprite drawing logic
            column = 1 if i < 2 else 2
            row = i % 2
            
            base_enemy_x = SCREEN_WIDTH - scale_x(250)
            if column == 2:
                base_enemy_x -= scale_x(150)
            
            enemy_x = base_enemy_x - (row * scale_x(40))
            enemy_y = SCREEN_HEIGHT // 2 - scale_y(96) + (row * scale_y(100))
            
            # Set screen_pos to top-center of the 192x192 enemy sprite
            e['screen_pos'] = (enemy_x + scale_x(96), enemy_y + scale_y(20))

        # --- Player stats ---
        self.player_max_hp = int(self.player.get("max_hp", self.player.get("hp", 1)))
        self.player_hp = min(self.player_max_hp, int(self.player.get("current_hp", self.player.get("hp", 1))))
        
        self.player_max_mp = int(self.player.get("max_mp", 0))
        self.player_mp = min(self.player_max_mp, int(self.player.get("current_mp", 0)))
        
        self.player_max_sp = int(self.player.get("max_sp", 0))
        self.player_sp = min(self.player_max_sp, int(self.player.get("current_sp", 0)))

        # --- Enemy setup ---
        for e in self.enemies:
            e["current_hp"] = int(e.get("current_hp", e.get("hp", 10)))
            e["max_hp"] = int(e.get("hp", 10))
            
            # Initialize Resources
            e["max_sp"] = 10
            e["current_sp"] = 0
            e["max_mp"] = 10
            e["current_mp"] = 0
            e["has_healed"] = False
            
            e.setdefault("conditions", {})

        # --- Combat stats ---
        self.p_attack_count = int(self.player.get("attack_count", 1))
        self.attacks_made = 0
        self.ability_hits_made = 0

        # --- Data ---
        self.consumables_db = load_consumables()
        self.spells_db = load_spells()
        self.skills_db = load_skills()

        # --- Effects ---
        self.player_advantage = 0
        self.enemy_advantage = 0
        self.extra_damage_once = 0
        self.player_conditions = {}

        # --- Menus ---
        options = ["Attack"]
        
        has_skills = len(self.player.get("skills", [])) > 0
        has_spells = len(self.player.get("spells", [])) > 0
        
        # Fallback check for casting classes
        caster_classes = ["wizard", "druid", "alchemist", "sorcerer"]
        if self.player.get("class") in caster_classes:
            has_spells = True
            
        if has_skills: options.append("Skill")
        if has_spells: options.append("Spell")
        
        options.extend(["Item", "Run"])
        self.main_menu = Menu(options, font)
        self.target_menu = None
        self.sub_menu = None

        self.menu_state = "MAIN"
        self.active_menu = self.main_menu

        # --- Flow ---
        self.phase = "INITIATIVE"
        self.pending_action = None
        self.action_data = None

        # --- Messages ---
        self.message_queue = []

        names = ", ".join([e["name"] for e in self.enemies])
        self.queue_message(f"Encountered: {names}!")
        self.start_next_message()

    # ========================
    # BASESTATE HOOK
    # ========================
    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)
        elif self.menu_state == "SPELL":
            self.handle_spell_menu(option)
        elif self.menu_state == "SKILL":
            self.handle_skill_menu(option)
        elif self.menu_state == "ITEM":
            self.handle_item_menu(option)
        elif self.menu_state == "TARGETING":
            self.handle_targeting(option)

    # ========================
    # UPDATE LOOP
    # ========================
    def update(self, events):
        self.float_mgr.update()
        # --- Dialogue blocks input ---
        if self.dialogue.current_message:
            self.dialogue.update()

            for event in events:
                if event.type == pygame.KEYDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)
                    if not was_typing and not self.dialogue.current_message:
                        if self.message_queue:
                            self.start_next_message()
                        elif self.phase == "END_COMBAT":
                            self.exit_to_hub()
                        elif self.phase == "LEVEL_UP":
                            from interfaces.pygame.states.level_up import LevelUpState
                            self.game.change_state(LevelUpState(self.game, self.font))
            return

        # --- Combat phases ---
        if self.phase == "INITIATIVE":
            self.handle_initiative()

        elif self.phase == "PLAYER_TURN":
            # --- Handle Condition Durations and DOTs ---
            if not self.dialogue.current_message and not self.message_queue:
                if not hasattr(self, '_turn_start_processed'):
                    self.attacks_made = 0 # Reset attacks for new turn
                    self.ability_hits_made = 0 # Reset ability hits for new turn
                    # 1. Resolve DOTs/HOTs on Player
                    if 'dot' in self.player_conditions:
                        from core.combat.attack_roller import roll_dice
                        dice, duration = self.player_conditions['dot']
                        dmg = roll_dice(dice)
                        self.player_hp = max(0, self.player_hp - dmg)
                        self.queue_message(f"Lingering effect deals {dmg} damage to you!")
                        
                        if duration > 1:
                            self.player_conditions['dot'] = (dice, duration - 1)
                        else:
                            del self.player_conditions['dot']
                            self.queue_message("Lingering effect faded.")

                    if 'hot' in self.player_conditions:
                        from core.combat.attack_roller import roll_dice
                        dice, duration = self.player_conditions['hot']
                        heal = roll_dice(dice)
                        self.player_hp = min(self.player_max_hp, self.player_hp + heal)
                        self.queue_message(f"Regeneration restores {heal} HP!")
                        
                        if duration > 1:
                            self.player_conditions['hot'] = (dice, duration - 1)
                        else:
                            del self.player_conditions['hot']
                            self.queue_message("Regeneration effect faded.")

                    # 2. Decrement other conditions
                    expired = []
                    for cond, duration in self.player_conditions.items():
                        if cond == 'dot': continue # Handled above
                        if duration > 0:
                            self.player_conditions[cond] -= 1
                            if self.player_conditions[cond] <= 0:
                                expired.append(cond)
                    
                    for cond in expired:
                        del self.player_conditions[cond]
                        if cond == 'crit_on_19':
                            self.player['crit_on_19'] = False
                            self.queue_message("Lethal Focus worn off.")
                    
                    self._turn_start_processed = True
                    if self.message_queue:
                        self.start_next_message()
                        return # Let messages play out before showing menu

            if self.player_conditions.get('stunned', 0) > 0:
                self.queue_message("You are stunned and skip your turn!")
                self.phase = "ENEMY_TURN"
                self.start_next_message()
            else:
                super().update(events)

        elif self.phase == "ENEMY_TURN":
            self.handle_enemy_turn()

        elif self.phase == "RESOLVE_VICTORY":
            if not self.dialogue.current_message and not self.message_queue:
                self.handle_victory()
                self.start_next_message()

        elif self.phase == "CHECK_END":
            self.check_combat_end()

    def process_loot(self):
        loot_results = CombatEngine.generate_loot(self.enemies)
        
        inventory = self.game.player.setdefault("inventory_ref", {})
        inventory.setdefault("gold", 0)
        
        inventory["gold"] += loot_results["gold"]
        for item_type, item_name in loot_results["items"]:
            category = inventory.setdefault(item_type, {})
            
            if item_name in category:
                category[item_name] += 1
            else:
                category[item_name] = 1

        for msg in loot_results["messages"]:
            self.queue_message(msg)

    # ========================
    # MENU HANDLERS
    # ========================
    def handle_main_menu(self, option):
        if option == "Attack":
            self.start_targeting("ATTACK")

        elif option == "Spell":
            spells = self.player.get("spells", [])
            if spells:
                # Format for display
                display_spells = [s.replace('_', ' ').title() for s in spells]
                disabled = ManaCheck.get_disabled_spell_indices(self.player_mp, spells, self.spells_db)
                self.sub_menu = Menu(display_spells + ["Back"], self.font, disabled_indices=disabled, header="Cast Spell")
                self.menu_state = "SPELL"
                self.active_menu = self.sub_menu
            else:
                self.queue_message("No spells!")
                self.start_next_message()

        elif option == "Skill":
            skills = self.player.get("skills", [])
            if skills:
                # Format for display
                display_skills = [s.replace('_', ' ').title() for s in skills]
                # Basic check for SP
                disabled = []
                for i, s_name in enumerate(skills):
                    s_key = s_name.lower().replace(" ", "_")
                    s_data = self.skills_db.get(s_key, {})
                    if self.player_sp < s_data.get('cost', 1):
                        disabled.append(i)
                
                self.sub_menu = Menu(display_skills + ["Back"], self.font, disabled_indices=disabled, header="Use Skill")
                self.menu_state = "SKILL"
                self.active_menu = self.sub_menu
            else:
                self.queue_message("No skills!")
                self.start_next_message()

        elif option == "Item":
            inventory = self.player.get("inventory_ref", {})
            consumables = inventory.get("consumable", {})
            if consumables:
                # Show name (xCount)
                items_with_counts = [f"{name.replace('_', ' ').title()} (x{count})" for name, count in consumables.items()]
                self.sub_menu = Menu(items_with_counts + ["Back"], self.font, header="Use Item")
                self.menu_state = "ITEM"
                self.active_menu = self.sub_menu
            else:
                self.queue_message("No items!")
                self.start_next_message()

        elif option == "Run":
            if random.random() < 0.4:
                self.queue_message("Escaped!")
                self.phase = "END_COMBAT"
            else:
                self.queue_message("Failed escape!")
                self.phase = "ENEMY_TURN"
            self.start_next_message()

    def handle_spell_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        elif self.player_conditions.get('silenced', 0) > 0:
            self.queue_message("You are silenced and cannot cast spells!")
            self.start_next_message()
        else:
            spell_key = option.lower().replace(" ", "_")
            spell_data = self.spells_db.get(spell_key, {})
            if not ManaCheck.can_cast(self.player_mp, option, self.spells_db):
                self.queue_message("Not enough mana")
                self.start_next_message()
            else:
                # Decide targeting based on effect
                if spell_data.get('type') == 'heal' or spell_data.get('effect_type') == 'healing':
                    self.start_targeting("SPELL_PLAYER", option)
                else:
                    self.start_targeting("SPELL", option)

    def handle_skill_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            skill_key = option.lower().replace(" ", "_")
            skill_data = self.skills_db.get(skill_key, {})
            cost = skill_data.get('cost', 1)
            
            if self.player_sp < cost:
                self.queue_message("Not enough stamina")
                self.start_next_message()
            else:
                if skill_data.get('type') == 'heal':
                    self.start_targeting("SKILL_PLAYER", option)
                else:
                    self.start_targeting("SKILL", option)

    def handle_item_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            # strip (xN) if present
            display_name = option.split(" (x")[0]
            item_key = display_name.lower().replace(' ', '_')
            item_data = self.consumables_db.get(item_key)
            
            if item_data:
                # Healing or buff items target the player
                hp_g = item_data.get('hp_gain', 0)
                mp_g = item_data.get('mana_gain', 0)
                bn_g = item_data.get('bonus_gain', 0)
                at_g = item_data.get('attack_gain', 0)
                
                # Check for effect_type mapping as well
                e_type = item_data.get('effect_type')
                if e_type in ['heal', 'restore_mana', 'buff_bonus', 'buff_attacks', 'extra_damage']:
                    self.start_targeting("ITEM_PLAYER", display_name)
                elif hp_g > 0 or mp_g > 0 or bn_g > 0 or at_g > 0:
                    self.start_targeting("ITEM_PLAYER", display_name)
                else:
                    self.start_targeting("ITEM", display_name)
            else:
                self.queue_message("Item data missing!")
                self.start_next_message()

    def handle_targeting(self, option):
        if option == "Back":
            # If we've already started a multi-hit ability, we can't go back
            if self.pending_action in ["SKILL", "SPELL", "SKILL_PLAYER", "SPELL_PLAYER"] and self.ability_hits_made > 0:
                self.queue_message("You are committed to this action!")
                self.start_next_message()
                self.start_targeting(self.pending_action, self.action_data)
                return

            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            if self.pending_action in ["SPELL_PLAYER", "SKILL_PLAYER", "ITEM_PLAYER"]:
                # Single player targeting for now
                self.execute_targeted_action(None) # None means player
                
                # Check for multi-hit self-targeting abilities
                ability_key = self.action_data.lower().replace(" ", "_") if self.action_data else None
                ability_data = self.skills_db.get(ability_key) or self.spells_db.get(ability_key, {})
                iterations = self.p_attack_count if ability_data.get('use_attack_count') else 1
                
                if self.ability_hits_made < iterations:
                    self.start_targeting(self.pending_action, self.action_data)
                    return

                self.menu_state = "MAIN"
                self.active_menu = self.main_menu
                self.phase = "ENEMY_TURN"
            else:
                # Safer targeting extraction
                try:
                    idx_str = option.split(".")[0]
                    idx = int(idx_str) - 1
                    self.execute_targeted_action(idx)
                    
                    # Sequential multi-attack check (Basic Attack)
                    if self.pending_action == "ATTACK" and self.attacks_made < self.p_attack_count:
                        if any(e["current_hp"] > 0 for e in self.enemies):
                            self.start_targeting("ATTACK") # Prompt again for next attack
                            return 

                    # Sequential multi-hit check (Abilities)
                    if self.pending_action in ["SKILL", "SPELL"]:
                        ability_key = self.action_data.lower().replace(" ", "_")
                        ability_data = self.skills_db.get(ability_key) or self.spells_db.get(ability_key, {})
                        
                        iterations = self.p_attack_count if ability_data.get('use_attack_count') else 1
                        if self.ability_hits_made < iterations:
                            if any(e["current_hp"] > 0 for e in self.enemies):
                                self.start_targeting(self.pending_action, self.action_data)
                                return

                    self.menu_state = "MAIN"
                    self.active_menu = self.main_menu
                    self.phase = "ENEMY_TURN"
                except (ValueError, IndexError):
                    self.queue_message("Invalid target!")
                    self.start_next_message()

    # ========================
    # FLOW HELPERS
    # ========================
    def start_targeting(self, action_type, data=None):
        ability_key = data.lower().replace(" ", "_") if data else None
        ability_data = self.skills_db.get(ability_key) or self.spells_db.get(ability_key, {})
        is_aoe = ability_data.get('aoe', False)

        self.pending_action = action_type
        self.action_data = data

        if action_type in ["SPELL_PLAYER", "SKILL_PLAYER", "ITEM_PLAYER"]:
            options = [self.player.get("name", "Player")]
            if self.ability_hits_made == 0:
                options.append("Back")
        elif is_aoe:
            self.execute_targeted_action(None)
            
            iterations = self.p_attack_count if ability_data.get('use_attack_count') else 1
            if self.ability_hits_made < iterations:
                if any(e["current_hp"] > 0 for e in self.enemies):
                    self.start_targeting(action_type, data) 
                    return

            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
            self.phase = "ENEMY_TURN"
            return
        else:
            alive_indices = [i for i, e in enumerate(self.enemies) if e["current_hp"] > 0]
            if not alive_indices:
                return
            
            options = [f"{i+1}. {self.enemies[i]['name']}" for i in alive_indices]
            if (action_type == "ATTACK" and self.attacks_made == 0) or \
               (action_type in ["SKILL", "SPELL"] and self.ability_hits_made == 0):
                options.append("Back")

        header = "Target?"
        if action_type == "ATTACK":
            header = f"Attack Whom? ({self.attacks_made + 1}/{self.p_attack_count})"
        elif action_type in ["SPELL", "SPELL_PLAYER"]:
            header = f"Cast {data} on?"
        elif action_type in ["SKILL", "SKILL_PLAYER"]:
            header = f"Use {data} on?"
        elif action_type in ["ITEM", "ITEM_PLAYER"]:
            header = f"Use {data} on?"

        self.target_menu = Menu(options, self.font, header=header)
        self.menu_state = "TARGETING"
        self.active_menu = self.target_menu

    def handle_initiative(self):
        max_e_bonus = max([int(e.get("bonus", 0)) for e in self.enemies])
        p_init = random.randint(1, 20) + int(self.player.get("proficiency_bonus", 0))
        e_init = random.randint(1, 20) + max_e_bonus

        self.queue_message(f"Initiative: You {p_init}, Enemies {e_init}")
        self.phase = "PLAYER_TURN" if p_init >= e_init else "ENEMY_TURN"
        self.start_next_message()

    def handle_enemy_turn(self):
        from core.combat.enemy_ai import EnemyAI
        from core.combat.attack_roller import roll_dice
        
        # Reset turn flag for player's next turn
        if hasattr(self, '_turn_start_processed'):
            delattr(self, '_turn_start_processed')

        for i, enemy in enumerate(self.enemies):
            if enemy["current_hp"] > 0:
                # 0. Resolve DOTs on Enemy
                if 'dot' in enemy.get('conditions', {}):
                    dice, duration = enemy['conditions']['dot']
                    dmg = roll_dice(dice)
                    enemy["current_hp"] = max(0, enemy["current_hp"] - dmg)
                    self.queue_message(f"Lingering effect deals {dmg} damage to {enemy['name']}!")
                    
                    if duration > 1:
                        enemy['conditions']['dot'] = (dice, duration - 1)
                    else:
                        del enemy['conditions']['dot']
                        self.queue_message(f"Lingering effect on {enemy['name']} faded.")
                
                if 'hot' in enemy.get('conditions', {}):
                    dice, duration = enemy['conditions']['hot']
                    heal = roll_dice(dice)
                    enemy["current_hp"] = min(enemy["max_hp"], enemy["current_hp"] + heal)
                    self.queue_message(f"Regeneration restores {heal} HP to {enemy['name']}!")
                    
                    if duration > 1:
                        enemy['conditions']['hot'] = (dice, duration - 1)
                    else:
                        del enemy['conditions']['hot']
                        self.queue_message(f"Regeneration effect on {enemy['name']} faded.")
                
                if enemy["current_hp"] <= 0:
                    self.queue_message(f"{enemy['name']} succumbed to lingering effects!")
                    continue

                # 1. Generate Resources (+1 SP, +1 MP)
                enemy["current_sp"] = min(enemy["max_sp"], enemy.get("current_sp", 0) + 1)
                enemy["current_mp"] = min(enemy["max_mp"], enemy.get("current_mp", 0) + 1)
                
                # 2. Check Conditions
                if enemy.get('conditions', {}).get('stunned', 0) > 0:
                    self.queue_message(f"{enemy['name']} is stunned and skips their turn!")
                    enemy['conditions']['stunned'] -= 1
                    continue
                
                # 3. Decide Action
                action = EnemyAI.decide_action(enemy)
                
                if action['type'] == 'ability':
                    # Execute Ability
                    ability_data = action['data']
                    
                    # Decide targets
                    if ability_data.get('type') == 'heal':
                        # Heal self
                        targets = [enemy]
                    elif ability_data.get('aoe'):
                        # Hit player? (In this simple 1vX, AOE just hits player)
                        targets = [self.player]
                    else:
                        targets = [self.player]
                        
                    res = CombatEngine.resolve_ability(ability_data, enemy, targets, debug=self.game.debug_overlay, float_mgr=self.float_mgr)
                    
                    # Deduct cost
                    cost = res.get('mana_cost', 0)
                    resource = ability_data.get('resource', 'mp')
                    enemy[f'current_{resource}'] -= cost
                    
                    # Apply results
                    if res['damage'] > 0:
                        self.player_hp = max(0, self.player_hp - res['damage'])
                    if res['healing'] > 0:
                        enemy['current_hp'] = min(enemy['max_hp'], enemy['current_hp'] + res['healing'])
                        
                    # Queue message
                    self.queue_message(f"{enemy['name']} uses {action['name']}!")
                    for m in res.get('msg', []):
                        self.queue_message(m)
                    
                    # Apply effects to player
                    for effect, val in res['effects']:
                        if effect == 'player_advantage': self.enemy_advantage = val
                        elif effect == 'enemy_advantage': self.player_advantage = val
                        elif effect == 'stunned':
                            self.player_conditions['stunned'] = val
                            self.queue_message("You are stunned!")
                        elif effect == 'msg': self.queue_message(val)
                
                else:
                    # Default Attack
                    self.enemy_attack(enemy, i)

        self.start_next_message()
        self.phase = "CHECK_END"

    # ========================
    # ACTIONS
    # ========================
    def execute_targeted_action(self, target_idx):
        if self.pending_action == "ATTACK":
            self.player_attack(target_idx)
        elif self.pending_action in ["SPELL", "SPELL_PLAYER", "SKILL", "SKILL_PLAYER"]:
            self.cast_ability(self.action_data, target_idx)
        elif self.pending_action in ["ITEM", "ITEM_PLAYER"]:
            self.use_item(self.action_data, target_idx)

    def player_attack(self, target_idx):
        enemy = self.enemies[target_idx]

        res = CombatEngine.resolve_attack(self.player, enemy, advantage=self.player_advantage, debug=self.game.debug_overlay, float_mgr=self.float_mgr, extra_damage=self.extra_damage_once)
        self.player_advantage = 0
        self.extra_damage_once = 0
        
        enemy["current_hp"] = max(0, enemy["current_hp"] - res['damage'])
        if enemy["current_hp"] <= 0:
            self.player['kill_count'] = self.player.get('kill_count', 0) + 1
        
        for m in res.get('msg', []):
            self.queue_message(m)
        
        for effect, val in res['effects']:
            if effect == 'player_advantage': self.player_advantage = val; self.queue_message("Vex: Advantage next!")
            elif effect == 'enemy_advantage': self.enemy_advantage = val; self.queue_message("Sap: Enemy disadvantage!")
            elif effect == 'heal_attacker':
                self.player_hp = min(self.player_max_hp, self.player_hp + val)
                self.queue_message(f"Lifesteal: +{val} HP")
            elif effect == 'stunned':
                enemy['conditions']['stunned'] = val
                self.queue_message(f"{enemy['name']} is stunned!")
            elif effect == 'msg': self.queue_message(val)

        self.attacks_made += 1
        self.start_next_message()

    def enemy_attack(self, enemy, index):
        res = CombatEngine.resolve_attack(enemy, self.player, advantage=self.enemy_advantage, debug=self.game.debug_overlay, float_mgr=self.float_mgr)
        self.enemy_advantage = 0

        self.player_hp = max(0, self.player_hp - res['damage'])
        for m in res.get('msg', []):
            self.queue_message(m)
            
        for effect, val in res['effects']:
            if effect == 'player_advantage': self.enemy_advantage = val
            elif effect == 'enemy_advantage': self.player_advantage = val
            elif effect == 'stunned':
                self.player_conditions['stunned'] = val
                self.queue_message("You are stunned!")
            elif effect == 'msg': self.queue_message(val)

    def cast_ability(self, ability_name, target_idx):
        ability_key = ability_name.lower().replace(" ", "_")
        # Check skills first, then spells
        ability_data = self.skills_db.get(ability_key) or self.spells_db.get(ability_key, {})
        
        cost = ability_data.get('cost', ability_data.get('level', 0))
        resource_type = ability_data.get('resource', 'mp')
        
        current_resource = self.player_mp if resource_type == 'mp' else self.player_sp
        
        # Pay cost only on first hit
        if self.ability_hits_made == 0:
            if current_resource < cost:
                self.queue_message(f"Not enough {resource_type.upper()}!")
                self.start_next_message()
                return

        # AOE logic
        is_aoe = ability_data.get('aoe', False)
        alive_enemies = [e for e in self.enemies if e["current_hp"] > 0]
        
        if is_aoe:
            targets = alive_enemies
        else:
            # If target_idx is None, target is self (player)
            targets = [self.player] if target_idx is None else [self.enemies[target_idx]]
        
        # Resolve ONE iteration
        res = CombatEngine.resolve_ability(ability_data, self.player, targets, debug=self.game.debug_overlay, float_mgr=self.float_mgr, skip_cost=(self.ability_hits_made > 0))
        
        # Deduct resource
        deduction = res.get('mana_cost', 0)
        if resource_type == 'mp':
            self.player_mp -= deduction
            self.player['current_mp'] = self.player_mp
        else:
            self.player_sp -= deduction
            self.player['current_sp'] = self.player_sp
        
        # Apply damage to targets
        dmg_map = res.get('damage_by_target', {})
        for target in targets:
            dmg = dmg_map.get(id(target), 0)
            if dmg > 0:
                if target == self.player:
                    self.player_hp = max(0, self.player_hp - dmg)
                else:
                    target['current_hp'] = max(0, target['current_hp'] - dmg)
        
        if res['healing'] > 0:
            self.player_hp = min(self.player_max_hp, self.player_hp + res['healing'])
            self.queue_message(f"Healed for {res['healing']} HP!")
            
        for effect, val in res['effects']:
            if effect == 'enemy_advantage': 
                self.enemy_advantage = val
                self.queue_message("Enemies Disadvantaged!")
            elif effect == 'player_advantage' or effect == 'advantage':
                self.player_advantage = 1
                self.player_conditions['advantage'] = val
                self.queue_message(f"Gained Advantage ({val} turns)!")
            elif effect == 'extra_damage' or effect == 'damage':
                self.extra_damage_once += val
                self.player_conditions['damage_buff'] = val
                self.queue_message(f"Next hit will deal +{val} damage!")
            elif effect == 'crit on 19':
                self.player['crit_on_19'] = True
                self.player_conditions['crit_on_19'] = val
                self.queue_message(f"Lethal Focus: Crit on 19 ({val} turns)!")
            elif effect == 'heal_attacker':
                self.player_hp = min(self.player_max_hp, self.player_hp + val)
                self.queue_message(f"Healed for {val} HP!")
            elif effect == 'dot' or effect == 'hot':
                # val is (dice, duration)
                dice, duration = val
                for target in targets:
                    if target == self.player:
                        self.player_conditions[effect] = (dice, duration)
                    else:
                        target.setdefault('conditions', {})
                        target['conditions'][effect] = (dice, duration)
            elif effect == 'stunned':
                for target in targets:
                    if target == self.player:
                        self.player_conditions['stunned'] = val
                        self.queue_message("You are stunned!")
                    else:
                        target.setdefault('conditions', {})
                        target['conditions']['stunned'] = val
                        self.queue_message(f"{target['name']} is stunned!")
        
        for m in res.get('msg', []):
            self.queue_message(m)
        
        self.ability_hits_made += 1
        self.start_next_message()

    def use_item(self, item_name, target_idx):
        # target_idx is ignored for now as most items are player-focused (healing/buffs)
        item_key = item_name.lower().replace(' ', '_')
        item_data = self.consumables_db.get(item_key)
        
        if item_data:
            res = CombatEngine.resolve_item(item_data, self.player)
            self.queue_message(res['msg'])
            
            if res['hp_gain'] > 0:
                self.player_hp = min(self.player_max_hp, self.player_hp + res['hp_gain'])
                self.queue_message(f"Healed for {res['hp_gain']} HP!")
            
            if res.get('mana_gain', 0) > 0:
                self.player_mp = min(self.player_max_mp, self.player_mp + res['mana_gain'])
                self.queue_message(f"Restored {res['mana_gain']} Mana!")

            if res['bonus_gain'] > 0:
                self.player['weapon_bonus'] = self.player.get('weapon_bonus', 0) + res['bonus_gain']
                self.queue_message(f"Bonus +{res['bonus_gain']}!")
            
            if res['attack_gain'] > 0:
                self.p_attack_count += res['attack_gain']
                self.queue_message(f"+{res['attack_gain']} Attacks!")
            
            if res['extra_damage'] > 0:
                self.extra_damage_once += res['extra_damage']
                self.queue_message(f"Next hit +{res['extra_damage']}!")
                
            # Remove from inventory using count-based system
            from core.players.player_inventory import remove_item
            remove_item(self.player.get("inventory_ref", {}), item_key, "consumable")
        else:
            self.queue_message("Item failed!")
            
        self.start_next_message()

    # ========================
    # END / CHECK
    # ========================
    def handle_victory(self):
        total_xp = sum(e.get("xp", 0) for e in self.enemies)

        from core.players.leveler import update_xp_and_level
        level_up_available = update_xp_and_level(self.game.player, total_xp)

        self.queue_message(f"You gained {total_xp} XP!")

        self.process_loot()

        from core.players.leveler import xp_to_next_level
        next_xp = xp_to_next_level(self.game.player["xp"])

        if next_xp is not None:
            self.queue_message(f"{next_xp} XP until next level.")

        if level_up_available:
            self.queue_message("LEVEL UP!")
            self.phase = "LEVEL_UP"
        else:
            self.phase = "END_COMBAT"

    def check_combat_end(self):
        if all(e["current_hp"] <= 0 for e in self.enemies):
            self.queue_message("Victory!")
            self.phase = "RESOLVE_VICTORY"
            self.start_next_message()
        elif self.player_hp <= 0:
            self.queue_message("Defeat...")
            self.phase = "END_COMBAT"
            self.start_next_message()
        else:
            self.phase = "PLAYER_TURN"

    def exit_to_hub(self):
        self.game.player["current_hp"] = self.player_hp
        self.game.player["current_mp"] = self.player_mp
        self.game.player["current_sp"] = self.player_sp

        if self.player_hp <= 0:
            from interfaces.pygame.states.game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font))
        else:
            # Tell manager to pick a new town/hub background for next visit
            BackgroundManager.refresh_hub_bg(self.game.player)
            
            from interfaces.pygame.states.hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    # ========================
    # MESSAGES
    # ========================
    def queue_message(self, text):
        self.message_queue.append(text)

    def start_next_message(self):
        if self.message_queue:
            self.dialogue.set_messages([self.message_queue.pop(0)])

    # ========================
    # DRAW
    # ========================
    def draw(self, screen):
        self.draw_background(screen)

        px = scale_x(40)
        py = scale_y(40)

        from interfaces.pygame.ui.panel import draw_text_outlined
        draw_text_outlined(screen, self.player.get("name", "Player"), self.font, (255,255,255), px, py)

        # Player HP Bar
        draw_bar(screen, px, py + scale_y(30), scale_x(200), scale_y(25),
                 self.player_hp, self.player_max_hp, (200,50,50), self.font)
        
        # Player MP Bar
        if self.player_max_mp > 0:
            from core.game_rules.constants import COLOR_BLUE
            draw_bar(screen, px, py + scale_y(65), scale_x(200), scale_y(25),
                     self.player_mp, self.player_max_mp, COLOR_BLUE, self.font)
        
        # Player SP Bar
        if self.player_max_sp > 0:
            from core.game_rules.constants import COLOR_YELLOW
            # If both exist, offset SP bar further down
            y_offset = scale_y(100) if self.player_max_mp > 0 else scale_y(65)
            draw_bar(screen, px, py + y_offset, scale_x(200), scale_y(25),
                     self.player_sp, self.player_max_sp, COLOR_YELLOW, self.font)

        # Draw Player Sprite
        player_class = self.player.get("class", "fighter")
        player_sprite = SpriteManager.get_player_sprite(player_class, size=(scale_x(256), scale_y(256)))
        if player_sprite:
            screen.blit(player_sprite, (scale_x(0), SCREEN_HEIGHT // 2 - scale_y(128)))

        # --- Enemy HP Bars (2x2 Grid) ---
        col1_x = SCREEN_WIDTH - scale_x(170)
        col2_x = SCREEN_WIDTH - scale_x(280)
        
        for i, enemy in enumerate(self.enemies):
            column = 1 if i < 2 else 2
            row = i % 2
            
            ex = col1_x if column == 1 else col2_x
            y_off = scale_y(50) + (row * scale_y(105))
            
            name_str = enemy["name"]
            if enemy.get('conditions'):
                name_str += f" [{', '.join(enemy['conditions'].keys())}]"
                
            draw_text_outlined(screen, name_str, self.font, (255,255,255), ex, y_off - scale_y(25))

            # HP Bar
            draw_bar(screen, ex, y_off, scale_x(150), scale_y(25),
                     enemy["current_hp"], enemy["max_hp"], (200,50,50), self.font)

            # Enemy Resource Bars
            has_sp = len(enemy.get("skills", [])) > 0
            has_mp = len(enemy.get("spells", [])) > 0
            
            if has_mp:
                from core.game_rules.constants import COLOR_BLUE
                draw_bar(screen, ex, y_off + scale_y(30), scale_x(150), scale_y(20),
                         enemy["current_mp"], enemy["max_mp"], COLOR_BLUE, self.font)
            
            if has_sp:
                from core.game_rules.constants import COLOR_YELLOW
                y_gap = scale_y(55) if has_mp else scale_y(30)
                draw_bar(screen, ex, y_off + y_gap, scale_x(150), scale_y(20),
                         enemy["current_sp"], enemy["max_sp"], COLOR_YELLOW, self.font)

            # Draw Enemy Sprite
            enemy_key = enemy["name"].lower().replace(" ", "_")
            if enemy_key[-2:] in ["_a", "_b", "_c"]:
                enemy_key = enemy_key[:-2]
            elif enemy_key[-1] in ["a", "b", "c"] and enemy_key[-2] == " ":
                enemy_key = enemy_key[:-2].replace(" ", "_")

            enemy_sprite = SpriteManager.get_enemy_sprite(enemy_key, size=(scale_x(192), scale_y(192)))
            if enemy_sprite:
                base_enemy_x = SCREEN_WIDTH - scale_x(250)
                if column == 2:
                    base_enemy_x -= scale_x(150)
                
                enemy_x = base_enemy_x - (row * scale_x(40))
                enemy_y = SCREEN_HEIGHT // 2 - scale_y(96) + (row * scale_y(100))
                
                is_stunned = enemy.get('conditions', {}).get('stunned', 0) > 0
                
                if enemy["current_hp"] <= 0:
                    enemy_sprite = enemy_sprite.copy()
                    enemy_sprite.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
                elif is_stunned:
                    enemy_sprite = enemy_sprite.copy()
                    enemy_sprite.fill((255, 255, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
                
                screen.blit(enemy_sprite, (enemy_x, enemy_y))

        # =========================
        # MENU LAYOUT
        # =========================
        if self.phase == "PLAYER_TURN" and not self.dialogue.current_message:
            width, height = screen.get_size()
            main_menu = self.main_menu
            main_width = main_menu.get_width()
            main_x = scale_x(80) + main_width // 2
            main_y = height
            main_menu.draw(screen, main_x, main_y)

            if self.active_menu != self.main_menu and self.active_menu:
                submenu = self.active_menu
                submenu_width = submenu.get_width()
                sub_x = main_x + (main_width // 2) + (submenu_width // 2) + scale_x(20)
                sub_y = main_y
                submenu.draw(screen, sub_x, sub_y)

        self.dialogue.draw(screen)
        self.float_mgr.draw(screen)
