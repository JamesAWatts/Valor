import pygame
from interfaces.pygame.ui.debug_overlay import DebugOverlay

pygame.init()

class GameManager:
    def __init__(self, god_mode=False, music_manager=None):
        self.state = None
        self.player = None
        self.enemies = []
        self.god_mode = god_mode
        self.debug_overlay = None
        self.music_manager = music_manager

    def set_debug_font(self, font):
        # The new DebugOverlay initializes its own font based on size, 
        # but we can pass a size or just use the default.
        self.debug_overlay = DebugOverlay()

    def change_state(self, new_state):
        self.state = new_state

        # Automatically update music when state changes
        if self.music_manager and new_state:
            # Get the class name (e.g., 'HubState')
            state_class_name = type(new_state).__name__

            # Convert 'HubState' -> 'hub', 'TitleState' -> 'title', etc.
            state_key = state_class_name.replace('State', '').lower()

            # Tell the music manager to play music for this state
            self.music_manager.play_state_music(state_key)

    def update(self, events):
        if self.state:
            self.state.update(events)

    def draw(self, screen):
        if self.state:
            self.state.draw(screen)

        if self.debug_overlay:
            # Clear transient data each frame
            self.debug_overlay.clear_frame_data()
            self.debug_overlay.draw(screen, self)