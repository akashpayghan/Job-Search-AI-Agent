import os
from typing import List

class Config:
    """Configuration for the Job Search Agent"""
    
    # API Keys - Use environment variables or Streamlit secrets
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    
    # ChromaDB Settings
    CHROMA_DB_PATH = "./chroma_db"
    COLLECTION_NAME = "resume_collection"
    
    # Target Companies (20 companies)
    TARGET_COMPANIES: List[str] = [
        "A.P. Moller - Maersk", "Capgemini", "Infosys", "Cybage", "Persistent",
        "siemens", "Yes Tech", "⁠Encora", "aci worldwide", "infineon technologies",
        "Herofin", "Wipro", "⁠johnson controls", "⁠synechron", "⁠Mastercard",
        "⁠DEUS EX", "⁠TCS", "JUST DIAL", "Accenture", "TCL","barclays","cognizant","Tipco",
        "Syngenta","EY"
    ]
    
    # Job Search Platforms
    JOB_PLATFORMS = [
        "naukri.com",
        "indeed.com",
        "linkedin.com",
        "glassdoor.com"
    ]
    
    # OpenAI Model
    OPENAI_MODEL = "gpt-4o-mini"  # More cost-effective
    
    # Search Settings
    MAX_RESULTS_PER_QUERY = 5
    
    @classmethod
    def validate_keys(cls):
        """Validate that API keys are set"""
        errors = []
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY == "":
            errors.append("OPENAI_API_KEY is not set")
        if not cls.SERPER_API_KEY or cls.SERPER_API_KEY == "":
            errors.append("SERPER_API_KEY is not set")
        return errors
