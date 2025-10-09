"""
Campaign Generator Service
Handles creation of Bible verse and TAME exploration campaigns
"""

from typing import List, Dict, Any, Optional
from data.supabase_client import supabaseClient
from datetime import datetime
import requests


class BibleAPIError(Exception):
    """Raised when Bible API requests fail"""
    pass


def fetch_bible_verses(book: str, start_chapter: int, start_verse: int,
                       end_chapter: int, end_verse: int,
                       translation: str = "BSB") -> List[Dict[str, Any]]:
    """
    Fetch verses from Bible API (bible.helloao.org)

    Args:
        book: Bible book name (e.g., "Genesis", "John") or 3-letter code (e.g., "GEN", "JHN")
        start_chapter: Starting chapter number
        start_verse: Starting verse number
        end_chapter: Ending chapter number
        end_verse: Ending verse number
        translation: Bible translation code (default: "BSB" - Berean Standard Bible)

    Returns:
        List of verse dictionaries with book, chapter, verse, text
    """
    verses = []

    # Map common book names to 3-letter codes used by helloao API
    book_codes = {
        "genesis": "GEN", "exodus": "EXO", "leviticus": "LEV", "numbers": "NUM", "deuteronomy": "DEU",
        "joshua": "JOS", "judges": "JDG", "ruth": "RUT", "1 samuel": "1SA", "2 samuel": "2SA",
        "1 kings": "1KI", "2 kings": "2KI", "1 chronicles": "1CH", "2 chronicles": "2CH",
        "ezra": "EZR", "nehemiah": "NEH", "esther": "EST", "job": "JOB", "psalms": "PSA",
        "proverbs": "PRO", "ecclesiastes": "ECC", "song of solomon": "SNG", "isaiah": "ISA",
        "jeremiah": "JER", "lamentations": "LAM", "ezekiel": "EZK", "daniel": "DAN",
        "hosea": "HOS", "joel": "JOL", "amos": "AMO", "obadiah": "OBA", "jonah": "JON",
        "micah": "MIC", "nahum": "NAM", "habakkuk": "HAB", "zephaniah": "ZEP", "haggai": "HAG",
        "zechariah": "ZEC", "malachi": "MAL", "matthew": "MAT", "mark": "MRK", "luke": "LUK",
        "john": "JHN", "acts": "ACT", "romans": "ROM", "1 corinthians": "1CO", "2 corinthians": "2CO",
        "galatians": "GAL", "ephesians": "EPH", "philippians": "PHP", "colossians": "COL",
        "1 thessalonians": "1TH", "2 thessalonians": "2TH", "1 timothy": "1TI", "2 timothy": "2TI",
        "titus": "TIT", "philemon": "PHM", "hebrews": "HEB", "james": "JAS", "1 peter": "1PE",
        "2 peter": "2PE", "1 john": "1JN", "2 john": "2JN", "3 john": "3JN", "jude": "JUD",
        "revelation": "REV"
    }

    try:
        # Convert book name to uppercase 3-letter code
        book_code = book_codes.get(book.lower(), book.upper()[:3])
        base_url = "https://bible.helloao.org/api"

        # Fetch chapter by chapter
        for chapter in range(start_chapter, end_chapter + 1):
            # Determine verse range for this chapter
            first_verse = start_verse if chapter == start_chapter else 1
            last_verse = end_verse if chapter == end_chapter else 999

            # API format: /api/{translation}/{book}/{chapter}.json
            url = f"{base_url}/{translation}/{book_code}/{chapter}.json"

            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Extract verses from the data
            # The API returns data in format: {"data": [...verse objects...]}
            verse_data_list = data.get("data", [])

            for verse_item in verse_data_list:
                verse_num = verse_item.get("verse")

                # Filter by verse range
                if verse_num and first_verse <= verse_num <= last_verse:
                    # Extract text from verse content
                    verse_text = ""
                    contents = verse_item.get("contents", [])
                    for content in contents:
                        if content.get("type") == "text":
                            verse_text += content.get("text", "")

                    if verse_text.strip():
                        verses.append({
                            "book": book,
                            "chapter": chapter,
                            "verse": verse_num,
                            "text": verse_text.strip()
                        })

        return verses

    except requests.RequestException as e:
        raise BibleAPIError(f"Failed to fetch verses: {str(e)}")


