from llms.gpt4_generator import generate_post
from topics.topic_manager import get_topic
from llms.prompts import build_linkedin_prompt
from pipeline.editor import run_evaluation_flow
from utils.logger import get_logger
from dotenv import load_dotenv
import asyncio
import sys

load_dotenv()

logger = get_logger("Worker")


async def create_post(progress_callback=None, user_topic=None):
    """ 
    Full content creation pipeline with post evaluation and editing.
    """
    try:
        # 10% - Getting Topic
        if progress_callback: progress_callback(10, "Selecting Topic...")
        
        # Get topic from llm or user input
        topic_data = get_topic(user_topic=user_topic)
        
        # Handle dict (from DB) or string
        if isinstance(topic_data, dict):
            topic = topic_data.get('content')
        else:
            topic = topic_data

        # 25% - building prompt
        if progress_callback: progress_callback(25, "Drafting Content...")

        # Create prompt with the topic
        prompt = build_linkedin_prompt(topic)
        logger.info(f"Generated prompt: {prompt}")

        # Generate a post with the prompt
        post = generate_post(prompt)
        logger.info(f"Generated post: {post}")

        # 50% - Evaluating
        if progress_callback: progress_callback(50, "Evaluating Draft...")

        # Run evaluation flow
        finished_post, evaluation = await run_evaluation_flow(post, topic)
        logger.info(f"Finished post: {finished_post} \n Evaluation: {evaluation}")
        
        # 90% - Finalizing
        if progress_callback: progress_callback(90, "Finalizing...")
        
        return finished_post

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        if progress_callback: progress_callback(0, "Error Occurred")
        raise

if __name__ == "__main__":
    asyncio.run(create_post())
