from llms.gpt4_generator import generate_post, rewrite_post
from llms.gemini_evaluator import evaluate_post
from notifier.telegram import send_to_telegram
from utils.logger import get_logger
from utils.validators import validate_evaluation
import copy

logger = get_logger("Rewrite Module")


import uuid

async def run_evaluation_flow(initial_post, topic, max_retries=2, post_id=None):
    """
    Handles a single draft post with retry logic:
    1. Evaluates the post
    2. If fails, rewrites and retries (up to max_retries)
    3. If passes or exhausted, sends to Telegram/DB
    """
    current_post = copy.deepcopy(initial_post)
    attempt = 0
    
    # Use existing ID or generate a new one
    if not post_id:
        post_id = str(uuid.uuid4())[:8]

    try:
        while attempt <= max_retries:
            raw_evaluation = evaluate_post(current_post)

            try:
                evaluation = validate_evaluation(raw_evaluation)
            except ValueError as e:
                logger.error(f"Evaluation validation failed: {e}. Post: {current_post}")
                # Safety fallback: send for manual review
                await send_to_telegram(current_post, topic, post_id=post_id, review_required=True)
                return current_post, raw_evaluation

            if evaluation["pass"]:
                logger.info(
                    f"Post passed evaluation on attempt {attempt + 1}. Sending to Telegram. Post: {current_post}"
                )
                await send_to_telegram(current_post, topic, post_id=post_id)
                return current_post, evaluation

            rewrite_instructions = evaluation.get("rewrite_instructions", "")
            attempt += 1

            if attempt > max_retries:
                logger.warning(
                    f"Post failed after {max_retries} retries. Sending for manual review. Feedback: {evaluation}"
                )
                await send_to_telegram(current_post, topic, post_id=post_id, review_required=True)
                return current_post, evaluation

            logger.info(
                f"Post failed evaluation on attempt {attempt}. Rewriting using evaluator instructions. Feedback: {evaluation}"
            )

            # rewrite: original post + evaluator instructions
            current_post = rewrite_post(
                original_post=current_post,
                rewrite_instructions=rewrite_instructions
            )

    except Exception as e:
        logger.error(f"Unexpected error in editor loop: {e}", exc_info=True)
        # Fallback: send post for manual review
        await send_to_telegram(current_post, topic, post_id=post_id, review_required=True)
        # Return a structured failure evaluation
        return current_post, {
            "pass": False,
            "rewrite_instructions": "",
            "error": str(e)
        }
