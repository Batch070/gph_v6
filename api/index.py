import sys
import os
from pathlib import Path

# Add the root directory to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)

try:
    print("✨ [Vercel] Attempting to import app.main...")
    from app.main import app
    print("✅ [Vercel] Import successful!")
except Exception as e:
    print(f"❌ [Vercel] CRITICAL IMPORT ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise e

app = app
# Vercel Deployment Sync
