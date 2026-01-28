# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_HOST 0.0.0.0
ENV FLASK_PORT 7860
ENV FLASK_DEBUG False

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Expose the port (Hugging Face standard)
EXPOSE 7860

# Command to run the application
# Using gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app.main:app"]
