
import os 
from celery import Celery 

# Celery configuration to read from environment variables so docker can supply the values
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
CELERY_BACKEND_URL = os.environ.get('CELERY_BACKEND_URL', 'redis://localhost:6379/1')

#create a celery instance with the name of the project and the broker and backend urls
celery = Celery("redacTLDR", broker = CELERY_BROKER_URL, backend = CELERY_BACKEND_URL)

