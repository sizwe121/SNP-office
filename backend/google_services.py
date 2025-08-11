# Google Services Integration for Automated Email Outreach System
import os
import json
import base64
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

# Google API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import gspread
from googlesearch import search
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class GoogleWorkspaceAutomation:
    """Main class for Google Workspace automation"""
    
    def __init__(self):
        # Service account file paths
        self.search_sa_file = os.getenv('GOOGLE_SEARCH_SERVICE_ACCOUNT')
        self.gmail_sa_file = os.getenv('GOOGLE_GMAIL_SERVICE_ACCOUNT')
        self.sheets_sa_file = os.getenv('GOOGLE_SHEETS_SERVICE_ACCOUNT')
        
        # API configurations
        self.search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        
        # Team configuration
        self.user_email = os.getenv('USER_EMAIL', 'zwelakhe23diko@gmail.com')
        self.colleague_email = os.getenv('COLLEAGUE_EMAIL', 'phozisa23diko@gmail.com')
        
        # Rate limiting
        self.daily_email_limit = int(os.getenv('DAILY_EMAIL_LIMIT', '15'))
        self.max_follow_ups = int(os.getenv('MAX_FOLLOW_UPS', '3'))
        
        # Initialize services
        self.gmail_service = None
        self.sheets_service = None
        self.calendar_service = None
        self.custom_search_service = None
        
        # Email tracking
        self.emails_sent_today = 0
        self.last_reset_date = datetime.now().date()
        
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all Google services"""
        try:
            # Gmail service
            if self.gmail_sa_file and os.path.exists(self.gmail_sa_file):
                gmail_credentials = service_account.Credentials.from_service_account_file(
                    self.gmail_sa_file,
                    scopes=[
                        'https://www.googleapis.com/auth/gmail.readonly',
                        'https://www.googleapis.com/auth/gmail.send',
                        'https://www.googleapis.com/auth/gmail.modify'
                    ]
                )
                # Enable domain-wide delegation for your email
                gmail_credentials = gmail_credentials.with_subject(self.user_email)
                self.gmail_service = build('gmail', 'v1', credentials=gmail_credentials)
                logger.info("Gmail service initialized successfully")
            
            # Sheets service
            if self.sheets_sa_file and os.path.exists(self.sheets_sa_file):
                sheets_credentials = service_account.Credentials.from_service_account_file(
                    self.sheets_sa_file,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                self.sheets_service = gspread.authorize(sheets_credentials)
                logger.info("Sheets service initialized successfully")
            
            # Calendar service
            if self.gmail_sa_file and os.path.exists(self.gmail_sa_file):  # Reuse Gmail service account
                calendar_credentials = service_account.Credentials.from_service_account_file(
                    self.gmail_sa_file,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
                calendar_credentials = calendar_credentials.with_subject(self.user_email)
                self.calendar_service = build('calendar', 'v3', credentials=calendar_credentials)
                logger.info("Calendar service initialized successfully")
            
            # Custom Search service
            if self.search_sa_file and os.path.exists(self.search_sa_file):
                search_credentials = service_account.Credentials.from_service_account_file(
                    self.search_sa_file,
                    scopes=['https://www.googleapis.com/auth/cse']
                )
                self.custom_search_service = build('customsearch', 'v1', 
                                                   credentials=search_credentials)
                logger.info("Custom Search service initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing Google services: {str(e)}")

class SchoolDiscoveryService:
    """Service for finding and enriching school data"""
    
    def __init__(self, google_automation: GoogleWorkspaceAutomation):
        self.google_automation = google_automation
        self.ai_chat = LlmChat(
            api_key=google_automation.google_api_key,
            session_id="school_discovery"
        ).with_model("gemini", "gemini-2.0-flash")
    
    async def find_schools_in_area(self, area: str, school_type: str = "primary") -> List[Dict]:
        """Find schools in a specific area using Google search"""
        schools = []
        
        try:
            # Create search queries
            queries = [
                f"{school_type} schools {area} South Africa contact",
                f"{school_type} schools {area} principal email",
                f"schools {area} Gauteng contact details"
            ]
            
            for query in queries:
                try:
                    # Use Google Search API or fallback to googlesearch
                    if self.google_automation.custom_search_service:
                        results = self._search_with_custom_api(query)
                    else:
                        results = self._search_with_library(query)
                    
                    for result in results[:10]:  # Top 10 results per query
                        school_data = await self._extract_school_info(result)
                        if school_data and not self._is_duplicate(school_data, schools):
                            schools.append(school_data)
                    
                    # Rate limiting
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error searching with query '{query}': {str(e)}")
                    continue
            
            # Enrich school data with AI
            enriched_schools = await self._enrich_school_data(schools)
            
            return enriched_schools
            
        except Exception as e:
            logger.error(f"Error finding schools in {area}: {str(e)}")
            return []
    
    def _search_with_custom_api(self, query: str) -> List[Dict]:
        """Search using Google Custom Search API"""
        try:
            result = self.google_automation.custom_search_service.cse().list(
                q=query,
                cx=self.google_automation.search_engine_id,
                num=10
            ).execute()
            
            return result.get('items', [])
        except Exception as e:
            logger.error(f"Custom search API error: {str(e)}")
            return []
    
    def _search_with_library(self, query: str) -> List[Dict]:
        """Search using googlesearch library as fallback"""
        try:
            results = []
            for url in search(query, num_results=10, sleep_interval=1):
                results.append({'link': url, 'title': '', 'snippet': ''})
            return results
        except Exception as e:
            logger.error(f"Google search library error: {str(e)}")
            return []
    
    async def _extract_school_info(self, search_result: Dict) -> Optional[Dict]:
        """Extract school information from search result using AI"""
        try:
            prompt = f"""Extract school information from this search result:
            
