import pygame
import random
import os
import copy
import json

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
from interfaces.pygame.ui.dice_animation import DiceAnimation
from core.game_rules.path_utils import get_resource_path


class CombatState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_combat_bg()

        self.dialogue = DialogueBox(self.font)
        self.float_mgr = FloatingTextManager()
        self.dice_anim = DiceAnimation()

        self.party = game.party # All members
        self.enemies = game.enemies
        
        # --- Position Party Members ---
        sorted_party = sorted(self.party, key=lambda p: p.get('max_hp', 10), reverse=True)
        self.party_positions = {}
        for i, p in enumerate(sorted_party):
            col_idx = 2 - i
            base_x = scale_x(20) + (col_idx * scale_x(60))
            base_y = SCREEN_HEIGHT // 2 - scale_y(100) + (i * scale_y(50))
            p['screen_pos'] = (base_x + scale_x(48), base_y + scale_y(10))
            self.party_positions[id(p)] = (base_x, base_y)

        # --- Format Enemy Names ---
        name_counts = {}
        for e in self.enemies:
            e["enemy_type"] = e.get('base_name', e.get('name', 'enemy').lower().replace(' ', '_'))
            base_display_name = e.get('base_name', e['name']).replace('_', ' ').title()
            name_counts[base_display_name] = name_counts.get(base_display_name, 0) + 1
            
        name_trackers = {}
        for e in self.enemies:
            base_display_name = e.get('base_name', e['name']).replace('_', ' ').title()
            if name_counts[base_display_name] > 1:
                instance_idx = name_trackers.get(base_display_name, 0)
                suffix = f" {chr(65 + instance_idx)}"
                e["name"] = base_display_name + suffix
                name_trackers[base_display_name] = instance_idx + 1
            else:
                e["name"] = base_display_name

        # --- Set Screen Positions (3 Columns) ---
        self.column_x = [
            SCREEN_WIDTH - scale_x(460), # Column 0 (Summon Column)
            SCREEN_WIDTH - scale_x(320), # Column 1 (Minion Column)
            SCREEN_WIDTH - scale_x(180)  # Column 2 (Leader/Boss Column)
        ]
        
        leader_unit = next((e for e in self.enemies if e.get('is_leader')), None)
        minions = [e for e in self.enemies if not e.get('is_leader')]

        if leader_unit:
            # Boss Fight: Minions in col 1 (max 4), then overflow minions in col 2
            for i, m in enumerate(minions):
                if i < 4:
                    enemy_x = self.column_x[1] + (i * scale_x(20))
                    enemy_y = SCREEN_HEIGHT // 2 - scale_y(150) + (i * scale_y(80))
                    m['_combat_column'] = 1
                else:
                    # Extra minions in leader column (above/below leader)
                    extra_idx = i - 4
                    direction = -1 if extra_idx % 2 == 0 else 1
                    offset = ((extra_idx // 2) + 1) * scale_y(120)
                    enemy_x = self.column_x[2] + scale_x(20)
                    enemy_y = (SCREEN_HEIGHT // 2 - scale_y(60)) + (direction * offset)
                    m['_combat_column'] = 2
                
                m['_combat_pos'] = (enemy_x, enemy_y)
                m['screen_pos'] = (enemy_x + scale_x(62), enemy_y + scale_y(20))
            
            # Position Leader in center of Col 2
            enemy_x = self.column_x[2]
            enemy_y = SCREEN_HEIGHT // 2 - scale_y(60)
            leader_unit['_combat_pos'] = (enemy_x, enemy_y)
            leader_unit['screen_pos'] = (enemy_x + scale_x(62), enemy_y + scale_y(20))
            leader_unit['_combat_column'] = 2
        else:
            # Standard Fight: Split minions between minion and leader columns (max 4 each)
            for i, m in enumerate(minions):
                col_idx = i // 4
                row_idx = i % 4
                target_x = self.column_x[col_idx + 1] # Offset by 1 to leave Col 0 for summons
                
                enemy_x = target_x + (row_idx * scale_x(20))
                enemy_y = SCREEN_HEIGHT // 2 - scale_y(150) + (row_idx * scale_y(80))
                
                m['_combat_pos'] = (enemy_x, enemy_y)
                m['screen_pos'] = (enemy_x + scale_x(62), enemy_y + scale_y(20))
                m['_combat_column'] = col_idx + 1

        # Sort enemies so leader is drawn last (top-most layer)
        self.enemies.sort(key=lambda x: x.get('is_leader', False))

        # --- Setup Combatants ---
        for p in self.party:
            buff = p.get('hp_buff', 0)
            p['max_hp_combat'] = int(p.get("max_hp", 10)) + buff
            p['current_hp'] = min(p['max_hp_combat'], int(p.get("current_hp", p.get("hp", 10))) + buff)
            p.setdefault("conditions", {})

        for e in self.enemies:
            e["current_hp"] = int(e.get("current_hp", e.get("hp", 10)))
            e["max_hp"] = int(e.get("hp", 10))
            lvl = e.get('level', 1)
            e["max_sp"] = 10
            e["current_sp"] = (lvl + 3) // 4
            e["max_mp"] = 10
            e["current_mp"] = (lvl + 3) // 4
            e["heal_available"] = True
            e["summon_alive"] = False
            e.setdefault("conditions", {})
            
            enemy_type = e.get("enemy_type", e.get("name", "enemy").lower().replace(" ", "_"))
            filenames = SpriteManager._enemy_mapping.get(enemy_type, [])
            if filenames: e["sprite_filename"] = random.choice(filenames)
            else: e["sprite_filename"] = f"{enemy_type}.png"

        # --- Data & Ability Registry ---
        self.consumables_db = load_consumables()
        self._raw_spells_db = load_spells()
        self._raw_skills_db = load_skills()
        self.ability_registry = {} # actor_id -> { ability_name -> resolved_data }
        self._initialize_actor_abilities()

        # --- Combat State ---
        self.player_advantage = 0
        self.enemy_advantage = 0
        self.extra_damage_once = 0
        self.original_attack_count = None
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
        self.summons = {} # Map of owner_id -> summon_actor
        self.attacks_made = 0
        self.ability_hits_made = 0

        names = ", ".join([e["name"] for e in self.enemies])
        self.queue_message(f"Encountered: {names}!")
        self.start_next_message()

    def _initialize_actor_abilities(self):
        all_participants = self.party + self.enemies
        for actor in all_participants:
            self._register_actor_abilities(actor)

    def _register_actor_abilities(self, actor):
        actor_id = id(actor)
        self.ability_registry[actor_id] = {}
        ability_names = list(set(actor.get('skills', []) + actor.get('spells', [])))
        from core.combat.enemy_ai import EnemyAI
        for name in ability_names:
            raw_data = EnemyAI.get_ability_data(name)
            if not raw_data: continue
            baked_data = copy.deepcopy(raw_data)
            res = CombatEngine.resolve_ability(baked_data, actor, [actor], skip_cost=False)
            baked_data['cost'] = res['mana_cost']
            baked_data['level'] = res['mana_cost']
            self.ability_registry[actor_id][name.lower().replace(' ', '_')] = baked_data

    @property
    def current_actor(self):
        if not self.turn_order: return None
        return self.turn_order[self.turn_index]

    def get_living_players(self):
        living = [p for p in self.party if p.get('current_hp', 0) > 0]
        summons = [s for s in self.summons.values() if not s.get('is_enemy_summon') and s.get('current_hp', 0) > 0]
        return living + summons

    def get_living_enemies(self):
        living = [e for e in self.enemies if e.get('current_hp', 0) > 0]
        summons = [s for s in self.summons.values() if s.get('is_enemy_summon') and s.get('current_hp', 0) > 0]
        return living + summons

    def handle_summon(self, owner, ability_data):
        try:
            raw_types = ability_data.get('summon_type', 'wolf')
            summon_types = raw_types if isinstance(raw_types, list) else [raw_types]
            owner_id = id(owner)
            is_enemy = any(id(owner) == id(e) for e in self.enemies)
            prof = int(owner.get('proficiency_bonus', 0))
            total_level = sum(owner.get('class_levels', {}).values()) if owner.get('class_levels') else owner.get('level', 1)
            mp_val = int(owner.get('standby_mp', owner.get('current_mp', 0)))
            sp_val = int(owner.get('standby_sp', owner.get('current_sp', 0)))
            placeholders = {
                "{damage_die}": str(owner.get('damage_die', owner.get('die', 4))),
                "{level}": str(total_level),
                "{level/2}": str(total_level // 2),
                "{prof}": str(prof),
                "{current_mp}": str(mp_val),
                "{current_mp/2}": str(mp_val // 2),
                "{current_sp}": str(sp_val),
                "{current_sp/2}": str(sp_val // 2)
            }
            context = {'level': total_level, 'prof': prof, 's_level': total_level, 's_prof': prof, 's_name': owner['name']}
            raw_count = ability_data.get('summon_count', 1)
            summon_count = 1
            if isinstance(raw_count, str):
                try:
                    resolved = CombatEngine._resolve_math(raw_count, placeholders)
                    if not resolved.isdigit():
                        formula = raw_count.format(**context)
                        summon_count = max(1, int(eval(formula, {"__builtins__": None}, context)))
                    else: summon_count = max(1, int(resolved))
                except: summon_count = 1
            else: summon_count = int(raw_count)

            to_remove = [sid for sid, s in self.summons.items() if s.get('owner_id') == owner_id]
            for sid in to_remove:
                old_summon = self.summons[sid]
                if old_summon in self.turn_order: self.turn_order.remove(old_summon)
                del self.summons[sid]

            summons_db = {}
            try:
                path = get_resource_path(os.path.join('data', 'combat', 'summons.json'))
                with open(path, 'r') as f: summons_db = json.load(f)
            except: return

            summons_created = []
            for s_type in summon_types:
                data = summons_db.get(s_type)
                if not data: continue
                for i in range(summon_count):
                    name = data.get('name_template', "{owner_name}'s Summon").format(**context)
                    if summon_count > 1: name = f"{name} {chr(65+i)}"
                    
                    # Determine sprite folder and category
                    json_folder = data.get('sprite_folder')
                    if json_folder:
                        folder = json_folder
                    elif not is_enemy:
                        folder = os.path.join("assets", "sprites", "player_sprites", "summons")
                    else:
                        folder = os.path.join("assets", "sprites", "enemy_images", "summons")
                    
                    category = "humanoid"
                    if "enemy_images" in folder:
                        f_path = folder.replace("\\", "/")
                        parts = f_path.split("/")
                        try:
                            idx = parts.index("enemy_images")
                            if idx + 1 < len(parts):
                                category = parts[idx+1]
                        except: pass
                    elif "player_sprites" in folder and "summons" not in folder:
                        category = "player"

                    summon = {
                        'name': name, 'is_summon': True, 'owner_id': owner_id, 'is_enemy_summon': is_enemy,
                        'conditions': {}, 'enemy_type': s_type, 
                        'sprite_filename': random.choice(data.get('sprites', ['default.png'])),
                        'sprite_folder': folder,
                        'sprite_category': category,
                        'inventory_ref': owner.get('inventory_ref', {})
                    }
                    raw_stats = data.get('stats', {})
                    for stat, val in raw_stats.items():
                        if isinstance(val, str):
                            # Always attempt to resolve and evaluate
                            resolved = val.format(**context)
                            try:
                                # Safe eval for math expressions
                                if any(c in resolved for c in "+-*/()"):
                                    summon[stat] = int(eval(resolved, {"__builtins__": None}, {}))
                                else:
                                    # Simple integer conversion
                                    summon[stat] = int(resolved)
                            except:
                                summon[stat] = resolved # Keep as string (e.g. dice "2d6")
                        else:
                            summon[stat] = val
                    
                    summon['max_hp'] = int(summon.get('hp', 10))
                    summon['current_hp'] = summon['max_hp']
                    
                    # Initialize resources based on summoner proficiency
                    summon['max_mp'] = 10
                    summon['current_mp'] = prof // 2
                    summon['max_sp'] = 10
                    summon['current_sp'] = prof // 2
                    
                    prev = summons_created[-1] if summons_created else owner
                    if prev in self.turn_order:
                        idx = self.turn_order.index(prev)
                        self.turn_order.insert(idx + 1, summon)
                    summons_created.append(summon)

            for i, summon in enumerate(summons_created):
                if not is_enemy:
                    owner_pos = self.party_positions.get(owner_id, (scale_x(100), scale_y(100)))
                    col = i // 2; row = i % 2
                    offset_x = scale_x(140 + col * 60); offset_y = scale_y(50 + row * 60)
                    summon_pos = (owner_pos[0] + offset_x, owner_pos[1] + offset_y)
                    summon['screen_pos'] = (summon_pos[0] + scale_x(48), summon_pos[1] + scale_y(10))
                    self.party_positions[id(summon)] = summon_pos
                else:
                    active_enemy_summons = [s for s in self.summons.values() if s.get('is_enemy_summon')]
                    total_idx = len(active_enemy_summons) + i
                    row = total_idx % 4; col = total_idx // 4
                    base_enemy_x = SCREEN_WIDTH - scale_x(420) - (col * scale_x(100))
                    stagger = scale_x(40) if row % 2 == 0 else 0
                    summon_x = base_enemy_x - stagger
                    summon_y = SCREEN_HEIGHT // 2 - scale_y(150) + (row * scale_y(90))
                    summon['screen_pos'] = (summon_x + scale_x(62), summon_y + scale_y(20))
                    self.party_positions[id(summon)] = (summon_x, summon_y)
                    summon['_combat_column'] = 0 # Enemy summons go in the leftmost column
                self.summons[id(summon)] = summon
            if summons_created:
                owner['summon_alive'] = True
                self.queue_message(f"{owner['name']} summoned {len(summons_created)} creature(s)!")
        except Exception as e: print(f"Error in handle_summon: {e}")

    def on_select(self, option):
        if self.menu_state == "MAIN": self.handle_main_menu(option)
        elif self.menu_state == "SPELL": self.handle_spell_menu(option)
        elif self.menu_state == "SKILL": self.handle_skill_menu(option)
        elif self.menu_state == "ITEM": self.handle_item_menu(option)
        elif self.menu_state == "TARGETING": self.handle_targeting(option)
        elif self.menu_state == "TARGET_COLUMN": self.handle_target_column(option)

    def update(self, events):
        self.float_mgr.update()
        self.dice_anim.update()
        for actor in self.party + self.enemies:
            if actor.get('flash_frames', 0) > 0: actor['flash_frames'] -= 1
        if self.dialogue.current_message:
            if self.active_attacker:
                is_player = any(self.active_attacker is p for p in self.party)
                direction = 1 if is_player else -1
                self.attacker_offset = scale_x(20) * direction
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)
                    if not was_typing and not self.dialogue.current_message:
                        # --- Trigger Dice AFTER Phase 1 Dialogue ---
                        pending = getattr(self, '_pending_dice_result', None)
                        if pending and pending.get('trigger_dice_after'):
                            res = pending['res']; targets = pending['target']
                            is_aoe = isinstance(targets, list); targets_list = targets if is_aoe else [targets]
                            
                            rolls = []
                            saves_info = res.get('saves_info', {})
                            for t in targets_list:
                                info = saves_info.get(id(t))
                                if info: rolls.append((info['roll'], t['screen_pos']))
                            
                            self.dice_anim.start_multi_roll(rolls, pending['actor'].get('dice_style', 'gothic'))
                            self.dice_anim.stay_settled = True
                            pending['trigger_dice_after'] = False # Dice triggered, proceed to normal settlement flow
                            return # Let dice animation take over

                        self.active_attacker = None
                        self.attacker_offset = 0
                        if self.message_queue: self.start_next_message()
                        elif self.phase == "END_COMBAT": self.exit_to_hub()
                        elif self.phase == "LEVEL_UP":
                            from interfaces.pygame.states.level_up import LevelUpState
                            self.game.change_state(LevelUpState(self.game, self.font, player=getattr(self, '_levelup_starter', None)))
            return
        if self.dice_anim.is_active:
            # Check if animation is ready to progress even if still fading
            is_finalized = getattr(self.dice_anim, 'is_result_finalized', False)
            
            # ALLOW advancement if stayed settled
            if self.dice_anim.state == "SETTLED" and self.dice_anim.stay_settled:
                for event in events:
                    if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                        self.dice_anim.stay_settled = False
                        self.dice_anim.timer = 0 # Force immediate transition to FADING
            
            if is_finalized:
                # Progress game while die is fading
                self._waiting_for_dice = True
            else:
                return # Keep waiting

        if getattr(self, '_waiting_for_dice', False):
            self._waiting_for_dice = False
            
            # Retrieve held data from dice roll
            pending = getattr(self, '_pending_dice_result', None)
            if pending:
                actor = pending['actor']; target = pending['target']; res = pending['res']
                is_aoe = isinstance(target, list); targets_list = target if is_aoe else [target]
                
                if pending.get('is_save'):
                    # PHASE 2: Results Dialogue
                    self._save_dialogue_phase = 1
                    results = self.format_combat_message(res, actor, target)
                    self.queue_message(results)
                    self._save_dialogue_phase = 0 # Reset
                    
                    # PHASE 3: Prepare Floating Animations (Sequenced with delays)
                    saves_info = res.get('saves_info', {})
                    for t in targets_list:
                        info = saves_info.get(id(t))
                        if info:
                            # 1. SAVE/FAIL appears first
                            self.float_mgr.add("SAVE" if info['success'] else "FAIL", t['screen_pos'], color_key="save" if info['success'] else "fail")
                            
                            # 2. Damage appears with delay
                            dmg = res.get('damage_by_target', {}).get(id(t), 0)
                            if dmg > 0:
                                self.float_mgr.add(f"-{dmg}", t['screen_pos'], color_key="damage", delay=60)
                            
                            t['flash_frames'] = 36
                            t['flash_type'] = 'damage'

                    # 3. Status Effect appears last
                    for effect, val in res.get('effects', []):
                        if effect not in ['dot', 'heal_attacker', 'extra_dmg']:
                            # Display effect name on first failed target
                            first_failed = next((t for t in targets_list if not saves_info.get(id(t), {}).get('success', True)), None)
                            if first_failed:
                                self.float_mgr.add(effect.upper(), first_failed['screen_pos'], color_key="effect", delay=120)
                else:
                    msg = pending.get('msg', "Action resolved.")
                    
                    # Floating Text & Flashes
                    if res.get('hit') or res.get('damage', 0) > 0:
                        for t in targets_list:
                            tid = id(t)
                            dmg = res.get('damage_by_target', {}).get(tid, res.get('damage', 0))
                            is_crit = res.get('critical', False)
                            
                            if dmg > 0:
                                self.float_mgr.add(f"-{dmg}", t['screen_pos'], color_key="crit" if is_crit else "damage")
                            
                            t['flash_frames'] = 36
                            t['flash_type'] = 'crit' if is_crit else 'damage'
                    elif not res.get('hit'):
                        for t in targets_list:
                            self.float_mgr.add("Miss", t['screen_pos'], color_key="miss")
                    
                    self.queue_message(msg)
                
                # Effects
                if self.pending_action == "ATTACK":
                    self.apply_attack_effects(res, target if not is_aoe else target[0])
                else:
                    self.apply_ability_effects(res, targets_list, actor)

                del self._pending_dice_result

            self.start_next_message()
            
            if hasattr(self, '_pending_dice_followup'):
                followup = self._pending_dice_followup
                del self._pending_dice_followup
                followup()
            return
        if self.phase == "INITIATIVE": 
            self.handle_initiative()
        if self.phase == "TURN_START": 
            self.process_turn_start()
        
        if self.phase == "PLAYER_TURN": 
            super().update(events)
        elif self.phase == "ENEMY_TURN": 
            self.handle_enemy_turn()
            # If enemy turn finished, potentially transition to next phase in same frame
            if self.phase != "ENEMY_TURN":
                self.update(events) # Recurse once to catch transition
        elif self.phase == "CHECK_END": 
            self.check_combat_end()
            if self.phase != "CHECK_END":
                self.update(events) # Catch transition to TURN_START or VICTORY
        elif self.phase == "RESOLVE_VICTORY":
            if not self.dialogue.current_message and not self.message_queue:
                self.handle_victory()
                self.start_next_message()

    def handle_initiative(self):
        combatants = []
        for p in self.party:
            roll = random.randint(1, 20) + int(p.get("proficiency_bonus", 0)) + int(p.get("initiative_boost", 0))
            combatants.append({'actor': p, 'init': roll, 'is_player': True})
        for e in self.enemies:
            roll = random.randint(1, 20) + (int(e.get("proficiency_bonus", 0)) // 2) + int(e.get("initiative_boost", 0))
            combatants.append({'actor': e, 'init': roll, 'is_player': False})
        def sort_key(c):
            hp = c['actor'].get('current_hp', c['actor'].get('hp', 0))
            return (-c['init'], hp, c['actor'].get('name', ''))
        combatants.sort(key=sort_key)
        self.turn_order = [c['actor'] for c in combatants]
        self.turn_index = 0
        self.queue_message("Turn Order: " + " > ".join([a['name'] for a in self.turn_order]))
        self.phase = "TURN_START"; self.start_next_message()

    def process_turn_start(self):
        actor = self.current_actor
        if actor['current_hp'] <= 0:
            if actor.get('is_summon'):
                if id(actor) in self.summons:
                    owner_id = actor.get('owner_id')
                    del self.summons[id(actor)]
                    owner_has_more = any(s.get('owner_id') == owner_id for s in self.summons.values())
                    if not owner_has_more:
                        for p_o in self.party + self.enemies:
                            if id(p_o) == owner_id: p_o['summon_alive'] = False; break
            self.phase = "CHECK_END"; self.start_next_message(); return
        conds = actor.get('conditions', {})
        from core.combat.attack_roller import roll_dice
        dots = conds.get('dots', {})
        if dots:
            total_dmg = 0; applied = []; expired = []
            for name, (dice, dur) in dots.items():
                dmg = roll_dice(dice); total_dmg += dmg; applied.append(name)
                if dur > 1: dots[name] = (dice, dur - 1)
                else: expired.append(name)
            if total_dmg > 0:
                actor['current_hp'] = max(0, actor['current_hp'] - total_dmg)
                self.queue_message(f"{actor['name']} took {total_dmg} DOT damage from {', '.join(applied)}.")
                actor['flash_frames'] = 36; actor['flash_type'] = 'damage'
            for name in expired: del dots[name]
        hots = conds.get('hots', {})
        if hots:
            total_heal = 0; applied = []; expired = []
            for name, (dice, dur) in hots.items():
                heal = roll_dice(dice); total_heal += heal; applied.append(name)
                if dur > 1: hots[name] = (dice, dur - 1)
                else: expired.append(name)
            if total_heal > 0:
                max_hp = actor.get('max_hp_combat', actor.get('max_hp', 10))
                actor['current_hp'] = min(max_hp, actor['current_hp'] + total_heal)
                self.queue_message(f"{actor['name']} regained {total_heal} HP from {', '.join(applied)}.")
            for name in expired: del hots[name]
        expired_conds = []
        for cond, duration in conds.items():
            if cond in ['dots', 'hots', 'stunned']: continue
            if isinstance(duration, int) and duration > 0:
                conds[cond] -= 1
                if conds[cond] <= 0: expired_conds.append(cond)
            elif isinstance(duration, (list, tuple)) and len(duration) > 1:
                val, dur = duration
                if isinstance(dur, int) and dur > 0:
                    new_dur = dur - 1
                    if new_dur <= 0: expired_conds.append(cond)
                    else: conds[cond] = (val, new_dur)
        for cond in expired_conds:
            del conds[cond]; self.queue_message(f"{actor['name']}'s {cond.title()} effect faded.")
        is_p = any(actor is p for p in self.party); is_ps = actor.get('is_summon') and not actor.get('is_enemy_summon')
        
        # All actors (Players, Summons, Enemies) regenerate 1 SP/MP per turn if they have a max set
        for res in ["sp", "mp"]:
            mx = actor.get(f"max_{res}", 0)
            if mx > 0: actor[f"current_{res}"] = min(mx, actor.get(f"current_{res}", 0) + 1)
            
        if actor['current_hp'] <= 0:
            self.queue_message(f"{actor['name']} is defeated!"); self.phase = "CHECK_END"; self.start_next_message(); return
        if int(conds.get('stunned', 0)) > 0:
            self.queue_message(f"{actor['name']} is stunned!"); conds['stunned'] = int(conds['stunned']) - 1
            if int(conds['stunned']) <= 0: del conds['stunned']
            self.phase = "CHECK_END"; self.start_next_message(); return
        actor['standby_mp'] = actor.get('current_mp', 0)
        actor['standby_sp'] = actor.get('current_sp', 0)
        self._register_actor_abilities(actor)
        if is_p or is_ps: self.phase = "PLAYER_TURN"; self.setup_player_menu(actor)
        else: self.phase = "ENEMY_TURN"; self.setup_enemy_turn(actor)

    def setup_player_menu(self, actor):
        options = ["Attack"]
        if actor.get("skills"): options.append("Skill")
        if actor.get("spells") or actor.get("class") in ["wizard", "druid", "alchemist", "sorcerer", "cleric"]: options.append("Spell")
        options.append("Item")
        if not actor.get('is_summon'): options.append("Run")
        self.main_menu = Menu(options, self.font, header=f"{actor['name']}'s Turn", pos=(400, 480))
        self.menu_state = "MAIN"; self.active_menu = self.main_menu
        self.attacks_made = 0; self.ability_hits_made = 0

    def setup_enemy_turn(self, actor):
        self.attacks_made = 0; self.ability_hits_made = 0; self.pending_action = None; self.action_data = None

    def format_effects(self, res, attacker_name, target_name):
        from core.combat.combat_engine import get_advantage_desc
        parts = []
        for effect, val in res.get('effects', []):
            is_buff = effect.lower() in ['vex', 'swift', 'advantage', 'invisible', 'lifesteal', 'player_advantage', 'heal_attacker', 'extra_dmg', 'hot']
            subject = attacker_name if is_buff else target_name
            disp = effect.replace('_', ' ').title()
            if effect in ['player_advantage', 'enemy_advantage']: disp, _ = get_advantage_desc(val)
            elif effect == 'dot': disp = "Lingering Damage"
            elif effect == 'hot': disp = "Regeneration"
            parts.append(f"{disp} applied to {subject}.")
        return " ".join(parts)

    def format_combat_message(self, res, actor, target):
        attacker_name = actor.get('name', 'Attacker')
        is_aoe = isinstance(target, list); targets_list = target if is_aoe else [target]
        
        # --- Handle Save Type flow (PHASE-BASED) ---
        saves_info = res.get('saves_info', {})
        if saves_info:
            # PHASE 1: Initial Challenge
            if not getattr(self, '_save_dialogue_phase', 0):
                first_tid = list(saves_info.keys())[0]
                dc = saves_info[first_tid].get('dc', 10)
                target_name = "Party" if is_aoe else targets_list[0]['name']
                return f"{attacker_name} used {res.get('ability_name', 'Ability')} on {target_name}. Roll a {dc} or higher to make your save."

            # PHASE 2: Results building
            if self._save_dialogue_phase == 1:
                results_msgs = []
                for t in targets_list:
                    info = saves_info.get(id(t))
                    if not info: continue
                    
                    msg = f"{t['name']} rolled a {info['roll']}. "
                    if info['success']:
                        msg += "SAVED!"
                        dmg = res.get('damage_by_target', {}).get(id(t), 0)
                        if dmg > 0: msg += " Take half damage"
                        
                        # Effects check
                        has_eff = any(e[0] not in ['dot', 'heal_attacker', 'extra_dmg'] for e in res.get('effects', []))
                        if has_eff: msg += f" and resist {res.get('effects', [['effect']])[0][0].replace('_',' ').title()}!"
                        else: msg += "."
                    else:
                        msg += "FAILED!"
                    
                    results_msgs.append(msg)
                
                return results_msgs

        if self.pending_action == "ATTACK": prefix = f"{attacker_name} is attacking, .."
        elif self.pending_action and (self.pending_action.startswith("SPELL") or self.pending_action.startswith("SKILL") or self.pending_action == "ABILITY"):
            prefix = f"{attacker_name} used {res.get('ability_name', 'Ability')}, .."
        elif self.pending_action and self.pending_action.startswith("ITEM"):
            prefix = f"{attacker_name} used {res.get('item_name', 'Item')} on {targets_list[0].get('name', 'Target')}, .."
        else: prefix = f"{attacker_name} acts, .."
        
        if self.pending_action and self.pending_action.startswith("ITEM"):
            for res_type in ['hp', 'mana', 'stamina']:
                if res.get(f'{res_type}_gain', 0) > 0: return f"{prefix} restoring {res[f'{res_type}_gain']} {res_type.upper().replace('MANA','MP').replace('STAMINA','SP')}."
            return f"{prefix} it worked."

        if res.get('healing', 0) > 0 and res.get('damage', 0) <= 0: return f"{prefix} restoring {res['healing']} HP."
        status = "Hit!" if res.get('hit') else "Miss."
        if res.get('critical'): status = "CRITICAL Hit!"
        
        if 'roll' in res and 'attack_bonus' in res:
            body = f"{attacker_name} attacked with a {res['total_roll']}. {status}"
        else: body = f"{attacker_name} attacked {targets_list[0]['name'] if not is_aoe else 'everyone'} and {status}"
        
        if res.get('hit'):
            if res.get('damage', 0) > 0: body += f", dealing {res['damage']} damage."
            eff = self.format_effects(res, attacker_name, targets_list[0]['name'] if not is_aoe else 'everyone')
            if eff: body += f" {eff}"
        return f"{prefix} {body}"

    def process_action_result(self, actor, target, res):
        is_p = any(actor is p for p in self.party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))
        saves_info = res.get('saves_info', {})
        
        if saves_info:
            # PHASE 1: Initial Challenge
            self._save_dialogue_phase = 0
            msg = self.format_combat_message(res, actor, target)
            
            # Store result for visuals later, including flag to trigger dice AFTER this message
            self._pending_dice_result = {
                'actor': actor,
                'target': target,
                'res': res,
                'is_save': True,
                'trigger_dice_after': True # NEW FLAG
            }
            
            # Queue message and start it - will wait for player before moving to Phase 2 (dice)
            self.queue_message(msg)
            self.start_next_message()
            return True

        msg = self.format_combat_message(res, actor, target)
        roll_val = res.get('roll')
            
        if roll_val is not None and is_p:
            self.dice_anim.start_roll(roll_val, actor.get('dice_style', 'gothic'))
            self.dice_anim.stay_settled = True
            # Store the full result to process visuals later
            self._pending_dice_result = {
                'actor': actor,
                'target': target,
                'res': res,
                'msg': msg
            }
            return True
            
        self.queue_message(msg); return False

    def handle_enemy_turn(self):
        actor = self.current_actor
        from core.combat.enemy_ai import EnemyAI
        if self.attacks_made == 0 and self.ability_hits_made == 0:
            action = EnemyAI.decide_action(actor, summons=self.summons.values())
            self.pending_action = "ATTACK" if action['type'] == 'attack' else "ABILITY"
            self.action_data = action.get('name') if action['type'] == 'ability' else None
            self._enemy_current_action = action
        else: action = self._enemy_current_action
        player_side = self.get_living_players()
        if action['type'] == 'ability':
            if action['data'].get('type') == 'heal': targets = [actor]
            elif action['data'].get('aoe'): targets = player_side
            else:
                t = EnemyAI.pick_target(actor, player_side, action['data'])
                if not t: self.phase = "CHECK_END"; return
                targets = [t]
        else:
            t = EnemyAI.pick_target(actor, player_side)
            if not t: self.phase = "CHECK_END"; return
            targets = [t]
        is_aoe = action.get('data', {}).get('aoe', False)
        t_obj = targets if is_aoe else targets[0]
        res = self.execute_action(actor, t_obj)
        is_anim = self.process_action_result(actor, t_obj, res)
        should_end = True
        mx_atk = int(actor.get('attack_count', 1))
        if any(p['current_hp'] > 0 for p in player_side):
            if action['type'] == 'attack':
                self.attacks_made += 1
                if self.attacks_made < mx_atk: should_end = False
            elif action['type'] == 'ability' and action['data'].get('use_attack_count'):
                self.ability_hits_made += 1
                if self.ability_hits_made < mx_atk: should_end = False
        if should_end:
            if self.original_attack_count is not None: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
        else: self.phase = "ENEMY_TURN"
        if not is_anim: self.start_next_message()

    def apply_ability_effects(self, res, targets, actor=None):
        failed_map = res.get('failed_saves_by_target', {})
        name = res.get('ability_name', 'Ability').title()
        source = actor if actor else self.current_actor
        for effect, val in res['effects']:
            for t in targets:
                if failed_map.get(id(t), 0) > 0 or not res.get('saves_info'):
                    if effect == 'stunned': t['conditions']['stunned'] = val
                    elif effect == 'taunted': t['conditions']['taunted'] = (id(source), val)
                    elif effect == 'dot':
                        if 'dots' not in t['conditions']: t['conditions']['dots'] = {}
                        t['conditions']['dots'][name] = val
                    elif effect == 'hot':
                        if 'hots' not in t['conditions']: t['conditions']['hots'] = {}
                        t['conditions']['hots'][name] = val
                    elif effect == 'heal_attacker':
                        mx = source.get('max_hp_combat', source.get('max_hp', 10))
                        source['current_hp'] = min(mx, source['current_hp'] + val)

    def apply_attack_effects(self, res, target):
        for effect, val in res['effects']:
            if effect == 'stunned': target['conditions']['stunned'] = val
            elif effect == 'poisoned': target['conditions']['poisoned'] = val
            elif effect == 'vex': self.current_actor['conditions']['advantage'] = val
            elif effect == 'sap': target['conditions']['disadvantage'] = val
            elif effect == 'dot':
                if 'dots' not in target['conditions']: target['conditions']['dots'] = {}
                # Use weapon name or a generic name for the DOT
                name = self.current_actor.get('weapon', 'Poison')
                target['conditions']['dots'][name] = val
            elif effect == 'heal_attacker':
                mx = self.current_actor.get('max_hp_combat', self.current_actor.get('max_hp', 10))
                self.current_actor['current_hp'] = min(mx, self.current_actor['current_hp'] + val)

    def handle_main_menu(self, option):
        actor = self.current_actor
        if option == "Attack": self.start_targeting("ATTACK")
        elif option == "Spell":
            spells = actor.get("spells", [])
            reg = self.ability_registry.get(id(actor), {})
            disabled = [i for i, s in enumerate(spells) if actor.get('current_mp', 0) < reg.get(s.lower().replace(' ', '_'), {}).get('cost', 1)]
            self.sub_menu = Menu([s.replace('_', ' ').title() for s in spells] + ["Back"], self.font, disabled_indices=disabled, header="Cast Spell")
            self.menu_state = "SPELL"; self.active_menu = self.sub_menu
        elif option == "Skill":
            skills = actor.get("skills", [])
            reg = self.ability_registry.get(id(actor), {})
            disabled = [i for i, s in enumerate(skills) if actor.get('current_sp', 0) < reg.get(s.lower().replace(' ', '_'), {}).get('cost', 1)]
            self.sub_menu = Menu([s.replace('_', ' ').title() for s in skills] + ["Back"], self.font, disabled_indices=disabled, header="Use Skill")
            self.menu_state = "SKILL"; self.active_menu = self.sub_menu
        elif option == "Item":
            items = [f"{n.replace('_',' ').title()} (x{c})" for n, c in actor.get("inventory_ref", {}).get("consumable", {}).items()]
            self.sub_menu = Menu(items + ["Back"], self.font, header="Use Item")
            self.menu_state = "ITEM"; self.active_menu = self.sub_menu
        elif option == "Run":
            if random.random() < 0.4: self.queue_message("Escaped!"); self.phase = "END_COMBAT"
            else: self.queue_message("Failed escape!"); self.phase = "CHECK_END"
            self.start_next_message()

    def handle_spell_menu(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            actor = self.current_actor; key = option.lower().replace(" ", "_")
            data = self.ability_registry.get(id(actor), {}).get(key)
            if not data: from core.combat.enemy_ai import EnemyAI; data = EnemyAI.get_ability_data(key)
            if actor.get('current_mp', 0) < data.get("cost", 0):
                self.queue_message("Not enough MP!"); self.start_next_message(); return
            if data.get('aoe'):
                self.pending_action = "SPELL"; self.action_data = option
                # Visual order: 1:Summons (L), 2:Minions (M), 3:Leader (R). Start highlighting Col 2.
                self.target_menu = Menu(["Column 1", "Column 2", "Column 3", "Back"], self.font, header="Target Column?", initial_selection=1)
                self.menu_state = "TARGET_COLUMN"; self.active_menu = self.target_menu
            elif data.get('type') == 'summon':
                ts = self.get_living_players()
                self.pending_action = "SPELL"; self.action_data = option
                res = self.execute_action(actor, ts)
                is_anim = self.process_action_result(actor, ts, res)
                if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
                self.phase = "CHECK_END"
                if not is_anim: self.start_next_message()
            elif data.get('type') == 'heal': self.start_targeting("SPELL_FRIENDLY", option)
            else: self.start_targeting("SPELL", option)

    def handle_skill_menu(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            actor = self.current_actor; key = option.lower().replace(" ", "_")
            data = self.ability_registry.get(id(actor), {}).get(key)
            if not data: from core.combat.enemy_ai import EnemyAI; data = EnemyAI.get_ability_data(key)
            if actor.get('current_sp', 0) < data.get("cost", 0):
                self.queue_message("Not enough SP!"); self.start_next_message(); return
            if data.get('aoe'):
                self.pending_action = "SKILL"; self.action_data = option
                # Visual order: 1:Summons (L), 2:Minions (M), 3:Leader (R). Start highlighting Col 2.
                self.target_menu = Menu(["Column 1", "Column 2", "Column 3", "Back"], self.font, header="Target Column?", initial_selection=1)
                self.menu_state = "TARGET_COLUMN"; self.active_menu = self.target_menu
            elif data.get('type') == 'summon':
                ts = self.get_living_players()
                self.pending_action = "SKILL"; self.action_data = option
                res = self.execute_action(actor, ts)
                is_anim = self.process_action_result(actor, ts, res)
                if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
                self.phase = "CHECK_END"
                if not is_anim: self.start_next_message()
            elif data.get('type') == 'heal': self.start_targeting("SKILL_FRIENDLY", option)
            else: self.start_targeting("SKILL", option)

    def handle_item_menu(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else: self.start_targeting("ITEM_FRIENDLY", option.split(" (x")[0])

    def handle_targeting(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            actor = self.current_actor; target = None
            if self.pending_action.endswith("_FRIENDLY"): target = next(t for t in self.get_living_players() if t['name'] == option)
            elif option.startswith("S. "): target = next(s for s in self.summons.values() if s['name'] == option[3:])
            else: target = self.enemies[int(option.split(".")[0]) - 1]
            res = self.execute_action(actor, target)
            is_anim = self.process_action_result(actor, target, res)
            should_end = True; mx_atk = int(actor.get('attack_count', 1))
            if any(e['current_hp'] > 0 for e in self.get_living_enemies()):
                if self.pending_action == "ATTACK":
                    self.attacks_made += 1
                    if self.attacks_made < mx_atk: should_end = False
                elif self.pending_action.startswith(("SPELL", "SKILL")):
                    reg = self.ability_registry.get(id(actor), {})
                    if reg.get(self.action_data.lower().replace(" ", "_"), {}).get('use_attack_count'):
                        self.ability_hits_made += 1
                        if self.ability_hits_made < mx_atk: should_end = False
            if should_end:
                if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
                self.phase = "CHECK_END"
                if not is_anim: 
                    self.start_next_message()
                    self.check_combat_end() # Process end immediately
            else:
                if is_anim: self._pending_dice_followup = lambda: self.start_targeting(self.pending_action, self.action_data)
                else: 
                    self.start_next_message()
                    self.start_targeting(self.pending_action, self.action_data)
                    super().update(events) # Process new menu immediately

    def execute_action(self, actor, target):
        self.active_attacker = actor; ability_data = None; reg = self.ability_registry.get(id(actor), {})
        if self.pending_action == "ABILITY" and hasattr(self, '_enemy_current_action'):
            ability_data = reg.get(self._enemy_current_action.get('name', '').lower().replace(' ', '_')) or self._enemy_current_action.get('data')
        elif self.pending_action.startswith(("SPELL", "SKILL", "ABILITY")):
            key = self.action_data.lower().replace(" ", "_")
            ability_data = reg.get(key)
            if not ability_data: from core.combat.enemy_ai import EnemyAI; ability_data = EnemyAI.get_ability_data(key)
        if ability_data and ability_data.get('aoe') and not isinstance(target, list):
            is_e = any(id(e) == id(actor) for e in self.enemies) or actor.get('is_enemy_summon')
            if ability_data.get('type') == 'heal': targets = self.get_living_enemies() if is_e else self.get_living_players()
            else: targets = self.get_living_players() if is_e else self.get_living_enemies()
        else: targets = target if isinstance(target, list) else [target]
        
        # Determine if we should suppress immediate visuals (attack rolls)
        is_player = any(actor is p for p in self.party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))
        # We only hold for player actions that involve a d20 roll
        should_hold = is_player and self.pending_action in ["ATTACK", "SPELL", "SKILL", "ABILITY"]

        if self.pending_action == "ATTACK":
            t = targets[0]
            # Calculate advantage/disadvantage
            adv = 0; conds = actor.get('conditions', {})
            if 'advantage' in conds: adv += 1
            if 'disadvantage' in conds: adv -= 1
            if 'poisoned' in conds: adv -= 1
            if 'blinded' in conds: adv -= 1
            adv = max(-1, min(1, adv))
            
            # --- Bestiary Crit Range Bonus ---
            e_type = t.get('enemy_type', t.get('name', 'enemy').lower().replace(' ', '_'))
            rp = self.game.bestiary_rp.get(e_type, 0)
            crit_range = [20]
            if rp >= 100: crit_range = [17, 18, 19, 20]
            elif rp >= 60: crit_range = [18, 19, 20]
            elif rp >= 20: crit_range = [19, 20]
            
            # Merge with actor's natural crit range
            if actor.get('crit_on_18'): crit_range = list(set(crit_range + [18, 19, 20]))
            elif actor.get('crit_on_19'): crit_range = list(set(crit_range + [19, 20]))
            
            # Pass float_mgr=None if holding to prevent immediate text
            res = CombatEngine.resolve_attack(actor, t, advantage=adv, float_mgr=None if should_hold else self.float_mgr, crit_range=crit_range)
            t['current_hp'] = max(0, t['current_hp'] - res['damage'])
            if not should_hold:
                if res['hit'] or res['damage'] > 0: t['flash_frames'] = 36; t['flash_type'] = 'crit' if res.get('critical') else 'damage'
                self.apply_attack_effects(res, t)
            return res
        if self.pending_action.startswith(("SPELL", "SKILL", "ABILITY")):
            if not ability_data: return {'hit': False, 'damage': 0, 'effects': [], 'msg': ["Missing data"]}
            is_first = self.ability_hits_made == 0
            override = ability_data.get("attack_count_override", ability_data.get("attack_count_overide"))
            if is_first and override is not None:
                self.original_attack_count = int(actor.get('attack_count', 1)); new_c = self.original_attack_count
                if isinstance(override, int): new_c = override
                elif isinstance(override, str):
                    o = override.strip()
                    if o.isdigit(): new_c = int(o)
                    elif len(o) > 1 and o[0] in '+-*/':
                        op = o[0]; v = int(o[1:])
                        if op == '*': new_c *= v
                        elif op == '/': new_c //= v if v else 1
                        elif op == '+': new_c += v
                        elif op == '-': new_c = max(1, new_c - v)
                actor['attack_count'] = max(1, int(new_c))
            
            # Pass float_mgr=None if holding
            res = CombatEngine.resolve_ability(ability_data, actor, targets, float_mgr=None if should_hold else self.float_mgr, skip_cost=not is_first)
            res['ability_name'] = ability_data.get('name', self.action_data)
            if is_first:
                # Use the resolved mana_cost from resolve_ability
                cost = res.get('mana_cost', 0)
                res_type = ability_data.get('resource', 'mp')
                actor[f"current_{res_type}"] = max(0, actor.get(f"current_{res_type}", 0) - cost)
                if ability_data.get('type') == 'summon': self.handle_summon(actor, ability_data)
            dmg_map = res.get('damage_by_target', {}); heal_map = res.get('healing_by_target', {}); hits_map = res.get('hits_by_target', {})
            for t in targets:
                tid = id(t); dmg = dmg_map.get(tid, 0); hit = hits_map.get(tid, 0) > 0
                if dmg > 0: t['current_hp'] = max(0, t['current_hp'] - dmg)
                if not should_hold:
                    if hit: t['flash_frames'] = 36; t['flash_type'] = 'damage'
                    heal = heal_map.get(tid, res['healing'] if len(targets) == 1 else 0)
                    if heal > 0: t['current_hp'] = min(t.get('max_hp_combat', t.get('max_hp', 10)), t['current_hp'] + heal)
            
            if not should_hold:
                self.apply_ability_effects(res, targets, actor)
            return res
        if self.pending_action.startswith("ITEM"):
            t = targets[0]; item_name = self.action_data; item_data = self.consumables_db.get(item_name.lower().replace(' ', '_'))
            res = CombatEngine.resolve_item(item_data, t)
            t['current_hp'] = min(t.get('max_hp_combat', t.get('max_hp', 10)), t['current_hp'] + res.get('hp_gain', 0))
            if t.get('max_mp', 0) > 0: t['current_mp'] = min(t['max_mp'], t.get('current_mp', 0) + res.get('mana_gain', 0))
            if t.get('max_sp', 0) > 0: t['current_sp'] = min(t['max_sp'], t.get('current_sp', 0) + res.get('stamina_gain', 0))
            from core.players.player_inventory import remove_item
            remove_item(self.game.player['inventory_ref'], item_name.lower().replace(' ', '_'), "consumable")
            res['item_name'] = item_name; res['hit'] = True; self.phase = "CHECK_END"; return res

    def start_targeting(self, action_type, data=None):
        self.pending_action = action_type; self.action_data = data
        if action_type.endswith("_FRIENDLY"): options = [t['name'] for t in self.get_living_players()]
        else:
            options = [f"{i+1}. {e['name']}" for i, e in enumerate(self.enemies) if e['current_hp'] > 0]
            options += [f"S. {s['name']}" for s in self.summons.values() if s.get('is_enemy_summon') and s['current_hp'] > 0]
        if not options: self.queue_message("No targets!"); self.phase = "CHECK_END"; self.start_next_message(); return
        self.target_menu = Menu(options + ["Back"], self.font, header="Target?"); self.menu_state = "TARGETING"; self.active_menu = self.target_menu

    def next_turn(self):
        self.turn_index += 1
        if self.turn_index >= len(self.turn_order): self.turn_index = 0; self.round_number += 1
        self.phase = "TURN_START"

    def get_next_living_actor(self):
        for i in range(1, len(self.turn_order) + 1):
            actor = self.turn_order[(self.turn_index + i) % len(self.turn_order)]
            if actor.get('current_hp', 0) > 0: return actor
        return None

    def check_combat_end(self):
        # --- Handle Permanent Death ---
        from core.players.player_inventory import add_item
        dead_party = [p for p in self.party if p.get('current_hp', 0) <= 0 and not p.get('is_summon')]
        for p in dead_party:
            if self.party.index(p) == 0: continue # Main player death is Game Over, handled below
            
            self.queue_message(f"{p['name']} has fallen in battle!")
            # Recover items
            recovered = []
            for slot in ['weapon', 'armor', 'shield', 'trinket']:
                item = p.get(slot)
                if item:
                    add_item(self.game.inventory, item, slot if slot != 'trinket' else 'trinket')
                    recovered.append(item.replace('_', ' ').title())
            if recovered:
                self.queue_message(f"Recovered from {p['name']}: {', '.join(recovered)}")
            
            # Remove from party
            self.party.remove(p)
            if p in self.turn_order: self.turn_order.remove(p)

        if not self.get_living_enemies(): self.queue_message("Victory!"); self.phase = "RESOLVE_VICTORY"
        elif not self.get_living_players(): self.queue_message("Defeat..."); self.phase = "END_COMBAT"
        else: self.next_turn()
        self.start_next_message()

    def handle_victory(self):
        cc = self.game.consecutive_combats
        bonus_mult = 1.0
        if cc >= 6: bonus_mult = 1.5
        elif cc == 5: bonus_mult = 1.4
        elif cc == 4: bonus_mult = 1.3
        elif cc == 3: bonus_mult = 1.2
        elif cc == 2: bonus_mult = 1.1
        
        if cc > 1:
            self.queue_message(f"Consecutive Combat #{cc}! Bonus: {int((bonus_mult-1)*100)}%")

        total_xp = sum(e.get("xp", 0) for e in self.enemies)
        total_xp = int(total_xp * bonus_mult)
        
        xp_per = total_xp // len(self.party) if self.party else 0
        from core.players.leveler import update_xp_and_level
        levelup_player = None
        for p in self.party:
            if update_xp_and_level(p, xp_per):
                if levelup_player is None: levelup_player = p
        
        if xp_per > 0: self.queue_message(f"Each party member gained {xp_per} XP!")
        
        # --- Bestiary RP Tracking ---
        party_lvl = sum(p.get('level', 1) for p in self.party)
        rp_gain = 1
        if party_lvl >= 51: rp_gain = 3
        elif party_lvl >= 41: rp_gain = 2

        for enemy in self.enemies:
            if enemy.get('current_hp', 0) <= 0:
                e_type = enemy.get('enemy_type', enemy.get('name', 'enemy').lower().replace(' ', '_'))
                self.game.bestiary_rp[e_type] = self.game.bestiary_rp.get(e_type, 0) + rp_gain
        
        self.process_loot(bonus_mult)
        
        if levelup_player: self.queue_message("LEVEL UP!"); self.phase = "LEVEL_UP"; self._levelup_starter = levelup_player
        else: self.phase = "END_COMBAT"

    def process_loot(self, bonus_mult=1.0):
        from core.players.player_inventory import add_item
        loot = CombatEngine.generate_loot(self.enemies); inv = self.game.inventory
        
        # Apply CC Bonus to Gold
        loot_gold = int(loot['gold'] * bonus_mult)
        inv['gold'] = inv.get('gold', 0) + loot_gold
        
        # Apply CC Extra Drops
        cc = self.game.consecutive_combats
        if cc >= 3:
            # Guaranteed random potion
            potions = ["healing_potion", "mana_potion", "stamina_potion"]
            p = random.choice(potions)
            add_item(inv, p, "consumable")
            self.queue_message(f"CC Reward: Found {p.replace('_',' ').title()}!")
        
        if cc >= 4:
            # Guaranteed Grind Stone
            add_item(inv, "grind_stone", "consumable")
            self.queue_message("CC Reward: Found Grind Stone!")
            
        if cc >= 6:
            # Random Junk (value <= budget * 50)
            budget = sum(e.get('level', 1) for e in self.enemies) # Rough budget proxy
            max_val = budget * 50
            junk_db = {}
            try:
                path = get_resource_path(os.path.join('data', 'items', 'junk.json'))
                with open(path, 'r') as f: junk_db = json.load(f).get('junk_list', {})
                valid_junk = [k for k, v in junk_db.items() if v.get('cost', 0) <= max_val]
                if valid_junk:
                    j = random.choice(valid_junk)
                    add_item(inv, j, "junk")
                    self.queue_message(f"CC Reward: Found {j.replace('_',' ').title()}!")
            except: pass

        for t, n in loot['items']: add_item(inv, n, t)
        
        if loot_gold > 0: self.queue_message(f"Gained {loot_gold} gold!")
        for msg in loot['messages']: self.queue_message(msg)

    def exit_to_hub(self):
        for p in self.party: validate_player_data(p)
        if all(p['current_hp'] <= 0 for p in self.party):
            from interfaces.pygame.states.game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font))
        else:
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    def queue_message(self, text):
        if isinstance(text, list):
            self.message_queue.extend(text)
        else:
            self.message_queue.append(text)

    def start_next_message(self, skip_typing=False):
        if self.message_queue:
            msg = self.message_queue.pop(0)
            # Ensure msg is a string before passing to set_messages
            if isinstance(msg, list):
                # Flatten nested list if it somehow got in
                self.message_queue = msg[1:] + self.message_queue
                msg = msg[0]
            self.dialogue.set_messages(str(msg), skip_typing=skip_typing)

    def handle_target_column(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            # Menu options are "Column 1" (Summons), "Column 2" (Minions), "Column 3" (Leader)
            # Internally mapped to _combat_column indices 0, 1, 2
            col_num = int(option.split(" ")[1])
            col = col_num - 1
            actor = self.current_actor
            
            # Filter enemies/summons in the selected column
            targets = [e for e in self.get_living_enemies() if e.get('_combat_column') == col]
            
            if not targets: 
                self.queue_message(f"No enemies in Column {col_num}!")
                self.start_next_message()
                return
            
            res = self.execute_action(actor, targets)
            is_anim = self.process_action_result(actor, targets, res)
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message()

    def draw(self, screen):
        screen.blit(self.background, (0, 0))
        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import COLOR_WHITE, COLOR_GOLD, COLOR_BLUE, COLOR_YELLOW
        
        # --- Pulse Animation for TARGET_COLUMN ---
        if self.phase == "PLAYER_TURN" and self.menu_state == "TARGET_COLUMN":
            import math
            pulse = (math.sin(pygame.time.get_ticks() * 0.005) + 1) / 2 # 0 to 1
            alpha = int(50 + pulse * 100)
            sel_idx = self.active_menu.selected
            if sel_idx < 3: # Column 1, 2, or 3 (mapped to indices 0, 1, 2)
                target_x = self.column_x[sel_idx]
                # Column width covers the staggered sprites
                col_rect = pygame.Rect(target_x - scale_x(10), scale_y(50), scale_x(140), SCREEN_HEIGHT - scale_y(100))
                overlay = pygame.Surface((col_rect.width, col_rect.height), pygame.SRCALPHA)
                overlay.fill((255, 255, 0, alpha))
                screen.blit(overlay, col_rect.topleft)

        status_y = scale_y(20); spacing = scale_y(25)
        draw_text_outlined(screen, f"Round: {self.round_number}", self.font, COLOR_WHITE, scale_x(20), status_y)
        draw_text_outlined(screen, f"Active: {self.current_actor['name'] if self.current_actor else 'None'}", self.font, COLOR_GOLD, scale_x(20), status_y + spacing)
        next_a = self.get_next_living_actor()
        draw_text_outlined(screen, f"Next: {next_a['name'] if next_a else 'None'}", self.font, COLOR_WHITE, scale_x(20), status_y + spacing * 2)
        for p in sorted(self.party, key=lambda p: self.party_positions[id(p)][1]):
            bx, by = self.party_positions[id(p)]; draw_x = bx + (self.attacker_offset if self.active_attacker is p else 0)
            sprite = SpriteManager.get_player_sprite(p.get('class', 'fighter'), size=(scale_x(128), scale_y(128)))
            if p['current_hp'] <= 0: sprite = sprite.copy(); sprite.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif p.get('flash_frames', 0) > 0: sprite = self.apply_flash_effect(sprite, p['flash_frames'], p.get('flash_type', 'damage'))
            screen.blit(sprite, (draw_x, by))
            bar_x, bar_y = draw_x + scale_x(10), by - scale_y(30)
            draw_bar(screen, bar_x, bar_y, scale_x(100), scale_y(15), p['current_hp'], p.get('max_hp_combat', 10), (200, 50, 50), self.font)
            curr_y = bar_y + scale_y(18)
            if p.get('max_mp', 0) > 0: draw_bar(screen, bar_x, curr_y, scale_x(100), scale_y(10), p.get('current_mp', 0), p['max_mp'], COLOR_BLUE, self.font); curr_y += scale_y(12)
            if p.get('max_sp', 0) > 0: draw_bar(screen, bar_x, curr_y, scale_x(100), scale_y(10), p.get('current_sp', 0), p['max_sp'], COLOR_YELLOW, self.font)
            if self.current_actor is p: pygame.draw.polygon(screen, (255, 255, 0), [(bar_x + scale_x(40), bar_y - scale_y(10)), (bar_x + scale_x(60), bar_y - scale_y(10)), (bar_x + scale_x(50), bar_y)])
        for summon in self.summons.values():
            if summon['current_hp'] <= 0: continue
            bx, by = self.party_positions[id(summon)]; draw_x = bx + (self.attacker_offset if self.active_attacker is summon else 0)
            
            folder = summon.get('sprite_folder', "")
            filename = summon.get('sprite_filename', "")
            category = summon.get('sprite_category', "humanoid")
            sz = (scale_x(100), scale_y(100))
            sprite = None

            if category == "player":
                # Base class sprites
                sprite = SpriteManager.get_player_sprite(filename.replace(".png", ""), size=sz)
            elif "enemy_images" in folder and "summons" not in folder:
                # Scaled enemy images
                sprite = SpriteManager.get_enemy_sprite(summon.get('enemy_type', 'enemy'), category=category, forced_filename=filename, size=sz)
            else:
                # Custom summons folder or legacy path - Manual load
                try:
                    path = get_resource_path(os.path.join(folder, filename))
                    sprite = pygame.image.load(path).convert_alpha()
                    sprite = pygame.transform.scale(sprite, sz)
                except:
                    # Fallback to circle
                    sprite = pygame.Surface(sz, pygame.SRCALPHA)
                    color = (200, 100, 100) if summon.get('is_enemy_summon') else (100, 100, 200)
                    pygame.draw.circle(sprite, color, (sz[0]//2, sz[1]//2), sz[0]//3)

            if summon.get('flash_frames', 0) > 0: sprite = self.apply_flash_effect(sprite, summon['flash_frames'], summon.get('flash_type', 'damage'))
            screen.blit(sprite, (draw_x, by))
            
            bar_w = scale_x(80)
            bar_x, bar_y = draw_x + scale_x(10), by - scale_y(25)
            
            # HP Bar
            draw_bar(screen, bar_x, bar_y, bar_w, scale_y(10), summon['current_hp'], summon['max_hp'], (200, 50, 50), self.font)
            
            # Resource Bars (MP/SP)
            cy = bar_y + scale_y(12)
            if summon.get('max_mp', 0) > 0:
                draw_bar(screen, bar_x, cy, bar_w, scale_y(8), summon.get('current_mp', 0), summon['max_mp'], COLOR_BLUE, self.font)
                cy += scale_y(10)
            if summon.get('max_sp', 0) > 0:
                draw_bar(screen, bar_x, cy, bar_w, scale_y(8), summon.get('current_sp', 0), summon['max_sp'], COLOR_YELLOW, self.font)
                
            if self.current_actor is summon: pygame.draw.polygon(screen, (255, 255, 0), [(bar_x + scale_x(30), bar_y - scale_y(10)), (bar_x + scale_x(50), bar_y - scale_y(10)), (bar_x + scale_x(40), bar_y)])
        for enemy in self.enemies:
            ex, ey = enemy.get('_combat_pos', (0, 0)); dx = ex + (self.attacker_offset if self.active_attacker is enemy else 0)
            sz = int(125 * 1.3 if enemy.get('is_leader') else 125)
            sprite = SpriteManager.get_enemy_sprite(enemy.get("enemy_type", "enemy"), category=enemy.get('category'), forced_filename=enemy.get("sprite_filename"), size=(scale_x(sz), scale_y(sz)))
            if enemy["current_hp"] <= 0: sprite = sprite.copy(); sprite.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif enemy.get('flash_frames', 0) > 0: sprite = self.apply_flash_effect(sprite, enemy['flash_frames'], enemy.get('flash_type', 'damage'))
            screen.blit(sprite, (dx, ey))
            
            # Resource bars at feet
            bar_w = scale_x(80)
            bar_x = dx + (scale_x(sz) - bar_w) // 2
            bar_y = ey + scale_y(sz) + scale_y(5)
            
            e_type = enemy.get('enemy_type', enemy.get('name', 'enemy').lower().replace(' ', '_'))
            show_hp = self.game.bestiary_rp.get(e_type, 0) >= 1
            draw_bar(screen, bar_x, bar_y, bar_w, scale_y(10), enemy["current_hp"], enemy["max_hp"], (200, 50, 50), self.font, show_numbers=show_hp)
            cy = bar_y
            if enemy.get('max_mp', 0) > 0 and enemy.get('spells'):
                cy += scale_y(12)
                draw_bar(screen, bar_x, cy, bar_w, scale_y(8), enemy.get('current_mp', 0), enemy['max_mp'], COLOR_BLUE, self.font)
            if enemy.get('max_sp', 0) > 0 and enemy.get('skills'):
                cy += scale_y(10)
                draw_bar(screen, bar_x, cy, bar_w, scale_y(8), enemy.get('current_sp', 0), enemy['max_sp'], COLOR_YELLOW, self.font)
                
            if self.current_actor is enemy:
                ind_w = scale_x(20)
                ind_h = scale_y(10)
                cx = bar_x + bar_w // 2
                tri_y = bar_y - scale_y(5)
                pygame.draw.polygon(screen, (255, 255, 0), [(cx - ind_w//2, tri_y - ind_h), (cx + ind_w//2, tri_y - ind_h), (cx, tri_y)])
        if self.phase == "PLAYER_TURN" and not self.dialogue.current_message:
            if self.menu_state == "TARGETING" and self.active_menu:
                sel = self.active_menu.selected
                if sel < len(self.active_menu.options) and self.active_menu.options[sel] != "Back":
                    opt = self.active_menu.options[sel]; t = None
                    if self.pending_action.endswith("_FRIENDLY"): t = next((p for p in self.party if p['name'] == opt), None)
                    elif opt.startswith("S. "): t = next((s for s in self.summons.values() if s['name'] == opt[3:]), None)
                    else:
                        try: t = self.enemies[int(opt.split(".")[0]) - 1]
                        except: pass
                    if t:
                        tx, ty = t['screen_pos']; import math; b = math.sin(pygame.time.get_ticks() * 0.01) * scale_y(10)
                        aw = scale_x(20); ah = scale_y(20); ay = ty - scale_y(80) + b
                        pts = [(tx - aw//2, ay), (tx + aw//2, ay), (tx, ay + ah)]
                        pygame.draw.polygon(screen, COLOR_GOLD, pts); pygame.draw.polygon(screen, COLOR_WHITE, pts, 2)
            self.active_menu.draw(screen, 400, 500)
        self.dialogue.draw(screen); self.float_mgr.draw(screen); self.dice_anim.draw(screen)

    def apply_flash_effect(self, sprite, frames, flash_type):
        new_s = sprite.copy()
        if flash_type == 'damage' and (frames // 6) % 2 == 1:
            try: return pygame.transform.grayscale(new_s)
            except: new_s.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
        elif flash_type == 'crit':
            cyc = (frames // 4) % 3
            if cyc == 1:
                try: return pygame.transform.grayscale(new_s)
                except: new_s.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif cyc == 2: new_s.fill((255, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return new_s
