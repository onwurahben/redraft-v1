from llms.gpt4_generator import generate_post, rewrite_post
from llms.gemini_evaluator import evaluate_post
from notifier.telegram import send_to_telegram
from memory.db_handler import add_post, log_activity
from utils.logger import get_logger
from utils.validators import validate_evaluation
import asyncio
import copy
import uuid

logger = get_logger("Rewrite Module")

async def _safe_notify(draft, topic, post_id, review_required=False):
    """
    Guarded notification helper. 
    Awaits Telegram with a timeout to prevent hanging the main loop.
    """
    try:
        # We wrap the call in wait_for to ensure it doesn't hang the AI loop
        # The timeout here is 5 seconds.
        await asyncio.wait_for(
            send_to_telegram(draft, topic, post_id=post_id, review_required=review_required),
            timeout=7.0
        )
    except asyncio.TimeoutError:
        logger.error(f"Telegram notification timed out for '{topic}'")
    except Exception as e:
        logger.error(f"Telegram notification failed for '{topic}': {e}")

async def run_evaluation_flow(initial_post, topic, max_retries=2, post_id=None, force_rewrite=False):
    """
    Handles a single draft post with retry logic:
    1. If force_rewrite is True, it performs a rewrite first.
    2. Evaluates the post.
    3. If fails, rewrites and retries (up to max_retries).
    4. If passes or exhausted, sends to Telegram/DB.
    """
    current_post = copy.deepcopy(initial_post)
    attempt = 0
    
    # If the user manually triggered this (Redraft), force a change immediately
    if force_rewrite:
        logger.info(f"Manual redraft triggered for '{topic}'. Forcing rewrite.")
        current_post = rewrite_post(
            original_post=current_post,
            rewrite_instructions="The user wants a fresh version. Try a different hook and a new perspective."
        )
    
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
                # Save to DB first
                add_post(post_id, topic, current_post, status="pending")
                log_activity("info", f"Validation failed for '{topic}', saved for manual review.")
                # Notify with timeout
                await _safe_notify(current_post, topic, post_id=post_id, review_required=True)
                return current_post, raw_evaluation

            if evaluation["pass"]:
                logger.info(
                    f"Post passed evaluation on attempt {attempt + 1}. Sending to Telegram. Post: {current_post}"
                )
                # Save to DB first
                add_post(post_id, topic, current_post, status="pending")
                log_activity("info", f"Post for '{topic}' passed AI evaluation.")
                # Notify with timeout
                await _safe_notify(current_post, topic, post_id=post_id)
                return current_post, evaluation

            rewrite_instructions = evaluation.get("rewrite_instructions", "")
            attempt += 1

            if attempt > max_retries:
                logger.warning(
                    f"Post failed after {max_retries} retries. Sending for manual review. Feedback: {evaluation}"
                )
                # Save to DB first
                add_post(post_id, topic, current_post, status="pending")
                log_activity("warning", f"Post for '{topic}' reached retry limit, saved for manual review.")
                # Notify with timeout
                await _safe_notify(current_post, topic, post_id=post_id, review_required=True)
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
        # Save to DB first
        add_post(post_id, topic, current_post, status="pending")
        log_activity("error", f"Unexpected error while processing '{topic}', saved draft.")
        # Notify with timeout
        await _safe_notify(current_post, topic, post_id=post_id, review_required=True)
        # Return a structured failure evaluation
        return current_post, {
            "pass": False,
            "rewrite_instructions": "",
            "error": str(e)
        }
