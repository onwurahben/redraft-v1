import os
import time
from supabase import create_client, Client
from utils.logger import get_logger
from dotenv import load_dotenv
import sys

load_dotenv()
logger = get_logger("DB Handler")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# Initialize client only if valid credentials exist
supabase: Client = None

if not (url and key):
    logger.error("Supabase credentials not found.")
else:
    try:
        supabase = create_client(url, key)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {e}")

def safe_execute(query_builder, max_retries=3):
    """
    Executes a Supabase query with retries specifically for WinError 10035 (Windows socket busy).
    """
    for attempt in range(max_retries):
        try:
            return query_builder.execute()
        except Exception as e:
            err_msg = str(e)
            if ("10035" in err_msg or "WSAEWOULDBLOCK" in err_msg) and attempt < max_retries - 1:
                wait_time = 0.2 * (attempt + 1)
                logger.warning(f"Database busy (10035). Retrying in {wait_time}s... (Attempt {attempt + 1})")
                time.sleep(wait_time)
                continue
            raise e

def get_stats():
    """Fetch statistics from the database."""
    if not supabase:
        return {"total_generated": 0, "pending_review": 0, "topics_available": 0}
    
    try:
        posts = safe_execute(supabase.table("posts").select("id", count="exact"))
        pending = safe_execute(supabase.table("posts").select("id", count="exact").eq("status", "pending"))
        topics = safe_execute(supabase.table("topics").select("id", count="exact").eq("used", False))
        
        return {
            "total_generated": posts.count or 0,
            "pending_review": pending.count or 0,
            "topics_available": topics.count or 0
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"total_generated": 0, "pending_review": 0, "topics_available": 0}

def get_activity(limit=5):
    """Fetch recent system activity."""
    if not supabase:
        # Fallback dummy data
        return [{"type": "info", "message": "Database not configured. Using placeholder data.", "time": "Just now"}]
    
    try:
        response = safe_execute(supabase.table("activity").select("*").order("created_at", desc=True).limit(limit))
        return response.data
    except Exception as e:
        logger.error(f"Error fetching activity: {e}")
        return []

def log_activity(activity_type, message):
    """Log a new activity to the database."""
    if not supabase:
        logger.info(f"MOCK LOG [{activity_type}]: {message}")
        return
    
    try:
        safe_execute(supabase.table("activity").insert({"type": activity_type, "message": message}))
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

def get_pending_posts():
    """Fetch posts awaiting review."""
    if not supabase:
        return []
    
    try:
        response = safe_execute(supabase.table("posts").select("*").eq("status", "pending").order("created_at", desc=True))
        return response.data
    except Exception as e:
        logger.error(f"Error fetching pending posts: {e}")
        return []

def update_post_status(post_id, status, content=None):
    """Update a post's status and optionally its content."""
    if not supabase:
        return False
    
    try:
        update_data = {"status": status}
        if content:
            update_data["content"] = content
        
        safe_execute(supabase.table("posts").update(update_data).eq("id", post_id))
        return True
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        return False

def get_post(post_id):
    """Fetch a single post by ID."""
    if not supabase:
        return None
    
    try:
        response = safe_execute(supabase.table("posts").select("*").eq("id", post_id))
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching post {post_id}: {e}")
        return None

def add_post(post_id, topic, content, status="pending"):
    """Insert a new post draft into the database."""
    if not supabase:
        logger.info(f"MOCK POST SAVE: {topic}")
        return False
    
    try:
        safe_execute(supabase.table("posts").upsert({
            "id": post_id,
            "topic": topic,
            "content": content,
            "status": status
        }))
        return True
    except Exception as e:
        logger.error(f"Error adding post: {e}")
        return False

def add_topics(topic_list):
    """Insert multiple topics into the database."""
    if not supabase:
        logger.info(f"MOCK TOPICS SAVE: {len(topic_list)} topics")
        return False
    
    try:
        data = [{"content": t, "used": False} for t in topic_list]
        safe_execute(supabase.table("topics").insert(data))
        return True
    except Exception as e:
        logger.error(f"Error adding topics: {e}")
        return False

def mark_topic_used(topic):
    """Mark a topic as used in the database."""
    if not supabase:
        logger.info(f"MOCK TOPIC MARK AS USED: {topic}")
        return False
    
    try:
        safe_execute(supabase.table("topics").update({"used": True}).eq("content", topic))
        return True
    except Exception as e:
        logger.error(f"Error marking topic as used: {e}")
        return False

def get_unused_topics():
    """Get unused topics from the database."""
    if not supabase:
        logger.info("MOCK GET UNUSED TOPICS")
        return []
    
    try:
        response = safe_execute(supabase.table("topics").select("*").eq("used", False))
        return response.data
    except Exception as e:
        logger.error(f"Error getting unused topics: {e}")
        return []

def delete_topic(topic):
    """
    Deletes a topic from the database.
    """
    if not supabase:
        logger.info(f"MOCK TOPIC DELETE: {topic}")
        return False
    
    try:
        safe_execute(supabase.table("topics").delete().eq("content", topic))
        return True
    except Exception as e:
        logger.error(f"Error deleting topic: {e}")
        return False

def get_setting(key, default=None):
    """Fetch a configuration setting from the database."""
    if not supabase:
        return default
    try:
        response = safe_execute(supabase.table("settings").select("value").eq("key", key))
        if response.data:
            return response.data[0]["value"]
        return default
    except Exception as e:
        logger.error(f"Error fetching setting {key}: {e}")
        return default

def update_setting(key, value):
    """Update or create a configuration setting in the database."""
    if not supabase:
        return False
    try:
        safe_execute(supabase.table("settings").upsert({"key": key, "value": value}))
        return True
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        return False