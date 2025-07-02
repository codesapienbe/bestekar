#!/usr/bin/env python3
"""
Bestewk - Celery task queue system for Bestekar
Handles background music generation and UI tasks
"""

import os
import sys
import time
import asyncio
from pathlib import Path
from typing import Optional, Any, List, Dict
from datetime import datetime

# Celery imports
from celery import Celery
from celery.result import AsyncResult
from celery.signals import worker_ready, worker_shutdown

# Logging
from loguru import logger

# Configure logging for worker
def _configure_worker_logging():
    """Configure logging specifically for Celery workers."""
    logger.remove()
    
    # Worker-specific log level
    level = os.getenv("BESTEWK_LOG_LEVEL", "INFO").upper()
    
    # Console logging for worker
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>WORKER</cyan> | <level>{message}</level>",
        colorize=True
    )
    
    # Worker-specific log file
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "bestewk_worker.log",
        rotation="50 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | WORKER | {message}"
    )

_configure_worker_logging()

# --------------------------------------------------
# Celery App Configuration
# --------------------------------------------------

def create_celery_app() -> Celery:
    """Create and configure Celery app for task management."""
    
    # Create Celery app with memory-based broker for simplicity
    celery_app = Celery(
        'bestewk',
        broker='memory://',
        backend='cache+memory://',
        include=['bestewk']
    )
    
    # Celery configuration optimized for music generation
    celery_app.conf.update(
        # Serialization
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        
        # Timezone
        timezone='UTC',
        enable_utc=True,
        
        # Task tracking
        task_track_started=True,
        task_send_sent_event=True,
        task_time_limit=7200,  # 2 hours max per task
        task_soft_time_limit=6600,  # 1h 50m soft limit
        
        # Routing
        task_routes={
            'bestewk.generate_music': {'queue': 'generate_music'},
            'bestewk.open_help': {'queue': 'ui_actions'},
            'bestewk.exit_app': {'queue': 'ui_actions'},
        },
        
        # Worker configuration
        worker_prefetch_multiplier=1,  # Process one task at a time
        task_acks_late=True,  # Acknowledge after completion
        worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
        worker_pool_restarts=True,
        
        # Memory optimization
        worker_disable_rate_limits=True,
        task_ignore_result=False,  # Keep results for monitoring
        result_expires=3600,  # Results expire after 1 hour
        
        # Error handling
        task_reject_on_worker_lost=True,
        task_default_retry_delay=60,
        task_max_retries=3,
    )
    
    return celery_app

# Global Celery app instance
celery_app = create_celery_app()

# --------------------------------------------------
# Task Definitions
# --------------------------------------------------

