FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir kopf kubernetes

# Copy operator code
COPY src/operator.py .

# Run the operator
CMD ["kopf", "run", "--namespace=film-review", "operator.py"]
