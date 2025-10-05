import os
import json
from dotenv import load_dotenv
from pywa_async import WhatsApp
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware

from data.supabase_client import (
    store_response,
    get_user_progress,
    update_user_progress,
)
from data.audio import AudioHandler

load_dotenv()
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)


# Load questions from Supabase
def load_questions_from_supabase():
    try:
        result = supabase.table('questions').select('*').execute()
        questions_by_domain = {}
        for row in result.data:
            domain = row['domain']
            if domain not in questions_by_domain:
                questions_by_domain[domain] = {'questions': []}
            questions_by_domain[domain]['questions'].append({
                'id': row['id'],
                'text': row['text']
            })
        return {'domains': questions_by_domain}
    except Exception as e:
        print(f"Error loading questions: {e}")
        return {'domains': {}}


QUESTIONS = load_questions_from_supabase()


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
    return {"webhook_url": f"{NGROK_URL}/webhook"}


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


wa = WhatsApp(
    phone_id=os.getenv('WHATSAPP_PHONE_ID'),
    token=WHATSAPP_TOKEN,
    server=fastapi_app,
    verify_token=os.getenv('WHATSAPP_VERIFY_TOKEN'),
    webhook_challenge_delay=60,  # Increase delay
    # Temporarily remove these to avoid auto-registration issues
    # callback_url=os.getenv('WHATSAPP_CALLBACK_URL'),
    # app_id=int(os.getenv('WHATSAPP_APP_ID')),
    # app_secret=os.getenv('WHATSAPP_APP_SECRET'),
)


async def suggest_next_question(user_id: str, domain: str, response: str) -> str:
    """Use LLM to suggest and validate next question."""
    remaining_qs = [q for q in QUESTIONS['domains'][domain]['questions'] if q['id'] not in (await get_user_progress(user_id)).get('answered_questions', [])]
    if not remaining_qs:
        return "All questions answered! Thanks!"
    
    prompt = f"""
    User response: '{response}' for domain '{domain}'.
    Remaining questions: {json.dumps(remaining_qs, indent=2)}.
    
    1. Validate/clean the response: Flag errors, suggest corrections (linguistic focus).
    2. Suggest the next question ID (1-based from remaining) that's most relevant, with 1-sentence reason.
    Output JSON: {{"validation": "cleaned text or 'valid'", "score": 1-10, "next_id": int, "reason": "str"}}
    """
    
    response_llm = await client.chat.completions.create(  # Await for async
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    try:
        result = json.loads(response_llm.choices[0].message.content)
        
        # Log the response for analysis
        await store_response(
            user_id=user_id,
            question_id=remaining_qs[0]['id'],
            user_answer=response,
            validation=result['validation'],
            score=result['score']
        )
        
        await update_user_progress(user_id, answered_id=result['next_id'])
        
        next_q = next(q for q in remaining_qs if q['id'] == result['next_id'])
        return f"Validation: {result['validation']} (Score: {result['score']}/10)\nNext: {next_q['text']}"
    except:
        # Fallback to first remaining
        next_q = remaining_qs[0]
        await update_user_progress(user_id, answered_id=next_q['id'])
        return f"Next: {next_q['text']}"


openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
if not openai_client.api_key:
    raise ValueError("Set OPENAI_API_KEY in .env file")

audio_handler = AudioHandler(
    whatsapp_token=WHATSAPP_TOKEN,
    openai_client=openai_client
)


@wa.on_message()
async def handle_message(wa_client, msg):
    try:
        user_id = msg.from_user.wa_id

        # Handle audio messages
        if msg.type == "audio":
            await wa_client.send_message(
                to=user_id,
                text="🎵 Processing your audio message..."
            )
            
            audio_result = await audio_handler.process_audio_message(
                media_id=msg.audio.id,
                user_id=user_id
            )
            
            if "error" in audio_result:
                await wa_client.send_message(
                    to=user_id,
                    text="Sorry, I couldn't process your audio message. Please try again."
                )
                return
            
            # Handle skipped transcription
            if audio_result.get("skipped", False):
                await wa_client.send_message(
                    to=user_id,
                    text=(
                        f"🎵 Audio received! Thank you <3"
                        "Language detected: {audio_result.get('language', 'unknown')}\n\n" #TODO
                    )
                )
                return
            
            # Handle successful transcription
            text = audio_result["transcription"]
            confidence = audio_result["confidence"]

            confidence_emoji = "✅" if confidence > 0.8 else "⚠️" if confidence > 0.5 else "❌"

            await wa_client.send_message(
                to=user_id,
                text=(
                    f"📝 I heard: \"{text}\"\n"
                    f"{confidence_emoji} Confidence: {confidence:.1%}\n\n"
                    "Is this correct? If you want to edit, tap 'Edit' and send the corrected text." 
                ),
                buttons=[
                    {"type": "reply", "reply": {"id": "correct", "title": "Correct ✅"}},
                    {"type": "reply", "reply": {"id": "edit", "title": "Edit ✏️"}},
                    {"type": "reply", "reply": {"id": "continue", "title": "Continue ➡️"}}
                ]
            )
            return
            
        else:
            # Handle text messages
            text = msg.text.lower().strip()
            
            progress = await get_user_progress(user_id)
            
            if text == 'start':
                await wa_client.send_message(
                    to=user_id,
                    text="Hi! Domains: kinship. Reply 'start kinship' to begin."
                )
                return
            
            if text.startswith('start '):
                domain = text.split(' ', 2)[1]
                if domain not in QUESTIONS['domains']:
                    await wa_client.send_message(
                        to=user_id,
                        text=f"Unknown domain. Available: {list(QUESTIONS['domains'].keys())}"
                    )
                    return
                await update_user_progress(user_id, domain=domain)
                first_q = QUESTIONS['domains'][domain]['questions'][0]
                await update_user_progress(user_id, answered_id=first_q['id'])
                await wa_client.send_message(
                    to=user_id,
                    text=f"Starting {domain} domain.\n{first_q['text']}"
                )
                return
            
            if progress['domain'] is None:
                await wa_client.send_message(
                    to=user_id,
                    text="Say 'start kinship' to begin."
                )
                return
            
            domain = progress['domain']
            next_msg = await suggest_next_question(user_id, domain, text)  # Await async LLM
            await wa_client.send_message(to=user_id, text=next_msg)
            
            if len(progress['answered_questions']) % 2 == 0:
                await wa_client.send_message(
                    to=user_id,
                    text="Bonus: Rate this sample response (1-5): 'Uncle is 'mama kaka'."
                )
            
    except Exception as e:
        print(f"Error in handle_message: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("poc_app:fastapi_app", host="0.0.0.0", port=int(os.getenv('LOCAL_PORT', 5017)), log_level="info")