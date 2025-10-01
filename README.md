# Local development
pip install -r requirements.txt
python -m uvicorn poc_app:fastapi_app --reload --port 8000

# Docker
docker compose up --build