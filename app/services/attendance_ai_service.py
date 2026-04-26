"""
AI service for interacting with OpenRouter Vision Models to parse attendance registers.
"""

import base64
import json
import re
import httpx
from fastapi import HTTPException, status
from app.config import settings

def extract_attendance_from_image(image_bytes: bytes, total_classes: int) -> list:
    """
    Sends the register image to the OpenRouter Vision model and expects
    a JSON response containing roll numbers and attended classes.
    """
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenRouter API Key is not configured."
        )

    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    mime_type = "image/jpeg"

    # Define the strict system prompt for structured output
    sys_prompt = f"""
You are an expert OCR and data extraction AI. You have been given an image of a student attendance register.
The total number of classes held is {total_classes}.
Extract the attendance of each student.

Return the data STRICTLY as a JSON array of objects. Do not include any markdown, backticks, or conversational text.
Format:
[
  {{"student_name": "John Doe", "attended_classes": 12}},
  {{"student_name": "Jane Smith", "attended_classes": 15}}
]
Rules:
1. "student_name" must be the exact name of the student as written in the register.
2. "attended_classes" must be an integer between 0 and {total_classes}. Extract this value STRICTLY from the very last column of the image.
3. Ignore blank lines or unreadable handwriting.
"""

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Batch070/cdh_v3",
        "X-Title": "CDH v4 Attendance System"
    }
    
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": sys_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }

    try:
        print(f"⏳ Sending extraction request to {settings.OPENROUTER_MODEL}...")
        response = httpx.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120.0
        )
        response.raise_for_status()
        
        result_json = response.json()
        content = result_json['choices'][0]['message']['content']
        
        print("\n\n========== AI EXTRACTION OUTPUT ==========")
        print(content)
        print("==========================================\n")

        # Clean up markdown if the AI mistakenly outputted it
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            clean_json = match.group(0)
        else:
            clean_json = content
            
        return json.loads(clean_json)

    except httpx.HTTPStatusError as e:
        import traceback
        traceback.print_exc()
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service limit reached (429). Please wait a moment or use Manual Entry."
            )
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"AI Service Error: {str(e)}"
        )
    except httpx.RequestError as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error communicating with AI service: {str(e)}"
        )
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        import traceback
        traceback.print_exc()
        print("Raw Content:", result_json.get('choices', [{}])[0].get('message', {}).get('content', ''))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to parse AI response. Ensure the image is clear or switch to manual entry."
        )
