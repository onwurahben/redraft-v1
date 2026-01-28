import random
from llms.gpt4_generator import generate_post
from utils.logger import get_logger
from llms.prompts import topics_prompt_linkedin
from memory.db_handler import add_topics, get_unused_topics, mark_topic_used, delete_topic as db_delete_topic

logger = get_logger("TopicManager")

# Topic pool pulled in from DB


def _generate_topics():
    """
    Uses GPT-4 to generate a list of post topics.
    """
    topics_prompt = topics_prompt_linkedin

    raw = generate_post(topics_prompt)

    topics = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove numbering if present
        if line[0].isdigit():
            line = line.split(".", 1)[-1].strip()
        topics.append(line)

    logger.info(f"Generated {len(topics)} new topics")
    
    # Add topics to DB
    add_topics(topics)
    
    return topics


def get_topic(user_topic=None):
    """
    Returns a topic string.

    Priority:
    1. User-provided topic
    2. AI-generated topic pool
    """

    # Manual override always wins
    if user_topic:
        logger.info("Using user-provided topic")
        topic = user_topic.strip()
        add_topics([topic])
        return topic



    # 1. Try to get existing unused topics from DB
    available = get_unused_topics()

    # 2. If none, generate more
    if not available:
        logger.info("No unused topics found in DB. Generating new batch...")
        new_batch = _generate_topics() 

        available = new_batch

    if not available:
        # Fallback if generation failed
        logger.error("Failed to generate topics.")
        return "LinkedIn Content Strategy: How to be consistent."

    # 3. Select one
    topic = random.choice(available)

    # Handle topic being a dict (from DB) or string (fallback/user)
    topic_content = topic['content'] if isinstance(topic, dict) else topic
    
    logger.info(f"Selected topic: {topic_content}")
    
    mark_topic_used(topic_content)
    
    return topic


def add_user_topic(topic):
    """
    Adds a user-provided topic to the pool.
    """
    add_topics([topic])
    logger.info(f"Added user topic: {topic}")



def delete_topic(topic):
    """
    Deletes a topic from the pool.
    """
    db_delete_topic(topic)
    logger.info(f"Deleted topic: {topic}")