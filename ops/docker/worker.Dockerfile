#set the base environemnt
FROM python:3.11-slim

#set the working directory for all the commands to run inside the container
WORKDIR /app

#copy the requirements.txt file into the container
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

# -A points at the celery app instance; -Q default restricts to the default queue
CMD ["celery", "-A", "services.worker.app.celery_app.celery", "worker", "-Q", "default", "--loglevel=INFO"]