async def create_bible_campaign(
    project_id: int,
    campaign_name: str,
    book: str,
    start_chapter: int,
    start_verse: int,
    end_chapter: int,
    end_verse: int,
    response_type: str = "either",  # 'text', 'voice', 'either'
    translation: str = "BSB",
    active: bool = True
) -> Dict[str, Any]:
    """
    Create a Bible verse translation campaign

    Args:
        project_id: ID of the project
        campaign_name: Name for this campaign
        book: Bible book name
        start_chapter: Starting chapter
        start_verse: Starting verse
        end_chapter: Ending chapter
        end_verse: Ending verse
        response_type: Expected response type
        translation: Bible translation to use
        active: Whether campaign is active

    Returns:
        Campaign object with generated questions
    """

    # Fetch verses from Bible API
    verses = fetch_bible_verses(book, start_chapter, start_verse,
                                end_chapter, end_verse, translation)

    if not verses:
        raise ValueError("No verses found for the specified range")

    # Get the Bible translation template
    template_result = supabaseClient.table('question_templates').select('*').eq(
        'template_type', 'bible_translation'
    ).execute()

    if not template_result.data:
        raise ValueError("Bible translation template not found. Run campaign_templates.sql first.")

    template = template_result.data[0]

    # Create campaign
    campaign_data = {
        'project_id': project_id,
        'name': campaign_name,
        'description': f"Bible translation: {book} {start_chapter}:{start_verse} - {end_chapter}:{end_verse}",
        'active': active,
        'created_at': datetime.utcnow().isoformat()
    }

    campaign_result = supabaseClient.table('campaigns').insert(campaign_data).execute()
    campaign = campaign_result.data[0] if campaign_result.data else None

    if not campaign:
        raise ValueError("Failed to create campaign")

    campaign_id = campaign['id']

    # Create questions for each verse
    questions = []
    for idx, verse_data in enumerate(verses):
        # Format question text from template
        question_text = template['template_text'].format(
            book=verse_data['book'],
            chapter=verse_data['chapter'],
            verse=verse_data['verse'],
            verse_text=verse_data['text']
        )

        # Get project languages
        project = supabaseClient.table('projects').select('ui_language, target_language').eq(
            'id', project_id
        ).execute()

        if not project.data:
            raise ValueError(f"Project {project_id} not found")

        ui_lang = project.data[0]['ui_language']
        target_lang = project.data[0]['target_language']

        # Create question
        question_data = {
            'input_text': question_text,
            'input_language': ui_lang,
            'output_language': target_lang,
            'template_id': template['id'],
            'project_id': project_id,
            'created_at': datetime.utcnow().isoformat()
        }

        question_result = supabaseClient.table('questions').insert(question_data).execute()

        if question_result.data:
            question = question_result.data[0]
            questions.append(question)

            # Link question to campaign
            campaign_question_data = {
                'campaign_id': campaign_id,
                'question_id': question['id'],
                'sequence_order': idx + 1
            }
            supabaseClient.table('campaign_questions').insert(campaign_question_data).execute()

    return {
        'campaign': campaign,
        'questions_created': len(questions),
        'questions': questions
    }


