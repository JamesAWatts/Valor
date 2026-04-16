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
from core.players.player import load_consumables, load_spells, load_skills, validate_player_data
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

        self.party = game.party # All members
        self.enemies = game.enemies
        
        # --- Position Party Members ---
        # Sort by HP (Descending) for column priority
        sorted_party = sorted(self.party, key=lambda p: p.get('max_hp', 10), reverse=True)
        
        # Column mapping: 
        # Size 1: Col 2
        # Size 2: Col 2 (High HP), Col 1 (Low HP)
        # Size 3: Col 2 (High), Col 1 (Mid), Col 0 (Low)
        self.party_positions = {}
        for i, p in enumerate(sorted_party):
            # Col index: 2, 1, 0
            col_idx = 2 - i
            
            # Position columns starting from left
            # Col 0 is x=0, Col 1 is x=60, Col 2 is x=120 (roughly)
            base_x = scale_x(20) + (col_idx * scale_x(60))
            # Shift y per column for depth - increased spacing to avoid bar overlap
            base_y = SCREEN_HEIGHT // 2 - scale_y(100) + (i * scale_y(50))
            
            p['screen_pos'] = (base_x + scale_x(48), base_y + scale_y(10))
            self.party_positions[id(p)] = (base_x, base_y)

        # --- Format Enemy Names and set Screen Positions (Matching Sprite Layout) ---
        for i, e in enumerate(self.enemies):
            if "name" in e:
                # Add unique suffix if multiple of same type
                same_type = [en for en in self.enemies if en.get('class') == e.get('class') or en.get('name').split(' ')[0] == e.get('name').split(' ')[0]]
                if len(same_type) > 1:
                    suffix = chr(65 + i) # A, B, C...
                    e["name"] = f"{e['name'].replace('_', ' ').title()} {suffix}"
                else:
                    e["name"] = e["name"].replace("_", " ").title()
            
            column = 1 if i < 2 else 2
            row = i % 2
            
            base_enemy_x = SCREEN_WIDTH - scale_x(150)
            if column == 2:
                base_enemy_x -= scale_x(100)
            
            enemy_x = base_enemy_x - (row * scale_x(20))
            enemy_y = SCREEN_HEIGHT // 2 - scale_y(48) + (row * scale_y(100))
            
            e['screen_pos'] = (enemy_x + scale_x(48), enemy_y + scale_y(10))

        # --- Setup Combatants ---
        for p in self.party:
            # Apply HP buff from Feast without destructive pop
            buff = p.get('hp_buff', 0)
            p['max_hp_combat'] = int(p.get("max_hp", 10)) + buff
            p['current_hp'] = min(p['max_hp_combat'], int(p.get("current_hp", p.get("hp", 10))) + buff)
            
            p.setdefault("conditions", {})

        for e in self.enemies:
            e["current_hp"] = int(e.get("current_hp", e.get("hp", 10)))
            e["max_hp"] = int(e.get("hp", 10))
            e["max_sp"] = 10
            e["current_sp"] = 0
            e["max_mp"] = 10
            e["current_mp"] = 0
            e.setdefault("conditions", {})

        # --- Data ---
        self.consumables_db = load_consumables()
        self.spells_db = load_spells()
        self.skills_db = load_skills()

        # --- Combat State ---
        self.player_advantage = 0
        self.enemy_advantage = 0
        self.extra_damage_once = 0
        
        self.turn_order = []
        self.turn_index = 0
        self.phase = "INITIATIVE"
        self.round_number = 1
        self.pending_action = None
        self.action_data = None
        self.message_queue = []
        
        self.main_menu = None
        self.target_menu = None
        self.sub_menu = None
        self.menu_state = "MAIN"
        self.active_menu = None

        self.active_attacker = None
        self.attacker_offset = 0

        names = ", ".join([e["name"] for e in self.enemies])
        self.queue_message(f"Encountered: {names}!")
        self.start_next_message()

    @property
    def current_actor(self):
        if not self.turn_order: return None
        return self.turn_order[self.turn_index]

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

    def update(self, events):
        self.float_mgr.update()

        # Decrement flash frames for all combatants
        for actor in self.party + self.enemies:
            if actor.get('flash_frames', 0) > 0:
                actor['flash_frames'] -= 1

        if self.dialogue.current_message:
            # While dialogue is active, if there's an active attacker, they move forward
            if self.active_attacker:
                # Forward is +X for players, -X for enemies
                is_player = any(self.active_attacker is p for p in self.party)
                direction = 1 if is_player else -1
                self.attacker_offset = scale_x(20) * direction
            
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)
                    if not was_typing and not self.dialogue.current_message:
                        # Reset attacker offset when dialogue ends
                        self.active_attacker = None
                        self.attacker_offset = 0

                        if self.message_queue:
                            self.start_next_message()
                        elif self.phase == "END_COMBAT":
                            self.exit_to_hub()
                        elif self.phase == "LEVEL_UP":
                            from interfaces.pygame.states.level_up import LevelUpState
                            # Use the player we found during handle_victory
                            self.game.change_state(LevelUpState(self.game, self.font, player=getattr(self, '_levelup_starter', None)))
            return

        if self.phase == "INITIATIVE":
            self.handle_initiative()
        elif self.phase == "TURN_START":
            self.process_turn_start()
        elif self.phase == "PLAYER_TURN":
            super().update(events)
        elif self.phase == "ENEMY_TURN":
            self.handle_enemy_turn()
        elif self.phase == "CHECK_END":
            self.check_combat_end()
        elif self.phase == "RESOLVE_VICTORY":
            if not self.dialogue.current_message and not self.message_queue:
                self.handle_victory()
                self.start_next_message()

    def handle_initiative(self):
        combatants = []
        for p in self.party:
            roll = random.randint(1, 20) + int(p.get("proficiency_bonus", 0))
            combatants.append({'actor': p, 'init': roll, 'is_player': True})
        
        for e in self.enemies:
            roll = random.randint(1, 20) + int(e.get("bonus", 0))
            combatants.append({'actor': e, 'init': roll, 'is_player': False})
        
        # Sorting logic:
        # 1. Initiative (High to Low)
        # 2. HP (Low to High) - Ties
        # 3. Name (Alphabetical) - Further ties
        def sort_key(c):
            hp = c['actor'].get('current_hp', c['actor'].get('hp', 0))
            name = c['actor'].get('name', '')
            # Negate init for descending, hp ascending, name ascending
            return (-c['init'], hp, name)

        combatants.sort(key=sort_key)
        self.turn_order = [c['actor'] for c in combatants]
        self.turn_index = 0
        
        msg = "Turn Order: " + " > ".join([a['actor']['name'] for a in combatants])
        self.queue_message(msg)
        self.phase = "TURN_START"
        self.start_next_message()

    def process_turn_start(self):
        actor = self.current_actor
        if actor['current_hp'] <= 0:
            self.next_turn()
            return

        # Handle DOT/HOT
        conds = actor.get('conditions', {})
        if 'dot' in conds:
            from core.combat.attack_roller import roll_dice
            dice, duration = conds['dot']
            dmg = roll_dice(dice)
            actor['current_hp'] = max(0, actor['current_hp'] - dmg)
            self.queue_message(f"{actor['name']} takes {dmg} DOT damage!")
            if duration > 1: conds['dot'] = (dice, duration - 1)
            else: 
                del conds['dot']
                self.queue_message(f"DOT faded on {actor['name']}.")

        if 'hot' in conds:
            from core.combat.attack_roller import roll_dice
            dice, duration = conds['hot']
            heal = roll_dice(dice)
            max_hp = actor.get('max_hp_combat', actor.get('max_hp', 10))
            actor['current_hp'] = min(max_hp, actor['current_hp'] + heal)
            self.queue_message(f"{actor['name']} heals {heal} from HOT!")
            if duration > 1: conds['hot'] = (dice, duration - 1)
            else: 
                del conds['hot']
                self.queue_message(f"HOT faded on {actor['name']}.")

        # Decrement other conditions
        expired = []
        for cond, duration in conds.items():
            if cond in ['dot', 'hot']: continue
            if isinstance(duration, int) and duration > 0:
                conds[cond] -= 1
                if conds[cond] <= 0: expired.append(cond)
        for cond in expired:
            del conds[cond]
            self.queue_message(f"{actor['name']}'s {cond.title()} effect faded.")

        if actor.get('current_hp', 0) <= 0:
            self.queue_message(f"{actor['name']} is defeated!")
            self.next_turn()
            return

        if conds.get('stunned', 0) > 0:
            self.queue_message(f"{actor['name']} is stunned and skips their turn!")
            self.next_turn()
            return

        # Determine if Player or Enemy turn
        is_player = any(actor is p for p in self.party)
        if is_player:
            self.phase = "PLAYER_TURN"
            self.setup_player_menu(actor)
        else:
            self.phase = "ENEMY_TURN"

    def setup_player_menu(self, actor):
        options = ["Attack"]
        has_skills = len(actor.get("skills", [])) > 0
        has_spells = len(actor.get("spells", [])) > 0
        caster_classes = ["wizard", "druid", "alchemist", "sorcerer", "cleric"]
        if actor.get("class") in caster_classes: has_spells = True
            
        if has_skills: options.append("Skill")
        if has_spells: options.append("Spell")
        options.extend(["Item", "Run"])
        
        # Use Base (800x600) coordinates for menu
        self.main_menu = Menu(options, self.font, header=f"{actor['name']}'s Turn", pos=(400, 480))
        self.menu_state = "MAIN"
        self.active_menu = self.main_menu
        self.attacks_made = 0
        self.ability_hits_made = 0

    def handle_enemy_turn(self):
        actor = self.current_actor
        from core.combat.enemy_ai import EnemyAI
        
        # Resources
        actor["current_sp"] = min(actor["max_sp"], actor.get("current_sp", 0) + 1)
        actor["current_mp"] = min(actor["max_mp"], actor.get("current_mp", 0) + 1)
        
        action = EnemyAI.decide_action(actor)
        if action['type'] == 'ability':
            ability_data = action['data']
            if ability_data.get('type') == 'heal': targets = [actor]
            else:
                alive_party = [p for p in self.party if p['current_hp'] > 0]
                targets = alive_party if ability_data.get('aoe') else [random.choice(alive_party)]
            
            res = CombatEngine.resolve_ability(ability_data, actor, targets, float_mgr=self.float_mgr)
            cost = res.get('mana_cost', 0)
            actor[f"current_{ability_data.get('resource', 'mp')}"] -= cost
            
            # Apply results
            for t in targets:
                dmg = res.get('damage_by_target', {}).get(id(t), 0)
                t['current_hp'] = max(0, t['current_hp'] - dmg)
            if res['healing'] > 0:
                actor['current_hp'] = min(actor['max_hp'], actor['current_hp'] + res['healing'])
            
            for m in res['msg']: self.queue_message(m)
            self.apply_ability_effects(res, targets)
        else:
            # Simple Attack
            alive_party = [p for p in self.party if p['current_hp'] > 0]
            target = random.choice(alive_party)
            res = CombatEngine.resolve_attack(actor, target, float_mgr=self.float_mgr)
            target['current_hp'] = max(0, target['current_hp'] - res['damage'])
            for m in res['msg']: self.queue_message(m)
            self.apply_attack_effects(res, target)

        self.phase = "CHECK_END"
        self.start_next_message()

    def apply_ability_effects(self, res, targets):
        for effect, val in res['effects']:
            for t in targets:
                if effect == 'stunned':
                    t['conditions']['stunned'] = val
                    self.queue_message(f"{t['name']} is stunned!")
                elif effect == 'dot' or effect == 'hot':
                    t['conditions'][effect] = val

    def apply_attack_effects(self, res, target):
        for effect, val in res['effects']:
            if effect == 'stunned':
                target['conditions']['stunned'] = val
                self.queue_message(f"{target['name']} is stunned!")

    def next_turn(self):
        self.turn_index += 1
        if self.turn_index >= len(self.turn_order):
            self.turn_index = 0
            self.round_number += 1
        self.phase = "TURN_START"

    def get_next_living_actor(self):
        if not self.turn_order: return None
        for i in range(1, len(self.turn_order) + 1):
            idx = (self.turn_index + i) % len(self.turn_order)
            actor = self.turn_order[idx]
            if actor.get('current_hp', 0) > 0:
                return actor
        return None

    def check_combat_end(self):
        if all(e["current_hp"] <= 0 for e in self.enemies):
            self.queue_message("Victory!")
            self.phase = "RESOLVE_VICTORY"
        elif all(p["current_hp"] <= 0 for p in self.party):
            self.queue_message("Defeat...")
            self.phase = "END_COMBAT"
        else:
            self.next_turn()
        self.start_next_message()

    def handle_main_menu(self, option):
        actor = self.current_actor
        if option == "Attack": self.start_targeting("ATTACK")
        elif option == "Spell":
            spells = actor.get("spells", [])
            display_spells = [s.replace('_', ' ').title() for s in spells]
            disabled = ManaCheck.get_disabled_spell_indices(actor.get('current_mp', 0), spells, self.spells_db)
            self.sub_menu = Menu(display_spells + ["Back"], self.font, disabled_indices=disabled, header="Cast Spell")
            self.menu_state = "SPELL"; self.active_menu = self.sub_menu
        elif option == "Skill":
            skills = actor.get("skills", [])
            display_skills = [s.replace('_', ' ').title() for s in skills]
            disabled = [i for i, s in enumerate(skills) if actor.get('current_sp', 0) < self.skills_db.get(s.lower().replace(' ', '_'), {}).get('cost', 1)]
            self.sub_menu = Menu(display_skills + ["Back"], self.font, disabled_indices=disabled, header="Use Skill")
            self.menu_state = "SKILL"; self.active_menu = self.sub_menu
        elif option == "Item":
            inventory = actor.get("inventory_ref", {})
            consumables = inventory.get("consumable", {})
            items = [f"{n.replace('_',' ').title()} (x{c})" for n, c in consumables.items()]
            self.sub_menu = Menu(items + ["Back"], self.font, header="Use Item")
            self.menu_state = "ITEM"; self.active_menu = self.sub_menu
        elif option == "Run":
            if random.random() < 0.4: self.queue_message("Escaped!"); self.phase = "END_COMBAT"
            else: self.queue_message("Failed escape!"); self.phase = "CHECK_END"
            self.start_next_message()

    def handle_spell_menu(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            spell_key = option.lower().replace(" ", "_")
            spell_data = self.spells_db.get(spell_key, {})
            cost = spell_data.get("level", 0)
            if self.current_actor.get('current_mp', 0) < cost:
                self.queue_message("Not enough MP to use! Visit the Tavern to recover them!")
                self.start_next_message()
                return

            if spell_data.get('aoe'):
                targets = [p for p in self.party if p['current_hp'] > 0] if spell_data.get('type') == 'heal' else [e for e in self.enemies if e['current_hp'] > 0]
                self.pending_action = "SPELL"
                self.action_data = option
                self.execute_action(self.current_actor, targets)
                self.phase = "CHECK_END"
                self.start_next_message()
                return

            if spell_data.get('type') == 'heal': self.start_targeting("SPELL_FRIENDLY", option)
            else: self.start_targeting("SPELL", option)

    def handle_skill_menu(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            skill_key = option.lower().replace(" ", "_")
            skill_data = self.skills_db.get(skill_key, {})
            cost = skill_data.get("cost", 0)
            if self.current_actor.get('current_sp', 0) < cost:
                self.queue_message("Not enough SP to use! Visit the Tavern to recover them!")
                self.start_next_message()
                return

            if skill_data.get('aoe'):
                targets = [p for p in self.party if p['current_hp'] > 0] if skill_data.get('type') == 'heal' else [e for e in self.enemies if e['current_hp'] > 0]
                self.pending_action = "SKILL"
                self.action_data = option
                self.execute_action(self.current_actor, targets)
                self.phase = "CHECK_END"
                self.start_next_message()
                return

            if skill_data.get('type') == 'heal': self.start_targeting("SKILL_FRIENDLY", option)
            else: self.start_targeting("SKILL", option)

    def handle_item_menu(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            display_name = option.split(" (x")[0]
            self.start_targeting("ITEM_FRIENDLY", display_name)

    def handle_targeting(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            actor = self.current_actor
            target = None
            if self.pending_action.endswith("_FRIENDLY"):
                target = next(p for p in self.party if p['name'] == option)
            else:
                idx = int(option.split(".")[0]) - 1
                target = self.enemies[idx]
            
            self.execute_action(actor, target)
            
            # --- Check if Turn Ends or Continues (Multi-Hit) ---
            should_end = True
            max_attacks = int(actor.get('attack_count', 1))
            
            if self.pending_action == "ATTACK":
                self.attacks_made += 1
                if self.attacks_made < max_attacks:
                    should_end = False
            elif self.pending_action.startswith("SPELL") or self.pending_action.startswith("SKILL"):
                db = self.spells_db if self.pending_action.startswith("SPELL") else self.skills_db
                ability_data = db.get(self.action_data.lower().replace(" ", "_"), {})
                if ability_data.get('use_attack_count'):
                    self.ability_hits_made += 1
                    if self.ability_hits_made < max_attacks:
                        should_end = False

            if should_end:
                self.phase = "CHECK_END"
            else:
                # Refresh Targeting Menu for next hit (allows switching targets)
                self.start_targeting(self.pending_action, self.action_data)

    def execute_action(self, actor, target):
        self.active_attacker = actor
        # Ensure target is a list for uniform processing
        targets = target if isinstance(target, list) else [target]
        
        if self.pending_action == "ATTACK":
            # Attacks are single target
            t = targets[0]
            res = CombatEngine.resolve_attack(actor, t, float_mgr=self.float_mgr)
            t['current_hp'] = max(0, t['current_hp'] - res['damage'])
            
            # Trigger Flash Animation
            if res['hit']:
                t['flash_frames'] = 36
                t['flash_type'] = 'crit' if res['critical'] else 'damage'

            for m in res['msg']: self.queue_message(m)
            self.apply_attack_effects(res, t)
        elif self.pending_action.startswith("SPELL") or self.pending_action.startswith("SKILL"):
            db = self.spells_db if self.pending_action.startswith("SPELL") else self.skills_db
            ability_data = db.get(self.action_data.lower().replace(" ", "_"), {})
            
            # Only pay cost on the first hit
            is_first_hit = self.ability_hits_made == 0
            res = CombatEngine.resolve_ability(ability_data, actor, targets, float_mgr=self.float_mgr, skip_cost=not is_first_hit)
            
            if is_first_hit:
                resource_type = ability_data.get('resource', 'mp')
                actor[f"current_{resource_type}"] -= res['mana_cost']
            
            # Apply results to all targets
            dmg_map = res.get('damage_by_target', {})
            heal_map = res.get('healing_by_target', {})
            hits_map = res.get('hits_by_target', {})
            
            for t in targets:
                tid = id(t)
                dmg = dmg_map.get(tid, 0)
                hit = hits_map.get(tid, 0) > 0

                if dmg > 0:
                    t['current_hp'] = max(0, t['current_hp'] - dmg)
                
                if hit:
                    # Trigger Flash Animation for any hit (damage or effect)
                    t['flash_frames'] = 36
                    t['flash_type'] = 'damage'
                
                # Apply healing (fallback to total if map missing)
                heal = heal_map.get(tid, res['healing'] if len(targets) == 1 else 0)
                if heal > 0:
                    t['current_hp'] = min(t.get('max_hp_combat', t.get('max_hp', 10)), t['current_hp'] + heal)

            for m in res['msg']: self.queue_message(m)
            self.apply_ability_effects(res, targets)
        elif self.pending_action.startswith("ITEM"):
            t = targets[0]
            item_data = self.consumables_db.get(self.action_data.lower().replace(' ', '_'))
            res = CombatEngine.resolve_item(item_data, t)
            t['current_hp'] = min(t.get('max_hp_combat', t.get('max_hp', 10)), t['current_hp'] + res['hp_gain'])
            t['current_mp'] = min(t.get('max_mp', 0), t.get('current_mp', 0) + res['mana_gain'])
            # Remove item
            from core.players.player_inventory import remove_item
            remove_item(self.game.player['inventory_ref'], self.action_data.lower().replace(' ', '_'), "consumable")
            self.queue_message(res['msg'])
            self.phase = "CHECK_END" # Items always end turn immediately for now

    def start_targeting(self, action_type, data=None):
        self.pending_action = action_type; self.action_data = data
        if action_type.endswith("_FRIENDLY"):
            options = [p['name'] for p in self.party if p['current_hp'] > 0]
        else:
            options = [f"{i+1}. {e['name']}" for i, e in enumerate(self.enemies) if e['current_hp'] > 0]
        self.target_menu = Menu(options + ["Back"], self.font, header="Target?")
        self.menu_state = "TARGETING"; self.active_menu = self.target_menu

    def handle_victory(self):
        total_xp = sum(e.get("xp", 0) for e in self.enemies)
        # Distribute XP
        xp_per_person = total_xp // len(self.party)
        from core.players.leveler import update_xp_and_level
        levelup_player = None
        for p in self.party:
            if update_xp_and_level(p, xp_per_person):
                if levelup_player is None:
                    levelup_player = p
        
        self.queue_message(f"Each party member gained {xp_per_person} XP!")
        self.process_loot()
        
        if levelup_player:
            self.queue_message("LEVEL UP!")
            self.phase = "LEVEL_UP"
            self._levelup_starter = levelup_player
        else:
            self.phase = "END_COMBAT"

    def process_loot(self):
        loot = CombatEngine.generate_loot(self.enemies)
        inv = self.game.player['inventory_ref']
        inv['gold'] += loot['gold']
        for msg in loot['messages']: self.queue_message(msg)

    def exit_to_hub(self):
        for p in self.party: validate_player_data(p)
        if all(p['current_hp'] <= 0 for p in self.party):
            from interfaces.pygame.states.game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font))
        else:
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    def queue_message(self, text): self.message_queue.append(text)
    def start_next_message(self):
        if self.message_queue: self.dialogue.set_messages([self.message_queue.pop(0)])

    def draw(self, screen):
        self.draw_background(screen)
        
        # --- Draw Combat Status (Top Left) ---
        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import COLOR_WHITE, COLOR_GOLD
        status_x = scale_x(20)
        status_y = scale_y(20)
        spacing = scale_y(25)
        
        draw_text_outlined(screen, f"Round: {self.round_number}", self.font, COLOR_WHITE, status_x, status_y)
        
        active_name = self.current_actor['name'] if self.current_actor else "None"
        draw_text_outlined(screen, f"Active: {active_name}", self.font, COLOR_GOLD, status_x, status_y + spacing)
        
        next_actor = self.get_next_living_actor()
        next_name = next_actor['name'] if next_actor else "None"
        draw_text_outlined(screen, f"Next: {next_name}", self.font, COLOR_WHITE, status_x, status_y + spacing * 2)

        # --- Draw Party ---
        from core.game_rules.constants import COLOR_BLUE, COLOR_YELLOW
        # Sort by screen y-coordinate so characters in front (higher y) are drawn last
        sorted_drawing_party = sorted(self.party, key=lambda p: self.party_positions[id(p)][1])
        for p in sorted_drawing_party:
            bx, by = self.party_positions[id(p)]
            
            # Apply Attacker Offset
            draw_x = bx
            if self.active_attacker is p:
                draw_x += self.attacker_offset

            # Sprite
            sprite = SpriteManager.get_player_sprite(p.get('class', 'fighter'), size=(scale_x(128), scale_y(128)))
            
            # Apply Flashes/Effects
            if p['current_hp'] <= 0:
                sprite = sprite.copy()
                sprite.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif p.get('flash_frames', 0) > 0:
                sprite = self.apply_flash_effect(sprite, p['flash_frames'], p.get('flash_type', 'damage'))

            screen.blit(sprite, (draw_x, by))
            
            # HP Bar
            bar_x, bar_y = draw_x + scale_x(10), by - scale_y(30)
            draw_bar(screen, bar_x, bar_y, scale_x(100), scale_y(15), p['current_hp'], p.get('max_hp_combat', 10), (200, 50, 50), self.font)
            
            # Resource Bars (MP/SP)
            # Use a more robust positioning that doesn't overlap when one is missing
            current_y = bar_y + scale_y(18)
            if p.get('max_mp', 0) > 0:
                draw_bar(screen, bar_x, current_y, scale_x(100), scale_y(10), p.get('current_mp', 0), p['max_mp'], COLOR_BLUE, self.font)
                current_y += scale_y(12)
            
            if p.get('max_sp', 0) > 0:
                draw_bar(screen, bar_x, current_y, scale_x(100), scale_y(10), p.get('current_sp', 0), p['max_sp'], COLOR_YELLOW, self.font)

            # Turn Indicator (Top of the whole stack)
            if self.current_actor is p:
                pygame.draw.polygon(screen, (255, 255, 0), [(bar_x + scale_x(40), bar_y - scale_y(10)), (bar_x + scale_x(60), bar_y - scale_y(10)), (bar_x + scale_x(50), bar_y)])

        # --- Draw Enemies ---
        for i, enemy in enumerate(self.enemies):
            column = 1 if i < 2 else 2
            row = i % 2
            base_enemy_x = SCREEN_WIDTH - scale_x(150)
            if column == 2: base_enemy_x -= scale_x(100)
            enemy_x = base_enemy_x - (row * scale_x(20))
            enemy_y = SCREEN_HEIGHT // 2 - scale_y(48) + (row * scale_y(100))
            
            # Apply Attacker Offset
            draw_x, draw_y = enemy_x, enemy_y
            if self.active_attacker is enemy:
                draw_x += self.attacker_offset

            enemy_key = enemy["name"].lower().split(' ')[0]
            e_size = 192 if enemy_key == "ancient_dragon" else 96
            sprite = SpriteManager.get_enemy_sprite(enemy_key, size=(scale_x(e_size), scale_y(e_size)))
            
            if enemy_key == "ancient_dragon":
                draw_x -= scale_x(48); draw_y -= scale_y(48)
                
            # Apply Flashes/Effects
            if enemy["current_hp"] <= 0:
                sprite = sprite.copy()
                sprite.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif enemy.get('flash_frames', 0) > 0:
                sprite = self.apply_flash_effect(sprite, enemy['flash_frames'], enemy.get('flash_type', 'damage'))

            screen.blit(sprite, (draw_x, draw_y))
            
            # HP Bar
            bar_x, bar_y = draw_x, draw_y - scale_y(20)
            draw_bar(screen, bar_x, bar_y, scale_x(80), scale_y(10), enemy["current_hp"], enemy["max_hp"], (200, 50, 50), self.font)
            
            # Enemy Resources
            current_bar_y = bar_y
            if enemy.get('max_mp', 0) > 0 and (len(enemy.get('spells', [])) > 0):
                current_bar_y += scale_y(12)
                draw_bar(screen, bar_x, current_bar_y, scale_x(80), scale_y(8), enemy.get('current_mp', 0), enemy['max_mp'], COLOR_BLUE, self.font)
            
            if enemy.get('max_sp', 0) > 0 and (len(enemy.get('skills', [])) > 0):
                current_bar_y += scale_y(10)
                draw_bar(screen, bar_x, current_bar_y, scale_x(80), scale_y(8), enemy.get('current_sp', 0), enemy['max_sp'], COLOR_YELLOW, self.font)

            # Turn Indicator
            if self.current_actor is enemy:
                pygame.draw.polygon(screen, (255, 255, 0), [(bar_x + scale_x(30), bar_y - scale_y(15)), (bar_x + scale_x(50), bar_y - scale_y(15)), (bar_x + scale_x(40), bar_y - scale_y(5))])

        if self.phase == "PLAYER_TURN" and not self.dialogue.current_message:
            self.active_menu.draw(screen, 400, 500)

        self.dialogue.draw(screen)
        self.float_mgr.draw(screen)

    def apply_flash_effect(self, sprite, frames, flash_type):
        """Helper to apply grayscale/red flash effects to a sprite."""
        new_sprite = sprite.copy()
        
        if flash_type == 'damage':
            # Flash between normal and grayscale every 6 frames
            if (frames // 6) % 2 == 1:
                try:
                    # Pygame CE check
                    return pygame.transform.grayscale(new_sprite)
                except AttributeError:
                    # Fallback tint
                    new_sprite.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
        
        elif flash_type == 'crit':
            # Cycle: Normal -> Grayscale -> Red -> Normal... every 4 frames
            cycle = (frames // 4) % 3
            if cycle == 1:
                try:
                    return pygame.transform.grayscale(new_sprite)
                except AttributeError:
                    new_sprite.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif cycle == 2:
                new_sprite.fill((255, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
        
        return new_sprite

