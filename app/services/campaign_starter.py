"""
Simple Campaign Starter Service
Sends WhatsApp messages to start campaigns
"""

from typing import List, Dict, Any
from data.supabase_client import supabaseClient
from datetime import datetime


async def add_recipients_to_campaign(campaign_id: int, phone_numbers: List[str]) -> Dict[str, Any]:
    """
    Add phone numbers to a campaign

    Args:
        campaign_id: Campaign ID
        phone_numbers: List of phone numbers (with country code, e.g., +1234567890)

    Returns:
        Dictionary with added recipients
    """
    recipients = []

    for phone in phone_numbers:
        # Clean phone number
        clean_phone = phone.strip().replace(' ', '').replace('-', '')

        # Add to database
        recipient_data = {
            'campaign_id': campaign_id,
            'phone_number': clean_phone,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }

        result = supabaseClient.table('campaign_recipients').insert(recipient_data).execute()

        if result.data:
            recipients.append(result.data[0])

    return {
        'campaign_id': campaign_id,
        'recipients_added': len(recipients),
        'recipients': recipients
    }


async def get_campaign_recipients(campaign_id: int) -> List[Dict[str, Any]]:
    """Get all recipients for a campaign"""
    result = supabaseClient.table('campaign_recipients').select('*').eq(
        'campaign_id', campaign_id
    ).execute()

    return result.data if result.data else []


async def start_campaign_flow(campaign_id: int, wa_client=None) -> Dict[str, Any]:
    """
    Start a campaign - send first message to all recipients

    Args:
        campaign_id: Campaign ID
        wa_client: WhatsApp client (pywa_async.WhatsApp instance)

    Returns:
        Dictionary with results
    """
    # Get campaign details
    campaign_result = supabaseClient.table('campaigns').select(
        '*, campaign_questions(sequence_order, question_id, questions(*))'
    ).eq('id', campaign_id).execute()

    if not campaign_result.data:
        raise ValueError(f"Campaign {campaign_id} not found")

    campaign = campaign_result.data[0]

    # Get first question
    questions = sorted(
        campaign.get('campaign_questions', []),
        key=lambda x: x.get('sequence_order', 0)
    )

    if not questions:
        raise ValueError("Campaign has no questions")

    first_question = questions[0]['questions']

    # Get recipients
    recipients = await get_campaign_recipients(campaign_id)

    if not recipients:
        raise ValueError("Campaign has no recipients")

    # Send messages
    sent_count = 0
    failed_count = 0
    results = []

    for recipient in recipients:
        phone = recipient['phone_number']

        try:
            # Prepare message
            message_text = f"""Hello! 👋

You've been invited to participate in: *{campaign['name']}*

{campaign.get('description', '')}

Let's start with the first question:

{first_question['input_text']}

Please respond with your answer."""

            # Send via WhatsApp if client provided
            if wa_client:
                print(phone)
                await wa_client.send_message(
                    to=phone,
                    text=message_text
                )
                sent_count += 1

                # Update recipient status
                supabaseClient.table('campaign_recipients').update({
                    'status': 'active'
                }).eq('id', recipient['id']).execute()

                results.append({
                    'phone': phone,
                    'status': 'sent'
                })
            else:
                # No WhatsApp client - just mark as ready
                results.append({
                    'phone': phone,
                    'status': 'ready',
                    'message': message_text
                })

        except Exception as e:
            failed_count += 1
            results.append({
                'phone': phone,
                'status': 'failed',
                'error': str(e)
            })

    # Update campaign status
    supabaseClient.table('campaigns').update({
        'status': 'active'
    }).eq('id', campaign_id).execute()

    return {
        'campaign_id': campaign_id,
        'campaign_name': campaign['name'],
        'total_recipients': len(recipients),
        'sent': sent_count,
        'failed': failed_count,
        'results': results
    }


async def remove_recipient(campaign_id: int, phone_number: str) -> bool:
    """Remove a phone number from a campaign"""
    result = supabaseClient.table('campaign_recipients').delete().match({
        'campaign_id': campaign_id,
        'phone_number': phone_number
    }).execute()

    return result.data is not None
