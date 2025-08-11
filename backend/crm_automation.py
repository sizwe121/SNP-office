# CRM and Automation Services for Google Sheets Integration
import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import re

import gspread
from google.oauth2 import service_account
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Configure logging
logger = logging.getLogger(__name__)

class CRMService:
    """Advanced CRM service using Google Sheets"""
    
    def __init__(self, google_automation):
        self.google_automation = google_automation
        self.sheets_service = google_automation.sheets_service
        self.spreadsheet_id = os.getenv('CRM_SPREADSHEET_ID')
        
        # AI for data processing
        self.ai_chat = LlmChat(
            api_key=google_automation.google_api_key,
            session_id="crm_automation"
        ).with_model("gemini", "gemini-2.0-flash")
        
        # Worksheet configurations
        self.worksheets = {
            'schools': 'Schools Database',
            'contacts': 'Contacts',
            'campaigns': 'Email Campaigns',
            'do_not_contact': 'Do Not Contact',
            'analytics': 'Analytics Dashboard',
            'schedule_notes': 'Schedule & Notes',
            'follow_ups': 'Follow Up Tracking'
        }
    
    async def initialize_crm_structure(self, spreadsheet_id: str = None) -> Dict[str, Any]:
        """Initialize or update CRM structure in Google Sheets"""
        if not spreadsheet_id:
            spreadsheet_id = self.spreadsheet_id
        
        if not spreadsheet_id:
            raise Exception("No CRM spreadsheet ID configured")
        
        try:
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            
            # Create/update each worksheet
            for worksheet_key, worksheet_name in self.worksheets.items():
                await self._create_or_update_worksheet(workbook, worksheet_name, worksheet_key)
            
            logger.info("CRM structure initialized successfully")
            return {
                'status': 'success',
                'spreadsheet_id': spreadsheet_id,
                'worksheets_created': len(self.worksheets),
                'spreadsheet_url': f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            }
            
        except Exception as e:
            logger.error(f"Error initializing CRM structure: {str(e)}")
            raise
    
    async def _create_or_update_worksheet(self, workbook, worksheet_name: str, worksheet_type: str):
        """Create or update a specific worksheet"""
        try:
            # Try to get existing worksheet
            try:
                sheet = workbook.worksheet(worksheet_name)
                logger.info(f"Worksheet '{worksheet_name}' already exists")
            except gspread.WorksheetNotFound:
                # Create new worksheet
                sheet = workbook.add_worksheet(title=worksheet_name, rows=1000, cols=20)
                logger.info(f"Created new worksheet: {worksheet_name}")
            
            # Set up headers based on worksheet type
            headers = self._get_worksheet_headers(worksheet_type)
            
            # Update headers (only if first row is empty or different)
            try:
                existing_headers = sheet.row_values(1)
                if not existing_headers or existing_headers != headers:
                    # Clear first row and add headers
                    sheet.clear()
                    sheet.append_row(headers)
                    
                    # Apply formatting
                    self._format_worksheet_headers(sheet, worksheet_type)
                    
            except Exception as e:
                logger.warning(f"Could not update headers for {worksheet_name}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error creating/updating worksheet {worksheet_name}: {str(e)}")
    
    def _get_worksheet_headers(self, worksheet_type: str) -> List[str]:
        """Get appropriate headers for each worksheet type"""
        headers_map = {
            'schools': [
                'School ID', 'School Name', 'Address', 'District', 'Province', 
                'Phone', 'Email', 'Website', 'School Type', 'Student Count',
                'Demographics', 'Pricing Tier', 'Status', 'Source', 
                'Discovery Date', 'Last Updated', 'Notes'
            ],
            'contacts': [
                'Contact ID', 'School ID', 'Name', 'Position', 'Email', 
                'Phone', 'Is Primary', 'Status', 'Last Contact', 
                'Response Type', 'Follow Up Count', 'Notes', 'Created Date'
            ],
            'campaigns': [
                'Campaign ID', 'School ID', 'Contact ID', 'Subject', 'Status',
                'Sent Date', 'Email Type', 'Pricing Offered', 'Opened', 
                'Replied', 'Response Date', 'Response Type', 'Follow Up Date',
                'Outcome', 'Notes'
            ],
            'do_not_contact': [
                'Email', 'Contact Name', 'School Name', 'Reason', 
                'Date Added', 'Added By', 'Status', 'Notes'
            ],
            'analytics': [
                'Date', 'Emails Sent', 'Emails Opened', 'Replies Received',
                'Positive Responses', 'Meetings Booked', 'Conversion Rate',
                'Daily Status', 'Notes'
            ],
            'schedule_notes': [
                'Date', 'Time', 'Activity Type', 'School/Contact', 
                'Status', 'Priority', 'Assigned To', 'Notes', 
                'Follow Up Date', 'Outcome'
            ],
            'follow_ups': [
                'Follow Up ID', 'Campaign ID', 'School Name', 'Contact Name',
                'Original Date', 'Follow Up Type', 'Due Date', 'Status',
                'Priority', 'Assigned To', 'Completed Date', 'Outcome', 'Notes'
            ]
        }
        
        return headers_map.get(worksheet_type, ['Data'])
    
    def _format_worksheet_headers(self, sheet, worksheet_type: str):
        """Apply formatting to worksheet headers"""
        try:
            # Format header row (row 1)
            header_format = {
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'textFormat': {'bold': True, 'fontSize': 11}
            }
            
            # Apply formatting to header row
            sheet.format('1:1', header_format)
            
            # Set column widths based on content
            column_widths = self._get_column_widths(worksheet_type)
            for col_index, width in enumerate(column_widths, 1):
                if width:
                    sheet.columns_auto_resize(col_index, col_index)
                    
        except Exception as e:
            logger.warning(f"Could not format headers: {str(e)}")
    
    def _get_column_widths(self, worksheet_type: str) -> List[int]:
        """Get optimal column widths for each worksheet type"""
        width_maps = {
            'schools': [120, 200, 250, 120, 100, 120, 180, 180, 100, 80, 150, 80, 100, 120, 120, 120, 200],
            'contacts': [120, 120, 150, 100, 180, 120, 80, 100, 120, 120, 80, 200, 120],
            'campaigns': [120, 120, 120, 250, 100, 120, 120, 100, 80, 80, 120, 120, 120, 150, 200],
            'do_not_contact': [180, 150, 200, 200, 120, 100, 100, 200],
            'analytics': [100, 80, 80, 80, 80, 80, 100, 150, 200],
            'schedule_notes': [100, 80, 120, 200, 100, 80, 120, 200, 120, 150],
            'follow_ups': [120, 120, 200, 150, 120, 120, 120, 100, 80, 120, 120, 150, 200]
        }
        
        return width_maps.get(worksheet_type, [])
    
    async def add_school(self, school_data: Dict, spreadsheet_id: str = None) -> Dict[str, Any]:
        """Add a school to the CRM"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['schools'])
            
            # Generate unique school ID
            school_id = f"SCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(sheet.get_all_records()) + 1}"
            
            # Prepare row data
            row_data = [
                school_id,
                school_data.get('name', ''),
                school_data.get('address', ''),
                school_data.get('district', ''),
                school_data.get('province', 'Gauteng'),
                school_data.get('phone', ''),
                school_data.get('email', ''),
                school_data.get('website', ''),
                school_data.get('school_type', ''),
                school_data.get('estimated_students', ''),
                json.dumps(school_data.get('demographics', {})),
                school_data.get('pricing_tier', 3),
                'New',
                school_data.get('source', 'Manual'),
                school_data.get('discovered_at', datetime.now().isoformat()),
                datetime.now().isoformat(),
                school_data.get('notes', '')
            ]
            
            # Add row
            sheet.append_row(row_data)
            
            logger.info(f"Added school: {school_data['name']} ({school_id})")
            return {
                'status': 'success',
                'school_id': school_id,
                'message': f"School {school_data['name']} added successfully"
            }
            
        except Exception as e:
            logger.error(f"Error adding school: {str(e)}")
            raise
    
    async def add_contact(self, contact_data: Dict, spreadsheet_id: str = None) -> Dict[str, Any]:
        """Add a contact to the CRM"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['contacts'])
            
            # Generate unique contact ID
            contact_id = f"CON_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(sheet.get_all_records()) + 1}"
            
            # Prepare row data
            row_data = [
                contact_id,
                contact_data.get('school_id', ''),
                contact_data.get('name', ''),
                contact_data.get('position', 'Principal'),
                contact_data.get('email', ''),
                contact_data.get('phone', ''),
                contact_data.get('is_primary', True),
                'Active',
                '',  # Last Contact
                '',  # Response Type
                0,   # Follow Up Count
                contact_data.get('notes', ''),
                datetime.now().isoformat()
            ]
            
            # Add row
            sheet.append_row(row_data)
            
            logger.info(f"Added contact: {contact_data['name']} ({contact_id})")
            return {
                'status': 'success',
                'contact_id': contact_id,
                'message': f"Contact {contact_data['name']} added successfully"
            }
            
        except Exception as e:
            logger.error(f"Error adding contact: {str(e)}")
            raise
    
    async def log_campaign(self, campaign_data: Dict, spreadsheet_id: str = None) -> Dict[str, Any]:
        """Log email campaign to CRM"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['campaigns'])
            
            # Prepare row data
            row_data = [
                campaign_data.get('campaign_id', ''),
                campaign_data.get('school_id', ''),
                campaign_data.get('contact_id', ''),
                campaign_data.get('subject', ''),
                campaign_data.get('status', 'Sent'),
                campaign_data.get('sent_at', datetime.now().isoformat()),
                campaign_data.get('email_type', 'Outreach'),
                campaign_data.get('pricing_offered', ''),
                False,  # Opened
                False,  # Replied
                '',     # Response Date
                '',     # Response Type
                '',     # Follow Up Date
                campaign_data.get('outcome', ''),
                campaign_data.get('notes', '')
            ]
            
            # Add row
            sheet.append_row(row_data)
            
            # Update daily analytics
            await self._update_daily_analytics(spreadsheet_id)
            
            logger.info(f"Logged campaign: {campaign_data.get('campaign_id')}")
            return {
                'status': 'success',
                'message': 'Campaign logged successfully'
            }
            
        except Exception as e:
            logger.error(f"Error logging campaign: {str(e)}")
            raise
    
    async def check_do_not_contact(self, email: str, spreadsheet_id: str = None) -> bool:
        """Check if email is in do-not-contact list"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            
            try:
                sheet = workbook.worksheet(self.worksheets['do_not_contact'])
                records = sheet.get_all_records()
                
                for record in records:
                    if record.get('Email', '').lower() == email.lower():
                        return record.get('Status', '').lower() == 'active'
                        
                return False
                
            except gspread.WorksheetNotFound:
                return False
                
        except Exception as e:
            logger.error(f"Error checking do-not-contact list: {str(e)}")
            return False
    
    async def add_to_do_not_contact(self, email: str, reason: str, 
                                   contact_name: str = "", school_name: str = "",
                                   spreadsheet_id: str = None) -> Dict[str, Any]:
        """Add email to do-not-contact list"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            
            try:
                sheet = workbook.worksheet(self.worksheets['do_not_contact'])
            except gspread.WorksheetNotFound:
                # Create worksheet if it doesn't exist
                await self._create_or_update_worksheet(workbook, self.worksheets['do_not_contact'], 'do_not_contact')
                sheet = workbook.worksheet(self.worksheets['do_not_contact'])
            
            # Check if already exists
            records = sheet.get_all_records()
            for record in records:
                if record.get('Email', '').lower() == email.lower():
                    return {
                        'status': 'exists',
                        'message': f'Email {email} already in do-not-contact list'
                    }
            
            # Add new record
            row_data = [
                email,
                contact_name,
                school_name,
                reason,
                datetime.now().isoformat(),
                self.google_automation.user_email,
                'Active',
                ''
            ]
            
            sheet.append_row(row_data)
            
            logger.info(f"Added to do-not-contact: {email}")
            return {
                'status': 'success',
                'message': f'Added {email} to do-not-contact list'
            }
            
        except Exception as e:
            logger.error(f"Error adding to do-not-contact: {str(e)}")
            raise
    
    async def get_schools(self, filters: Dict = None, spreadsheet_id: str = None) -> List[Dict]:
        """Get schools from CRM with optional filters"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['schools'])
            
            records = sheet.get_all_records()
            
            # Apply filters if provided
            if filters:
                filtered_records = []
                for record in records:
                    include = True
                    
                    if 'status' in filters and record.get('Status', '').lower() != filters['status'].lower():
                        include = False
                    if 'district' in filters and filters['district'].lower() not in record.get('District', '').lower():
                        include = False
                    if 'school_type' in filters and record.get('School Type', '').lower() != filters['school_type'].lower():
                        include = False
                    
                    if include:
                        filtered_records.append(record)
                
                return filtered_records
            
            return records
            
        except Exception as e:
            logger.error(f"Error getting schools: {str(e)}")
            return []
    
    async def get_contacts(self, school_id: str = None, spreadsheet_id: str = None) -> List[Dict]:
        """Get contacts from CRM"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['contacts'])
            
            records = sheet.get_all_records()
            
            if school_id:
                return [r for r in records if r.get('School ID') == school_id]
            
            return records
            
        except Exception as e:
            logger.error(f"Error getting contacts: {str(e)}")
            return []
    
    async def update_contact_status(self, contact_id: str, status: str, 
                                   response_type: str = "", notes: str = "",
                                   spreadsheet_id: str = None):
        """Update contact status in CRM"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['contacts'])
            
            # Find contact row
            records = sheet.get_all_records()
            for idx, record in enumerate(records, start=2):  # Start from row 2 (after headers)
                if record.get('Contact ID') == contact_id:
                    # Update relevant columns
                    sheet.update_cell(idx, 8, status)  # Status column
                    sheet.update_cell(idx, 9, datetime.now().isoformat())  # Last Contact
                    if response_type:
                        sheet.update_cell(idx, 10, response_type)  # Response Type
                    if notes:
                        current_notes = record.get('Notes', '')
                        new_notes = f"{current_notes}\n[{datetime.now().strftime('%Y-%m-%d')}] {notes}".strip()
                        sheet.update_cell(idx, 12, new_notes)  # Notes
                    
                    logger.info(f"Updated contact {contact_id} status to {status}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating contact status: {str(e)}")
            return False
    
    async def add_schedule_note(self, note_data: Dict, spreadsheet_id: str = None):
        """Add a schedule/note entry"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['schedule_notes'])
            
            row_data = [
                note_data.get('date', datetime.now().strftime('%Y-%m-%d')),
                note_data.get('time', datetime.now().strftime('%H:%M')),
                note_data.get('activity_type', 'Note'),
                note_data.get('school_contact', ''),
                note_data.get('status', 'Active'),
                note_data.get('priority', 'Medium'),
                note_data.get('assigned_to', self.google_automation.user_email),
                note_data.get('notes', ''),
                note_data.get('follow_up_date', ''),
                note_data.get('outcome', '')
            ]
            
            sheet.append_row(row_data)
            
            logger.info("Added schedule note")
            return {'status': 'success'}
            
        except Exception as e:
            logger.error(f"Error adding schedule note: {str(e)}")
            raise
    
    async def _update_daily_analytics(self, spreadsheet_id: str):
        """Update daily analytics"""
        try:
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            sheet = workbook.worksheet(self.worksheets['analytics'])
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Get existing records
            records = sheet.get_all_records()
            today_record = None
            today_row = None
            
            for idx, record in enumerate(records, start=2):
                if record.get('Date') == today:
                    today_record = record
                    today_row = idx
                    break
            
            # Count today's activities from campaigns
            campaign_sheet = workbook.worksheet(self.worksheets['campaigns'])
            campaign_records = campaign_sheet.get_all_records()
            
            emails_sent = 0
            replies_received = 0
            positive_responses = 0
            
            for campaign in campaign_records:
                sent_date = campaign.get('Sent Date', '')
                if sent_date.startswith(today):
                    emails_sent += 1
                    
                    if campaign.get('Replied'):
                        replies_received += 1
                        
                        response_type = campaign.get('Response Type', '').lower()
                        if 'interested' in response_type or 'positive' in response_type:
                            positive_responses += 1
            
            # Calculate conversion rate
            conversion_rate = (positive_responses / emails_sent * 100) if emails_sent > 0 else 0
            
            analytics_data = [
                today,
                emails_sent,
                0,  # Emails opened (would need email tracking)
                replies_received,
                positive_responses,
                0,  # Meetings booked
                f"{conversion_rate:.1f}%",
                f"Active - {emails_sent} sent, {replies_received} replies",
                f"Updated at {datetime.now().strftime('%H:%M')}"
            ]
            
            if today_row:
                # Update existing row
                for col, value in enumerate(analytics_data, start=1):
                    sheet.update_cell(today_row, col, value)
            else:
                # Add new row
                sheet.append_row(analytics_data)
            
            logger.info("Updated daily analytics")
            
        except Exception as e:
            logger.error(f"Error updating analytics: {str(e)}")
    
    async def get_analytics_summary(self, days: int = 7, spreadsheet_id: str = None) -> Dict[str, Any]:
        """Get analytics summary for specified days"""
        try:
            spreadsheet_id = spreadsheet_id or self.spreadsheet_id
            workbook = self.sheets_service.open_by_key(spreadsheet_id)
            
            # Get campaign data
            campaign_sheet = workbook.worksheet(self.worksheets['campaigns'])
            campaigns = campaign_sheet.get_all_records()
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Analyze campaigns
            total_sent = 0
            total_replies = 0
            positive_responses = 0
            schools_contacted = set()
            
            for campaign in campaigns:
                sent_date_str = campaign.get('Sent Date', '')
                if sent_date_str:
                    try:
                        sent_date = datetime.fromisoformat(sent_date_str.replace('Z', '+00:00'))
                        if start_date <= sent_date <= end_date:
                            total_sent += 1
                            schools_contacted.add(campaign.get('School ID', ''))
                            
                            if campaign.get('Replied'):
                                total_replies += 1
                                
                                response_type = campaign.get('Response Type', '').lower()
                                if 'interested' in response_type or 'positive' in response_type:
                                    positive_responses += 1
                    except:
                        continue
            
            # Calculate metrics
            response_rate = (total_replies / total_sent * 100) if total_sent > 0 else 0
            conversion_rate = (positive_responses / total_sent * 100) if total_sent > 0 else 0
            
            return {
                'period_days': days,
                'emails_sent': total_sent,
                'schools_contacted': len(schools_contacted),
                'replies_received': total_replies,
                'positive_responses': positive_responses,
                'response_rate': f"{response_rate:.1f}%",
                'conversion_rate': f"{conversion_rate:.1f}%",
                'daily_average': f"{total_sent / days:.1f}",
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics summary: {str(e)}")
            return {'status': 'error', 'message': str(e)}

# Initialize CRM service (will be imported by main server)
crm_service = None

def initialize_crm(google_automation):
    """Initialize CRM service with Google automation"""
    global crm_service
    crm_service = CRMService(google_automation)
    return crm_service