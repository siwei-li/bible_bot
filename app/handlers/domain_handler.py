from session.session_manager import SessionManager, UserState
from services.questions_service import QuestionsService


class DomainHandler:
    def __init__(self, session_manager: SessionManager, questions_service: QuestionsService):
        self.session_manager = session_manager
        self.questions_service = questions_service
    
    async def handle_domain_selection(self, wa_client, user_id: str, text: str):
        """Handle domain selection"""
        if text.lower() == 'info':
            await wa_client.send_message(
                to=user_id,
                text=(
                    "📖 About this project:\n\n"
                    "We're researching how different concepts are expressed "
                    "in various languages and cultures to improve Bible translations.\n\n"
                    "Each session takes about 5-10 minutes.\n\n"
                    "Available domains will be shown next."
                )
            )
            # Show available domains
            await self.show_available_domains(wa_client, user_id)
            return
        
        # Check if it's a valid domain
        available_domains = await self.questions_service.get_domains()
        if text.lower() in [d.lower() for d in available_domains]:
            # Find the actual domain name (case-sensitive)
            domain = next(d for d in available_domains if d.lower() == text.lower())
            
            session = self.session_manager.get_session(user_id)
            session["domain"] = domain
            await wa_client.send_message(
                to=user_id,
                text=(
                    f"✅ You've selected the '{domain}' domain.\n\n"
                    # f"Reply 'next' to get your first question."
                )
            )

        else:
            await self.show_available_domains(wa_client, user_id)
    
    async def show_available_domains(self, wa_client, user_id: str):
        """Show available domains to user with continue options"""
        domains = await self.questions_service.get_domains()
        session = self.session_manager.get_session(user_id)
        current_domain = session.get("domain")
        
        domain_options = []

        if current_domain:
            from data.supabase_client import get_user_progress
            progress = await get_user_progress(user_id)
            answered_ids = progress.get('answered_questions', [])
            remaining_questions = await self.questions_service.get_unanswered_questions(
                current_domain, answered_ids
            )
            
            if remaining_questions:
                domain_options.append(f"• 'continue {current_domain}' - Resume {current_domain} ({len(remaining_questions)} questions left)")
        
        # Show all available domains
        for domain in domains:
            if domain != current_domain:
                domain_options.append(f"• '{domain}' - Start {domain} domain")
        
        domain_list = "\n".join(domain_options)
        
        await wa_client.send_message(
            to=user_id,
            text=(
                f"Available options:\n\n{domain_list}\n\n"
                f"Reply with a domain name to start, 'continue [domain]' to resume."
                # ", or 'info' to learn more."
            )
        )
        # else:
        #     await wa_client.send_message(
        #         to=user_id,
        #         text="No domains available at the moment. Please try again later."
        #     )
