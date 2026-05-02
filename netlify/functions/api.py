import sys
import os
from pathlib import Path
from mangum import Mangum

# Add current and root directory to path so absolute imports work
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir.parent.parent))

try:
    from app.main import app
    # Create the handler for Netlify
    handler = Mangum(app)
except Exception as e:
    import traceback
    error_msg = f"Initialization Error: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    
    async def handler(event, context):
        return {
            "statusCode": 500,
            "body": f"Backend Initialization Error. Check logs.\n{str(e)}"
        }
