import pygame

class BaseState:
    def __init__(self, game, font):
        self.game = game
        self.font = font
        self.active_menu = None
        self.background = None

    def update(self, events):
        if not self.active_menu:
            return

        # Handle all input (keyboard and mouse) via the menu's own event handling
        # handle_event returns the selected option string if confirmed
        for event in events:
            if not self.active_menu:
                break
            
            # 1. Keyboard Navigation & Selection
            result = self.active_menu.handle_event(event)
            if result:
                self.on_select(result)
                return

            # 2. Mouse Navigation & Selection
            if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION]:
                mouse_pos = pygame.mouse.get_pos()
                mouse_click = (event.type == pygame.MOUSEBUTTONDOWN)
                
                # handle_mouse returns the index of the option if clicked, or just updates hover
                selection_idx = self.active_menu.handle_mouse(mouse_pos, mouse_click)
                if selection_idx is not None and mouse_click:
                    option = self.active_menu.options[selection_idx]
                    self.on_select(option)
                    return

    def on_select(self, option):
        raise NotImplementedError

    def draw_background(self, screen):
        """Renders the background image if it exists."""
        if self.background:
            screen.blit(self.background, (0, 0))

    def draw(self, screen):
        """
        Default draw: renders background, then centers active menu.
        States can override this or call draw_background() specifically.
        """
        self.draw_background(screen)

        if self.active_menu:
            width, height = screen.get_size()
            self.active_menu.draw(screen, width // 2, height // 3)