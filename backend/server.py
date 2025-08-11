from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
from enum import Enum
from emergentintegrations.llm.chat import LlmChat, UserMessage
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize AI Chat with Google API key
google_api_key = os.environ.get('GOOGLE_API_KEY')

# Enums
class EmailStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    REPLIED = "replied"
    BOUNCED = "bounced"

class ContactType(str, Enum):
    PRINCIPAL = "principal"
    ADMIN = "admin"
    SECRETARY = "secretary"
    OTHER = "other"

class IntentType(str, Enum):
    INTERESTED = "interested"
    NEED_INFO = "need_info"
    NOT_INTERESTED = "not_interested"
    UNCLEAR = "unclear"

class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"

# Data Models
class School(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: str
    district: Optional[str] = None
    province: str
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    student_count: Optional[int] = None
    demographics: Dict[str, Any] = Field(default_factory=dict)  # e.g., {"socioeconomic": "low", "area_type": "rural"}
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Contact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    school_id: str
    name: str
    email: str
    phone: Optional[str] = None
    position: ContactType
    is_primary: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PricingRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    conditions: Dict[str, Any]  # e.g., {"student_count_max": 200, "demographics.socioeconomic": "low"}
    price_per_learner: float  # R19-R95
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Campaign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    status: CampaignStatus = CampaignStatus.ACTIVE
    daily_limit: int = 15
    emails_sent_today: int = 0
    last_email_date: Optional[datetime] = None
    target_schools: List[str] = Field(default_factory=list)  # school IDs
    email_template_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class Email(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str
    school_id: str
    contact_id: str
    subject: str
    content: str
    status: EmailStatus = EmailStatus.DRAFT
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    reply_content: Optional[str] = None
    reply_intent: Optional[IntentType] = None
    pricing_info: Optional[Dict[str, Any]] = None
    auto_response_sent: bool = False

class DoNotContact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    reason: str
    added_at: datetime = Field(default_factory=datetime.utcnow)

# Create Models
class SchoolCreate(BaseModel):
    name: str
    address: str
    district: Optional[str] = None
    province: str
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    student_count: Optional[int] = None
    demographics: Dict[str, Any] = Field(default_factory=dict)

class ContactCreate(BaseModel):
    school_id: str
    name: str
    email: str
    phone: Optional[str] = None
    position: ContactType
    is_primary: bool = False

class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    daily_limit: int = 15
    target_schools: List[str] = Field(default_factory=list)

class EmailGenerationRequest(BaseModel):
    school_id: str
    contact_id: str
    campaign_id: str

class EmailReplyRequest(BaseModel):
    email_id: str
    reply_content: str

# Helper functions
def calculate_pricing(school: School) -> float:
    """Calculate dynamic pricing based on school demographics and size"""
    base_price = 57.0  # Middle range R57
    
    # Adjust based on student count
    if school.student_count:
        if school.student_count <= 100:
            base_price -= 20  # Smaller schools get discount
        elif school.student_count >= 500:
            base_price += 15  # Larger schools pay more
    
    # Adjust based on demographics
    demographics = school.demographics or {}
    socioeconomic = demographics.get('socioeconomic', 'medium')
    
    if socioeconomic == 'low':
        base_price -= 25  # Low socioeconomic areas get significant discount
    elif socioeconomic == 'high':
        base_price += 20  # Higher income areas pay more
    
    # Ensure within range R19-R95
    return max(19.0, min(95.0, base_price))

async def generate_email_with_ai(school: School, contact: Contact, pricing: float) -> Dict[str, str]:
    """Generate personalized email using Gemini AI"""
    
    # Create system message for the AI
    system_message = """You are an AI assistant helping S&P Smiles Co., a student-led oral health team, write professional and personalized emails to schools for dental screening services.

Your emails must be:
- Warm and approachable but professional
- Clear and concise
- Polite with proper punctuation
- NO contractions or slang
- NO robotic phrases
- Human-like and personalized
- Include the provided pricing
- Focus on oral health benefits for students

Always include:
1. Personalized greeting using contact's name and school name
2. Brief introduction of S&P Smiles Co.
3. Benefits of dental screening for students
4. Personalized pricing information
5. Call to action for booking/discussion
6. Professional closing with contact information"""

    try:
        # Initialize chat
        chat = LlmChat(
            api_key=google_api_key,
            session_id=f"email_gen_{uuid.uuid4()}",
            system_message=system_message
        ).with_model("gemini", "gemini-2.0-flash")
        
        # Create personalized prompt
        prompt = f"""Write a personalized email to {contact.name} at {school.name} school.

School Details:
- Name: {school.name}
- Location: {school.address}, {school.province}
- Student Count: {school.student_count or 'Not specified'}
- Contact: {contact.name} ({contact.position})

Pricing: R{pricing} per learner (special rate calculated for their school)

Write a compelling email that introduces S&P Smiles Co. dental screening services. Make it personal, professional, and focused on the health benefits for their students. Include the pricing naturally in the content.

Return ONLY the email content, no additional text or formatting."""

        # Generate email
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Extract subject from first line or generate one
        content_lines = response.strip().split('\n')
        subject = f"Dental Screening Partnership Opportunity for {school.name}"
        
        return {
            "subject": subject,
            "content": response.strip()
        }
        
    except Exception as e:
        logging.error(f"AI email generation failed: {str(e)}")
        # Fallback to template
        return {
            "subject": f"Dental Screening Partnership Opportunity for {school.name}",
            "content": f"""Dear {contact.name},

I hope this email finds you well. I am writing to introduce S&P Smiles Co., a student-led oral health initiative dedicated to improving dental health awareness and access for school communities.

We would like to partner with {school.name} to provide comprehensive dental screening services for your students. Our team of qualified dental professionals offers:

• Comprehensive oral health assessments
• Early detection of dental issues
• Preventive care recommendations
• Health education sessions for students

We have calculated a special rate of R{pricing} per learner for {school.name}, taking into consideration your school's specific needs and circumstances.

These screenings can help identify dental issues early, potentially saving families significant costs and ensuring students maintain optimal oral health for better overall academic performance.

Would you be available for a brief discussion about how we can support your students' health and wellbeing? I would be happy to provide more details about our services and answer any questions you may have.

Thank you for your time and consideration.

Best regards,

S&P Smiles Co. Team
Contact: zwelakhe23diko@gmail.com
Building healthier smiles, one school at a time."""
        }

async def analyze_reply_intent(reply_content: str) -> IntentType:
    """Analyze email reply intent using AI"""
    
    system_message = """You are an AI assistant that analyzes email replies to categorize the sender's intent for dental screening services.

Your task is to read the email reply and determine the intent:
- INTERESTED: Shows interest, wants to learn more, or agrees to proceed
- NEED_INFO: Asks questions, needs more details, wants clarification
- NOT_INTERESTED: Declines, not interested, or politely refuses
- UNCLEAR: Intent is ambiguous or unclear

Respond with ONLY one word: INTERESTED, NEED_INFO, NOT_INTERESTED, or UNCLEAR"""

    try:
        chat = LlmChat(
            api_key=google_api_key,
            session_id=f"intent_analysis_{uuid.uuid4()}",
            system_message=system_message
        ).with_model("gemini", "gemini-2.0-flash")
        
        user_message = UserMessage(text=f"Analyze this email reply and determine the intent:\n\n{reply_content}")
        response = await chat.send_message(user_message)
        
        # Parse response
        intent_str = response.strip().upper()
        if intent_str == "INTERESTED":
            return IntentType.INTERESTED
        elif intent_str == "NEED_INFO":
            return IntentType.NEED_INFO
        elif intent_str == "NOT_INTERESTED":
            return IntentType.NOT_INTERESTED
        else:
            return IntentType.UNCLEAR
            
    except Exception as e:
        logging.error(f"Intent analysis failed: {str(e)}")
        return IntentType.UNCLEAR

async def generate_auto_response(reply_intent: IntentType, original_email: Email, school: School) -> str:
    """Generate automated response based on reply intent"""
    
    system_message = """You are an AI assistant generating professional automated responses for S&P Smiles Co. based on the intent of incoming email replies.

Your responses must be:
- Professional and courteous
- Brief but helpful
- Action-oriented
- Include contact information for follow-up
- NO contractions or slang
- Proper punctuation and grammar"""

    try:
        chat = LlmChat(
            api_key=google_api_key,
            session_id=f"auto_response_{uuid.uuid4()}",
            system_message=system_message
        ).with_model("gemini", "gemini-2.0-flash")
        
        if reply_intent == IntentType.INTERESTED:
            prompt = f"Generate an automated response for someone who showed interest in dental screening services for {school.name}. Thank them, provide next steps, and include contact information."
        elif reply_intent == IntentType.NEED_INFO:
            prompt = f"Generate an automated response for someone who needs more information about dental screening services for {school.name}. Offer to provide details and include contact information."
        elif reply_intent == IntentType.NOT_INTERESTED:
            prompt = f"Generate a polite automated response acknowledging their decision not to proceed with dental screening services. Thank them for their time and leave door open for future."
        else:  # UNCLEAR
            prompt = f"Generate an automated response for an unclear reply regarding dental screening services for {school.name}. Ask for clarification politely."
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        return response.strip()
        
    except Exception as e:
        logging.error(f"Auto response generation failed: {str(e)}")
        return f"Thank you for your email regarding dental screening services for {school.name}. We will be in touch shortly to address your inquiry. Please contact us directly at zwelakhe23diko@gmail.com for immediate assistance."

# API Endpoints

@api_router.get("/")
async def root():
    return {"message": "S&P Smiles Co. Outreach Agent API"}

# School Management
@api_router.post("/schools", response_model=School)
async def create_school(school_data: SchoolCreate):
    school = School(**school_data.dict())
    await db.schools.insert_one(school.dict())
    return school

@api_router.get("/schools", response_model=List[School])
async def get_schools():
    schools = await db.schools.find().to_list(1000)
    return [School(**school) for school in schools]

@api_router.get("/schools/{school_id}", response_model=School)
async def get_school(school_id: str):
    school = await db.schools.find_one({"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return School(**school)

# Contact Management
@api_router.post("/contacts", response_model=Contact)
async def create_contact(contact_data: ContactCreate):
    contact = Contact(**contact_data.dict())
    await db.contacts.insert_one(contact.dict())
    return contact

@api_router.get("/contacts/school/{school_id}", response_model=List[Contact])
async def get_school_contacts(school_id: str):
    contacts = await db.contacts.find({"school_id": school_id}).to_list(100)
    return [Contact(**contact) for contact in contacts]

# Campaign Management
@api_router.post("/campaigns", response_model=Campaign)
async def create_campaign(campaign_data: CampaignCreate):
    campaign = Campaign(**campaign_data.dict())
    await db.campaigns.insert_one(campaign.dict())
    return campaign

@api_router.get("/campaigns", response_model=List[Campaign])
async def get_campaigns():
    campaigns = await db.campaigns.find().to_list(100)
    return [Campaign(**campaign) for campaign in campaigns]

@api_router.get("/campaigns/{campaign_id}", response_model=Campaign)
async def get_campaign(campaign_id: str):
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return Campaign(**campaign)

# Email Generation and Management
@api_router.post("/emails/generate", response_model=Email)
async def generate_email(request: EmailGenerationRequest):
    # Get school and contact data
    school = await db.schools.find_one({"id": request.school_id})
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    contact = await db.contacts.find_one({"id": request.contact_id})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    campaign = await db.campaigns.find_one({"id": request.campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Check daily limits
    today = datetime.utcnow().date()
    campaign_obj = Campaign(**campaign)
    
    if (campaign_obj.last_email_date and 
        campaign_obj.last_email_date.date() == today and 
        campaign_obj.emails_sent_today >= campaign_obj.daily_limit):
        raise HTTPException(status_code=429, detail="Daily email limit reached for this campaign")
    
    # Calculate pricing
    school_obj = School(**school)
    contact_obj = Contact(**contact)
    pricing = calculate_pricing(school_obj)
    
    # Generate email using AI
    email_data = await generate_email_with_ai(school_obj, contact_obj, pricing)
    
    # Create email record
    email = Email(
        campaign_id=request.campaign_id,
        school_id=request.school_id,
        contact_id=request.contact_id,
        subject=email_data["subject"],
        content=email_data["content"],
        pricing_info={"price_per_learner": pricing, "total_estimate": pricing * (school_obj.student_count or 100)}
    )
    
    await db.emails.insert_one(email.dict())
    
    # Update campaign counters
    update_data = {}
    if campaign_obj.last_email_date and campaign_obj.last_email_date.date() == today:
        update_data["emails_sent_today"] = campaign_obj.emails_sent_today + 1
    else:
        update_data["emails_sent_today"] = 1
        update_data["last_email_date"] = datetime.utcnow()
    
    await db.campaigns.update_one({"id": request.campaign_id}, {"$set": update_data})
    
    return email

@api_router.get("/emails", response_model=List[Email])
async def get_emails():
    emails = await db.emails.find().to_list(1000)
    return [Email(**email) for email in emails]

@api_router.get("/emails/campaign/{campaign_id}", response_model=List[Email])
async def get_campaign_emails(campaign_id: str):
    emails = await db.emails.find({"campaign_id": campaign_id}).to_list(1000)
    return [Email(**email) for email in emails]

# Email Reply Processing
@api_router.post("/emails/process-reply")
async def process_email_reply(request: EmailReplyRequest):
    # Get original email
    email = await db.emails.find_one({"id": request.email_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    email_obj = Email(**email)
    
    # Analyze reply intent
    intent = await analyze_reply_intent(request.reply_content)
    
    # Get school info for context
    school = await db.schools.find_one({"id": email_obj.school_id})
    school_obj = School(**school) if school else None
    
    # Generate auto response
    auto_response = await generate_auto_response(intent, email_obj, school_obj)
    
    # Update email record
    update_data = {
        "reply_content": request.reply_content,
        "reply_intent": intent,
        "replied_at": datetime.utcnow(),
        "status": EmailStatus.REPLIED,
        "auto_response_sent": True
    }
    
    await db.emails.update_one({"id": request.email_id}, {"$set": update_data})
    
    # If not interested, add to do-not-contact list
    if intent == IntentType.NOT_INTERESTED:
        contact = await db.contacts.find_one({"id": email_obj.contact_id})
        if contact:
            do_not_contact = DoNotContact(
                email=contact["email"],
                reason="Requested not to be contacted"
            )
            await db.do_not_contact.insert_one(do_not_contact.dict())
    
    return {
        "intent": intent,
        "auto_response": auto_response,
        "message": "Reply processed successfully"
    }

# Analytics
@api_router.get("/analytics/dashboard")
async def get_analytics():
    # Get counts
    total_schools = await db.schools.count_documents({})
    total_contacts = await db.contacts.count_documents({})
    total_campaigns = await db.campaigns.count_documents({})
    total_emails = await db.emails.count_documents({})
    
    # Email status breakdown
    emails_sent = await db.emails.count_documents({"status": EmailStatus.SENT})
    emails_replied = await db.emails.count_documents({"status": EmailStatus.REPLIED})
    emails_draft = await db.emails.count_documents({"status": EmailStatus.DRAFT})
    
    # Intent breakdown
    interested_count = await db.emails.count_documents({"reply_intent": IntentType.INTERESTED})
    need_info_count = await db.emails.count_documents({"reply_intent": IntentType.NEED_INFO})
    not_interested_count = await db.emails.count_documents({"reply_intent": IntentType.NOT_INTERESTED})
    
    return {
        "overview": {
            "total_schools": total_schools,
            "total_contacts": total_contacts,
            "total_campaigns": total_campaigns,
            "total_emails": total_emails
        },
        "email_status": {
            "sent": emails_sent,
            "replied": emails_replied,
            "draft": emails_draft
        },
        "reply_intent": {
            "interested": interested_count,
            "need_info": need_info_count,
            "not_interested": not_interested_count
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()