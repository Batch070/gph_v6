import sys
import os

# Now that this file is in the root, it can easily find 'app'
from app.main import app

# Export the app for Vercel
app = app
