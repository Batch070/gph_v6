"""
AI service for interacting with OpenRouter Vision Models to parse attendance registers.
"""

import base64
import json
import re
import httpx
import asyncio
from fastapi import HTTPException, status
from app.config import settings

async def extract_attendance_from_image(image_bytes: bytes, total_classes: int) -> list:
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
You are a highly accurate OCR and data extraction agent specialized in academic attendance registers.
Analyze the provided image of a student attendance register.
The total number of classes held for this subject is {total_classes}.

TASK:
Extract the attendance data for every student listed in the register.
The register typically contains columns for:
1. Serial Number
2. Roll Number or ID
3. Student Name
4. Daily attendance marks (dots, ticks, or 'P'/'A')
5. A FINAL COLUMN indicating the "Total Attended" or "Grand Total".

CRITICAL RULES:
1. Extract the "student_name" EXACTLY as written.
2. Extract the "attended_classes" as an integer. This is usually found in the very LAST column of the table.
3. The "attended_classes" MUST be between 0 and {total_classes}.
4. If a student's attendance is unclear, use your best judgment based on the daily marks, but prioritize the total column if present.
5. IGNORE header rows, footer notes, or empty rows.

OUTPUT FORMAT:
Return ONLY a valid JSON array of objects. No preamble, no explanation, no markdown formatting.
Example:
[
  {{"student_name": "ROHIT KUMAR", "attended_classes": 24}},
  {{"student_name": "SNEHA SHARMA", "attended_classes": 28}}
]
"""

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Batch070/Mark1",
        "X-Title": "GPH Automated Fine System"
    }
    
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional data extraction tool that outputs valid JSON only."
            },
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
        ],
        "temperature": 0.1,  # Keep it deterministic
    }

    max_retries = 3
    retry_delay = 5  # seconds
    content = ""
    
    for attempt in range(max_retries):
        try:
            print(f"⏳ [AI] Sending extraction request to {settings.OPENROUTER_MODEL} (Attempt {attempt + 1})...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0
                )
            
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    print(f"⚠️ [AI] Rate limit hit. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="AI service limit reached. Please wait a moment or use Manual Entry."
                    )
            
            response.raise_for_status()
            
            result_json = response.json()
            if 'choices' not in result_json:
                print(f"❌ [AI] Unexpected response: {result_json}")
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="AI service returned an unexpected response.")

            content = result_json['choices'][0]['message']['content'].strip()
            
            # Clean up common AI artifacts
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()

            # Final regex fallback to ensure we only get the JSON array
            match = re.search(r'\[\s*{.*}\s*\]', content, re.DOTALL)
            if match:
                clean_json = match.group(0)
            else:
                clean_json = content
                
            extracted_data = json.loads(clean_json)
            print(f"✅ [AI] Successfully extracted {len(extracted_data)} student records.")
            return extracted_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code != 429:
                print(f"❌ [AI] HTTP Error: {e.response.status_code} - {e.response.text}")
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"AI Service Error: {e.response.text[:200]}"
                )
        except asyncio.TimeoutError:
            print(f"❌ [AI] Request timed out.")
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail="AI service request timed out.")
        except json.JSONDecodeError as e:
            print(f"❌ [AI] JSON Parse Error: {str(e)}")
            print(f"Raw content was: {content[:500]}...")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to parse AI response. Please ensure the image is clear or use manual entry."
            )
        except Exception as e:
            print(f"❌ [AI] Unexpected Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during AI extraction: {str(e)}"
            )
    return []
