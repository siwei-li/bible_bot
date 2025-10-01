import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from pywa_async import WhatsApp
from openai import OpenAI
from fastapi import FastAPI  # Replace Flask


load_dotenv()

# Global state (in prod, use DB like SQLite) #TODO - migrate to DB
user_progress: Dict[str, Dict[str, Any]] = {}
# Load questions
with open('questions.json', 'r') as f:
    QUESTIONS = json.load(f)


# LLM Client setup #TODO - use Gloo API
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
if not client.api_key:
    raise ValueError("Set OPENAI_API_KEY in .env file")


fastapi_app = FastAPI()
wa = WhatsApp(
    phone_id=os.getenv('WHATSAPP_PHONE_ID'),
    token=os.getenv('WHATSAPP_TOKEN'),
    server=fastapi_app,
    verify_token=os.getenv('WHATSAPP_VERIFY_TOKEN'),
    callback_url=os.getenv('WHATSAPP_CALLBACK_URL'),
    app_id=int(os.getenv('WHATSAPP_APP_ID')),
    app_secret=os.getenv('WHATSAPP_APP_SECRET'),
    webhook_challenge_delay=10
)

async def suggest_next_question(user_id: str, domain: str, response: str) -> str:
    """Use LLM to suggest and validate next question."""
    remaining_qs = [q for q in QUESTIONS['domains'][domain]['questions'] if q['id'] not in user_progress[user_id].get('answered', [])]
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
        # Update progress
        user_progress[user_id]['answered'].append(result['next_id'])
        next_q = next(q for q in remaining_qs if q['id'] == result['next_id'])
        return f"Validation: {result['validation']} (Score: {result['score']}/10)\nNext: {next_q['text']}"
    except:
        # Fallback to first remaining
        next_q = remaining_qs[0]
        user_progress[user_id]['answered'].append(next_q['id'])
        return f"Next: {next_q['text']}"


@wa.on_message()
async def handle_message(wa_client, msg):
    try:
        user_id = msg.from_user.wa_id
        text = msg.text.lower().strip()
        
        if user_id not in user_progress:
            user_progress[user_id] = {"domain": None, "answered": []}
        
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
            user_progress[user_id] = {"domain": domain, "answered": []}
            first_q = QUESTIONS['domains'][domain]['questions'][0]
            user_progress[user_id]['answered'].append(first_q['id'])
            await wa_client.send_message(
                to=user_id,
                text=f"Starting {domain} domain.\n{first_q['text']}"
            )
            return
        
        if user_progress[user_id]['domain'] is None:
            await wa_client.send_message(
                to=user_id,
                text="Say 'start kinship' to begin."
            )
            return
        
        domain = user_progress[user_id]['domain']
        next_msg = await suggest_next_question(user_id, domain, text)  # Await async LLM
        await wa_client.send_message(to=user_id, text=next_msg)
        
        if len(user_progress[user_id]['answered']) % 2 == 0:
            await wa_client.send_message(
                to=user_id,
                text="Bonus: Rate this sample response (1-5): 'Uncle is 'mama kaka'."
            )
            
    except Exception as e:
        print(f"Error in handle_message: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("poc_app:fastapi_app", host="0.0.0.0", port=os.getenv('LOCAL_PORT'), log_level="info")