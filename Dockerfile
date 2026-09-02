FROM python:3.12-slim

WORKDIR /app

COPY venus_api/requirements.txt venus_api/requirements.txt
RUN pip install --no-cache-dir -r venus_api/requirements.txt

COPY venus_api/ venus_api/

RUN addgroup --system venus && adduser --system --ingroup venus venus
USER venus

EXPOSE 8080
CMD ["uvicorn", "venus_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