@celery_app.task(bind=True, name='bestewk.generate_music', queue='generate_music')
def generate_music_task(self, lyrics_text: str, style_text: str, duration: int, 
                       rvc_model_path: str = "", mode: str = "Complete Song (RVC)"):
    """
    Celery task for music generation.
    
    Args:
        lyrics_text: The lyrics text content
        style_text: Musical style description
        duration: Duration in seconds
        rvc_model_path: Path to RVC model (optional)
        mode: Generation mode
    
    Returns:
        Dict with generation results
    """
    task_id = self.request.id
    start_time = time.time()
    
    try:
        # Update task state to show progress
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'initializing',
                'progress': 5,
                'message': 'Starting music generation...',
                'task_id': task_id
            }
        )
        
        logger.info(f"Starting music generation task {task_id}")
        logger.info(f"Mode: {mode}, Duration: {duration}s, Lyrics: {len(lyrics_text)} chars")
        
        # Import here to avoid circular imports and ensure worker isolation
        from bestekar import TurkishSongGenerator, TurkishSongGeneratorWithRVC, RVCSinger
        
        # Create output directory
        output_dir = Path("music")
        output_dir.mkdir(exist_ok=True)
        
        # Progress update
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'setup',
                'progress': 10,
                'message': 'Setting up AI models...',
                'task_id': task_id
            }
        )
        
        output_file = None
        
        async def _run_generation():
            """Async wrapper for generation tasks."""
            nonlocal output_file
            
            if mode == "Complete Song (RVC)":
                logger.info("Starting complete song generation with RVC")
                
                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'rvc_setup',
                        'progress': 15,
                        'message': 'Initializing RVC pipeline...',
                        'task_id': task_id
                    }
                )
                
                generator = TurkishSongGeneratorWithRVC(
                    model_name=None,  # Use automatic resource-based selection
                    rvc_model_path=rvc_model_path if rvc_model_path else None
                )
                
                # Progress update for generation start
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'generating',
                        'progress': 25,
                        'message': 'Generating complete song with vocals...',
                        'task_id': task_id
                    }
                )
                
                output_file = await generator.generate_complete_song(
                    lyrics=lyrics_text,
                    style=style_text,
                    duration=duration,
                    output_name=f"music/bestewk_rvc_{int(time.time())}",
                    add_vocals=True
                )
                
            elif mode == "Instrumental Only":
                logger.info("Starting instrumental generation")
                
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'instrumental',
                        'progress': 20,
                        'message': 'Generating instrumental track...',
                        'task_id': task_id
                    }
                )
                
                generator = TurkishSongGenerator(None)  # Auto-select model
                
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'generating',
                        'progress': 30,
                        'message': 'Creating instrumental music...',
                        'task_id': task_id
                    }
                )
                
                output_file = generator.generate_song(
                    lyrics=lyrics_text,
                    style=style_text,
                    duration=duration,
                    output_name=f"music/bestewk_instrumental_{int(time.time())}",
                    instrumental=True
                )
                
            elif mode == "Vocals Only (RVC)":
                logger.info("Starting vocals-only generation with RVC")
                
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'vocals',
                        'progress': 25,
                        'message': 'Generating vocals with RVC...',
                        'task_id': task_id
                    }
                )
                
                rvc_singer = RVCSinger(rvc_model_path, None)
                output_file = await rvc_singer.generate_singing_voice(
                    lyrics=lyrics_text,
                    output_path=f"music/bestewk_vocals_{int(time.time())}.wav"
                )
            
            # Final progress update
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': 'finalizing',
                    'progress': 95,
                    'message': 'Finalizing output...',
                    'task_id': task_id
                }
            )
        
        # Run the async generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_generation())
        finally:
            loop.close()
        
        # Check results and finalize
        elapsed_time = time.time() - start_time
        
        if output_file and Path(output_file).exists():
            file_size = Path(output_file).stat().st_size / (1024 * 1024)  # MB
            
            logger.success(
                f"Music generation task {task_id} completed successfully",
                file=output_file,
                duration=f"{elapsed_time:.1f}s",
                size=f"{file_size:.2f}MB"
            )
            
            return {
                'status': 'SUCCESS',
                'output_file': str(output_file),
                'filename': Path(output_file).name,
                'file_size_mb': file_size,
                'generation_time': elapsed_time,
                'mode': mode,
                'duration': duration,
                'progress': 100,
                'message': 'Generation completed successfully!',
                'task_id': task_id
            }
        else:
            logger.error(f"Music generation task {task_id} failed - no output file created")
            return {
                'status': 'FAILURE',
                'error': 'No output file generated',
                'mode': mode,
                'duration': duration,
                'generation_time': elapsed_time,
                'progress': 0,
                'message': 'Generation failed - no output created',
                'task_id': task_id
            }
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = str(e)
        
        logger.exception(f"Music generation task {task_id} crashed", error=error_msg)
        
        return {
            'status': 'FAILURE',
            'error': error_msg,
            'mode': mode,
            'duration': duration,
            'generation_time': elapsed_time,
            'progress': 0,
            'message': f'Generation failed: {error_msg}',
            'task_id': task_id
        }

