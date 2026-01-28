# llms/gpt4_generator.py
# Interface for generating text using GPT-4.
# Prompting and topic logic live outside this module.

import os
from openai import OpenAI
from utils.logger import get_logger
from dotenv import load_dotenv
from llms.prompts import SYSTEM_PROMPT_1

logger = get_logger("GPT4 Generator")
load_dotenv()

# Global OpenAI client placeholder
_client = None

def _get_client():
    """Lazy initialization of the OpenAI client."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Set your OPENAI_API_KEY environment variable!")
        _client = OpenAI(api_key=api_key)
    return _client


def generate_post(prompt):
    """
    Generate a new post using GPT-4.

    Args:
        prompt (list): List of message dicts (system/user)

    Returns:
        str: Generated text
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=prompt,
            max_tokens=500,
            temperature=0.7,
            top_p=1.0
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Error generating post: {e}")
        raise


def rewrite_post(original_post, rewrite_instructions):
    """
    Rewrite an existing post using evaluator feedback while maintaining global rules.

    Args:
        original_post (str): The post to be rewritten
        rewrite_instructions (str): Specific instructions for rewriting

    Returns:
        str: Rewritten post
    """
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    f"{SYSTEM_PROMPT_1}\n\n"
                    "TASK: You are editing a draft. You MUST maintain all the global rules above "
                    "while applying the specific REWRITE INSTRUCTIONS provided by the evaluator."
                )
            },
            {
                "role": "user",
                "content": f"ORIGINAL POST:\n{original_post}"
            },
            {
                "role": "user",
                "content": f"REWRITE INSTRUCTIONS:\n{rewrite_instructions}"
            }
        ]

        return generate_post(messages)

    except Exception as e:
        logger.error(f"Error rewriting post: {e}")
        raise

