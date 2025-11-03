#set the base environemnt
FROM python:3.11-slim

#set the working directory for all the commands to run inside the container
WORKDIR /app

#copy the requirements.txt file into the container
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

#celery worker command to run the worker, pointing to the cerlery app object and -Q default to run the default queue restricts the worker to that queue
CMD ["celery", "-A", "workers.celery_app.celery", "worker", "-Q", "default", "--loglevel=INFO"]
