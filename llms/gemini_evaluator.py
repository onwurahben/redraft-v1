# llms/gemini_evaluator.py: Interface for Gemini-based evaluation of generated posts against a defined rubric.
import os
import json
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig, ThinkingLevel
from utils.logger import get_logger
from llms.prompts import EVALUATOR_PROMPT_LINKEDIN as EVALUATOR_SYSTEM_PROMPT

logger = get_logger("Gemini Evaluator")

# Set global GenAI client using Application Credentials (google.key.json)
# Ensure GOOGLE_APPLICATION_CREDENTIALS points to your JSON key (Hugging Face Spaces)

_client = None

def _get_client():
    """Lazy initialization of the Gemini client."""
    global _client
    if _client is None:
        google_creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if google_creds_json:
            try:
                creds = json.loads(google_creds_json)
                _client = genai.Client(vertexai=True, api_key=creds) # Adjust if creds is a dict
            except Exception as e:
                logger.warning(f"Failed to load JSON credentials from ENV: {e}. Falling back to default.")
                _client = genai.Client(vertexai=True)
        else: 
            _client = genai.Client(vertexai=True)
    return _client


def evaluate_post(post_text):
    """
    Evaluates a LinkedIn post draft using Gemini 3 Flash with service account auth.

    Args:
        post_text: str, generated LinkedIn post

    Returns:
        dict: Parsed evaluator response
    """
    try:
        client = _get_client()
        # Call the Gemini 3 Flash model
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=post_text,
            config=GenerateContentConfig(
                system_instruction=EVALUATOR_SYSTEM_PROMPT,
                max_output_tokens=1024,
                temperature=0.0  # deterministic evaluation
            )
        )

        raw_output = response.text.strip()

        try:
            from utils.json_parser import parse_json_safely
            evaluation = parse_json_safely(raw_output)
        except ValueError as e:
            logger.error(f"Evaluator returned invalid JSON: {e}")
            raise

        return evaluation

    except Exception as e:
        logger.error(f"Evaluator failed: {e}")
        raise
