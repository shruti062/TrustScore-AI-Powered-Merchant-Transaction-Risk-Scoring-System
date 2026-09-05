# TrustScore — Docker image
#
# Build (from the repo root, where this file lives):
#     docker build -t trustscore .
# Run:
#     docker run -p 5000:5000 trustscore
#
# The image trains the model at build time (generate_data.py +
# model.py) so the container can score transactions immediately on
# startup, with no manual setup step.

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker caches this layer and skips
# reinstalling packages when only source code changes
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the project — app.py expects frontend/ to be a
# sibling of backend/, which this layout preserves
COPY backend/ backend/
COPY frontend/ frontend/

WORKDIR /app/backend

# Generate training data and train the model at build time
RUN python generate_data.py && python model.py

EXPOSE 5000

ENV FLASK_DEBUG=False
ENV PORT=5000

CMD ["python", "app.py"]
