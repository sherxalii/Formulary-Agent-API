# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# Copy .env if it exists for build-time env vars (optional)
COPY .env* ../
RUN npm run build

# Stage 2: Build the FastAPI backend
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies for PDF processing and OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY app/ ./app/
COPY backend/ ./backend/
COPY Data/ ./Data/
# Copy any other necessary directories mentioned in your code
# (e.g., Training_Source_Data if used at runtime)

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose the port Hugging Face expects
EXPOSE 7860

# Start the application on port 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]

