import os
import sys

def get_resource_path(relative_path):
    """
    Get the absolute path to a resource, works for development and for PyInstaller.
    
    PyInstaller creates a temporary folder and stores the path in _MEIPASS when the
    executable is running. In development, it uses the project root.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Not running as a bundled executable, use the project root
        # This file is in core/game_rules/, so root is ../../ from here
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.normpath(os.path.join(base_path, relative_path))

def get_writeable_path(relative_path):
    """
    Get the absolute path to a writable file/folder.
    In an executable, this should be in the same folder as the .exe.
    In development, it's relative to the project root.
    """
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable
        base_path = os.path.dirname(sys.executable)
    else:
        # Not running as a bundled executable, use the project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.normpath(os.path.join(base_path, relative_path))
