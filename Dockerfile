# Use the Python 3.10 base image
FROM python:3.10-slim

# Install required system packages (ffmpeg, ffprobe, etc.)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy source files
COPY requirements.txt ./
COPY main.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Use Functions Framework for Cloud Functions
ENV FUNCTION_TARGET=run
ENV FUNCTION_SIGNATURE_TYPE=cloudevent

# Expose the default port
EXPOSE 8080

# Run the Cloud Function
CMD ["functions-framework", "--target=run", "--port=8080"]
