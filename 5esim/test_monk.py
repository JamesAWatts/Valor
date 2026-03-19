import subprocess
import sys

# Automate the inputs for monk testing
inputs = [
    "2",        # Select Monk (option 2)
    "y",        # Confirm class selection
    "",         # Press Enter for initiative
    "y",        # First combat - press Enter for player turn (will need to handle combat flow)
]

input_str = "\n".join(inputs)

# Run simulator.py with automated inputs
result = subprocess.run(
    [sys.executable, "simulator.py"],
    input=input_str,
    text=True,
    capture_output=False
)
