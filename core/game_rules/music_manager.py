import pygame
import os
import random
from core.game_rules.path_utils import get_resource_path

class MusicManager:
    def __init__(self):
        # 1. Get the dynamic path to assets/bgm
        self.music_dir = get_resource_path(os.path.join('assets', 'bgm'))
        
        self.current_track = None
        self.last_combat_index = -1
        
        # Settings
        self.volume = 0.5
        self.is_muted = False
        
        # 2. Force a clean mixer initialization
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
            
        # 3. Set an initial volume
        pygame.mixer.music.set_volume(self.volume)
        print(f"MusicManager: Mixer initialized. Music Dir: {self.music_dir}")

    def set_volume(self, value):
        """Sets the volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, value))
        if not self.is_muted:
            pygame.mixer.music.set_volume(self.volume)

    def toggle_mute(self):
        """Toggles between muted and unmuted."""
        self.is_muted = not self.is_muted
        if self.is_muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(self.volume)
        return self.is_muted

    def play_state_music(self, state_name):
        """
        Only changes music if the new state has a track defined AND 
        it's different from the currently playing one.
        """
        new_path = None

        # 1. Map states to their music files/folders
        if state_name == 'title':
            new_path = os.path.join(self.music_dir, 'title', 'Theme - Into The Throne v3.mid')
        elif state_name == 'hub':
            new_path = os.path.join(self.music_dir, 'hub', 'Scene - Prepare For Tomorrow.mid')
        elif state_name in ['level_up', 'levelup']:
            new_path = os.path.join(self.music_dir, 'level_up', 'Jingle - Win.mid')
        elif state_name == 'combat':
            new_path = self._get_next_combat_track()

        # 2. Check if we actually have music for this state
        if new_path is None:
            return

        # 3. Check if we're already playing this exact track
        if new_path == self.current_track:
            return

        # 4. Perform the change
        if os.path.exists(new_path):
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(new_path)
                
                # Jingle/Win music should play only once (loop=0)
                loops = 0 if state_name in ['level_up', 'levelup'] else -1
                pygame.mixer.music.play(loops)
                
                self.current_track = new_path
                print(f"MusicManager: Now playing {new_path} (loops={loops})")
            except Exception as e:
                print(f"MusicManager Error: Could not play {new_path}: {e}")
        else:
            print(f"MusicManager Warning: Music file not found at {new_path}")

    def _get_next_combat_track(self):
        """
        Finds all .mid files in the combat folder and picks one 
        that isn't the one we just played.
        """
        combat_dir = os.path.join(self.music_dir, 'combat')
        if not os.path.exists(combat_dir):
            return None
            
        tracks = [f for f in os.listdir(combat_dir) if f.endswith('.mid')]
        
        if not tracks:
            return None

        # If there's only one track, just return it
        if len(tracks) == 1:
            full_path = os.path.join(combat_dir, tracks[0])
            self.last_combat_index = 0
            return full_path

        # Pick a random track that's different from the last one
        new_index = self.last_combat_index
        while new_index == self.last_combat_index:
            new_index = random.randint(0, len(tracks) - 1)
        
        self.last_combat_index = new_index
        return os.path.join(combat_dir, tracks[new_index])
