# Use the official Python lightweight image for maximum efficiency
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Enable layer caching: Copy only requirements.txt first
COPY requirements.txt .

# Install dependencies without storing cache to keep image size minimal
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8080 (Google Cloud Run expectation)
EXPOSE 8080

# Command to run the FastAPI server via uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
