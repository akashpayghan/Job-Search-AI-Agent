import os
from typing import List
import re
from datetime import datetime, timedelta


class Config:
    """Configuration for the Job Search Agent"""
    
    # API Keys - Use environment variables or Streamlit secrets
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    
    # ChromaDB Settings
    CHROMA_DB_PATH = "./chroma_db"
    COLLECTION_NAME = "resume_collection"
    
    # Default Target Companies (can be overridden by user input)
    DEFAULT_COMPANIES: List[str] = [
        "A.P. Moller - Maersk", "Capgemini", "Infosys", "Cybage", "Persistent",
        "Siemens", "Yes Tech", "Encora", "ACI Worldwide", "Infineon Technologies",
        "Herofin", "Wipro", "Johnson Controls", "Synechron", "Mastercard",
        "DEUS EX", "TCS", "JUST DIAL", "Accenture", "TCL", "Barclays", 
        "Cognizant", "Tipco", "Syngenta", "EY"
    ]
    
    # Job Search Platforms
    JOB_PLATFORMS = [
        "naukri.com",
        "indeed.com",
        "linkedin.com",
        "glassdoor.com"
    ]
    
    # OpenAI Models
    OPENAI_MODEL = "gpt-4o-mini"  # For job matching
    OPENAI_VALIDATION_MODEL = "gpt-4o-mini"  # For validation agent
    
    # Search Settings
    MAX_RESULTS_PER_QUERY = 5
    DAYS_FILTER = 15  # Filter jobs from last 15 days
    
    # Location Settings
    DEFAULT_LOCATION = "India"
    INDIAN_CITIES = [
        "Bangalore", "Mumbai", "Pune", "Hyderabad", "Chennai", 
        "Delhi", "NCR", "Gurugram", "Noida", "Kolkata", 
        "Ahmedabad", "Kochi", "Indore", "Jaipur", "Chandigarh"
    ]
    
    # Experience Level Mapping
    EXPERIENCE_LEVELS = {
        "entry": ["entry level", "fresher", "graduate", "0-2 years", "junior"],
        "mid": ["mid level", "intermediate", "2-5 years", "3-5 years", "associate"],
        "senior": ["senior", "experienced", "5+ years", "5-10 years", "lead"],
        "expert": ["expert", "principal", "staff", "10+ years", "architect", "director"]
    }
    
    @staticmethod
    def parse_comma_separated(input_str: str) -> List[str]:
        """Parse comma-separated input and clean"""
        if not input_str or not input_str.strip():
            return []
        
        items = [
            item.strip() 
            for item in input_str.split(',')
            if item.strip()
        ]
        
        return items
    
    @staticmethod
    def get_date_filter_query() -> str:
        """Get query string for recent jobs (last 15 days)"""
        # Google search operators for date filtering
        today = datetime.now()
        past_date = today - timedelta(days=Config.DAYS_FILTER)
        
        # Format: after:YYYY-MM-DD
        date_filter = f"after:{past_date.strftime('%Y-%m-%d')}"
        return date_filter
    
    @staticmethod
    def is_indian_location(location_text: str) -> bool:
        """Check if job location is in India"""
        if not location_text:
            return False
        
        location_lower = location_text.lower()
        
        # Direct India mention
        if "india" in location_lower:
            return True
        
        # Check for Indian cities
        for city in Config.INDIAN_CITIES:
            if city.lower() in location_lower:
                return True
        
        return False
    
    @staticmethod
    def extract_job_id(url: str) -> str:
        """Extract job ID from various job portal URLs"""
        if not url:
            return "N/A"
        
        # LinkedIn job ID pattern
        linkedin_match = re.search(r'linkedin\.com/jobs/view/(\d+)', url)
        if linkedin_match:
            return f"LI-{linkedin_match.group(1)}"
        
        # Indeed job ID pattern
        indeed_match = re.search(r'indeed\.com/.*jk=([a-zA-Z0-9]+)', url)
        if indeed_match:
            return f"IN-{indeed_match.group(1)}"
        
        # Naukri job ID pattern
        naukri_match = re.search(r'naukri\.com/job-listings-(.+?)(?:\?|$)', url)
        if naukri_match:
            return f"NK-{naukri_match.group(1)[:15]}"
        
        # Glassdoor job ID pattern
        glassdoor_match = re.search(r'glassdoor\.com/.*job-listing.*_(\d+)', url)
        if glassdoor_match:
            return f"GD-{glassdoor_match.group(1)}"
        
        # Generic pattern - extract numbers from URL
        generic_match = re.search(r'/(\d{6,})', url)
        if generic_match:
            return f"JOB-{generic_match.group(1)}"
        
        # If no pattern matches, generate hash from URL
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"ID-{url_hash}"
    
    @staticmethod
    def is_valid_job_url(url: str) -> bool:
        """Validate if URL is a proper job posting link"""
        if not url or url == "N/A":
            return False
        
        # Check if it's a valid URL format
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            return False
        
        # Check if URL contains job-related keywords
        job_keywords = ['job', 'career', 'position', 'vacancy', 'opening', 'hiring', 'apply']
        url_lower = url.lower()
        
        return any(keyword in url_lower for keyword in job_keywords)
    
    @staticmethod
    def extract_experience_years(text: str) -> tuple:
        """Extract years of experience from text"""
        if not text:
            return (0, 0)
        
        text_lower = text.lower()
        
        # Pattern: "X-Y years"
        range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)', text_lower)
        if range_match:
            return (int(range_match.group(1)), int(range_match.group(2)))
        
        # Pattern: "X+ years" or "X years+"
        plus_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', text_lower)
        if plus_match:
            min_years = int(plus_match.group(1))
            return (min_years, min_years + 5)
        
        # Pattern: "fresher" or "entry level"
        if any(term in text_lower for term in ['fresher', 'entry level', 'graduate']):
            return (0, 2)
        
        return (0, 0)
    
    @classmethod
    def validate_keys(cls):
        """Validate that API keys are set"""
        errors = []
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY == "":
            errors.append("OPENAI_API_KEY is not set")
        if not cls.SERPER_API_KEY or cls.SERPER_API_KEY == "":
            errors.append("SERPER_API_KEY is not set")
        return errors
