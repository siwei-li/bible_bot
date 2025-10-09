import os
import sys
import logging
from dotenv import load_dotenv
from pywa_async import WhatsApp
from pywa.types import CallbackSelection
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
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
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
if not openai_client.api_key:
    raise ValueError("Set OPENAI_API_KEY in .env file")

audio_handler = AudioHandler(
    whatsapp_token=WHATSAPP_TOKEN,
    openai_client=openai_client
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


@fastapi_app.get("/webhook")
def verify_webhook(request: Request):
    """Handle WhatsApp webhook verification"""
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    print(
        f"Webhook verification: mode={hub_mode}, "
        f"challenge={hub_challenge}, token={hub_verify_token}"
    )

    if (
        hub_mode == "subscribe"
        and hub_verify_token == os.getenv('WHATSAPP_VERIFY_TOKEN')
    ):
        return PlainTextResponse(content=str(hub_challenge))
    else:
        return PlainTextResponse(content="Forbidden", status_code=403)

# async def lifespan(app: FastAPI): #LATER - use lifespan for startup/shutdown tasks

wa = WhatsApp(
    phone_id=os.getenv('WHATSAPP_PHONE_ID'),
    token=WHATSAPP_TOKEN,
    server=fastapi_app,
    verify_token=os.getenv('WHATSAPP_VERIFY_TOKEN'),
    webhook_challenge_delay=60
)

@wa.on_callback_selection()  # No factory needed for simple string callback_data; add filters=filters.startswith('lang:') if you want to match only language callbacks
async def handle_language_selection(client: WhatsApp, sel: CallbackSelection):
    user_id = sel.from_user.wa_id
    language_selection = sel.data.replace("lang:", "")
    await consent_handler.handle_consent_response(client, user_id, language_selection)


@wa.on_message()
async def handle_message(wa_client, msg):
    """Main message handler - delegates to specialized handlers"""
    try:
        user_id = msg.from_user.wa_id
        session = session_manager.get_session(user_id)
        logger.info(f"Session state: {session['state']}")
        # logger.info(f"Message type: {msg.type}")
        logger.info(f"Message: {msg}")

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("poc_app:fastapi_app", host="0.0.0.0",
                port=int(os.getenv('LOCAL_PORT', 5017)), log_level="info")