Title: {search_result.get('title', 'N/A')}
Snippet: {search_result.get('snippet', 'N/A')}
URL: {search_result.get('link', 'N/A')}

Extract and return ONLY a JSON object with these fields:
- name: School name
- address: Full address if available
- district: District/area
- province: Province (should be Gauteng for our search)
- phone: Phone number if found
- email: Email address if found
- website: Website URL
- type: primary/secondary/combined
- estimated_students: rough estimate based on context (or null)

Return only valid JSON, no other text."""

            user_message = UserMessage(text=prompt)
            response = await self.ai_chat.send_message(user_message)
            
            # Try to parse JSON response
            try:
                school_data = json.loads(response.strip())
                if school_data.get('name'):
                    school_data['source_url'] = search_result.get('link', '')
                    school_data['discovered_at'] = datetime.now().isoformat()
                    return school_data
            except json.JSONDecodeError:
                # If AI doesn't return valid JSON, extract manually
                return self._manual_extract(search_result)
                
        except Exception as e:
            logger.error(f"Error extracting school info: {str(e)}")
            return None
    
    def _manual_extract(self, search_result: Dict) -> Optional[Dict]:
        """Manual extraction fallback"""
        title = search_result.get('title', '')
        snippet = search_result.get('snippet', '')
        
        if 'school' in title.lower() or 'school' in snippet.lower():
            return {
                'name': title,
                'address': '',
                'district': '',
                'province': 'Gauteng',
                'phone': '',
                'email': '',
                'website': search_result.get('link', ''),
                'type': 'unknown',
                'estimated_students': None,
                'source_url': search_result.get('link', ''),
                'discovered_at': datetime.now().isoformat()
            }
        return None
    
    def _is_duplicate(self, school: Dict, schools: List[Dict]) -> bool:
        """Check if school is already in the list"""
        for existing in schools:
            if (school['name'].lower() in existing['name'].lower() or 
                existing['name'].lower() in school['name'].lower()):
                return True
        return False
    
    async def _enrich_school_data(self, schools: List[Dict]) -> List[Dict]:
        """Enrich school data with AI analysis"""
        enriched = []
        
        for school in schools:
            try:
                prompt = f"""Analyze this school data and provide enrichment:

School: {school['name']}
Location: {school.get('address', 'Unknown')}
District: {school.get('district', 'Unknown')}

Based on the name and location, estimate:
1. Demographics (low/medium/high socioeconomic status)
2. Student count (rough estimate)
3. School type if not clear
4. Best contact approach

Return JSON with:
- demographics: {{socioeconomic: "low/medium/high", area_type: "urban/suburban/rural"}}
- estimated_students: number
- school_type: "primary/secondary/combined"
- contact_strategy: brief description of best approach
- pricing_tier: recommended tier based on demographics (1-5, 1=lowest pricing)

