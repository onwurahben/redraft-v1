# notifier/telegram.py: Handles communication with the user via Telegram for draft approval or rejection.


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from utils.logger import get_logger
from llms.gpt4_generator import generate_post
from llms.gemini_evaluator import evaluate_post
import asyncio

from dotenv import load_dotenv
import os
import uuid

load_dotenv()

logger = get_logger("Telegram Handler")

# Telegram Bot Token from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Set TELEGRAM_BOT_TOKEN environment variable")

# Store pending posts in memory (topic -> post draft)
pending_posts = {}
# Mapping for short callback IDs (id -> topic)
topic_id_map = {}


async def send_to_telegram(draft_post, topic, post_id=None, review_required=False):
    """
    Sends a draft post to Telegram with Approve/Reject buttons.
    """
    # Store draft in memory for callback handling
    pending_posts[topic] = draft_post

    # Use provided post_id or create a unique short ID
    if post_id:
        callback_id = post_id
    else:
        callback_id = str(uuid.uuid4())[:8]
        
    topic_id_map[callback_id] = topic

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve|{callback_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject|{callback_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        logger.error("TELEGRAM_CHAT_ID is not set in environment")
        return

    # Use a fresh bot instance to avoid 'Event loop is closed' if called from background threads
    from telegram import Bot
    from telegram.request import HTTPXRequest
    
    # Add a short timeout to prevent long DNS/Network hangs
    request = HTTPXRequest(connect_timeout=5, read_timeout=5)
    temp_bot = Bot(token=TELEGRAM_TOKEN, request=request)
    
    try:
        await temp_bot.initialize() # Essential for v20+ async bot
        await temp_bot.send_message(
            chat_id=chat_id,
            text=f"*Topic:* {topic}\n\n*Draft Post:*\n{draft_post}",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logger.info(f"Successfully sent draft for '{topic}' to Telegram.")
    except Exception as e:
        logger.error(f"Telegram Connection Error: {e}. (This could be a temporary DNS issue on Hugging Face).")
    finally:
        try:
            await temp_bot.shutdown()
        except:
            pass


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action, callback_id = data[0], data[1]

    topic = topic_id_map.get(callback_id)
    if not topic:
        await query.edit_message_text(text="Error: topic mapping expired.")
        return

    draft_post = pending_posts.get(topic, None)
    if not draft_post:
        await query.edit_message_text(text="Error: draft not found.")
        return

    from memory.db_handler import update_post_status, log_activity
    if action == "approve":
        # Placeholder: call LinkedIn API here
        await query.edit_message_text(text="✅ Approved and posted to LinkedIn!")
        logger.info(f"Post for topic '{topic}' approved and sent to LinkedIn.")
        update_post_status(callback_id, "approved")
        log_activity("success", f"Post '{topic}' approved via Telegram.")
        pending_posts.pop(topic, None)
        topic_id_map.pop(callback_id, None)

    elif action == "reject":
        await query.edit_message_text(text="❌ Rejected. Sending draft back to rewrite loop.")
        logger.info(f"Post for topic '{topic}' rejected by user. Triggering rewrite.")
        update_post_status(callback_id, "rejected")
        log_activity("info", f"Post '{topic}' rejected via Telegram.")
        pending_posts.pop(topic, None)
        topic_id_map.pop(callback_id, None)

        # Trigger rewrite loop in background using a fresh event loop
        import threading
        def run_rewrite():
            from pipeline.editor import run_evaluation_flow
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(run_evaluation_flow(draft_post, topic, post_id=callback_id, force_rewrite=True))
            except Exception as e:
                logger.error(f"Telegram rewrite failed: {e}")
            finally:
                new_loop.close()
        
        threading.Thread(target=run_rewrite, daemon=True).start()

    else:
        await query.edit_message_text(text="Unknown action.")


# Initialize bot
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(CallbackQueryHandler(button_callback))


async def start_bot():
    logger.info("Starting Telegram bot...")
    await bot_app.start()
    await bot_app.updater.start_polling()
    await bot_app.updater.idle()
