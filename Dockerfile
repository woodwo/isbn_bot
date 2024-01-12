# Use the official Python base image
FROM python:3.10-slim-buster

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 -y && apt-get install zbar-tools -y
# Set the working directory in the container
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Specify the command to run your application
CMD ["python", "app.py"]

