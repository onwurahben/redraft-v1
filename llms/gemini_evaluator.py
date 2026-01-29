# llms/gemini_evaluator.py: Interface for Gemini-based evaluation of generated posts against a defined rubric.
import os
import json
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig, ThinkingLevel
from utils.logger import get_logger
from llms.prompts import EVALUATOR_PROMPT_LINKEDIN as EVALUATOR_SYSTEM_PROMPT

logger = get_logger("Gemini Evaluator")

# Note: newer GenAI SDK client expects Application Credentials (google.key.json) file path.

_client = None

def _get_client():
    """Lazy initialization of the Gemini client."""
    global _client
    if _client is None:
    
        creds_val = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # If the env var contains the raw JSON string (common on HF/GitHub Secrets)
        if creds_val and creds_val.strip().startswith('{'):
            try:
                # Write the JSON to a temporary file so Google Auth can find it
                # We use /tmp because it's writable in most container environments (Hugging Face)
                key_path = "/tmp/google_key.json"
                with open(key_path, "w") as f:
                    f.write(creds_val)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
                logger.info(f"Detected JSON credentials in ENV. Wrote to {key_path}")
            except Exception as e:
                logger.error(f"Failed to write credentials file: {e}")
        
        try:
            # genai.Client with vertexai=True will now find the credentials at GOOGLE_APPLICATION_CREDENTIALS
            _client = genai.Client(vertexai=True)
            logger.info("GenAI Client initialized successfully using Vertex AI.")
        except Exception as e:
            logger.error(f"Failed to initialize GenAI Client: {e}")
            raise
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
