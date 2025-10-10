"""
Campaign Creation Routes for Linguist UI
Handles Bible verse and TAME campaign creation
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import os
import json

from linguist import auth
from services.campaign_generator import (
    create_bible_campaign,
    create_tame_campaign,
    BibleAPIError
)

router = APIRouter(prefix="/linguist/campaigns", tags=["campaigns"])

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/create/bible", response_class=HTMLResponse)
async def bible_campaign_form(request: Request, project_id: int):
    """Show Bible verse campaign creation form"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    return templates.TemplateResponse("campaigns/create_bible_campaign.html", {
        "request": request,
        "user": user,
        "project_id": project_id
    })


@router.post("/create/bible")
async def create_bible_campaign_submit(
    request: Request,
    project_id: int = Form(...),
    campaign_name: str = Form(...),
    book: str = Form(...),
    start_chapter: int = Form(...),
    start_verse: int = Form(...),
    end_chapter: int = Form(...),
    end_verse: int = Form(...),
    response_type: str = Form("either"),
    translation: str = Form("web")
):
    """Handle Bible campaign creation"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    try:
        result = await create_bible_campaign(
            project_id=project_id,
            campaign_name=campaign_name,
            book=book,
            start_chapter=start_chapter,
            start_verse=start_verse,
            end_chapter=end_chapter,
            end_verse=end_verse,
            response_type=response_type,
            translation=translation
        )

        # Redirect to campaign view
        return RedirectResponse(
            url=f"/linguist/campaigns/{result['campaign']['id']}",
            status_code=303
        )

    except BibleAPIError as e:
        return templates.TemplateResponse("campaigns/create_bible_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Bible API Error: {str(e)}"
        })
    except Exception as e:
        return templates.TemplateResponse("campaigns/create_bible_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Error creating campaign: {str(e)}"
        })


@router.get("/create/tame", response_class=HTMLResponse)
async def tame_campaign_form(request: Request, project_id: int):
    """Show TAME campaign creation form"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    return templates.TemplateResponse("create_tame_campaign.html", {
        "request": request,
        "user": user,
        "project_id": project_id
    })


@router.post("/create/tame")
async def create_tame_campaign_submit(
    request: Request,
    project_id: int = Form(...),
    campaign_name: str = Form(...),
    base_sentences: str = Form(...),  # JSON string of sentences
    categories: List[str] = Form(...),  # Multiple select
    response_type: str = Form("either")
):
    """Handle TAME campaign creation"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    try:
        # Parse base sentences JSON
        sentences = json.loads(base_sentences)
        if not isinstance(sentences, list):
            raise ValueError("Base sentences must be a list")

        result = await create_tame_campaign(
            project_id=project_id,
            campaign_name=campaign_name,
            base_sentences=sentences,
            categories=categories,
            response_type=response_type
        )

        # Redirect to campaign view
        return RedirectResponse(
            url=f"/linguist/campaigns/{result['campaign']['id']}",
            status_code=303
        )

    except json.JSONDecodeError:
        return templates.TemplateResponse("create_tame_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": "Invalid sentence format. Please check your JSON."
        })
    except Exception as e:
        return templates.TemplateResponse("create_tame_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Error creating campaign: {str(e)}"
        })


@router.get("/preview/tame", response_class=JSONResponse)
async def preview_tame_questions(
    request: Request,
    categories: str,  # Comma-separated
    sentence: str
):
    """Preview what questions will be generated for a TAME campaign"""
    user = await auth.get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from data.supabase_client import supabaseClient

    try:
        category_list = [c.strip() for c in categories.split(',')]
        preview_questions = []

        for category in category_list:
            # Get variations for this category
            variations_result = supabaseClient.table('tame_variations').select('*').eq(
                'category', category
            ).order('sort_order').execute()

            variations = variations_result.data if variations_result.data else []

            for var in variations:
                preview_questions.append({
                    "category": category,
                    "variation": var['variation_type'],
                    "example": var['example_context'],
                    "sample_question": f"How would you say '{sentence}' {var['example_context']}?"
                })

        return {
            "success": True,
            "total_questions": len(preview_questions),
            "questions": preview_questions
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
