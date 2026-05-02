import os
import sys
from pathlib import Path

# 1. Path Management: Ensure the root directory is in the path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# 2. Diagnostic Logging
print(f"🚀 [Pro Fix] Vercel startup initiated...")
print(f"📂 [Pro Fix] Working Directory: {os.getcwd()}")
print(f"📂 [Pro Fix] Base Directory: {BASE_DIR}")

# 3. Import the App with Safety
try:
    from app.main import app
    print("✅ [Pro Fix] App imported successfully!")
except Exception as e:
    print(f"❌ [Pro Fix] CRITICAL: App import failed: {e}")
    import traceback
    traceback.print_exc()
    raise e

# 4. Export for Vercel
app = app
