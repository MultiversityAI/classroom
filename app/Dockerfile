FROM python:3.10-slim

WORKDIR /app

# Copy the entire project directory
COPY . /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose both ports
EXPOSE 8001 8080

# Run using Python directly
CMD ["python", "main.py"]