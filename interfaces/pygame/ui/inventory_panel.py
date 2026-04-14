import pygame
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE
from interfaces.pygame.ui.panel import Panel, draw_text_outlined

from core.players.player import get_weapon_display_name, get_armor_display_name

class InventoryPanel:
    def __init__(self, font, weapons_db, armor_db, shields_db, trinkets_db):
        self.font = font
        self.weapons_db = weapons_db
        self.armor_db = armor_db
        self.shields_db = shields_db
        self.trinkets_db = trinkets_db
        self.hovered_item = None

    def draw(self, screen, player):
        if not player: return

        # Panel Dimensions
        pw, ph = scale_x(165), SCREEN_HEIGHT - scale_y(170)
        # Panel Position (Right Side)
        px, py = SCREEN_WIDTH - pw - scale_x(310), scale_y(40)

        panel = Panel(
            px / scale_x(1), py / scale_y(1), 
            pw / scale_x(1), ph / scale_y(1),
            bg_color=(30, 30, 50),
            border_color=COLOR_GOLD,
            border_width=3,
            alpha=220
        )
        rect = panel.draw(screen)

        # Content
        line_h = self.font.get_height()
        curr_y = rect.y + scale_y(20)
        center_x = rect.centerx

        # Name & Class
        name_str = f"{player.get('name', 'Player')} - Lvl {player.get('level', 1)}"
        nw, _ = self.font.size(name_str)
        draw_text_outlined(screen, name_str, self.font, COLOR_WHITE, center_x - nw // 2, curr_y)
        curr_y += line_h
        
        class_str = player.get('class', 'Fighter').title()
        cw, _ = self.font.size(class_str)
        draw_text_outlined(screen, class_str, self.font, COLOR_GOLD, center_x - cw // 2, curr_y)
        curr_y += line_h + scale_y(15)

        # AC & Spell Save
        ac_str = f"Armor Class: {player.get('ac', 10)}"
        draw_text_outlined(screen, ac_str, self.font, COLOR_WHITE, rect.x + scale_x(15), curr_y)
        curr_y += line_h
        
        ss_str = f"Spell Save Bonus: +{player.get('spell_save', 0)}"
        draw_text_outlined(screen, ss_str, self.font, COLOR_WHITE, rect.x + scale_x(15), curr_y)
        curr_y += line_h + scale_y(20)

        # Equipment
        eq = ["weapon", "armor", "shield", "trinket"]
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_item = None
        
        for slot in eq:
            item_key = player.get(slot, 'none')
            
            label = f"{slot.title()}: "
            
            if slot == 'weapon':
                val_str = get_weapon_display_name(player, item_key)
            elif slot == 'armor':
                val_str = get_armor_display_name(player, item_key)
            else:
                val_str = item_key.replace('_', ' ').title()
            
            # Draw label
            lx = rect.x + scale_x(15)
            draw_text_outlined(screen, label, self.font, COLOR_GOLD, lx, curr_y)
            
            # Draw value and check for hover
            vx = lx + self.font.size(label)[0]
            val_rect = draw_text_outlined(screen, val_str, self.font, COLOR_WHITE, vx, curr_y)
            
            if val_rect.collidepoint(mouse_pos):
                # Map to DB
                if slot == 'weapon': self.hovered_item = (self.weapons_db.get(item_key), 'weapon')
                elif slot == 'armor': self.hovered_item = (self.armor_db.get(item_key), 'armor')
                elif slot == 'shield': self.hovered_item = (self.shields_db.get(item_key), 'shield')
                elif slot == 'trinket': self.hovered_item = (self.trinkets_db.get(item_key), 'trinket')
            
            curr_y += line_h + scale_y(10)

        # Buffs
        curr_y += scale_y(20)
        draw_text_outlined(screen, "Active Buffs:", self.font, COLOR_GOLD, rect.x + scale_x(15), curr_y)
        curr_y += line_h + scale_y(5)
        
        buffs = []
        # Extract buffs from weapon enchantments
        upgrades = player.get('weapon_upgrades', {}).get(player.get('weapon', 'unarmed'), {})
        enchant = upgrades.get('enchantment')
        if enchant:
            buffs.append(f"Weapon: {enchant.replace('_', ' ').title()}")

        # Extract buffs from trinket/robes/shields
        t_stats = self.trinkets_db.get(player.get('trinket', 'none'), {})
        if t_stats.get('bonus_hp'): buffs.append(f"Health +{t_stats['bonus_hp']}")
        if t_stats.get('spell_save'): buffs.append(f"Spell Save +{t_stats['spell_save']}")
        if t_stats.get('bonus_sp'): buffs.append(f"Stamina +{t_stats['bonus_sp']}")
        if t_stats.get('bonus_atk'): buffs.append(f"Attack +{t_stats['bonus_atk']}")
        
        s_stats = self.shields_db.get(player.get('shield', 'none'), {})
        if s_stats.get('bonus_hp'): buffs.append(f"Health +{s_stats['bonus_hp']}")
        if s_stats.get('spell_save'): buffs.append(f"Spell Save +{s_stats['spell_save']}")
        if s_stats.get('bonus_sp'): buffs.append(f"Stamina +{s_stats['bonus_sp']}")

        # Robe buffs
        a_stats = self.armor_db.get(player.get('armor', 'none'), {})
        if a_stats.get('spell_save'): buffs.append(f"Spell Save +{a_stats['spell_save']}")
        if a_stats.get('bonus_sp'): buffs.append(f"Stamina +{a_stats['bonus_sp']}")
        if a_stats.get('bonus_dmg'): buffs.append(f"Damage +{a_stats['bonus_dmg']}")

        if not buffs:
            draw_text_outlined(screen, "None", self.font, (150, 150, 150), rect.x + scale_x(30), curr_y)
        else:
            for b in buffs:
                draw_text_outlined(screen, f"• {b}", self.font, (200, 255, 200), rect.x + scale_x(25), curr_y)
                curr_y += line_h

    def draw_tooltip(self, screen):
        if not self.hovered_item or not self.hovered_item[0]: return
        
        item_data, item_type = self.hovered_item
        text = item_data.get('description', 'No description.')
        
        # Add stats to text
        if item_type == 'weapon':
            text += f" (D{item_data.get('die', 4)}, {item_data.get('on_hit_effect', 'none').title()})"
        elif item_type == 'armor':
            text += f" (AC: {item_data.get('ac', 10)}, {item_data.get('type', 'none').title()})"
        elif item_type == 'shield':
            text += f" (AC: +{item_data.get('ac', 0)})"
            
        mouse_pos = pygame.mouse.get_pos()
        
        tw, th = 300, 120
        tx, ty = mouse_pos[0] + 20, mouse_pos[1] + 20
        
        # Wrap text
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w, _ = self.font.size(test_line)
            if w > scale_x(tw - 20):
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        lines.append(' '.join(current_line))
        
        th = len(lines) * self.font.get_height() + scale_y(30)
        
        # Clamp to screen
        if tx + scale_x(tw) > SCREEN_WIDTH: tx = mouse_pos[0] - scale_x(tw) - 20
        if ty + scale_y(th) > SCREEN_HEIGHT: ty = mouse_pos[1] - scale_y(th) - 20

        t_panel = Panel(
            tx / scale_x(1), ty / scale_y(1), 
            tw, th / scale_y(1),
            bg_color=(20, 20, 30), border_color=COLOR_GOLD, alpha=240
        )
        t_rect = t_panel.draw(screen)
        
        for i, line in enumerate(lines):
            draw_text_outlined(screen, line, self.font, COLOR_WHITE, t_rect.x + scale_x(10), t_rect.y + scale_y(10) + i * self.font.get_height())
