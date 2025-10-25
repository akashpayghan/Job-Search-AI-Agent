import json
from openai import OpenAI
from typing import Dict, List
from config import Config
import streamlit as st
import re


class ValidationAgent:
    """Agent to validate and verify job search results with experience filtering"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    def validate_job_data(self, job: Dict, user_experience: int = 0) -> Dict:
        """Validate individual job data quality and accuracy with experience check"""
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
        
        # 6. NEW: Validate Experience Match
        match_analysis = job.get('match_analysis', {})
        experience_match = match_analysis.get('experience_match', False)
        
        if not experience_match:
            # Extract required experience from job
            required_exp = match_analysis.get('required_experience', '')
            min_exp, max_exp = Config.extract_experience_years(required_exp)
            
            # Check if user experience is within reasonable range
            if min_exp > 0:
                if user_experience < min_exp - 1:  # Allow 1 year tolerance below
                    validation_results["issues"].append(f"Required {min_exp}+ years, user has {user_experience} years")
                    validation_results["quality_score"] -= 20
                elif user_experience > max_exp + 3:  # Allow 3 years tolerance above
                    validation_results["issues"].append(f"Job may be too junior (requires {min_exp}-{max_exp} years)")
                    validation_results["quality_score"] -= 15
        
        return validation_results
    
    def verify_with_ai(self, job: Dict, job_role: str, company: str, user_experience: int = 0) -> Dict:
        """Use AI to verify if job matches user's experience and requirements"""
        
        prompt = f"""
You are a job validation expert. Analyze this job posting and verify if it matches the candidate's profile.

Candidate Profile:
- Experience: {user_experience} years
- Target Roles: {job_role}

Job Details:
- Company: {company}
- Title: {job.get('title', 'N/A')}
- URL: {job.get('link', 'N/A')}
- Description: {job.get('snippet', 'N/A')[:500]}

Verify these criteria:
1. Is this a REAL job posting (not generic career page)?
2. Does the role match: "{job_role}"?
3. Is it from company: "{company}"?
4. Is the location in India?
5. MOST IMPORTANT: Does the required experience match {user_experience} years (allow ±2 years tolerance)?
6. Is the URL a direct job application link?

Return JSON with this format:
{{
    "is_valid_job": true,
    "matches_role": true,
    "matches_company": true,
    "is_india_location": true,
    "experience_appropriate": true,
    "required_experience_range": "2-5 years",
    "experience_gap": 0,
    "is_direct_link": true,
    "confidence_score": 85,
    "reasoning": "Brief explanation focusing on experience match"
}}
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=Config.OPENAI_VALIDATION_MODEL,
                messages=[
                    {"role": "system", "content": "You are a job validation expert specializing in experience-level matching. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=350
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean markdown code blocks
            result_text = result_text.strip('`').strip()
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()
            
            result = json.loads(result_text)
            
            # Ensure all fields exist
            required_fields = ["is_valid_job", "matches_role", "matches_company", 
                             "is_india_location", "experience_appropriate", "is_direct_link", "confidence_score"]
            for field in required_fields:
                if field not in result:
                    result[field] = False if field != "confidence_score" else 0
            
            # Extract experience gap if not provided
            if 'experience_gap' not in result:
                req_exp_str = result.get('required_experience_range', '')
                min_exp, max_exp = Config.extract_experience_years(req_exp_str)
                if min_exp > 0:
                    result['experience_gap'] = user_experience - min_exp
                else:
                    result['experience_gap'] = 0
            
            return result
            
        except Exception as e:
            st.warning(f"AI validation error: {e}")
            return {
                "is_valid_job": True,
                "matches_role": True,
                "matches_company": True,
                "is_india_location": True,
                "experience_appropriate": True,
                "required_experience_range": "Not specified",
                "experience_gap": 0,
                "is_direct_link": True,
                "confidence_score": 50,
                "reasoning": "Validation error",
                "error": str(e)
            }
    
    def validate_job_batch(self, jobs: List[Dict], job_roles: List[str], user_experience: int = 0) -> List[Dict]:
        """Validate a batch of jobs and return only valid ones matching experience requirements"""
        validated_jobs = []
        
        for job in jobs:
            # Basic validation with experience check
            basic_validation = self.validate_job_data(job, user_experience)
            
            # Skip if basic validation fails significantly
            if basic_validation["quality_score"] < 40:
                continue
            
            company = job.get('company', '')
            
            # Check if job matches any of the provided roles
            job_title_lower = job.get('title', '').lower()
            matches_any_role = any(role.lower() in job_title_lower for role in job_roles)
            
            if not matches_any_role:
                continue
            
            # AI validation with experience check
            ai_validation = self.verify_with_ai(job, ", ".join(job_roles), company, user_experience)
            
            # Strict experience filtering
            experience_appropriate = ai_validation.get("experience_appropriate", False)
            experience_gap = abs(ai_validation.get("experience_gap", 0))
            
            # Allow jobs with experience gap of ±2 years
            if experience_gap > 2 and not experience_appropriate:
                # Skip jobs that are too junior or too senior
                continue
            
            # Combine validations
            job['validation'] = {
                **basic_validation,
                **ai_validation,
                "final_valid": (
                    basic_validation["is_valid"] and 
                    basic_validation["quality_score"] >= 40 and
                    ai_validation.get("is_valid_job", False) and
                    ai_validation.get("is_india_location", False) and
                    ai_validation.get("experience_appropriate", False) and  # NEW: Must match experience
                    ai_validation.get("confidence_score", 0) >= 60
                )
            }
            
            # Only include if passed all validations including experience
            if job['validation']['final_valid']:
                validated_jobs.append(job)
        
        return validated_jobs
    
    def generate_validation_report(self, original_count: int, validated_count: int, 
                                   filtered_reasons: Dict, user_experience: int = 0) -> str:
        """Generate a detailed validation report with experience filtering info"""
        
        report = f"""
### 📊 Validation Report

**Candidate Experience Level:** {user_experience} years

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
        
        report += f"\n\n**Experience Filtering:**\n"
        report += f"- Jobs matched to {user_experience} years experience (±2 years tolerance)\n"
        report += f"- Too junior or too senior positions filtered out\n"
        report += f"- Focus on roles appropriate for your career stage"
        
        return report
