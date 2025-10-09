from session.session_manager import SessionManager, UserState
from handlers.domain_handler import DomainHandler
from data.supabase_client import supabaseClient


class ConsentHandler:
    def __init__(self, session_manager: SessionManager, questions_service):
        self.session_manager = session_manager
        self.questions_service = questions_service
    
    async def send_welcome_message(self, wa_client, user_id: str):
        """Send welcome message and ask for consent"""
        welcome_text = (
            "🙏 Welcome to the Bible Translation Research Project!\n\n"
            "We're working to improve Bible translations and would love your help. "
            "Your responses will contribute to creating more accurate and culturally appropriate translations.\n\n"
            "📋 We will collect:\n"
            "• Your text and voice responses\n"
            "• Language and cultural insights\n"
            "• Anonymous usage data\n\n"
            "🔒 Your data will be:\n"
            "• Used only for research purposes\n"
            "• Kept confidential and secure\n"
            "• Never sold or shared inappropriately\n\n"
            "Do you consent to participate in this research?\n"
            "Reply 'yes' to continue or 'no' to decline."
        )
        
        await wa_client.send_message(to=user_id, text=welcome_text)
        self.session_manager.set_state(user_id, UserState.AWAITING_CONSENT)
    
    async def handle_consent_response(self, wa_client, user_id: str, text: str):
        """Handle user consent response"""
        if text.lower() in ['yes', 'y', 'agree', 'accept', 'ok']:
            # await self._store_user_consent(user_id, True)

            domain_handler = DomainHandler(self.session_manager, self.questions_service)
            await domain_handler.send_domain_list(
                wa_client, 
                user_id, 
                prefix_message="✅ Thank you for participating!\n\nPick a domain to get started."
            )
            
        elif text.lower() in ['no', 'n', 'decline', 'refuse']:
            # await self._store_user_consent(user_id, False)
            await wa_client.send_message(
                to=user_id,
                text="Thank you for your time. If you change your mind, just send any message to start again."
            )
            self.session_manager.clear_session(user_id)
            
        else:
            await wa_client.send_message(
                to=user_id,
                text="Please reply 'yes' to participate or 'no' to decline."
            )
    
    # async def _store_user_consent(self, user_id: str, consented: bool):
    #     """Store user consent in database"""
    #     try:
    #         supabaseClient.table("user_progress").upsert({
    #             "user_id": user_id,
    #             "domain": None,
    #             "answered_questions": [],
    #             "consented": consented,
    #             "consent_date": "now()"
    #         }, on_conflict="user_id").execute()
    #     except Exception as e:
    #         print(f"Error storing consent: {e}")
