import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from pywa_async import WhatsApp
from openai import OpenAI
from fastapi import FastAPI  # Replace Flask
from supabase import create_client, Client
from datetime import datetime

load_dotenv()

# Initialize Supabase client
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

async def get_user_progress(user_id: str):
    """Get user progress from database"""
    try:
        result = supabase.table('user_progress').select('*').eq('user_id', user_id).execute()
        if result.data:
            return result.data[0]
        else:
            # Create new user progress
            new_progress = {
                'user_id': user_id,
                'domain': None,
                'answered_questions': [],
                'created_at': datetime.utcnow().isoformat()
            }
            supabase.table('user_progress').insert(new_progress).execute()
            return new_progress
    except Exception as e:
        print(f"Database error: {e}")
        return {'user_id': user_id, 'domain': None, 'answered_questions': []}

async def update_user_progress(user_id: str, domain: str = None, answered_id: int = None):
    """Update user progress in database"""
    try:
        current_progress = await get_user_progress(user_id)
        
        updates = {'updated_at': datetime.utcnow().isoformat()}
        if domain:
            updates['domain'] = domain
        if answered_id:
            answered_list = current_progress.get('answered_questions', [])
            if answered_id not in answered_list:
                answered_list.append(answered_id)
            updates['answered_questions'] = answered_list
        
        supabase.table('user_progress').update(updates).eq('user_id', user_id).execute()
    except Exception as e:
        print(f"Error updating progress: {e}")

async def log_response(user_id: str, question_id: int, user_answer: str, validation: str, score: int):
    """Log user responses for Fieldworks analysis"""
    try:
        response_data = {
            'user_id': user_id,
            'question_id': question_id,
            'user_answer': user_answer,
            'validation': validation,
            'score': score,
            'timestamp': datetime.utcnow().isoformat()
        }
        supabase.table('user_responses').insert(response_data).execute()
    except Exception as e:
        print(f"Error logging response: {e}")

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
        await log_response(
            user_id=user_id,
            question_id=remaining_qs[0]['id'],
            user_answer=response,
            validation=result['validation'],
            score=result['score']
        )
        
        # Update progress in database
        await update_user_progress(user_id, answered_id=result['next_id'])
        
        next_q = next(q for q in remaining_qs if q['id'] == result['next_id'])
        return f"Validation: {result['validation']} (Score: {result['score']}/10)\nNext: {next_q['text']}"
    except:
        # Fallback to first remaining
        next_q = remaining_qs[0]
        await update_user_progress(user_id, answered_id=next_q['id'])
        return f"Next: {next_q['text']}"


@wa.on_message()
async def handle_message(wa_client, msg):
    try:
        user_id = msg.from_user.wa_id
        text = msg.text.lower().strip()
        
        # Get user progress from database instead of in-memory dict
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