#use the python 3.11 slim image
FROM python:3.11-slim

#set up the working directory for all the commands to run inside the container
WORKDIR /app

#copy the requirements.txt file into the container
COPY requirements.txt .

#install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

#copy the rest of the application code into the container
COPY . .

#expose the port 8000
EXPOSE 8000

#run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

