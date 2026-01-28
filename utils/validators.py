def validate_evaluation(evaluation):
    """
    Validates the structure of the evaluation dictionary.
    """
    if not isinstance(evaluation, dict):
        raise ValueError("Evaluation must be a dictionary")
    
    required_keys = ["pass", "scores", "issues", "rewrite_instructions"]
    for key in required_keys:
        if key not in evaluation:
            raise ValueError(f"Missing required key in evaluation: {key}")
    
    return evaluation
