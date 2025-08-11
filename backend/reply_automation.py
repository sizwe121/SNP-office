# Reply Processing and Follow-up Automation
import os
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

class ResponseType(str, Enum):
    INTERESTED = "interested"
    NEED_INFO = "need_info" 
    NOT_INTERESTED = "not_interested"
    SCHEDULING = "scheduling"
    UNSUBSCRIBE = "unsubscribe"
    UNCLEAR = "unclear"

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ReplyProcessor:
    """Advanced reply processing with AI classification"""
    
    def __init__(self, google_automation, crm_service):
        self.google_automation = google_automation
        self.crm_service = crm_service
        
        # AI for reply analysis
        self.ai_chat = LlmChat(
            api_key=google_automation.google_api_key,
            session_id="reply_processing"
        ).with_model("gemini", "gemini-2.0-flash")
        
        # Response patterns for fallback classification
        self.positive_patterns = [
            r'\b(interested|sounds good|yes|tell me more|learn more|information|details)\b',
            r'\b(schedule|meeting|call|discuss|when|available)\b',
            r'\b(like to know|would like|please send|can you)\b'
        ]
        
        self.negative_patterns = [
            r'\b(not interested|no thank|decline|pass|busy|not now)\b',
            r'\b(maybe later|not at this time|budget|financial)\b'
        ]
        
        self.scheduling_patterns = [
            r'\b(schedule|calendar|meeting|appointment|time|when)\b',
            r'\b(available|book|arrange|set up|coordinate)\b'
        ]
        
        self.unsubscribe_patterns = [
            r'\b(unsubscribe|remove|stop|opt out|no more|do not contact)\b'
        ]
    
    async def process_inbox_automation(self, max_emails: int = 50) -> Dict[str, Any]:
        """Process inbox for automated reply handling"""
        try:
            # Read unread emails from last 48 hours
            query = "is:unread newer_than:2d"
            emails = await self.google_automation.email_automation.read_inbox(query, max_emails)
            
            processing_results = {
                'total_processed': 0,
                'interested': [],
                'need_info': [],
                'scheduling': [],
                'not_interested': [],
                'unsubscribe': [],
                'unclear': [],
                'errors': []
            }
            
            for email in emails:
                try:
                    result = await self._process_single_reply(email)
                    processing_results['total_processed'] += 1
                    
                    response_type = result['classification']['type']
                    processing_results[response_type].append({
                        'email_id': email['id'],
                        'from': email['from'],
                        'subject': email['subject'],
                        'confidence': result['classification']['confidence'],
                        'action_taken': result['action_taken']
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing email {email.get('id')}: {str(e)}")
                    processing_results['errors'].append({
                        'email_id': email.get('id'),
                        'error': str(e)
                    })
            
            # Generate summary
            summary = await self._generate_processing_summary(processing_results)
            processing_results['summary'] = summary
            
            logger.info(f"Processed {processing_results['total_processed']} emails")
            return processing_results
            
        except Exception as e:
            logger.error(f"Error in inbox automation: {str(e)}")
            return {'error': str(e)}
    
    async def _process_single_reply(self, email: Dict) -> Dict[str, Any]:
        """Process a single reply email"""
        # Extract sender email
        sender_email = self._extract_email_address(email['from'])
        
        # Check if this is a reply to our campaign
        is_campaign_reply = await self._is_campaign_reply(email, sender_email)
        
        if not is_campaign_reply:
            return {
                'classification': {'type': 'unclear', 'confidence': 0.1},
                'action_taken': 'skipped_not_campaign_reply'
            }
        
        # Classify the reply
        classification = await self._classify_reply_with_ai(email)
        
        # Take appropriate action based on classification
        action_result = await self._take_automated_action(email, classification, sender_email)
        
        return {
            'classification': classification,
            'action_taken': action_result
        }
    
    async def _classify_reply_with_ai(self, email: Dict) -> Dict[str, Any]:
        """Classify reply using AI with fallback to pattern matching"""
        try:
            system_message = """You are an AI assistant that analyzes email replies to dental screening outreach campaigns.

Your task is to classify the sender's intent and recommend appropriate follow-up actions.

Classify into one of these types:
- INTERESTED: Shows interest, wants to learn more, or is open to the service
- NEED_INFO: Asks questions, needs clarification, wants more details
- SCHEDULING: Wants to schedule a meeting, call, or appointment
- NOT_INTERESTED: Declines politely, not interested, or has concerns
- UNSUBSCRIBE: Requests removal, unsubscribe, or no further contact
- UNCLEAR: Intent is ambiguous or unclear

Respond with ONLY a JSON object:
{
    "type": "one_of_the_types_above",
    "confidence": 0.9,
    "reasoning": "brief explanation",
    "key_phrases": ["relevant", "phrases", "from", "email"],
    "suggested_action": "specific recommendation"
}"""

            self.ai_chat.system_message = system_message
            
            prompt = f"""Classify this email reply:

Subject: {email['subject']}
From: {email['from']}
Body: {email['body']}

Return only the JSON classification."""

            user_message = UserMessage(text=prompt)
            response = await self.ai_chat.send_message(user_message)
            
            # Try to parse AI response
            try:
                import json
                classification = json.loads(response.strip())
                
                # Validate classification
                if classification.get('type') in [e.value for e in ResponseType]:
                    return classification
                else:
                    raise ValueError("Invalid classification type")
                    
            except (json.JSONDecodeError, ValueError):
                # Fallback to pattern matching
                return self._classify_with_patterns(email)
            
        except Exception as e:
            logger.error(f"Error in AI classification: {str(e)}")
            return self._classify_with_patterns(email)
    
    def _classify_with_patterns(self, email: Dict) -> Dict[str, Any]:
        """Fallback classification using pattern matching"""
        body = email.get('body', '').lower()
        subject = email.get('subject', '').lower()
        combined_text = f"{subject} {body}"
        
        # Check for unsubscribe
        if any(re.search(pattern, combined_text) for pattern in self.unsubscribe_patterns):
            return {
                'type': ResponseType.UNSUBSCRIBE,
                'confidence': 0.8,
                'reasoning': 'Contains unsubscribe keywords',
                'key_phrases': ['unsubscribe', 'remove', 'stop'],
                'suggested_action': 'Add to do-not-contact list'
            }
        
        # Check for scheduling
        scheduling_matches = sum(1 for pattern in self.scheduling_patterns 
                               if re.search(pattern, combined_text))
        if scheduling_matches >= 2:
            return {
                'type': ResponseType.SCHEDULING,
                'confidence': 0.7,
                'reasoning': 'Multiple scheduling-related keywords',
                'key_phrases': ['schedule', 'meeting', 'time'],
                'suggested_action': 'Send available time slots'
            }
        
        # Check positive vs negative
        positive_matches = sum(1 for pattern in self.positive_patterns 
                             if re.search(pattern, combined_text))
        negative_matches = sum(1 for pattern in self.negative_patterns 
                             if re.search(pattern, combined_text))
        
        if positive_matches > negative_matches and positive_matches >= 1:
            return {
                'type': ResponseType.INTERESTED,
                'confidence': 0.6,
                'reasoning': 'Contains positive keywords',
                'key_phrases': ['interested', 'information'],
                'suggested_action': 'Send detailed information'
            }
        elif negative_matches > 0:
            return {
                'type': ResponseType.NOT_INTERESTED,
                'confidence': 0.6,
                'reasoning': 'Contains negative keywords',
                'key_phrases': ['not interested'],
                'suggested_action': 'Mark as not interested'
            }
        
        # Check for questions
        if '?' in combined_text or 'how' in combined_text or 'what' in combined_text:
            return {
                'type': ResponseType.NEED_INFO,
                'confidence': 0.5,
                'reasoning': 'Contains questions',
                'key_phrases': ['?', 'how', 'what'],
                'suggested_action': 'Provide additional information'
            }
        
        return {
            'type': ResponseType.UNCLEAR,
            'confidence': 0.3,
            'reasoning': 'No clear indicators found',
            'key_phrases': [],
            'suggested_action': 'Manual review required'
        }
    
    async def _take_automated_action(self, email: Dict, classification: Dict, sender_email: str) -> str:
        """Take automated action based on classification"""
        try:
            response_type = classification['type']
            
            if response_type == ResponseType.UNSUBSCRIBE:
                return await self._handle_unsubscribe(email, sender_email)
                
            elif response_type == ResponseType.INTERESTED:
                return await self._handle_interested_response(email, sender_email, classification)
                
            elif response_type == ResponseType.SCHEDULING:
                return await self._handle_scheduling_request(email, sender_email, classification)
                
            elif response_type == ResponseType.NEED_INFO:
                return await self._handle_info_request(email, sender_email, classification)
                
            elif response_type == ResponseType.NOT_INTERESTED:
                return await self._handle_not_interested(email, sender_email)
                
            else:  # UNCLEAR
                return await self._handle_unclear_response(email, sender_email)
            
        except Exception as e:
            logger.error(f"Error taking automated action: {str(e)}")
            return f"error: {str(e)}"
    
    async def _handle_interested_response(self, email: Dict, sender_email: str, classification: Dict) -> str:
        """Handle interested response with follow-up"""
        try:
            # Update contact status in CRM
            await self._update_contact_in_crm(sender_email, 'Interested', 'Positive response received')
            
            # Generate personalized follow-up
            follow_up_email = await self._generate_interested_follow_up(email, sender_email)
            
            # Send follow-up email
            await self.google_automation.email_automation.send_email(
                to_email=sender_email,
                subject=follow_up_email['subject'],
                body=follow_up_email['body']
            )
            
            # Log to CRM
            await self.crm_service.add_schedule_note({
                'activity_type': 'Auto Follow-up',
                'school_contact': sender_email,
                'status': 'Completed',
                'priority': 'High',
                'notes': f'Sent interested follow-up. AI confidence: {classification.get("confidence", 0)}'
            })
            
            # Notify colleague
            await self._notify_colleague_of_interest(email, sender_email)
            
            return 'sent_interested_followup'
            
        except Exception as e:
            logger.error(f"Error handling interested response: {str(e)}")
            return f'error_interested: {str(e)}'
    
    async def _handle_scheduling_request(self, email: Dict, sender_email: str, classification: Dict) -> str:
        """Handle scheduling request"""
        try:
            # Update contact status
            await self._update_contact_in_crm(sender_email, 'Meeting Requested', 'Scheduling request received')
            
            # Generate available time slots
            available_slots = await self._get_available_time_slots(5)  # Next 5 days
            
            # Create scheduling response
            scheduling_response = await self._generate_scheduling_response(email, sender_email, available_slots)
            
            # Send response
            await self.google_automation.email_automation.send_email(
                to_email=sender_email,
                subject=scheduling_response['subject'],
                body=scheduling_response['body']
            )
            
            # Notify user about scheduling request
            await self._notify_user_scheduling_request(email, sender_email)
            
            return 'sent_scheduling_options'
            
        except Exception as e:
            logger.error(f"Error handling scheduling: {str(e)}")
            return f'error_scheduling: {str(e)}'
    
    async def _handle_unsubscribe(self, email: Dict, sender_email: str) -> str:
        """Handle unsubscribe request"""
        try:
            # Add to do-not-contact list
            school_info = await self._get_school_info_from_email(sender_email)
            
            await self.crm_service.add_to_do_not_contact(
                email=sender_email,
                reason='Email unsubscribe request',
                contact_name=self._extract_name_from_email(email['from']),
                school_name=school_info.get('name', '')
            )
            
            # Send confirmation email
            unsubscribe_confirmation = f"""Dear {self._extract_name_from_email(email['from'])},

We have received your request and have removed your email address from our outreach list. You will not receive any further emails from S&P Smiles Co.

If this was sent in error or if you would like to receive information in the future, please contact us directly.

Thank you for your time.

Best regards,
Zwelakhe Mazibuko
S&P Smiles Co."""

            await self.google_automation.email_automation.send_email(
                to_email=sender_email,
                subject="Unsubscribe Confirmation - S&P Smiles Co.",
                body=unsubscribe_confirmation
            )
            
            # Update contact status
            await self._update_contact_in_crm(sender_email, 'Unsubscribed', 'Unsubscribe request processed')
            
            return 'processed_unsubscribe'
            
        except Exception as e:
            logger.error(f"Error handling unsubscribe: {str(e)}")
            return f'error_unsubscribe: {str(e)}'
    
    async def _generate_interested_follow_up(self, original_email: Dict, sender_email: str) -> Dict[str, str]:
        """Generate personalized follow-up for interested responses"""
        
        school_info = await self._get_school_info_from_email(sender_email)
        sender_name = self._extract_name_from_email(original_email['from'])
        
        prompt = f"""Write a warm, professional follow-up email for someone who showed interest in our dental screening services.

Original email details:
- From: {sender_name} at {school_info.get('name', 'their school')}
- Their message: {original_email['body']}

Write a follow-up email that:
1. Thanks them for their interest
2. Provides more detailed information about our services
3. Mentions our student-led approach and mission
4. Asks if they'd like to schedule a brief call to discuss details
5. Offers to answer any questions they might have
6. Includes a professional but warm tone

Do NOT use:
- Contractions or casual language
- AI-sounding phrases
- Overly formal language
- Em dashes or hyphens as punctuation

Write as Zwelakhe Mazibuko from S&P Smiles Co.
Return only the email body, no subject line."""

        try:
            user_message = UserMessage(text=prompt)
            response = await self.ai_chat.send_message(user_message)
            
            subject = f"Re: {original_email['subject']} - Additional Information"
            
            return {
                'subject': subject,
                'body': response.strip()
            }
            
        except Exception as e:
            logger.error(f"Error generating follow-up: {str(e)}")
            return {
                'subject': f"Re: {original_email['subject']}",
                'body': f"""Dear {sender_name},

Thank you for your interest in S&P Smiles Co.'s dental screening services. I am excited to learn more about how we can help your students maintain optimal oral health.

Our comprehensive screening program includes visual examinations, oral cancer awareness, preventive care education, and referrals when necessary. As a student-led initiative, we are passionate about making quality dental care accessible and affordable for school communities.

Would you be available for a brief 15-minute call to discuss how we can customize our services for your school's specific needs? I would be happy to answer any questions and provide additional details about our process.

Please let me know a convenient time for you, or feel free to reply with any questions you might have.

Thank you for your time and consideration.

Best regards,

Zwelakhe Mazibuko
S&P Smiles Co.
Email: {self.google_automation.user_email}
Building healthier smiles, one school at a time."""
            }
    
    async def _generate_scheduling_response(self, email: Dict, sender_email: str, available_slots: List[str]) -> Dict[str, str]:
        """Generate scheduling response email"""
        
        sender_name = self._extract_name_from_email(email['from'])
        school_info = await self._get_school_info_from_email(sender_email)
        
        slots_text = "\n".join([f"• {slot}" for slot in available_slots[:8]])  # Top 8 slots
        
        subject = f"Re: {email['subject']} - Available Meeting Times"
        
        body = f"""Dear {sender_name},

Thank you for your interest in scheduling a meeting to discuss S&P Smiles Co.'s dental screening services for {school_info.get('name', 'your school')}.

I have the following time slots available over the next few days:

{slots_text}

Please reply with your preferred time, and I will send you a calendar invitation. The meeting can be conducted via phone call or video conference, whichever is more convenient for you.

During our discussion, we can cover:
• Detailed overview of our screening services
• Customized pricing for your school
• Implementation timeline and logistics
• Any specific requirements or questions you may have

I look forward to speaking with you and exploring how we can support your students' oral health.

Could you also please share a phone number where I can reach you? This will help ensure smooth communication for our scheduled meeting.

Best regards,

Zwelakhe Mazibuko
S&P Smiles Co.
Email: {self.google_automation.user_email}
Phone: [Your phone number will be shared upon confirmation]"""

        return {'subject': subject, 'body': body}
    
    async def _get_available_time_slots(self, days: int = 5) -> List[str]:
        """Get available time slots for the next few days"""
        try:
            slots = []
            start_date = datetime.now().date() + timedelta(days=1)  # Start from tomorrow
            
            for day_offset in range(days):
                date = start_date + timedelta(days=day_offset)
                day_name = date.strftime('%A')
                date_str = date.strftime('%Y-%m-%d')
                
                # Skip weekends for now (can be customized)
                if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    continue
                
                # Add morning and afternoon slots
                slots.extend([
                    f"{day_name}, {date.strftime('%B %d')} at 09:00 AM",
                    f"{day_name}, {date.strftime('%B %d')} at 11:00 AM", 
                    f"{day_name}, {date.strftime('%B %d')} at 02:00 PM",
                    f"{day_name}, {date.strftime('%B %d')} at 04:00 PM"
                ])
            
            return slots[:10]  # Return top 10 slots
            
        except Exception as e:
            logger.error(f"Error getting time slots: {str(e)}")
            return [
                "Tomorrow at 10:00 AM",
                "Tomorrow at 2:00 PM", 
                "Day after tomorrow at 9:00 AM",
                "Day after tomorrow at 3:00 PM"
            ]
    
    def _extract_email_address(self, from_field: str) -> str:
        """Extract email address from 'from' field"""
        import re
        email_pattern = r'<(.+?)>|([^\s<>]+@[^\s<>]+\.[^\s<>]+)'
        match = re.search(email_pattern, from_field)
        if match:
            return match.group(1) or match.group(2)
        return from_field.strip()
    
    def _extract_name_from_email(self, from_field: str) -> str:
        """Extract name from email 'from' field"""
        if '<' in from_field:
            name = from_field.split('<')[0].strip().strip('"\'')
            return name if name else 'Principal'
        return 'Principal'
    
    async def _is_campaign_reply(self, email: Dict, sender_email: str) -> bool:
        """Check if this email is a reply to our outreach campaign"""
        try:
            # Check if subject contains "Re:" and our typical subjects
            subject = email.get('subject', '').lower()
            if not subject.startswith('re:'):
                return False
            
            # Check if we have this email in our campaigns
            campaigns = await self.crm_service.get_campaigns_by_email(sender_email)
            return len(campaigns) > 0
            
        except Exception as e:
            logger.error(f"Error checking campaign reply: {str(e)}")
            # If we can't determine, assume it might be a reply for safety
            return True
    
    async def _update_contact_in_crm(self, email: str, status: str, notes: str):
        """Update contact status in CRM"""
        try:
            # Find contact by email
            contacts = await self.crm_service.get_contacts()
            
            for contact in contacts:
                if contact.get('Email', '').lower() == email.lower():
                    contact_id = contact.get('Contact ID')
                    if contact_id:
                        await self.crm_service.update_contact_status(
                            contact_id, status, notes=notes
                        )
                        return
            
            logger.warning(f"Contact not found in CRM for email: {email}")
            
        except Exception as e:
            logger.error(f"Error updating contact in CRM: {str(e)}")
    
    async def _get_school_info_from_email(self, email: str) -> Dict:
        """Get school information from email"""
        try:
            contacts = await self.crm_service.get_contacts()
            
            for contact in contacts:
                if contact.get('Email', '').lower() == email.lower():
                    school_id = contact.get('School ID')
                    if school_id:
                        schools = await self.crm_service.get_schools({'school_id': school_id})
                        if schools:
                            return schools[0]
            
            return {'name': 'Unknown School'}
            
        except Exception as e:
            logger.error(f"Error getting school info: {str(e)}")
            return {'name': 'Unknown School'}
    
    async def _notify_colleague_of_interest(self, email: Dict, sender_email: str):
        """Notify colleague of interested response"""
        try:
            colleague_email = self.google_automation.colleague_email
            school_info = await self._get_school_info_from_email(sender_email)
            
            notification_subject = f"🎯 Interested Response: {school_info.get('name', 'School')}"
            
            notification_body = f"""Hi there,

Great news! We received an interested response from {school_info.get('name', 'a school')}.

Contact Details:
• Email: {sender_email}
• School: {school_info.get('name', 'Unknown')}
• Original Subject: {email.get('subject', 'N/A')}

Their Response:
{email.get('body', 'N/A')}

I've already sent an automated follow-up with more details. This looks promising!

Best regards,
Automated S&P Smiles System"""

            await self.google_automation.email_automation.send_email(
                to_email=colleague_email,
                subject=notification_subject,
                body=notification_body
            )
            
            logger.info(f"Notified colleague about interested response from {sender_email}")
            
        except Exception as e:
            logger.error(f"Error notifying colleague: {str(e)}")
    
    async def _notify_user_scheduling_request(self, email: Dict, sender_email: str):
        """Notify user about scheduling request"""
        try:
            user_email = self.google_automation.user_email
            school_info = await self._get_school_info_from_email(sender_email)
            
            notification_subject = f"📅 Meeting Request: {school_info.get('name', 'School')}"
            
            notification_body = f"""Hi Zwelakhe,

We received a meeting request from {school_info.get('name', 'a school')}!

Contact Details:
• Email: {sender_email}
• School: {school_info.get('name', 'Unknown')}

Their Message:
{email.get('body', 'N/A')}

I've sent them available time slots. Please check your calendar and confirm availability.

This is an automated notification from your S&P Smiles outreach system."""

            await self.google_automation.email_automation.send_email(
                to_email=user_email,
                subject=notification_subject,
                body=notification_body
            )
            
        except Exception as e:
            logger.error(f"Error notifying user about scheduling: {str(e)}")
    
    async def _handle_info_request(self, email: Dict, sender_email: str, classification: Dict) -> str:
        """Handle information request"""
        try:
            # Generate detailed information response
            info_response = await self._generate_info_response(email, sender_email)
            
            await self.google_automation.email_automation.send_email(
                to_email=sender_email,
                subject=info_response['subject'],
                body=info_response['body']
            )
            
            await self._update_contact_in_crm(sender_email, 'Information Requested', 'Sent detailed information')
            
            return 'sent_information'
            
        except Exception as e:
            return f'error_info: {str(e)}'
    
    async def _handle_not_interested(self, email: Dict, sender_email: str) -> str:
        """Handle not interested response"""
        try:
            await self._update_contact_in_crm(sender_email, 'Not Interested', 'Received negative response')
            
            # Send polite acknowledgment
            ack_response = f"""Dear {self._extract_name_from_email(email['from'])},

Thank you for taking the time to respond to our dental screening proposal.

I completely understand that our services may not be the right fit for your school at this time. We appreciate your consideration and wish you and your students all the best.

If circumstances change in the future, please feel free to reach out to us.

Best regards,

Zwelakhe Mazibuko
S&P Smiles Co."""

            await self.google_automation.email_automation.send_email(
                to_email=sender_email,
                subject=f"Re: {email['subject']} - Thank You",
                body=ack_response
            )
            
            return 'sent_acknowledgment'
            
        except Exception as e:
            return f'error_not_interested: {str(e)}'
    
    async def _handle_unclear_response(self, email: Dict, sender_email: str) -> str:
        """Handle unclear response - flag for manual review"""
        try:
            await self._update_contact_in_crm(sender_email, 'Needs Review', 'Unclear response received - requires manual review')
            
            # Notify user for manual review
            user_email = self.google_automation.user_email
            
            review_notification = f"""Hi Zwelakhe,

Received an email reply that needs manual review:

From: {email['from']}
Subject: {email['subject']}
Message:
{email['body']}

Please review and respond as appropriate.

This is an automated notification."""

            await self.google_automation.email_automation.send_email(
                to_email=user_email,
                subject=f"⚠️ Manual Review Needed: {self._extract_name_from_email(email['from'])}",
                body=review_notification
            )
            
            return 'flagged_for_review'
            
        except Exception as e:
            return f'error_unclear: {str(e)}'
    
    async def _generate_info_response(self, email: Dict, sender_email: str) -> Dict[str, str]:
        """Generate detailed information response"""
        
        sender_name = self._extract_name_from_email(email['from'])
        school_info = await self._get_school_info_from_email(sender_email)
        
        subject = f"Re: {email['subject']} - Detailed Information"
        
        body = f"""Dear {sender_name},

Thank you for your inquiry about S&P Smiles Co.'s dental screening services. I am happy to provide you with additional information about our program.

About S&P Smiles Co.:
We are a student-led oral health initiative focused on making quality dental care accessible to school communities across Gauteng. Our mission is to promote oral health awareness and provide affordable screening services that benefit both students and their families.

Our Comprehensive Screening Services Include:
• Visual oral examinations by qualified professionals
• Early detection of dental issues and abnormalities
• Oral cancer awareness and basic screening
• Preventive care education and recommendations
• Personalized oral hygiene guidance
• Professional referrals when treatment is needed
• Free screening services for school staff members

The Process:
1. We coordinate with your school to schedule a convenient date
2. Parents are notified about the optional screening program
3. We set up in a private room or designated area at your school
4. Individual screenings are conducted with complete privacy
5. Parents receive detailed reports with recommendations
6. Follow-up referrals are provided when necessary

Pricing and Payment:
• Affordable rate calculated specifically for your school's circumstances
• No cost to the school - parents pay directly for their children's screenings
• Significant savings compared to private practice fees
• Payment options available to accommodate different family situations

Benefits for Your School:
• Promotes student health and wellbeing
• No financial burden on the school budget
• Helps identify health issues that may affect academic performance
• Demonstrates the school's commitment to comprehensive student care
• Free health screenings for teaching and support staff

We would love to discuss how we can customize our services to meet {school_info.get('name', 'your school')}'s specific needs and schedule. Would you be interested in a brief phone call to discuss the details further?

Please feel free to ask any additional questions you may have. I am here to help and ensure you have all the information needed to make the best decision for your school community.

Thank you for your time and consideration.

Best regards,

Zwelakhe Mazibuko
S&P Smiles Co.
Email: {self.google_automation.user_email}
Building healthier smiles, one school at a time."""

        return {'subject': subject, 'body': body}
    
    async def _generate_processing_summary(self, results: Dict) -> Dict[str, Any]:
        """Generate summary of processing results"""
        total = results['total_processed']
        
        if total == 0:
            return {'message': 'No emails processed', 'recommendations': []}
        
        summary = {
            'total_emails': total,
            'interested_count': len(results['interested']),
            'scheduling_count': len(results['scheduling']), 
            'info_requests': len(results['need_info']),
            'not_interested_count': len(results['not_interested']),
            'unsubscribes': len(results['unsubscribe']),
            'unclear_count': len(results['unclear']),
            'error_count': len(results['errors'])
        }
        
        # Calculate engagement rate
        engaged = summary['interested_count'] + summary['scheduling_count'] + summary['info_requests']
        engagement_rate = (engaged / total * 100) if total > 0 else 0
        summary['engagement_rate'] = f"{engagement_rate:.1f}%"
        
        # Generate recommendations
        recommendations = []
        
        if summary['interested_count'] > 0:
            recommendations.append(f"🎯 {summary['interested_count']} interested responses - follow up quickly!")
        
        if summary['scheduling_count'] > 0:
            recommendations.append(f"📅 {summary['scheduling_count']} scheduling requests - confirm your availability")
        
        if summary['unclear_count'] > 0:
            recommendations.append(f"⚠️ {summary['unclear_count']} emails need manual review")
        
        if engagement_rate > 15:
            recommendations.append("🚀 Great engagement rate! Consider increasing outreach volume.")
        elif engagement_rate < 5:
            recommendations.append("📝 Low engagement - review email content and targeting.")
        
        summary['recommendations'] = recommendations
        
        return summary

# Initialize reply processor (will be imported by main server) 
reply_processor = None

def initialize_reply_processor(google_automation, crm_service):
    """Initialize reply processor with dependencies"""
    global reply_processor
    reply_processor = ReplyProcessor(google_automation, crm_service)
    return reply_processor