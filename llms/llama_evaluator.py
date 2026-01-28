import os
import time
import json
from dotenv import load_dotenv
from groq import Groq
from utils.logger import get_logger


logger = get_logger("LLAMA Evaluator")

load_dotenv()

def generate_response(messages):
    """
    Evaluates a LinkedIn post draft using Groq's LLaMA API.
    
    Args:
        messages (list): List of message dictionaries (role, content).
        
    Returns:
        dict: The evaluation result.
    """
    logger.info("Starting evaluation with llama.")
    
    if not messages:
        logger.warning("Empty messages provided for evaluation.")
        return "No content to evaluate."

    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        client = Groq(api_key=groq_api_key)
        
        logger.info(f"⏱️ Calling Groq API (multi-turn) with {len(messages)} messages...")
        api_start = time.time()
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=2048
        )
        api_time = time.time() - api_start
        logger.info(f"✅ Groq API call completed in {api_time:.2f} seconds")
        
        response = completion.choices[0].message.content
     
        raw_text = response.text.strip()
        
        evaluation = json.loads(raw_text)

        return evaluation
    
    except json.JSONDecodeError:
            logger.error("Evaluator returned invalid JSON")
            logger.error(raw_text)
            raise ValueError("Invalid evaluator JSON output")
