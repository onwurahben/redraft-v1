import asyncio
import os
import sys
from pipeline.worker import create_post
from utils.logger import get_logger

logger = get_logger("CLI-Pipeline")

async def main():
    """
    Main entry point for scheduled generation.
    Usage: python run_pipeline.py
    """
    logger.info("Starting automated post generation sequence...")
    
    try:
        # Check if automation is enabled in DB
        from memory.db_handler import get_setting
        is_enabled = get_setting("daily_generation_enabled", default=True)
        
        if not is_enabled:
            logger.info("Automation is DISABLED via dashboard. Skipping generation.")
            print("Automated generation is currently disabled.")
            return

        # We run the standard create_post flow.
        # It will automatically:
        # 1. Get a topic (AI generated since no user_topic passed)
        # 2. Build prompt
        # 3. Generate draft
        # 4. Evaluate and rewrite if needed
        # 5. Save to Supabase and notify Telegram (via evaluation flow)
        
        post_content = await create_post()
        
        if post_content:
            logger.info("Automated generation successful.")
            print("Successfully generated new LinkedIn post draft.")
        else:
            logger.error("Generation returned no content.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
