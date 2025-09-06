from celery import Celery

# Celery configuration
celery_app = Celery(
    'agent_hub',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['tasks.agent_tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

if __name__ == '__main__':
    celery_app.start()