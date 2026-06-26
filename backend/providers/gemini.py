import os
import google.generativeai as genai
from dotenv import load_dotenv
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """
    LLM provider implementation for Google Gemini.
    """
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self.last_usage_metadata = None
        # Load API key
        load_dotenv(override=True)
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Reload API key in case it was set dynamically
        load_dotenv(override=True)
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing. Please add it to your backend/.env file.")
        
        genai.configure(api_key=self.api_key)
        self.last_usage_metadata = None
        
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
                
            # Extract usage metadata
            if response.usage_metadata:
                self.last_usage_metadata = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count
                }
                
            return response.text.strip()
        except Exception as e:
            raise e

