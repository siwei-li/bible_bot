FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5017

CMD ["uvicorn", "app.poc_app:fastapi_app", "--host", "0.0.0.0", "--port", "5017"]