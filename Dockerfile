# Use Python 3.9 slim image for smaller container size
FROM python:3.9-slim

# Set working directory for the application
WORKDIR /app

# Copy requirements file first to leverage Docker layer caching
# Dependencies will only be reinstalled if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir: Reduces image size by not caching pip packages
# --trusted-host: Allows installation from PyPI without SSL verification issues
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the entire application directory structure
COPY main.py .
COPY app/ ./app/

# Create directory for persistent data storage
RUN mkdir -p /app/data

# Define volume mount point for data persistence across container restarts
VOLUME /app/data

# Expose port 5000 for the Flask application
EXPOSE 5000

# Set Flask environment variables
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run the Flask application
CMD ["python", "main.py"]