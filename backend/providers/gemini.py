import os
import google.generativeai as genai
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """
    LLM provider implementation for Google Gemini.
    """
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        # Load API key
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Reload API key in case it was set dynamically
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing. Please add it to your backend/.env file.")
        
        genai.configure(api_key=self.api_key)
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt
            )
            # Enforce JSON output and set timeout to 15 seconds
            response = model.generate_content(
                user_prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": 15.0}
            )
            
            if not response or not response.text:
                raise ValueError("Received empty response from Gemini API.")
                
            return response.text.strip()
        except Exception as e:
            raise e
