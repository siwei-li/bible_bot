
import os
from dotenv import load_dotenv
from data.supabase_client import supabaseClient

load_dotenv()

from datetime import datetime
from typing import List, Dict, Any, Optional

async def get_all_projects() -> List[Dict[str, Any]]:
    """Fetch all projects from database"""
    try:
        result = supabaseClient.table('projects').select('*').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching projects: {e}")
        return []

async def get_project_by_id(project_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single project by ID"""
    try:
        result = supabaseClient.table('projects').select('*').eq('id', project_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error fetching project: {e}")
        return None

async def create_project(title: str, ui_language: str, target_language: str, created_by: str) -> Dict[str, Any]:
    """Insert new project into database and add creator as owner"""
    try:
        project_data = {
            'title': title,
            'ui_language': ui_language,
            'target_language': target_language,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': created_by
        }

        result = supabaseClient.table('projects').insert(project_data).execute()
        project = result.data[0] if result.data else {}

        # Add creator to project_members as owner
        if project and isinstance(project, dict):
            member_data = {
                'user_id': created_by,
                'project_id': project.get('id'),
                'role': 'owner',
                'joined_at': datetime.utcnow().isoformat()
            }
            supabaseClient.table('project_members').insert(member_data).execute()
            print(f"Added user {created_by} as owner of project {project.get('id')}")

        return project if isinstance(project, dict) else {}
    except Exception as e:
        print(f"Error creating project: {e}")
        raise e

async def get_project_campaigns(project_id: int) -> List[Dict[str, Any]]:
    """Fetch campaigns for a specific project"""
    try:
        result = supabaseClient.table('campaigns').select('*').eq('project_id', project_id).order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching campaigns: {e}")
        return []

async def get_all_campaigns() -> List[Dict[str, Any]]:
    """Fetch all campaigns with project info"""
    try:
        result = supabaseClient.table('campaigns').select('*, projects(title)').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching campaigns: {e}")
        return []

async def get_campaign_responses(campaign_id: int) -> List[Dict[str, Any]]:
    """Fetch responses for a specific campaign"""
    try:
        # Get questions in this campaign first
        campaign_questions = supabaseClient.table('campaign_questions').select('question_id').eq('campaign_id', campaign_id).execute()
        question_ids = [q['question_id'] for q in campaign_questions.data] if campaign_questions.data else []

        if not question_ids:
            return []

        # Get responses for those questions
        result = supabaseClient.table('responses').select('*, questions(input_text)').in_('question_id', question_ids).order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching responses: {e}")
        return []

async def get_all_responses() -> List[Dict[str, Any]]:
    """Fetch all responses with question info"""
    try:
        result = supabaseClient.table('responses').select('*, questions(input_text)').order('created_at', desc=True).limit(100).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching responses: {e}")
        return []

async def create_campaign(
    name: str,
    project_id: int,
    description: Optional[str] = None,
    active: bool = True
) -> Dict[str, Any]:
    """Insert new campaign into database"""
    try:
        campaign_data = {
            'name': name,
            'project_id': project_id,
            'active': active,
            'created_at': datetime.utcnow().isoformat()
        }

        if description:
            campaign_data['description'] = description

        result = supabaseClient.table('campaigns').insert(campaign_data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"Error creating campaign: {e}")
        raise e
