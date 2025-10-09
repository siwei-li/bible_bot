import os
import sys
import logging
from dotenv import load_dotenv
from pywa_async import WhatsApp
from openai import OpenAI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from session.session_manager import SessionManager
from services.questions_service import QuestionsService
from data.audio_handler import AudioHandler
from handlers.message_handlers import MessageHandlers
from handlers.question_handler import QuestionHandler
from handlers.consent_handler import ConsentHandler
from handlers.domain_handler import DomainHandler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        # logging.StreamHandler(sys.stderr)
    ],
    force=True  # Override any existing logging configuration
)
logger = logging.getLogger("poc_app")
logging.getLogger().setLevel(logging.INFO)

load_dotenv()

WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
# openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
# if not openai_client.api_key:
#     raise ValueError("Set OPENAI_API_KEY in .env file")

audio_handler = AudioHandler(
    whatsapp_token=WHATSAPP_TOKEN,
)

session_manager = SessionManager()
questions_service = QuestionsService()
question_handler = QuestionHandler(session_manager, questions_service)
consent_handler = ConsentHandler(session_manager, questions_service)
domain_handler = DomainHandler(session_manager, questions_service)
message_handlers = MessageHandlers(
    session_manager,
    consent_handler,
    audio_handler,
    question_handler,
    domain_handler
)

fastapi_app = FastAPI()

NGROK_URL = os.getenv("NGROK_URL", "http://localhost:5017")
# Configure CORS to allow ngrok domains
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.ngrok.io",
        "https://*.ngrok-free.app", 
        "http://localhost:5017",
        NGROK_URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.get("/status")
def status():
    return {"message": "FastAPI app running"}


@fastapi_app.get("/webhook-url")
def get_webhook_url():
    return {"webhook_url": f"{NGROK_URL}/whatsapp"}

# Note: The /whatsapp webhook endpoint is automatically registered by pywa_async
# when we initialize the WhatsApp client with server=fastapi_app and webhook_endpoint='/whatsapp'
# No need to manually define the webhook route here


wa = WhatsApp(
    phone_id=os.getenv('WHATSAPP_PHONE_ID'),
    token=WHATSAPP_TOKEN,
    server=fastapi_app,
    verify_token=os.getenv('WHATSAPP_VERIFY_TOKEN'),
    webhook_endpoint='/whatsapp',  # Changed from default '/' to avoid conflicts
    webhook_challenge_delay=60,  # Increase delay
    # callback_url=os.getenv('WHATSAPP_CALLBACK_URL'),
    # app_id=int(os.getenv('WHATSAPP_APP_ID')),
    # app_secret=os.getenv('WHATSAPP_APP_SECRET'),
)


@wa.on_message()
async def handle_message(wa_client, msg):
    """Main message handler - delegates to specialized handlers"""
    try:
        user_id = msg.from_user.wa_id
        session = session_manager.get_session(user_id)
        logger.info(f"Session state: {session['state']}")
        logger.info(f"Message type: {msg.type}")

        if session["state"] == session_manager.UserState.NEW_USER:
            await consent_handler.send_welcome_message(wa_client, user_id)
            return

        if msg.type == "audio":
            await message_handlers.handle_audio_message(wa_client, user_id, msg)
        else:
            await message_handlers.handle_text_message(wa_client, user_id, msg.text)

    except Exception as e:
        print(f"Error in handle_message: {e}")
        await wa_client.send_message(
            to=user_id,
            text="Sorry, something went wrong. Please try again."
        )

from linguist.routes import router as linguist_router
from linguist.campaign_routes import router as campaign_router

# Make WhatsApp client available to campaign routes
fastapi_app.state.wa_client = wa

fastapi_app.include_router(linguist_router)
fastapi_app.include_router(campaign_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("poc_app:fastapi_app", host="0.0.0.0",
                port=int(os.getenv('LOCAL_PORT', 5017)), log_level="info")
