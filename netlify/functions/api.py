import sys
import os
from pathlib import Path
from mangum import Mangum

# Add the root directory to path so absolute imports work
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from app.main import app

# Create the handler for Netlify
handler = Mangum(app)
