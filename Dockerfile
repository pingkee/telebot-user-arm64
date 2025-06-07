FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

# Ensure dependencies for numpy, sentence-transformers, etc.
RUN apt-get update && apt-get install -y \
    dos2unix \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY ./main.py .
COPY userbot_session.session /app/userbot_session.session
RUN dos2unix /app/main.py

# Run the bot
CMD ["python", "/app/main.py"]

