"""
Celery application for distributed game execution.

This module initializes Celery with Redis as the broker and result backend.
Workers connect to this app to pull and execute game tasks.
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis connection URL from environment
# Format: redis://[user:password@]hostname:port/db_number
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Initialize Celery app
app = Celery(
    'snakebench',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks']  # Auto-discover tasks from tasks.py
)

# Celery configuration
app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata

    # Worker settings
    worker_prefetch_multiplier=1,  # Workers fetch one task at a time
    task_acks_late=True,  # Acknowledge task after completion (improves reliability)
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies

    # Task routing (using default 'celery' queue)
    # task_routes={
    #     'backend.tasks.run_game_task': {'queue': 'games'},
    # },

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

if __name__ == '__main__':
    app.start()
