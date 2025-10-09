from session.session_manager import SessionManager, UserState
from handlers.domain_handler import DomainHandler
from data.supabase_client import supabaseClient
from pywa.types import SectionList, Section, SectionRow


class ConsentHandler:
    def __init__(self, session_manager: SessionManager, questions_service):
        self.session_manager = session_manager
        self.questions_service = questions_service
        self.language_options = [
            {"code": "zh", "name": "Mandarin Chinese"},
             # African languages
            {"code": "ak", "name": "Akan"},
            {"code": "bm", "name": "Bambara"},
             # Asian/Pacific languages
            {"code": "km", "name": "Khmer"},
            {"code": "lo", "name": "Lao"},
            # Papua New Guinea/Pacific
            {"code": "tpi", "name": "Tok Pisin"},
            {"code": "ho", "name": "Hiri Motu"},
            {"code": "fj", "name": "Fijian"},
            # Americas indigenous
            {"code": "qu", "name": "Quechua"},
            {"code": "gn", "name": "Guarani"},
            # {"code": "other", "name": "Other (please specify)"}
        ]
    
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
            # "Do you consent to participate in this research?\n"
            # "Reply 'yes' to continue or 'no' to decline."
        )
        await wa_client.send_message(to=user_id, text=welcome_text)
        self.session_manager.set_state(user_id, UserState.AWAITING_CONSENT)

        """Send language selection options"""
        await  wa_client.send_message(to=user_id,header='Pick your language',
            text='Tap a button to select your language:',
            buttons=SectionList(
            button_title='Languages',
            sections=[
                Section(
                    title='Low-resource languages',
                    rows=[
                        SectionRow(
                            title=d['name'],
                            callback_data=f'lang:{d["code"]}',
                            description='For testing only (not a low-resource language)' if d['code']=='zh' else None,
                        ) for d in self.language_options
                    ],
                ),
            ]
            )
        )

    async def handle_consent_response(self, wa_client, user_id: str, language_code: str):
        """Handle user language response"""
        selected_language, language_name = None, None
        for lang in self.language_options:
            if lang["code"] == language_code:
                selected_language = lang
                language_name = lang["name"]
                break
    
        if selected_language:
            domain_handler = DomainHandler(self.session_manager, self.questions_service)
            await domain_handler.send_domain_list(
                wa_client, 
                user_id, 
                prefix_message=f"✅ Thanks for picking {language_name}!\n"
            )
            await supabaseClient.store_user_language(user_id, selected_language)
            # await self.complete_onboarding(wa_client, user_id, selected_language["name"])
        else:
            await wa_client.send_message(
                to=user_id,
                text="Sorry, there was an error with your selection. Please try again."
            )
                
        # elif text.lower() in ['yes', 'y', 'agree', 'accept', 'ok']:
        #     # await self._store_user_consent(user_id, True)

        #     domain_handler = DomainHandler(self.session_manager, self.questions_service)
        #     await domain_handler.send_domain_list(
        #         wa_client, 
        #         user_id, 
        #         prefix_message="✅ Thank you for participating!\n\nPick a domain to get started."
        #     )
            
        # elif text.lower() in ['no', 'n', 'decline', 'refuse']:
        #     # await self._store_user_consent(user_id, False)
        #     await wa_client.send_message(
        #         to=user_id,
        #         text="Thank you for your time. If you change your mind, just send any message to start again."
        #     )
        #     self.session_manager.clear_session(user_id)
            
        # else:
            # await wa_client.send_message(
            #     to=user_id,
            #     text="Please reply 'yes' to participate or 'no' to decline."
            # )
            # pass

    #LATER - 
    async def _store_user_consent(self, user_id: str, consented: bool):
        """Store user consent in database"""
        try:
            supabaseClient.table("user_progress").upsert({
                "user_id": user_id,
                "domain": None,
                "answered_questions": [],
                "consented": consented,
                "consent_date": "now()"
            }, on_conflict="user_id").execute()
        except Exception as e:
            print(f"Error storing consent: {e}")