async def create_tame_campaign(
    project_id: int,
    campaign_name: str,
    base_sentences: List[Dict[str, str]],  # [{"sentence": "I walk", "gloss": "walk-1SG.PRS"}]
    categories: List[str],  # ['tense', 'aspect', 'modality', 'evidentiality']
    response_type: str = "either",
    active: bool = True
) -> Dict[str, Any]:
    """
    Create a TAME exploration campaign

    Args:
        project_id: ID of the project
        campaign_name: Name for this campaign
        base_sentences: List of base sentences with glosses
        categories: List of TAME categories to explore
        response_type: Expected response type
        active: Whether campaign is active

    Returns:
        Campaign object with generated questions
    """

    # Validate categories
    valid_categories = ['tense', 'aspect', 'modality', 'evidentiality']
    for cat in categories:
        if cat not in valid_categories:
            raise ValueError(f"Invalid category: {cat}. Must be one of {valid_categories}")

    # Create campaign
    campaign_data = {
        'project_id': project_id,
        'name': campaign_name,
        'description': f"TAME exploration: {', '.join(categories)}",
        'active': active,
        'created_at': datetime.utcnow().isoformat()
    }

    campaign_result = supabaseClient.table('campaigns').insert(campaign_data).execute()
    campaign = campaign_result.data[0] if campaign_result.data else None

    if not campaign:
        raise ValueError("Failed to create campaign")

    campaign_id = campaign['id']

    # Get project languages
    project = supabaseClient.table('projects').select('ui_language, target_language').eq(
        'id', project_id
    ).execute()

    if not project.data:
        raise ValueError(f"Project {project_id} not found")

    ui_lang = project.data[0]['ui_language']
    target_lang = project.data[0]['target_language']

    questions = []
    sequence_order = 0

    # For each base sentence
    for base in base_sentences:
        base_sentence = base['sentence']
        base_gloss = base.get('gloss', '')

        # For each selected category
        for category in categories:
            # Get template for this category
            template_result = supabaseClient.table('question_templates').select('*').eq(
                'template_type', f'tame_{category}'
            ).execute()

            if not template_result.data:
                raise ValueError(f"Template for {category} not found. Run campaign_templates.sql first.")

            template = template_result.data[0]

            # Get variations for this category
            variations_result = supabaseClient.table('tame_variations').select('*').eq(
                'category', category
            ).order('sort_order').execute()

            variations = variations_result.data if variations_result.data else []

            # Create question for each variation
            for variation in variations:
                # Format question text
                question_text = template['template_text'].format(
                    base_sentence=base_sentence,
                    **{f'{category}_type': variation['variation_type'].replace('_', ' ')},
                    **{f'{category}_example': variation['example_context']}
                )

                # Create question
                question_data = {
                    'input_text': question_text,
                    'input_language': ui_lang,
                    'output_language': target_lang,
                    'template_id': template['id'],
                    'project_id': project_id,
                    'created_at': datetime.utcnow().isoformat()
                }

                question_result = supabaseClient.table('questions').insert(question_data).execute()

                if question_result.data:
                    question = question_result.data[0]
                    questions.append(question)

                    sequence_order += 1

                    # Link question to campaign
                    campaign_question_data = {
                        'campaign_id': campaign_id,
                        'question_id': question['id'],
                        'sequence_order': sequence_order
                    }
                    supabaseClient.table('campaign_questions').insert(campaign_question_data).execute()

    return {
        'campaign': campaign,
        'questions_created': len(questions),
        'questions': questions
    }


# Example usage functions for testing

async def example_bible_campaign():
    """Example: Create a campaign for Genesis 1:1-5"""
    result = await create_bible_campaign(
        project_id=1,
        campaign_name="Genesis Creation Week - Day 1",
        book="Genesis",
        start_chapter=1,
        start_verse=1,
        end_chapter=1,
        end_verse=5,
        response_type="either",
        translation="web"
    )
    return result


async def example_tame_campaign():
    """Example: Create a TAME campaign for basic verbs"""
    result = await create_tame_campaign(
        project_id=1,
        campaign_name="Basic Verbs - Tense & Aspect",
        base_sentences=[
            {"sentence": "I walk", "gloss": "walk-1SG"},
            {"sentence": "She eats", "gloss": "eat-3SG"},
            {"sentence": "They sleep", "gloss": "sleep-3PL"}
        ],
        categories=["tense", "aspect"],
        response_type="either"
    )
    return result