Return only valid JSON."""

                user_message = UserMessage(text=prompt)
                response = await self.ai_chat.send_message(user_message)
                
                try:
                    enrichment = json.loads(response.strip())
                    school.update(enrichment)
                except json.JSONDecodeError:
                    # Add basic enrichment if AI fails
                    school['demographics'] = {'socioeconomic': 'medium', 'area_type': 'urban'}
                    school['estimated_students'] = 300
                    school['pricing_tier'] = 3
                
                enriched.append(school)
                
                # Rate limiting for AI calls
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error enriching school data: {str(e)}")
                enriched.append(school)
        
        return enriched

class EmailAutomationService:
    """Service for automated email operations"""
    
    def __init__(self, google_automation: GoogleWorkspaceAutomation):
        self.google_automation = google_automation
        self.ai_chat = LlmChat(
            api_key=google_automation.google_api_key,
            session_id="email_automation"
        ).with_model("gemini", "gemini-2.0-flash")
    
    async def generate_human_like_email(self, school: Dict, contact: Dict, pricing: float) -> Dict[str, str]:
        """Generate human-like email using AI with specific instructions"""
        
        system_message = """You are Zwelakhe Mazibuko from S&P Smiles Co., writing professional emails to school principals about dental screening services.

CRITICAL REQUIREMENTS:
- Write in a warm, professional, human tone
- NO contractions or casual language  
- NO AI-sounding phrases like "I hope this email finds you well"
- NO overly formal or robotic language
- NO em dashes or hyphens as punctuation
- Use clear, direct communication
- Sound like a real person, not an AI

Email Structure:
1. Personal greeting with principal's name and school
2. Brief, genuine introduction of yourself and S&P Smiles Co.
3. Clear explanation of the dental screening offer
4. Benefits for students and parents
5. Pricing presented naturally
6. Call to action for discussion
7. Professional closing

Make it sound like Zwelakhe personally wrote this email."""

        try:
            self.ai_chat.system_message = system_message
            
            prompt = f"""Write a personalized email to the principal of {school['name']}.

School Details:
- Name: {school['name']}
- Location: {school.get('address', 'Unknown')}, {school.get('district', 'Gauteng')}
- Estimated Students: {school.get('estimated_students', 'Not specified')}
- School Type: {school.get('school_type', 'primary')}

Contact: {contact.get('name', 'Principal')} ({contact.get('position', 'Principal')})

Our Service Details:
- Comprehensive dental screenings at R{pricing} per learner
- No cost to the school (parents pay directly)
- Includes visual screenings, oral cancer checks, hygiene consultations
- Free staff screenings for school employees
- Referrals provided where needed

Write a compelling email that:
1. Introduces S&P Smiles Co. as a student-led oral health initiative
2. Explains the no-cost-to-school model clearly
3. Emphasizes health benefits for students
4. Mentions the affordable pricing naturally
5. Requests a brief discussion about implementation

Keep it concise but informative. Make it sound personal and genuine, like Zwelakhe personally knows about their school.

Return only the email body, no subject line or additional formatting."""

            user_message = UserMessage(text=prompt)
            response = await self.ai_chat.send_message(user_message)
            
            # Generate subject line
            subject_options = [
                f"Partnership Opportunity: Affordable Dental Screenings for {school['name']}",
                f"No-Cost Dental Health Program for {school['name']} Students",
                f"Student Health Initiative: Dental Screenings at {school['name']}",
                f"Dental Screening Partnership Proposal - {school['name']}"
            ]
            
            # Use AI to select best subject or create custom one
            subject_prompt = f"""Choose the most appropriate subject line for an email to {school['name']} about dental screenings, or suggest a better one:

Options:
1. {subject_options[0]}
2. {subject_options[1]}
3. {subject_options[2]}
4. {subject_options[3]}

Return only the subject line, nothing else."""

            subject_message = UserMessage(text=subject_prompt)
            subject_response = await self.ai_chat.send_message(subject_message)
            subject = subject_response.strip().strip('"\'')
            
            return {
                'subject': subject,
                'body': response.strip()
            }
            
        except Exception as e:
            logger.error(f"Error generating AI email: {str(e)}")
            # Fallback template
            return self._fallback_email_template(school, contact, pricing)
    
    def _fallback_email_template(self, school: Dict, contact: Dict, pricing: float) -> Dict[str, str]:
        """Fallback email template if AI fails"""
        
        contact_name = contact.get('name', 'Principal')
        school_name = school['name']
        
        subject = f"Dental Screening Partnership Opportunity for {school_name}"
        
        body = f"""Dear {contact_name},

