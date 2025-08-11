import React, { useState, useEffect } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Main Dashboard Component
const Dashboard = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/analytics/dashboard`);
      setAnalytics(response.data);
    } catch (error) {
      console.error("Failed to fetch analytics:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0 flex items-center">
                <div className="w-8 h-8 bg-blue-600 rounded-lg mr-3 flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h1 className="text-xl font-bold text-gray-900">S&P Smiles Co.</h1>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">Automated Outreach Agent</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Welcome Section */}
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-lg p-6 text-white mb-8">
            <h2 className="text-2xl font-bold mb-2">Welcome to Your Outreach Dashboard</h2>
            <p className="text-blue-100">
              Automate your dental screening outreach to schools with AI-powered email generation and intelligent follow-ups.
            </p>
          </div>

          {/* Quick Stats */}
          {analytics && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <StatCard
                title="Total Schools"
                value={analytics.overview.total_schools}
                icon="🏫"
                color="bg-green-500"
              />
              <StatCard
                title="Active Contacts"
                value={analytics.overview.total_contacts}
                icon="👥"
                color="bg-blue-500"
              />
              <StatCard
                title="Campaigns"
                value={analytics.overview.total_campaigns}
                icon="📧"
                color="bg-purple-500"
              />
              <StatCard
                title="Emails Generated"
                value={analytics.overview.total_emails}
                icon="✉️"
                color="bg-orange-500"
              />
            </div>
          )}

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <ActionCard
              title="Generate Email"
              description="Create personalized outreach emails using AI"
              icon="🤖"
              buttonText="Generate Now"
              onClick={() => window.location.hash = "#generate"}
            />
            <ActionCard
              title="Manage Schools"
              description="Add and manage your school database"
              icon="🏫"
              buttonText="Manage Schools"
              onClick={() => window.location.hash = "#schools"}
            />
            <ActionCard
              title="View Analytics"
              description="Track your outreach performance"
              icon="📊"
              buttonText="View Reports"
              onClick={() => window.location.hash = "#analytics"}
            />
          </div>

          {/* Recent Activity */}
          {analytics && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Email Status Overview</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{analytics.email_status.draft}</div>
                  <div className="text-sm text-gray-600">Draft Emails</div>
                </div>
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{analytics.email_status.sent}</div>
                  <div className="text-sm text-blue-600">Sent Emails</div>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{analytics.email_status.replied}</div>
                  <div className="text-sm text-green-600">Received Replies</div>
                </div>
              </div>

              {/* Reply Intent Breakdown */}
              <div className="mt-6 pt-6 border-t border-gray-200">
                <h4 className="text-md font-medium text-gray-900 mb-3">Reply Intent Analysis</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center p-3 bg-green-50 rounded">
                    <div className="text-xl font-bold text-green-600">{analytics.reply_intent.interested}</div>
                    <div className="text-xs text-green-600">Interested</div>
                  </div>
                  <div className="text-center p-3 bg-yellow-50 rounded">
                    <div className="text-xl font-bold text-yellow-600">{analytics.reply_intent.need_info}</div>
                    <div className="text-xs text-yellow-600">Need Info</div>
                  </div>
                  <div className="text-center p-3 bg-red-50 rounded">
                    <div className="text-xl font-bold text-red-600">{analytics.reply_intent.not_interested}</div>
                    <div className="text-xs text-red-600">Not Interested</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

// Email Generation Component
const EmailGenerator = () => {
  const [schools, setSchools] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedSchool, setSelectedSchool] = useState("");
  const [selectedContact, setSelectedContact] = useState("");
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [generatedEmail, setGeneratedEmail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (selectedSchool) {
      fetchContacts(selectedSchool);
    }
  }, [selectedSchool]);

  const fetchData = async () => {
    try {
      const [schoolsRes, campaignsRes] = await Promise.all([
        axios.get(`${API}/schools`),
        axios.get(`${API}/campaigns`)
      ]);
      setSchools(schoolsRes.data);
      setCampaigns(campaignsRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    }
  };

  const fetchContacts = async (schoolId) => {
    try {
      const response = await axios.get(`${API}/contacts/school/${schoolId}`);
      setContacts(response.data);
    } catch (error) {
      console.error("Failed to fetch contacts:", error);
    }
  };

  const generateEmail = async () => {
    if (!selectedSchool || !selectedContact || !selectedCampaign) {
      alert("Please select school, contact, and campaign");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/emails/generate`, {
        school_id: selectedSchool,
        contact_id: selectedContact,
        campaign_id: selectedCampaign
      });
      setGeneratedEmail(response.data);
    } catch (error) {
      console.error("Failed to generate email:", error);
      alert("Failed to generate email: " + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-gray-900">AI Email Generator</h1>
            <button
              onClick={() => window.location.hash = "#dashboard"}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              ← Back to Dashboard
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto py-6 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-6">Generate Personalized Outreach Email</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            {/* School Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Select School</label>
              <select
                value={selectedSchool}
                onChange={(e) => setSelectedSchool(e.target.value)}
                className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="">Choose a school...</option>
                {schools.map(school => (
                  <option key={school.id} value={school.id}>{school.name}</option>
                ))}
              </select>
            </div>

            {/* Contact Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Select Contact</label>
              <select
                value={selectedContact}
                onChange={(e) => setSelectedContact(e.target.value)}
                className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                disabled={!selectedSchool}
              >
                <option value="">Choose a contact...</option>
                {contacts.map(contact => (
                  <option key={contact.id} value={contact.id}>{contact.name} ({contact.position})</option>
                ))}
              </select>
            </div>

            {/* Campaign Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Select Campaign</label>
              <select
                value={selectedCampaign}
                onChange={(e) => setSelectedCampaign(e.target.value)}
                className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="">Choose a campaign...</option>
                {campaigns.map(campaign => (
                  <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Generate Button */}
          <div className="text-center mb-6">
            <button
              onClick={generateEmail}
              disabled={loading || !selectedSchool || !selectedContact || !selectedCampaign}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Generating with AI..." : "Generate Email"}
            </button>
          </div>

          {/* Generated Email Preview */}
          {generatedEmail && (
            <div className="border-t pt-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Generated Email</h3>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700">Subject:</label>
                  <div className="mt-1 p-2 bg-white border rounded">{generatedEmail.subject}</div>
                </div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700">Content:</label>
                  <div className="mt-1 p-4 bg-white border rounded whitespace-pre-wrap text-sm">
                    {generatedEmail.content}
                  </div>
                </div>
                {generatedEmail.pricing_info && (
                  <div className="bg-blue-50 p-3 rounded">
                    <div className="text-sm text-blue-800">
                      <strong>Pricing Info:</strong> R{generatedEmail.pricing_info.price_per_learner} per learner
                      {generatedEmail.pricing_info.total_estimate && 
                        ` (Estimated total: R${generatedEmail.pricing_info.total_estimate})`
                      }
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

// School Management Component
const SchoolManager = () => {
  const [schools, setSchools] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newSchool, setNewSchool] = useState({
    name: "",
    address: "",
    province: "",
    student_count: "",
    demographics: {}
  });

  useEffect(() => {
    fetchSchools();
  }, []);

  const fetchSchools = async () => {
    try {
      const response = await axios.get(`${API}/schools`);
      setSchools(response.data);
    } catch (error) {
      console.error("Failed to fetch schools:", error);
    }
  };

  const addSchool = async () => {
    try {
      const schoolData = {
        ...newSchool,
        student_count: newSchool.student_count ? parseInt(newSchool.student_count) : null
      };
      await axios.post(`${API}/schools`, schoolData);
      setNewSchool({ name: "", address: "", province: "", student_count: "", demographics: {} });
      setShowAddForm(false);
      fetchSchools();
    } catch (error) {
      console.error("Failed to add school:", error);
      alert("Failed to add school");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-gray-900">School Management</h1>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowAddForm(true)}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Add School
              </button>
              <button
                onClick={() => window.location.hash = "#dashboard"}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                ← Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto py-6 px-4">
        {/* Add School Form Modal */}
        {showAddForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-md">
              <h3 className="text-lg font-medium mb-4">Add New School</h3>
              <div className="space-y-4">
                <input
                  type="text"
                  placeholder="School Name"
                  value={newSchool.name}
                  onChange={(e) => setNewSchool({...newSchool, name: e.target.value})}
                  className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
                <input
                  type="text"
                  placeholder="Address"
                  value={newSchool.address}
                  onChange={(e) => setNewSchool({...newSchool, address: e.target.value})}
                  className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
                <input
                  type="text"
                  placeholder="Province"
                  value={newSchool.province}
                  onChange={(e) => setNewSchool({...newSchool, province: e.target.value})}
                  className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
                <input
                  type="number"
                  placeholder="Student Count"
                  value={newSchool.student_count}
                  onChange={(e) => setNewSchool({...newSchool, student_count: e.target.value})}
                  className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={addSchool}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Add School
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Schools List */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="text-lg font-medium text-gray-900">Schools Database</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">School</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Students</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Added</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {schools.map((school) => (
                  <tr key={school.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{school.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{school.address}</div>
                      <div className="text-sm text-gray-500">{school.province}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {school.student_count || "Not specified"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(school.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
};

// Utility Components
const StatCard = ({ title, value, icon, color }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <div className="flex items-center">
      <div className={`${color} rounded-lg p-3 text-white text-xl mr-4`}>
        {icon}
      </div>
      <div>
        <p className="text-sm text-gray-600">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  </div>
);

const ActionCard = ({ title, description, icon, buttonText, onClick }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <div className="text-center">
      <div className="text-3xl mb-3">{icon}</div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 mb-4">{description}</p>
      <button
        onClick={onClick}
        className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
      >
        {buttonText}
      </button>
    </div>
  </div>
);

// Main Router Component
const Router = () => {
  const [currentView, setCurrentView] = useState("dashboard");

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1);
      if (hash) {
        setCurrentView(hash);
      } else {
        setCurrentView("dashboard");
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    handleHashChange(); // Check initial hash

    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const renderView = () => {
    switch (currentView) {
      case "generate":
        return <EmailGenerator />;
      case "schools":
        return <SchoolManager />;
      case "analytics":
      case "dashboard":
      default:
        return <Dashboard />;
    }
  };

  return renderView();
};

function App() {
  return (
    <div className="App">
      <Router />
    </div>
  );
}

export default App;