@celery_app.task(name='bestewk.open_help', queue='ui_actions')
def open_help_task():
    """Celery task for opening help page."""
    import webbrowser
    
    try:
        help_url = "https://github.com/YapayMuzik/Bestekar"
        webbrowser.open(help_url)
        
        logger.info("Help page opened successfully", url=help_url)
        return {
            'status': 'SUCCESS',
            'action': 'help_opened',
            'url': help_url,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to open help page: {error_msg}")
        
        return {
            'status': 'FAILURE',
            'error': error_msg,
            'action': 'help_failed',
            'timestamp': datetime.now().isoformat()
        }

@celery_app.task(name='bestewk.exit_app', queue='ui_actions')
def exit_app_task():
    """Celery task for application exit coordination."""
    try:
        logger.info("Exit task initiated - coordinating shutdown")
        
        # Signal to cleanup resources
        cleanup_results = []
        
        # Try to cleanup any active generation tasks
        try:
            active_tasks = get_active_generation_tasks()
            if active_tasks:
                logger.info(f"Found {len(active_tasks)} active tasks during shutdown")
                
                # Revoke active generation tasks
                for task_info in active_tasks:
                    try:
                        celery_app.control.revoke(task_info['id'], terminate=True)
                        logger.info(f"Revoked task {task_info['id']}")
                        cleanup_results.append(f"Revoked task {task_info['id']}")
                    except Exception as e:
                        logger.warning(f"Failed to revoke task {task_info['id']}: {e}")
                        cleanup_results.append(f"Failed to revoke {task_info['id']}")
            else:
                cleanup_results.append("No active tasks to cleanup")
                
        except Exception as e:
            logger.warning(f"Error during task cleanup: {e}")
            cleanup_results.append(f"Cleanup error: {e}")
        
        logger.info("Application exit task completed")
        
        return {
            'status': 'SUCCESS',
            'action': 'exit_initiated',
            'cleanup_results': cleanup_results,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during exit task: {error_msg}")
        
        return {
            'status': 'FAILURE',
            'error': error_msg,
            'action': 'exit_failed',
            'timestamp': datetime.now().isoformat()
        }

# --------------------------------------------------
# Application Initialization Task
# --------------------------------------------------

@celery_app.task(name='bestewk.app_init', queue='ui_actions')
def app_init_task():
    """Run heavy application initialisation (e.g., downloading models) in a
    background Celery worker so the GUI remains responsive."""
    start_time = datetime.now()
    try:
        from bestekar import setup_rvc_integration  # Imported here to avoid heavy import in worker start

        setup_rvc_integration()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("Application initialisation completed", duration=f"{elapsed:.1f}s")
        return {
            'status': 'SUCCESS',
            'action': 'app_initialised',
            'duration_sec': elapsed,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.exception("Application initialisation failed", error=str(e))
        return {
            'status': 'FAILURE',
            'error': str(e),
            'action': 'app_initialisation_failed',
            'timestamp': datetime.now().isoformat()
        }

# --------------------------------------------------
# Task Management Functions
# --------------------------------------------------

def get_active_generation_tasks() -> List[Dict[str, Any]]:
    """Get all active music generation tasks."""
    try:
        active_tasks = []
        inspect = celery_app.control.inspect()
        
        # Get active tasks from all workers
        active = inspect.active()
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    if task['name'] == 'bestewk.generate_music':
                        active_tasks.append({
                            'id': task['id'],
                            'name': task['name'],
                            'worker': worker,
                            'args': task.get('args', []),
                            'kwargs': task.get('kwargs', {}),
                            'state': 'ACTIVE',
                            'time_start': task.get('time_start')
                        })
        
        # Get scheduled tasks
        scheduled = inspect.scheduled()
        if scheduled:
            for worker, tasks in scheduled.items():
                for task in tasks:
                    if task['request']['name'] == 'bestewk.generate_music':
                        active_tasks.append({
                            'id': task['request']['id'],
                            'name': task['request']['name'],
                            'worker': worker,
                            'state': 'SCHEDULED',
                            'eta': task.get('eta'),
                            'args': task['request'].get('args', []),
                            'kwargs': task['request'].get('kwargs', {})
                        })
        
        # Get reserved tasks (queued but not started)
        reserved = inspect.reserved()
        if reserved:
            for worker, tasks in reserved.items():
                for task in tasks:
                    if task['name'] == 'bestewk.generate_music':
                        active_tasks.append({
                            'id': task['id'],
                            'name': task['name'],
                            'worker': worker,
                            'state': 'RESERVED',
                            'args': task.get('args', []),
                            'kwargs': task.get('kwargs', {})
                        })
        
        return active_tasks
        
    except Exception as e:
        logger.error(f"Error getting active generation tasks: {e}")
        return []

def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """Get result of a specific task."""
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        task_info = {
            'id': task_id,
            'state': result.state,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else None,
            'failed': result.failed() if result.ready() else None,
        }
        
        if result.ready():
            if result.successful():
                task_info['result'] = result.result
            elif result.failed():
                task_info['error'] = str(result.info)
        else:
            # Task is still running, get progress info
            if hasattr(result, 'info') and isinstance(result.info, dict):
                task_info['progress'] = result.info
        
        return task_info
        
    except Exception as e:
        logger.error(f"Error getting task result for {task_id}: {e}")
        return None

def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """Revoke/cancel a task."""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Revoked task {task_id} (terminate={terminate})")
        return True
    except Exception as e:
        logger.error(f"Error revoking task {task_id}: {e}")
        return False

def get_worker_stats() -> Dict[str, Any]:
    """Get worker statistics."""
    try:
        inspect = celery_app.control.inspect()
        
        stats = {
            'workers': {},
            'total_workers': 0,
            'total_active_tasks': 0,
            'total_scheduled_tasks': 0,
            'total_reserved_tasks': 0,
        }
        
        # Get worker stats
        worker_stats = inspect.stats()
        if worker_stats:
            stats['workers'] = worker_stats
            stats['total_workers'] = len(worker_stats)
        
        # Count tasks
        active = inspect.active()
        if active:
            stats['total_active_tasks'] = sum(len(tasks) for tasks in active.values())
        
        scheduled = inspect.scheduled()
        if scheduled:
            stats['total_scheduled_tasks'] = sum(len(tasks) for tasks in scheduled.values())
        
        reserved = inspect.reserved()
        if reserved:
            stats['total_reserved_tasks'] = sum(len(tasks) for tasks in reserved.values())
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting worker stats: {e}")
        return {'error': str(e)}

# --------------------------------------------------
# Worker Lifecycle Hooks
# --------------------------------------------------

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready signal."""
    logger.info("Bestewk worker is ready and accepting tasks")
    logger.info(f"Worker: {sender}")
    logger.info("Queues: generate_music, ui_actions")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown signal."""
    logger.info("Bestewk worker is shutting down")
    
    # Cleanup any resources if needed
    try:
        # Cancel any running tasks if worker is shutting down
        active_tasks = get_active_generation_tasks()
        if active_tasks:
            logger.info(f"Cancelling {len(active_tasks)} active tasks during shutdown")
            for task in active_tasks:
                revoke_task(task['id'], terminate=True)
    except Exception as e:
        logger.error(f"Error during worker shutdown cleanup: {e}")

# --------------------------------------------------
# Worker Entry Point
# --------------------------------------------------

def run_worker(argv=None):
    """Run Celery worker for processing tasks."""
    print("🎵 Bestewk - Bestekar Task Worker")
    print("=" * 50)
    print("📋 Processing queues: generate_music, ui_actions")
    print("🔄 Memory-based broker (no Redis/RabbitMQ required)")
    print("🎯 Optimized for music generation tasks")
    print("💡 Use Ctrl+C to stop the worker")
    print("=" * 50)
    
    # Configure worker arguments
    worker_args = [
        'worker',
        '--loglevel=INFO',
        '--queues=generate_music,ui_actions',
        '--concurrency=1',  # Single process for memory broker
        '--pool=solo',      # Use solo pool for memory broker compatibility
        '--without-gossip', # Disable gossip for memory broker
        '--without-mingle', # Disable mingle for memory broker
        '--without-heartbeat', # Disable heartbeat for memory broker
    ]
    
    if argv:
        worker_args.extend(argv)
    
    try:
        # Start the worker
        celery_app.start(worker_args)
        return 0
        
    except KeyboardInterrupt:
        print("\n👋 Worker stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Worker error: {e}")
        logger.exception("Worker startup failed")
        return 1

# --------------------------------------------------
# Convenience Functions for Main App
# --------------------------------------------------

def submit_music_generation(lyrics_text: str, style_text: str, duration: int, 
                          rvc_model_path: str = "", mode: str = "Complete Song (RVC)") -> str:
    """
    Submit a music generation task.
    
    Returns:
        Task ID for monitoring
    """
    task = celery_app.send_task(
        'bestewk.generate_music',
        kwargs={
            'lyrics_text': lyrics_text,
            'style_text': style_text,
            'duration': duration,
            'rvc_model_path': rvc_model_path,
            'mode': mode,
        },
    )
    
    logger.info(f"Submitted music generation task {task.id}")
    return task.id

def submit_help_action() -> str:
    """Submit help action task."""
    task = celery_app.send_task('bestewk.open_help')
    logger.info(f"Submitted help task {task.id}")
    return task.id

def submit_exit_action() -> str:
    """Submit exit action task."""
    task = celery_app.send_task('bestewk.exit_app')
    logger.info(f"Submitted exit task {task.id}")
    return task.id

# Export commonly used functions and objects
__all__ = [
    'celery_app',
    'generate_music_task',
    'open_help_task', 
    'exit_app_task',
    'app_init_task',
    'get_active_generation_tasks',
    'get_task_result',
    'revoke_task',
    'get_worker_stats',
    'submit_music_generation',
    'submit_help_action',
    'submit_exit_action',
    'run_worker'
]

# --------------------------------------------------
# CLI Entry Point
# --------------------------------------------------

def main():
    exit(run_worker())

if __name__ == "__main__":
    main()