My name is Zwelakhe Mazibuko, and I represent S&P Smiles Co., a student-led oral health initiative dedicated to improving dental health access in school communities.

We would like to partner with {school_name} to provide comprehensive dental screening services for your students. Our program operates at no cost to the school - parents pay directly for their children's health screenings while the school serves as the host location.

Our screening services include:
• Comprehensive oral health assessments
• Early detection of dental issues
• Oral cancer screening and awareness
• Preventive care recommendations
• Health education for students
• Free screening for school staff members

We have calculated a special rate of R{pricing} per learner for {school_name}, taking into account your school's specific circumstances. This represents a significant saving compared to private practice fees, which typically range from R1,000 to R10,000.

These screenings help identify dental issues early, potentially saving families substantial costs while ensuring students maintain optimal oral health for better academic performance.

Would you be available for a brief discussion about how we can support your students' health and wellbeing? We would be happy to provide additional details and answer any questions you may have.

Thank you for your time and consideration.

Best regards,

Zwelakhe Mazibuko
S&P Smiles Co.
Email: {self.google_automation.user_email}
Building healthier smiles, one school at a time."""

        return {'subject': subject, 'body': body}
    
    async def send_email(self, to_email: str, subject: str, body: str, 
                        from_email: str = None) -> Dict[str, Any]:
        """Send email via Gmail API"""
        
        # Check daily limit
        if not self._check_daily_limit():
            raise Exception(f"Daily email limit of {self.google_automation.daily_email_limit} reached")
        
        try:
            if not self.google_automation.gmail_service:
                raise Exception("Gmail service not initialized")
            
            from_email = from_email or self.google_automation.user_email
            
            # Create message
            message = MIMEMultipart()
            message['to'] = to_email
            message['from'] = from_email
            message['subject'] = subject
            
            # Add body
            message.attach(MIMEText(body, 'plain'))
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send email
            result = self.google_automation.gmail_service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            # Update counter
            self.google_automation.emails_sent_today += 1
            
            logger.info(f"Email sent successfully to {to_email}")
            return {
                'message_id': result['id'],
                'status': 'sent',
                'sent_at': datetime.now().isoformat(),
                'to': to_email,
                'subject': subject
            }
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            raise
    
    def _check_daily_limit(self) -> bool:
        """Check if daily email limit is reached"""
        current_date = datetime.now().date()
        
        # Reset counter if it's a new day
        if current_date != self.google_automation.last_reset_date:
            self.google_automation.emails_sent_today = 0
            self.google_automation.last_reset_date = current_date
        
        return self.google_automation.emails_sent_today < self.google_automation.daily_email_limit
    
    async def read_inbox(self, query: str = "is:unread", max_results: int = 50) -> List[Dict]:
        """Read emails from Gmail inbox"""
        try:
            if not self.google_automation.gmail_service:
                raise Exception("Gmail service not initialized")
            
            # Search for messages
            results = self.google_automation.gmail_service.users().messages().list(
                userId='me', 
                q=query, 
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            email_data = []
            
            for message in messages:
                msg = self.google_automation.gmail_service.users().messages().get(
                    userId='me', 
                    id=message['id']
                ).execute()
                
                # Parse email
                email_info = self._parse_email(msg)
                email_data.append(email_info)
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error reading inbox: {str(e)}")
            return []
    
    def _parse_email(self, message: Dict) -> Dict:
        """Parse Gmail API message"""
        payload = message['payload']
        headers = payload.get('headers', [])
        
        email_data = {
            'id': message['id'],
            'thread_id': message['threadId'],
            'subject': '',
            'from': '',
            'to': '',
            'date': '',
            'body': '',
            'labels': message.get('labelIds', [])
        }
        
        # Extract headers
        for header in headers:
            name = header['name'].lower()
            if name == 'subject':
                email_data['subject'] = header['value']
            elif name == 'from':
                email_data['from'] = header['value']
            elif name == 'to':
                email_data['to'] = header['value']
            elif name == 'date':
                email_data['date'] = header['value']
        
        # Extract body
        email_data['body'] = self._extract_body(payload)
        
        return email_data
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        else:
            if payload['mimeType'] == 'text/plain':
                data = payload['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body

# Initialize the main automation service
google_automation = GoogleWorkspaceAutomation()
school_discovery = SchoolDiscoveryService(google_automation)
email_automation = EmailAutomationService(google_automation)