async def create_ordered_campaign(
    project_id: int,
    campaign_name: str,
    questions_list: List[str],  # List of question prompts in order
    response_type: str = "either",
    active: bool = True
) -> Dict[str, Any]:
    """
    Create an Ordered/Sequential campaign

    Questions are presented in a specific order and must be answered sequentially.
    Useful for structured interviews, training sessions, or progressive elicitation.

    Args:
        project_id: ID of the project
        campaign_name: Name for this campaign
        questions_list: List of question prompts (order matters!)
        response_type: Expected response type
        active: Whether campaign is active

    Returns:
        Campaign object with generated questions
    """

    if not questions_list or len(questions_list) == 0:
        raise ValueError("Questions list cannot be empty")

    # Get the ordered_sequential template
    template_result = supabaseClient.table('question_templates').select('*').eq(
        'template_type', 'ordered_sequential'
    ).execute()

    if not template_result.data:
        raise ValueError("Ordered sequential template not found. Run campaign_templates.sql first.")

    template = template_result.data[0]

    # Create campaign
    campaign_data = {
        'project_id': project_id,
        'name': campaign_name,
        'description': f"Ordered campaign with {len(questions_list)} sequential questions",
        'active': active,
        'created_at': datetime.utcnow().isoformat()
    }

    campaign_result = supabaseClient.table('campaigns').insert(campaign_data).execute()
    campaign = campaign_result.data[0] if campaign_result.data else None

    if not campaign:
        raise ValueError("Failed to create campaign")

    campaign_id = campaign['id']

    # Get project languages
    project = supabaseClient.table('projects').select('ui_language, target_language').eq(
        'id', project_id
    ).execute()

    if not project.data:
        raise ValueError(f"Project {project_id} not found")

    ui_lang = project.data[0]['ui_language']
    target_lang = project.data[0]['target_language']

    # Create questions in order
    questions = []
    total_questions = len(questions_list)

    for idx, prompt in enumerate(questions_list):
        if not prompt or not prompt.strip():
            raise ValueError(f"Question {idx + 1} is empty")

        # Format question text from template
        question_text = template['template_text'].format(prompt=prompt.strip())

        # Create question with order metadata
        question_data = {
            'input_text': question_text,
            'input_language': ui_lang,
            'output_language': target_lang,
            'template_id': template['id'],
            'project_id': project_id,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': {
                'prompt': prompt.strip(),
                'question_number': idx + 1,
                'total_questions': total_questions,
                'enforce_order': True
            }
        }

        question_result = supabaseClient.table('questions').insert(question_data).execute()

        if question_result.data:
            question = question_result.data[0]
            questions.append(question)

            # Link question to campaign with sequence_order
            campaign_question_data = {
                'campaign_id': campaign_id,
                'question_id': question['id'],
                'sequence_order': idx + 1  # 1-indexed for clarity
            }
            supabaseClient.table('campaign_questions').insert(campaign_question_data).execute()

    return {
        'campaign': campaign,
        'questions_created': len(questions),
        'questions': questions
    }


async def create_text_to_text_campaign(
    project_id: int,
    campaign_name: str,
    questions_data: List[Dict[str, str]],  # [{"prompt": "Translate this", "text": "Hello"}]
    response_type: str = "text",
    active: bool = True
) -> Dict[str, Any]:
    """
    Create a Text to Text campaign

    Useful for translation, paraphrasing, or text transformation tasks.
    """
    # Reuse ordered_sequential template
    template_result = supabaseClient.table('question_templates').select('*').eq(
        'template_type', 'ordered_sequential'
    ).execute()

    if not template_result.data:
        raise ValueError("Template not found. Run campaign_templates.sql first.")

    template = template_result.data[0]

    campaign_data = {
        'project_id': project_id,
        'name': campaign_name,
        'description': f"Text to text campaign with {len(questions_data)} question(s)",
        'active': active,
        'created_at': datetime.utcnow().isoformat()
    }

    campaign_result = supabaseClient.table('campaigns').insert(campaign_data).execute()
    campaign = campaign_result.data[0] if campaign_result.data else None

    if not campaign:
        raise ValueError("Failed to create campaign")

    campaign_id = campaign['id']

    project = supabaseClient.table('projects').select('ui_language, target_language').eq(
        'id', project_id
    ).execute()

    if not project.data:
        raise ValueError(f"Project {project_id} not found")

    ui_lang = project.data[0]['ui_language']
    target_lang = project.data[0]['target_language']

    questions = []
    for idx, q_data in enumerate(questions_data):
        prompt = q_data.get('prompt', '')
        text = q_data.get('text', '')

        if not prompt:
            raise ValueError(f"Question {idx + 1} missing 'prompt' field")

        full_prompt = f"{prompt}: {text}" if text else prompt
        question_text = template['template_text'].format(prompt=full_prompt)

        question_data = {
            'input_text': question_text,
            'input_language': ui_lang,
            'output_language': target_lang,
            'template_id': template['id'],
            'project_id': project_id,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': {'source_text': text, 'prompt': prompt}
        }

        question_result = supabaseClient.table('questions').insert(question_data).execute()

        if question_result.data:
            question = question_result.data[0]
            questions.append(question)

            campaign_question_data = {
                'campaign_id': campaign_id,
                'question_id': question['id'],
                'sequence_order': idx + 1
            }
            supabaseClient.table('campaign_questions').insert(campaign_question_data).execute()

    return {
        'campaign': campaign,
        'questions_created': len(questions),
        'questions': questions
    }


