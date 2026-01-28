import json
import re

def parse_json_safely(text):
    """
    Extracts and parses JSON from a string, handling potential markdown code blocks.
    
    Args:
        text: str, the string to parse (may contain ```json ... ``` blocks)
        
    Returns:
        dict: The parsed JSON object
        
    Raises:
        ValueError: If no valid JSON can be found or parsed
    """
    # Try to find JSON within markdown code blocks
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        clean_text = match.group(1)
    else:
        # Fallback to the whole string stripped of whitespace
        clean_text = text.strip()
    
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw output: {text}")
