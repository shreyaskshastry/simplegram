# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if any (none needed for this basic setup)
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Run the application
# host 0.0.0.0 is required for the container to be accessible from the outside
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]