from typing import List, Dict, Optional
from data.supabase_client import supabaseClient


class QuestionsService:
    def __init__(self):
        self.cache = {}  # Optional: simple cache for frequently accessed questions
    
    async def get_domains(self) -> List[str]:
        """Get all available domains"""
        try:
            result = supabaseClient.table('questions').select('domain').execute()
            domains = list(set(row['domain'] for row in result.data))
            print(f"Loaded domains: {domains}")
            return [d for d in domains if d != '']
        except Exception as e:
            print(f"Error loading domains: {e}")
            return []
    
    async def get_questions_by_domain(self, domain: str) -> List[Dict]:
        """Get all questions for a specific domain"""
        cache_key = f"domain_{domain}"
        
        # Check cache first (optional optimization)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            result = supabaseClient.table('questions').select('id, text, domain').eq('domain', domain).execute()
            questions = [
                {
                    'id': row['id'],
                    'text': row['text'],
                    'domain': row['domain']
                }
                for row in result.data
            ]
            
            # Cache the result (optional)
            self.cache[cache_key] = questions
            return questions
            
        except Exception as e:
            print(f"Error loading questions for domain {domain}: {e}")
            return []
    
    async def get_question_by_id(self, question_id: int) -> Optional[Dict]:
        """Get a specific question by ID"""
        try:
            result = supabaseClient.table('questions').select('*').eq('id', question_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error loading question {question_id}: {e}")
            return None
    
    async def get_unanswered_questions(self, domain: str, answered_ids: List[int]) -> List[Dict]:
        """Get questions that haven't been answered yet"""
        all_questions = await self.get_questions_by_domain(domain)
        return [q for q in all_questions if q['id'] not in answered_ids]
    
    def clear_cache(self, domain: str = None):
        """Clear cache for a domain or all domains"""
        if domain:
            cache_key = f"domain_{domain}"
            if cache_key in self.cache:
                del self.cache[cache_key]
        else:
            self.cache.clear()
