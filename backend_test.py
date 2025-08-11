#!/usr/bin/env python3
"""
Backend API Testing for S&P Smiles Co. Outreach Agent
Tests all backend endpoints with realistic data
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any

# Get backend URL from frontend .env
BACKEND_URL = "https://d358b5b0-99ea-4155-be8d-e427b7bc845a.preview.emergentagent.com/api"

class BackendTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = requests.Session()
        self.test_data = {}
        self.results = []
        
    def log_result(self, test_name: str, success: bool, message: str, details: Any = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   Details: {details}")
        
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details
        })
    
    def test_health_check(self):
        """Test API health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_result("API Health Check", True, f"API is healthy: {data['message']}")
                    return True
                else:
                    self.log_result("API Health Check", False, "Response missing message field", data)
                    return False
            else:
                self.log_result("API Health Check", False, f"HTTP {response.status_code}", response.text)
                return False
        except Exception as e:
            self.log_result("API Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def test_school_management(self):
        """Test school creation and retrieval"""
        # Test school creation
        school_data = {
            "name": "Greenwood Primary School",
            "address": "123 Education Street, Greenwood",
            "district": "Johannesburg East",
            "province": "Gauteng",
            "postal_code": "2001",
            "phone": "+27 11 123 4567",
            "email": "admin@greenwood.edu.za",
            "website": "https://greenwood.edu.za",
            "student_count": 250,
            "demographics": {
                "socioeconomic": "medium",
                "area_type": "urban"
            }
        }
        
        try:
            # Create school
            response = self.session.post(f"{self.base_url}/schools", json=school_data)
            if response.status_code == 200:
                school = response.json()
                if "id" in school and school["name"] == school_data["name"]:
                    self.test_data["school_id"] = school["id"]
                    self.test_data["school"] = school
                    self.log_result("School Creation", True, f"Created school: {school['name']} (ID: {school['id']})")
                else:
                    self.log_result("School Creation", False, "Invalid school response format", school)
                    return False
            else:
                self.log_result("School Creation", False, f"HTTP {response.status_code}", response.text)
                return False
            
            # Test school retrieval
            response = self.session.get(f"{self.base_url}/schools")
            if response.status_code == 200:
                schools = response.json()
                if isinstance(schools, list) and len(schools) > 0:
                    found_school = next((s for s in schools if s["id"] == self.test_data["school_id"]), None)
                    if found_school:
                        self.log_result("School Retrieval", True, f"Retrieved {len(schools)} schools, found our test school")
                        return True
                    else:
                        self.log_result("School Retrieval", False, "Created school not found in list", schools)
                        return False
                else:
                    self.log_result("School Retrieval", False, "Invalid schools list format", schools)
                    return False
            else:
                self.log_result("School Retrieval", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_result("School Management", False, f"Exception: {str(e)}")
            return False
    
    def test_contact_management(self):
        """Test contact creation and retrieval"""
        if "school_id" not in self.test_data:
            self.log_result("Contact Management", False, "No school_id available from previous test")
            return False
        
        contact_data = {
            "school_id": self.test_data["school_id"],
            "name": "Principal Sarah Smith",
            "email": "sarah.smith@greenwood.edu.za",
            "phone": "+27 11 123 4568",
            "position": "principal",
            "is_primary": True
        }
        
        try:
            # Create contact
            response = self.session.post(f"{self.base_url}/contacts", json=contact_data)
            if response.status_code == 200:
                contact = response.json()
                if "id" in contact and contact["name"] == contact_data["name"]:
                    self.test_data["contact_id"] = contact["id"]
                    self.test_data["contact"] = contact
                    self.log_result("Contact Creation", True, f"Created contact: {contact['name']} (ID: {contact['id']})")
                else:
                    self.log_result("Contact Creation", False, "Invalid contact response format", contact)
                    return False
            else:
                self.log_result("Contact Creation", False, f"HTTP {response.status_code}", response.text)
                return False
            
            # Test contact retrieval by school
            response = self.session.get(f"{self.base_url}/contacts/school/{self.test_data['school_id']}")
            if response.status_code == 200:
                contacts = response.json()
                if isinstance(contacts, list) and len(contacts) > 0:
                    found_contact = next((c for c in contacts if c["id"] == self.test_data["contact_id"]), None)
                    if found_contact:
                        self.log_result("Contact Retrieval", True, f"Retrieved {len(contacts)} contacts for school")
                        return True
                    else:
                        self.log_result("Contact Retrieval", False, "Created contact not found in school contacts", contacts)
                        return False
                else:
                    self.log_result("Contact Retrieval", False, "Invalid contacts list format", contacts)
                    return False
            else:
                self.log_result("Contact Retrieval", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_result("Contact Management", False, f"Exception: {str(e)}")
            return False
    
    def test_campaign_management(self):
        """Test campaign creation and retrieval"""
        if "school_id" not in self.test_data:
            self.log_result("Campaign Management", False, "No school_id available from previous test")
            return False
        
        campaign_data = {
            "name": "2025 Dental Screening Outreach",
            "description": "Comprehensive dental screening program for primary schools in Gauteng province",
            "daily_limit": 15,
            "target_schools": [self.test_data["school_id"]]
        }
        
        try:
            # Create campaign
            response = self.session.post(f"{self.base_url}/campaigns", json=campaign_data)
            if response.status_code == 200:
                campaign = response.json()
                if "id" in campaign and campaign["name"] == campaign_data["name"]:
                    self.test_data["campaign_id"] = campaign["id"]
                    self.test_data["campaign"] = campaign
                    self.log_result("Campaign Creation", True, f"Created campaign: {campaign['name']} (ID: {campaign['id']})")
                else:
                    self.log_result("Campaign Creation", False, "Invalid campaign response format", campaign)
                    return False
            else:
                self.log_result("Campaign Creation", False, f"HTTP {response.status_code}", response.text)
                return False
            
            # Test campaign retrieval
            response = self.session.get(f"{self.base_url}/campaigns")
            if response.status_code == 200:
                campaigns = response.json()
                if isinstance(campaigns, list) and len(campaigns) > 0:
                    found_campaign = next((c for c in campaigns if c["id"] == self.test_data["campaign_id"]), None)
                    if found_campaign:
                        self.log_result("Campaign Retrieval", True, f"Retrieved {len(campaigns)} campaigns, found our test campaign")
                        return True
                    else:
                        self.log_result("Campaign Retrieval", False, "Created campaign not found in list", campaigns)
                        return False
                else:
                    self.log_result("Campaign Retrieval", False, "Invalid campaigns list format", campaigns)
                    return False
            else:
                self.log_result("Campaign Retrieval", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_result("Campaign Management", False, f"Exception: {str(e)}")
            return False
    
    def test_ai_email_generation(self):
        """Test AI-powered email generation"""
        required_keys = ["school_id", "contact_id", "campaign_id"]
        for key in required_keys:
            if key not in self.test_data:
                self.log_result("AI Email Generation", False, f"Missing {key} from previous tests")
                return False
        
        email_request = {
            "school_id": self.test_data["school_id"],
            "contact_id": self.test_data["contact_id"],
            "campaign_id": self.test_data["campaign_id"]
        }
        
        try:
            response = self.session.post(f"{self.base_url}/emails/generate", json=email_request)
            if response.status_code == 200:
                email = response.json()
                required_fields = ["id", "subject", "content", "pricing_info"]
                
                if all(field in email for field in required_fields):
                    self.test_data["email_id"] = email["id"]
                    self.test_data["email"] = email
                    
                    # Check pricing calculation
                    pricing_info = email.get("pricing_info", {})
                    price_per_learner = pricing_info.get("price_per_learner", 0)
                    
                    if 19 <= price_per_learner <= 95:
                        pricing_msg = f"Pricing: R{price_per_learner} per learner (within R19-R95 range)"
                        self.log_result("AI Email Generation", True, f"Generated email with AI. {pricing_msg}")
                        
                        # Verify content quality
                        content = email["content"]
                        school_name = self.test_data["school"]["name"]
                        contact_name = self.test_data["contact"]["name"]
                        
                        if school_name in content and contact_name in content:
                            self.log_result("Email Personalization", True, "Email contains personalized school and contact names")
                        else:
                            self.log_result("Email Personalization", False, "Email missing personalization", 
                                          {"school_in_content": school_name in content, "contact_in_content": contact_name in content})
                        
                        return True
                    else:
                        self.log_result("AI Email Generation", False, f"Pricing R{price_per_learner} outside expected range R19-R95", pricing_info)
                        return False
                else:
                    missing_fields = [f for f in required_fields if f not in email]
                    self.log_result("AI Email Generation", False, f"Missing required fields: {missing_fields}", email)
                    return False
            else:
                self.log_result("AI Email Generation", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_result("AI Email Generation", False, f"Exception: {str(e)}")
            return False
    
    def test_email_reply_processing(self):
        """Test email reply processing with AI intent analysis"""
        if "email_id" not in self.test_data:
            self.log_result("Email Reply Processing", False, "No email_id available from previous test")
            return False
        
        # Test with interested reply
        reply_request = {
            "email_id": self.test_data["email_id"],
            "reply_content": "Thank you for reaching out! We are very interested in the dental screening program for our students. Could you please send us more details about the scheduling and what the students need to prepare? We have about 250 students and would like to proceed as soon as possible."
        }
        
        try:
            response = self.session.post(f"{self.base_url}/emails/process-reply", json=reply_request)
            if response.status_code == 200:
                result = response.json()
                required_fields = ["intent", "auto_response", "message"]
                
                if all(field in result for field in required_fields):
                    intent = result["intent"]
                    auto_response = result["auto_response"]
                    
                    # Verify intent analysis
                    valid_intents = ["interested", "need_info", "not_interested", "unclear"]
                    if intent in valid_intents:
                        self.log_result("Email Reply Processing", True, f"Processed reply with intent: {intent}")
                        
                        # Verify auto response generation
                        if len(auto_response) > 10:  # Basic check for meaningful response
                            self.log_result("Auto Response Generation", True, f"Generated {len(auto_response)} character auto-response")
                            return True
                        else:
                            self.log_result("Auto Response Generation", False, "Auto response too short", auto_response)
                            return False
                    else:
                        self.log_result("Email Reply Processing", False, f"Invalid intent: {intent}", result)
                        return False
                else:
                    missing_fields = [f for f in required_fields if f not in result]
                    self.log_result("Email Reply Processing", False, f"Missing required fields: {missing_fields}", result)
                    return False
            else:
                self.log_result("Email Reply Processing", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_result("Email Reply Processing", False, f"Exception: {str(e)}")
            return False
    
    def test_analytics_dashboard(self):
        """Test analytics dashboard endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/analytics/dashboard")
            if response.status_code == 200:
                analytics = response.json()
                required_sections = ["overview", "email_status", "reply_intent"]
                
                if all(section in analytics for section in required_sections):
                    overview = analytics["overview"]
                    
                    # Verify we have data from our tests
                    if (overview.get("total_schools", 0) > 0 and 
                        overview.get("total_contacts", 0) > 0 and 
                        overview.get("total_campaigns", 0) > 0):
                        
                        self.log_result("Analytics Dashboard", True, 
                                      f"Analytics: {overview['total_schools']} schools, "
                                      f"{overview['total_contacts']} contacts, "
                                      f"{overview['total_campaigns']} campaigns")
                        return True
                    else:
                        self.log_result("Analytics Dashboard", False, "Analytics showing zero counts", analytics)
                        return False
                else:
                    missing_sections = [s for s in required_sections if s not in analytics]
                    self.log_result("Analytics Dashboard", False, f"Missing sections: {missing_sections}", analytics)
                    return False
            else:
                self.log_result("Analytics Dashboard", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_result("Analytics Dashboard", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all backend tests in sequence"""
        print(f"🚀 Starting Backend API Tests for S&P Smiles Co. Outreach Agent")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 80)
        
        tests = [
            ("API Health Check", self.test_health_check),
            ("School Management", self.test_school_management),
            ("Contact Management", self.test_contact_management),
            ("Campaign Management", self.test_campaign_management),
            ("AI Email Generation", self.test_ai_email_generation),
            ("Email Reply Processing", self.test_email_reply_processing),
            ("Analytics Dashboard", self.test_analytics_dashboard)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n🧪 Running {test_name}...")
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                self.log_result(test_name, False, f"Unexpected error: {str(e)}")
        
        print("\n" + "=" * 80)
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Backend API is working correctly.")
            return True
        else:
            print(f"⚠️  {total - passed} tests failed. See details above.")
            return False

def main():
    """Main test execution"""
    tester = BackendTester()
    success = tester.run_all_tests()
    
    # Print detailed results for debugging
    print("\n" + "=" * 80)
    print("📋 DETAILED TEST RESULTS:")
    for result in tester.results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['test']}: {result['message']}")
        if result["details"] and not result["success"]:
            print(f"   Details: {result['details']}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())