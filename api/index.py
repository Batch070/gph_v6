import sys
import os
from pathlib import Path

# Add the root directory to sys.path so 'app' can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
app = app

