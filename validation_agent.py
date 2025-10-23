import json
from openai import OpenAI
from typing import Dict, List
from config import Config
import streamlit as st
import re


class ValidationAgent:
    """Agent to validate and verify job search results"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    def validate_job_data(self, job: Dict) -> Dict:
        """Validate individual job data quality and accuracy"""
        validation_results = {
            "is_valid": True,
            "issues": [],
            "quality_score": 100,
            "corrections": {}
        }
        
        # 1. Validate URL
        if not Config.is_valid_job_url(job.get('link', '')):
            validation_results["is_valid"] = False
            validation_results["issues"].append("Invalid or missing job URL")
            validation_results["quality_score"] -= 30
        
        # 2. Validate Company Name
        if not job.get('company') or job['company'] == 'N/A':
            validation_results["issues"].append("Missing company name")
            validation_results["quality_score"] -= 20
        
        # 3. Validate Job Title
        if not job.get('title') or job['title'] == 'N/A' or len(job.get('title', '')) < 5:
            validation_results["issues"].append("Invalid or too short job title")
            validation_results["quality_score"] -= 25
        
        # 4. Validate Job Description
        if not job.get('snippet') or len(job.get('snippet', '')) < 50:
            validation_results["issues"].append("Insufficient job description")
            validation_results["quality_score"] -= 15
        
        # 5. Check for India location (if location data available)
        snippet_text = job.get('snippet', '') + " " + job.get('title', '')
        if snippet_text and not Config.is_indian_location(snippet_text):
            validation_results["issues"].append("Job location may not be in India")
            validation_results["quality_score"] -= 10
        
        return validation_results
    
    def verify_with_ai(self, job: Dict, job_role: str, company: str) -> Dict:
        """Use AI to verify if job is relevant and accurate"""
        
        prompt = f"""
You are a job validation expert. Analyze this job posting and verify:

1. Is this a REAL job posting (not a generic career page or list)?
2. Does it match the job role: "{job_role}"?
3. Is it from company: "{company}"?
4. Is the location in India?
5. Is the URL a direct job application link?

Job Details:
- Title: {job.get('title', 'N/A')}
- URL: {job.get('link', 'N/A')}
- Description: {job.get('snippet', 'N/A')[:500]}

Return JSON with this format:
{{
    "is_valid_job": true,
    "matches_role": true,
    "matches_company": true,
    "is_india_location": true,
    "is_direct_link": true,
    "confidence_score": 85,
    "reasoning": "Brief explanation"
}}
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=Config.OPENAI_VALIDATION_MODEL,
                messages=[
                    {"role": "system", "content": "You are a job posting validation expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean markdown code blocks
            result_text = result_text.strip('`').strip()
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()
            
            result = json.loads(result_text)
            
            # Ensure all fields exist
            required_fields = ["is_valid_job", "matches_role", "matches_company", 
                             "is_india_location", "is_direct_link", "confidence_score"]
            for field in required_fields:
                if field not in result:
                    result[field] = False if field != "confidence_score" else 0
            
            return result
            
        except Exception as e:
            st.warning(f"AI validation error: {e}")
            return {
                "is_valid_job": True,  # Default to true if validation fails
                "matches_role": True,
                "matches_company": True,
                "is_india_location": True,
                "is_direct_link": True,
                "confidence_score": 50,
                "reasoning": "Validation error",
                "error": str(e)
            }
    
    def validate_job_batch(self, jobs: List[Dict], job_roles: List[str]) -> List[Dict]:
        """Validate a batch of jobs and return only valid ones"""
        validated_jobs = []
        
        for job in jobs:
            # Basic validation
            basic_validation = self.validate_job_data(job)
            
            # AI validation (for high-confidence checking)
            company = job.get('company', '')
            
            # Check if job matches any of the provided roles
            job_title_lower = job.get('title', '').lower()
            matches_any_role = any(role.lower() in job_title_lower for role in job_roles)
            
            if not matches_any_role:
                # Skip jobs that don't match any role
                continue
            
            # AI validation for matched jobs
            ai_validation = self.verify_with_ai(job, ", ".join(job_roles), company)
            
            # Combine validations
            job['validation'] = {
                **basic_validation,
                **ai_validation,
                "final_valid": (
                    basic_validation["is_valid"] and 
                    ai_validation.get("is_valid_job", False) and
                    ai_validation.get("is_india_location", False) and
                    ai_validation.get("confidence_score", 0) >= 60
                )
            }
            
            # Only include if passed validation
            if job['validation']['final_valid']:
                validated_jobs.append(job)
        
        return validated_jobs
    
    def generate_validation_report(self, original_count: int, validated_count: int, 
                                   filtered_reasons: Dict) -> str:
        """Generate a validation report"""
        
        report = f"""
### 📊 Validation Report

**Original Jobs Found:** {original_count}  
**Jobs After Validation:** {validated_count}  
**Jobs Filtered Out:** {original_count - validated_count}

**Filtering Reasons:**
"""
        
        for reason, count in filtered_reasons.items():
            if count > 0:
                report += f"- {reason}: {count} jobs\n"
        
        accuracy_rate = (validated_count / original_count * 100) if original_count > 0 else 0
        report += f"\n**Validation Accuracy:** {accuracy_rate:.1f}%"
        
        return report
