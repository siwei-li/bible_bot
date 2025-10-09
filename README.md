# Local development
pip3 install -r requirements.txt
python3 -m uvicorn poc_app:fastapi_app --reload --port 5017

# Docker
docker compose up --build

Expose ngrok: ngrok http 5017

---
TODO list:
- info for each of the domains
