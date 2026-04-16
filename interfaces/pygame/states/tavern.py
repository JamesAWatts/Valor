import pygame
import random
from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.panel import draw_text_outlined
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD
from core.players.player import validate_player_data

class TavernState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        # Reuse shop or hub background for now, or something cozy
        self.background = BackgroundManager.get_rest_bg() 

        # Calculate costs based on party size and levels
        self.feast_cost = len(self.game.party) * 100
        self.drink_cost = len(self.game.party) * 20
        self.rest_cost = sum([5 * p.get('level', 1) for p in self.game.party])

        self.options = [
            f"Order Feast ({self.feast_cost} Gold)", 
            f"Order Drinks ({self.drink_cost} Gold)", 
            f"Rest ({self.rest_cost} Gold)", 
            "Hired Help (500 Gold)", 
            "Back"
        ]
        self.menu = Menu(self.options, font, header="The Gilded Flask Tavern")
        self.active_menu = self.menu
        self.menu_state = "MAIN"
        
        # Hiring specific state
        self.hiring_name = ""
        self.is_typing_name = False

    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)

    def handle_main_menu(self, option):
        lead = self.game.player
        inv = lead['inventory_ref']
        
        # Initialize tavern tracking if not present
        if 'tavern_stats' not in lead:
            lead['tavern_stats'] = {'feast_used': False, 'drinks_count': 0}
        
        tavern_stats = lead['tavern_stats']

        if option == "Back":
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))
            
        elif "Order Feast" in option:
            if tavern_stats['feast_used']:
                print("DEBUG: You've already feasted! Rest to feast again.")
                return

            cost = len(self.game.party) * 100
            if inv['gold'] >= cost:
                inv['gold'] -= cost
                tavern_stats['feast_used'] = True
                # Full restore and buff
                for p in self.game.party:
                    p['current_hp'] = p['max_hp']
                    p['current_mp'] = p.get('max_mp', 0)
                    p['current_sp'] = p.get('max_sp', 0)
                    
                    # Grant HP buff (Temp HP for next combat)
                    buff_amt = 5 * p.get('level', 1)
                    p['hp_buff'] = buff_amt
                print(f"DEBUG: Ordered Feast. Cost: {cost}. Party buffed.")
            
        elif "Order Drink" in option:
            if tavern_stats['drinks_count'] >= 3:
                print("DEBUG: You've had enough to drink! Rest to sober up.")
                return

            cost = len(self.game.party) * 20
            if inv['gold'] >= cost:
                inv['gold'] -= cost
                tavern_stats['drinks_count'] += 1
                # Restore 50% HP/MP/SP
                for p in self.game.party:
                    h_restore = p['max_hp'] // 2
                    m_restore = p.get('max_mp', 0) // 2
                    s_restore = p.get('max_sp', 0) // 2
                    
                    p['current_hp'] = min(p['max_hp'], p['current_hp'] + h_restore)
                    p['current_mp'] = min(p.get('max_mp', 0), p.get('current_mp', 0) + m_restore)
                    p['current_sp'] = min(p.get('max_sp', 0), p.get('current_sp', 0) + s_restore)
                print(f"DEBUG: Ordered drinks. Cost: {cost}. Party restored 50%.")

        elif "Rest" in option:
            # 20 gold * level per player
            total_cost = sum([5 * p.get('level', 1) for p in self.game.party])
            
            if self.game.god_mode or inv.get("gold", 0) >= total_cost:
                if not self.game.god_mode: inv["gold"] -= total_cost
                
                # Reset tavern limits
                tavern_stats['feast_used'] = False
                tavern_stats['drinks_count'] = 0
                
                for p in self.game.party:
                    p["current_hp"] = p.get("max_hp", 10)
                    p["current_mp"] = p.get("max_mp", 0)
                    p["current_sp"] = p.get("max_sp", 0)
                    validate_player_data(p)
                
                lead["rest_count"] = lead.get("rest_count", 0) + 1
                print(f"DEBUG: Party rested. Cost: {total_cost}.")

        elif "Hired Help" in option:
            if len(self.game.party) >= 3:
                print("DEBUG: Party is full!")
                return
            
            if inv['gold'] >= 500:
                self.menu_state = "NAMING"
                self.is_typing_name = True
                self.hiring_name = ""

    def update(self, events):
        if self.menu_state == "NAMING":
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if self.hiring_name.strip():
                            # Pay and move to class select
                            self.game.player['inventory_ref']['gold'] -= 500
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
