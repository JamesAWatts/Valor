import pygame
import random
from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.panel import draw_text_outlined
from interfaces.pygame.ui.dialogue_box import DialogueBox
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD
from core.players.player import validate_player_data

class TavernState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_rest_bg() 

        party_lvl = sum(p.get('level', 1) for p in self.game.party)
        
        # Determine start level for Hired Help (logic synced with ClassSelectState)
        self.hire_level = 1
        if party_lvl >= 46: self.hire_level = 15
        elif party_lvl >= 31: self.hire_level = 10
        elif party_lvl >= 16: self.hire_level = 5
        elif party_lvl >= 6: self.hire_level = 3

        # Calculate costs
        self.feast_cost = len(self.game.party) * 100
        self.rest_cost = sum([5 * p.get('level', 1) for p in self.game.party])
        self.hire_cost = self.hire_level * 100
        self.rumor_cost = 50
        self.respec_cost = 500

        self.options = []
        if party_lvl >= 1:
            self.options.append(f"Rest ({self.rest_cost} Gold)")
        if party_lvl >= 3:
            self.options.append(f"Hired Help ({self.hire_cost} Gold)")
        if party_lvl >= 11:
            self.options.append(f"Rumors ({self.rumor_cost} Gold)")
        if party_lvl >= 26:
            self.options.append(f"Order Feast ({self.feast_cost} Gold)")
        if party_lvl >= 36:
            self.options.append(f"Training Hall ({self.respec_cost} Gold)")
        
        self.options.append("Back")

        self.menu = Menu(self.options, font, header="The Gilded Flask Tavern")
        self.active_menu = self.menu
        self.menu_state = "MAIN"
        
        self.dialogue = DialogueBox(self.font)
        self.hiring_name = ""
        self.is_typing_name = False

    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)
        elif self.menu_state == "RESPEC_SELECT":
            if option == "Back":
                self.menu_state = "MAIN"
                self.active_menu = self.menu
            else:
                self.handle_respec(option)

    def handle_main_menu(self, option):
        lead = self.game.player
        inv = lead['inventory_ref']
        party_lvl = sum(p.get('level', 1) for p in self.game.party)
        
        if 'tavern_stats' not in lead:
            lead['tavern_stats'] = {'feast_used': False}
        tavern_stats = lead['tavern_stats']

        if option == "Back":
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))
            
        elif "Order Feast" in option:
            if tavern_stats['feast_used']:
                self.dialogue.set_messages("You've already feasted! Rest to feast again.")
                return

            if inv['gold'] >= self.feast_cost:
                inv['gold'] -= self.feast_cost
                tavern_stats['feast_used'] = True
                
                # Feast scaling: Level 26 (base), 41 (+1), 51 (+2)
                mult = 5
                stat_bonus = 0
                if party_lvl >= 51:
                    mult = 15
                    stat_bonus = 2
                elif party_lvl >= 41:
                    mult = 10
                    stat_bonus = 1
                
                for p in self.game.party:
                    p['current_hp'] = p['max_hp']
                    p['current_mp'] = p.get('max_mp', 0)
                    p['current_sp'] = p.get('max_sp', 0)
                    p['hp_buff'] = mult * p.get('level', 1)
                    p['feast_bonus'] = stat_bonus

                msg = "The party feasts sumptuously."
                if stat_bonus > 0:
                    msg += f" Everyone feels significantly tougher and more capable (+{stat_bonus} to stats)!"
                else:
                    msg += " Everyone feels significantly tougher!"
                self.dialogue.set_messages(msg)

        elif "Rest" in option:
            if self.game.god_mode or inv.get("gold", 0) >= self.rest_cost:
                self.game.consecutive_combats = 0
                if not self.game.god_mode: inv["gold"] -= self.rest_cost
                tavern_stats['feast_used'] = False
                for p in self.game.party:
                    p["current_hp"] = p.get("max_hp", 10)
                    p["current_mp"] = p.get("max_mp", 0)
                    p["current_sp"] = p.get("max_sp", 0)
                    # Reset temp buffs (Grind Stone etc)
                    p['weapon_bonus'] = 0
                    p['feast_bonus'] = 0
                    validate_player_data(p)
                lead["rest_count"] = lead.get("rest_count", 0) + 1
                self.dialogue.set_messages(f"The party rests peacefully. All limits and temporary buffs reset.")

        elif "Hired Help" in option:
            if len(self.game.party) >= 3:
                self.dialogue.set_messages("The party is full!")
                return
            if inv['gold'] >= self.hire_cost:
                self.menu_state = "NAMING"
                self.is_typing_name = True
                self.hiring_name = ""
            else:
                self.dialogue.set_messages(f"Not enough gold! Costs {self.hire_cost} Gold.")

        elif "Rumors" in option:
            if inv['gold'] >= self.rumor_cost:
                inv['gold'] -= self.rumor_cost
                from core.creatures.enemies import get_scaled_enemies
                import math
                total_level = sum(p.get('level', 1) for p in self.game.party)
                party_size = len(self.game.party)
                encounter_level = math.ceil(total_level - (party_size / 2) + 1)
                
                next_enemies = get_scaled_enemies(encounter_level, battle_count=self.game.battle_counter + 1)
                self.game.next_encounter = next_enemies
                
                types = list(set([e.get('category', 'unknown') for e in next_enemies]))
                type_str = ", ".join([t.title() for t in types])
                self.dialogue.set_messages([f"You hear whispers of {type_str} lurking ahead in the next area."])
            else:
                self.dialogue.set_messages(f"Not enough gold for rumors ({self.rumor_cost} Gold).")

        elif "Training Hall" in option:
            self.menu_state = "RESPEC_SELECT"
            self.active_menu = Menu([p['name'] for p in self.game.party] + ["Back"], self.font, header=f"ReSpec Training ({self.respec_cost} Gold)")

    def handle_respec(self, name):
        inv = self.game.inventory
        if inv.get('gold', 0) < self.respec_cost:
            self.dialogue.set_messages("Not enough gold!")
            return

        target = next((p for p in self.game.party if p['name'] == name), None)
        if target:
            inv['gold'] -= self.respec_cost
            # Store XP and name, then reset
            xp = target.get('xp', 0)
            target_name = target['name']
            
            # Remove from party temporarily to recreate
            idx = self.game.party.index(target)
            self.game.party.pop(idx)
            
            # Transition to ClassSelect
            self.game.party_member_name = target_name
            from .class_select import ClassSelectState
            cs = ClassSelectState(self.game, self.font, hiring=True)
            cs.stored_xp = xp # Hack to pass XP back
            self.game.change_state(cs)

    def update(self, events):
        if self.dialogue.current_message:
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self.dialogue.handle_event(event)
            return

        if self.menu_state == "NAMING":
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if self.hiring_name.strip():
                            # Pay and move to class select
                            self.game.player['inventory_ref']['gold'] -= self.hire_cost
                            self.game.party_member_name = self.hiring_name.strip()
                            from .class_select import ClassSelectState
                            self.game.change_state(ClassSelectState(self.game, self.font, hiring=True))
                    elif event.key == pygame.K_BACKSPACE:
                        self.hiring_name = self.hiring_name[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.menu_state = "MAIN"
                        self.is_typing_name = False
                    else:
                        if len(self.hiring_name) < 15 and event.unicode.isprintable():
                            self.hiring_name += event.unicode
            return

        super().update(events)

    def draw(self, screen):
        self.draw_background(screen)
        width, height = screen.get_size()
        
        if self.menu_state == "NAMING":
            # Draw naming box
            box_w, box_h = scale_x(400), scale_y(150)
            bx, by = (width - box_w) // 2, (height - box_h) // 2
            pygame.draw.rect(screen, (30, 30, 30), (bx, by, box_w, box_h))
            pygame.draw.rect(screen, (200, 200, 200), (bx, by, box_w, box_h), 2)
            
            prompt = "Name your ally:"
            pw, ph = self.font.size(prompt)
            draw_text_outlined(screen, prompt, self.font, (255,255,255), bx + (box_w - pw)//2, by + scale_y(20))
            
            # Draw current typing name
            name_str = self.hiring_name + "_"
            nw, nh = self.font.size(name_str)
            draw_text_outlined(screen, name_str, self.font, (255, 255, 0), bx + (box_w - nw)//2, by + scale_y(70))
            
            instruct = "Press ENTER to confirm, ESC to cancel"
            iw, ih = self.font.size(instruct)
            draw_text_outlined(screen, instruct, self.font, (150, 150, 150), bx + (box_w - iw)//2, by + scale_y(110))
        else:
            self.active_menu.draw(screen, 400, 300)
            
            # Show party size
            party_str = f"Party Size: {len(self.game.party)}/3"
            pw, ph = self.font.size(party_str)
            draw_text_outlined(screen, party_str, self.font, (255,255,255), width // 2 - pw // 2, height // 2 - scale_y(150))
            
            # Show gold
            gold_str = f"Gold: {self.game.player['inventory_ref']['gold']}"
            gw, gh = self.font.size(gold_str)
            draw_text_outlined(screen, gold_str, self.font, COLOR_GOLD, width // 2 - gw // 2, height // 2 - scale_y(110))

        self.dialogue.draw(screen)