async def create_image_to_text_campaign(
    project_id: int,
    campaign_name: str,
    questions_data: List[Dict[str, str]],
    response_type: str = "text",
    active: bool = True
) -> Dict[str, Any]:
    """Create an Image to Text campaign"""
    template_result = supabaseClient.table('question_templates').select('*').eq(
        'template_type', 'image_to_text'
    ).execute()

    if not template_result.data:
        raise ValueError("Image to text template not found. Run campaign_templates.sql first.")

    template = template_result.data[0]

    campaign_data = {
        'project_id': project_id,
        'name': campaign_name,
        'description': f"Image to text campaign with {len(questions_data)} question(s)",
        'active': active,
        'created_at': datetime.utcnow().isoformat()
    }

    campaign_result = supabaseClient.table('campaigns').insert(campaign_data).execute()
    campaign = campaign_result.data[0] if campaign_result.data else None

    if not campaign:
        raise ValueError("Failed to create campaign")

    campaign_id = campaign['id']

    project = supabaseClient.table('projects').select('ui_language, target_language').eq(
        'id', project_id
    ).execute()

    if not project.data:
        raise ValueError(f"Project {project_id} not found")

    ui_lang = project.data[0]['ui_language']
    target_lang = project.data[0]['target_language']

    questions = []
    for idx, q_data in enumerate(questions_data):
        prompt = q_data.get('prompt', '')
        image_url = q_data.get('image_url', '')

        if not prompt:
            raise ValueError(f"Question {idx + 1} missing 'prompt' field")

        question_text = template['template_text'].format(prompt=prompt)

        question_data = {
            'input_text': question_text,
            'input_language': ui_lang,
            'output_language': target_lang,
            'template_id': template['id'],
            'project_id': project_id,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': {'image_url': image_url, 'prompt': prompt}
        }

        question_result = supabaseClient.table('questions').insert(question_data).execute()

        if question_result.data:
            question = question_result.data[0]
            questions.append(question)

            campaign_question_data = {
                'campaign_id': campaign_id,
                'question_id': question['id'],
                'sequence_order': idx + 1
            }
            supabaseClient.table('campaign_questions').insert(campaign_question_data).execute()

    return {
        'campaign': campaign,
        'questions_created': len(questions),
        'questions': questions
    }


async def create_audio_to_audio_campaign(
    project_id: int,
    campaign_name: str,
    questions_data: List[Dict[str, str]],
    response_type: str = "voice",
    active: bool = True
) -> Dict[str, Any]:
    """Create an Audio to Audio campaign"""
    template_result = supabaseClient.table('question_templates').select('*').eq(
        'template_type', 'audio_to_audio'
    ).execute()

    if not template_result.data:
        raise ValueError("Audio to audio template not found. Run campaign_templates.sql first.")

    template = template_result.data[0]

    campaign_data = {
        'project_id': project_id,
        'name': campaign_name,
        'description': f"Audio to audio campaign with {len(questions_data)} question(s)",
        'active': active,
        'created_at': datetime.utcnow().isoformat()
    }

    campaign_result = supabaseClient.table('campaigns').insert(campaign_data).execute()
    campaign = campaign_result.data[0] if campaign_result.data else None

    if not campaign:
        raise ValueError("Failed to create campaign")

    campaign_id = campaign['id']

    project = supabaseClient.table('projects').select('ui_language, target_language').eq(
        'id', project_id
    ).execute()

    if not project.data:
        raise ValueError(f"Project {project_id} not found")

    ui_lang = project.data[0]['ui_language']
    target_lang = project.data[0]['target_language']

    questions = []
    for idx, q_data in enumerate(questions_data):
        prompt = q_data.get('prompt', '')
        audio_url = q_data.get('audio_url', '')

        if not prompt:
            raise ValueError(f"Question {idx + 1} missing 'prompt' field")

        question_text = template['template_text'].format(prompt=prompt)

        question_data = {
            'input_text': question_text,
            'input_language': ui_lang,
            'output_language': target_lang,
            'template_id': template['id'],
            'project_id': project_id,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': {'audio_url': audio_url, 'prompt': prompt}
        }

        question_result = supabaseClient.table('questions').insert(question_data).execute()

        if question_result.data:
            question = question_result.data[0]
            questions.append(question)

            campaign_question_data = {
                'campaign_id': campaign_id,
                'question_id': question['id'],
                'sequence_order': idx + 1
            }
            supabaseClient.table('campaign_questions').insert(campaign_question_data).execute()

    return {
        'campaign': campaign,
        'questions_created': len(questions),
        'questions': questions
    }
