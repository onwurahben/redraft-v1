import asyncio
from flask import render_template, request, jsonify
from flask import render_template, request, jsonify
from notifier.telegram import pending_posts, topic_id_map
from utils.logger import get_logger
from memory.db_handler import (
    get_stats, get_activity, log_activity,
    get_pending_posts, update_post_status, get_setting, update_setting, log_activity
)

logger = get_logger("Flask Dashboard")

# Global state for generation progress
generation_status = {"progress": 0, "message": "Idle", "status": "idle"}

def register_routes(app):
    """
    Registers all Flask endpoints for the app.
    """

    #-------------------------------
    # API: Progress
    # Returns the current generation status.
    # URL: /api/progress
    # Method: GET
    #-------------------------------
    @app.route('/api/progress')
    def api_progress():
        return jsonify(generation_status)

    #-------------------------------
    # Dashboard Page
    # Renders the main dashboard showing stats and recent activity.
    # URL: /
    # Method: GET
    #-------------------------------
    @app.route('/')
    def dashboard():
        stats = get_stats()
        activity = get_activity()
        return render_template('dashboard.html', stats=stats, activity=activity)

    #-------------------------------
    # Review Page
    # Shows posts that are pending review for approval.
    # Combines database pending posts with in-memory posts.
    # URL: /review
    # Method: GET
    #-------------------------------
    @app.route('/review')
    def review():
        db_posts = get_pending_posts()
        
        posts = []
        for p in db_posts:
            posts.append({
                "id": p['id'],
                "topic": p['topic'],
                "content": p['content']
            })
        
        # Include in-memory legacy posts
        for callback_id, topic in topic_id_map.items():
            if not any(p['id'] == callback_id for p in posts):
                draft = pending_posts.get(topic)
                if draft:
                    posts.append({
                        "id": callback_id,
                        "topic": topic,
                        "content": draft
                    })
        
        return render_template('review.html', posts=posts)

    #-------------------------------
    # Settings Page
    # Renders the settings page.
    #-------------------------------
    @app.route('/settings')
    def settings():
        return render_template('settings.html')

    #-------------------------------
    # Generate Content
    # Triggers post generation in a background thread using async pipeline.
    # Does not block the request; returns immediately.
    #-------------------------------
    @app.route('/generate', methods=['POST'])
    def trigger_generation():
        """Manual trigger for post generation via a background thread."""
        try:
            import threading
            from pipeline.worker import create_post
            
            data = request.json or {}
            user_topic = data.get('topic')
            
            # Reset status
            generation_status["progress"] = 5
            generation_status["message"] = "Starting..."
            generation_status["status"] = "generating"
            
            def update_progress(progress, message):
                generation_status["progress"] = progress
                generation_status["message"] = message
            
            def run_in_background():
                # Create a new event loop for this thread to run the async pipeline
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Pass the callback and optional topic to create_post
                    loop.run_until_complete(create_post(progress_callback=update_progress, user_topic=user_topic))
                    
                    # Mark as complete
                    update_progress(100, "Completed!")
                    generation_status["status"] = "idle"
                    log_activity("info", f"Content generation completed{' for topic: ' + user_topic if user_topic else ''}.")
                    
                except Exception as e:
                    logger.error(f"Generation failed: {e}")
                    update_progress(0, "Error Failed")
                    generation_status["status"] = "error"
                finally:
                    loop.close()

            # Start the thread
            thread = threading.Thread(target=run_in_background, daemon=True)
            thread.start()
            
            log_activity("info", "Content generation triggered in background.")
            return jsonify({"status": "success", "message": "Generation started."})
        except Exception as e:
            logger.error(f"Failed to trigger generation: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    #-------------------------------
    # API: Stats
    # Returns JSON of current stats and activity for UI polling.
    #-------------------------------
    @app.route('/api/stats')
    def api_stats():
        """Endpoint for UI polling to get latest stats and activity."""
        return jsonify({
            "stats": get_stats(),
            "activity": get_activity()
        })

    #-------------------------------
    # API: Get Post Status
    # Returns JSON of a specific post.
    #-------------------------------
    @app.route('/api/post/<post_id>')
    def api_get_post(post_id):
        from memory.db_handler import get_post
        post = get_post(post_id)
        if post:
            return jsonify({"status": "success", "post": post})
        return jsonify({"status": "error", "message": "Post not found"}), 404

    #-------------------------------
    # API: Settings
    #-------------------------------
    @app.route('/api/settings/automation', methods=['GET', 'POST'])
    def api_automation_setting():
        """Get or update the daily generation automation setting."""
       
        if request.method == 'POST':
            data = request.json
            enabled = data.get('enabled', True)
            update_setting("daily_generation_enabled", enabled)
            
            status_text = "ENABLED" if enabled else "DISABLED"
            log_activity("info", f"Daily automation {status_text} via dashboard.")
            return jsonify({"status": "success", "enabled": enabled})
        
        # GET request
        enabled = get_setting("daily_generation_enabled", default=True)
        return jsonify({"status": "success", "enabled": enabled})

    #-------------------------------
    # API: Approve Post
    # Approves a pending post both in DB and in-memory.
    # Payload: { "id": str, "content": str }
    #-------------------------------
    @app.route('/api/approve', methods=['POST'])
    async def approve_post():
        from pipeline.worker import create_post # Import here too for consistency if needed, though not strictly used here
        data = request.json
        post_id = data.get('id')
        content = data.get('content')
        
        # Try updating DB
        success = update_post_status(post_id, "approved", content)
        
        # Also handle in-memory if it exists
        topic = topic_id_map.get(post_id)
        if topic:
            pending_posts.pop(topic, None)
            topic_id_map.pop(post_id, None)
            success = True
        
        if success:
            log_activity("success", f"Post approved!")
            return jsonify({"status": "success"})
            
        return jsonify({"status": "error", "message": "Post not found"}), 404
    #-------------------------------
    # API: Dismiss Post
    # Dismisses a post and triggers a rewrite loop in background.
    #-------------------------------
    @app.route('/api/dismiss', methods=['POST'])
    def dismiss_post():
        data = request.json
        post_id = data.get('id')
        content = data.get('content')
        topic = data.get('topic')

        # Update DB status
        update_post_status(post_id, "dismissed")
        
        # Trigger rewrite loop in background
        from pipeline.editor import run_evaluation_flow
        import threading
        
        def run_rewrite():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_evaluation_flow(content, topic, post_id=post_id, force_rewrite=True))
                log_activity("info", f"Manual rewrite triggered for post on '{topic}'")
            except Exception as e:
                logger.error(f"Rewrite failed: {e}")
            finally:
                loop.close()

        threading.Thread(target=run_rewrite, daemon=True).start()
        
        return jsonify({"status": "success", "message": "Rewrite triggered."})
