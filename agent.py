import requests
import json
from openai import OpenAI
from typing import List, Dict, Tuple
from config import Config
from database import ResumeDatabase
from validation_agent import ValidationAgent
import streamlit as st
import re
from datetime import datetime, timedelta


class JobSearchAgent:
    """AI Agent for searching and matching jobs"""
    
    def __init__(self, skip_validation=False):
        if not skip_validation:
            key_errors = Config.validate_keys()
            if key_errors:
                st.error(f"❌ API Key Error: {', '.join(key_errors)}")
                st.stop()
        
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.serper_api_key = Config.SERPER_API_KEY
        self.db = ResumeDatabase()
        self.validator = ValidationAgent()
        
        if not skip_validation:
            self._test_apis()
    
    def _test_apis(self):
        """Test if APIs are accessible"""
        try:
            response = self._make_serper_request({"q": "test", "num": 1})
            if response.status_code == 401:
                st.error("❌ Serper API Key is invalid!")
                st.stop()
            elif response.status_code != 200:
                st.warning(f"⚠️ Serper API returned status code: {response.status_code}")
        except Exception as e:
            st.error(f"❌ Serper API Connection Error: {str(e)}")
            st.stop()
        
        try:
            self.openai_client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[{"role": "system", "content": "Test"}],
                max_tokens=1
            )
            st.success("✅ APIs validated successfully!")
        except Exception as e:
            st.error(f"❌ OpenAI API Connection Error: {str(e)}")
            st.stop()

    def _make_serper_request(self, payload: Dict) -> requests.Response:
        """Helper method to make Serper API requests"""
        url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        return requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
    
    def search_jobs_serper(
        self, 
        company: str, 
        job_roles: List[str],
        region: str = "in", 
        language: str = "en"
    ) -> List[Dict]:
        """Search for jobs using Serper API with recent filter and multiple roles"""
        all_results = []
        seen_links = set()
        
        # Get date filter for last 15 days
        date_filter = Config.get_date_filter_query()
        
        # Search for each job role
        for job_role in job_roles:
            queries = [
                f"{company} {job_role} jobs India {date_filter}",
                f"{company} {job_role} opening India site:naukri.com",
                f"{company} {job_role} jobs India site:linkedin.com/jobs",
                f"{company} careers {job_role} India"
            ]
            
            for query in queries:
                payload = {
                    "q": query,
                    "num": Config.MAX_RESULTS_PER_QUERY,
                    "gl": region,
                    "hl": language,
                    "location": "India"
                }
                
                try:
                    response = self._make_serper_request(payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if 'organic' in data:
                            for result in data['organic'][:3]:
                                link = result.get('link', '')
                                
                                # Avoid duplicates and validate URL
                                if link and link not in seen_links and Config.is_valid_job_url(link):
                                    seen_links.add(link)
                                    job_id = Config.extract_job_id(link)
                                    result['job_id'] = job_id
                                    result['search_role'] = job_role
                                    all_results.append(result)
                        
                except Exception as e:
                    continue
        
        return all_results
    
    def analyze_job_match(
        self, 
        job_title: str, 
        job_snippet: str, 
        job_url: str, 
        resume: str, 
        user_experience: int = 0,
        target_roles: List[str] = []
    ) -> Dict:
        """Use OpenAI to analyze job match with resume and experience"""
        max_resume_length = 1500
        truncated_resume = resume[:max_resume_length]
        
        min_exp, max_exp = Config.extract_experience_years(job_snippet + " " + job_title)
        
        roles_str = ", ".join(target_roles)
        
        prompt = f"""
Analyze this job against the candidate's profile. Be concise and return valid JSON only.

Target Roles: {roles_str}
Job Title: {job_title}
Job Description: {job_snippet}
Job URL: {job_url}

Candidate Experience: {user_experience} years
Resume (excerpt): {truncated_resume}

Analyze:
1. Match score (0-100) - how well candidate fits this role
2. Matching skills from resume
3. Missing skills needed
4. Required experience level
5. Experience match
6. Location verification (must be India)
7. Recommendation (Apply/Consider/Skip)

Return JSON:
{{
    "match_score": 75,
    "matching_skills": ["Python", "AI"],
    "missing_skills": ["Docker"],
    "required_experience": "2-5 years",
    "experience_match": true,
    "location_india": true,
    "recommendation": "Apply"
}}
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a job matching expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400
            )
            
            result_text = response.choices[0].message.content.strip()
            result_text = result_text.strip('`').strip()
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()
            
            result = json.loads(result_text)
            
            if 'required_experience' not in result or not result['required_experience']:
                if min_exp > 0 or max_exp > 0:
                    result['required_experience'] = f"{min_exp}-{max_exp} years"
                else:
                    result['required_experience'] = "Not specified"
            
            if 'experience_match' not in result:
                result['experience_match'] = user_experience >= min_exp
            
            if 'location_india' not in result:
                result['location_india'] = Config.is_indian_location(job_snippet)
            
            required_fields = ["match_score", "matching_skills", "missing_skills", "recommendation"]
            for field in required_fields:
                if field not in result:
                    result[field] = 50 if field == "match_score" else ([] if "skills" in field else "Review")
            
            return result
            
        except Exception as e:
            return {
                "match_score": 50,
                "matching_skills": [],
                "missing_skills": [],
                "required_experience": f"{min_exp}-{max_exp} years" if min_exp > 0 else "Not specified",
                "experience_match": user_experience >= min_exp,
                "location_india": Config.is_indian_location(job_snippet),
                "recommendation": "Review",
                "error": str(e)
            }
    
    def search_all_companies(
    self, 
    companies: List[str],
    job_roles: List[str],
    user_experience: int = 0, 
    region: str = "in", 
    language: str = "en"
    ) -> Dict:
        """Search jobs across companies with experience-based validation"""
        all_jobs = []
        resume = self.db.get_full_resume()
    
        if not resume:
            st.error("❌ No resume found! Please upload your resume first.")
            return {"jobs": [], "validation_report": ""}
        
        if not companies:
            st.error("❌ No companies provided!")
            return {"jobs": [], "validation_report": ""}
        
        if not job_roles:
            st.error("❌ No job roles provided!")
            return {"jobs": [], "validation_report": ""}
        
        st.info(f"📄 Resume: ✓ | 👤 Experience: {user_experience} yrs | 🏢 Companies: {len(companies)} | 💼 Roles: {len(job_roles)}")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        company_job_count = {}
        
        try:
            for idx, company in enumerate(companies):
                status_text.text(f"🔍 Searching {company} for {len(job_roles)} role(s)... ({idx+1}/{len(companies)})")
                
                jobs = self.search_jobs_serper(company, job_roles, region, language)
                company_job_count[company] = len(jobs)
                
                for job in jobs:
                    job_info = {
                        "company": company,
                        "job_id": job.get('job_id', 'N/A'),
                        "title": job.get('title', 'N/A'),
                        "link": job.get('link', 'N/A'),
                        "snippet": job.get('snippet', 'N/A'),
                        "search_role": job.get('search_role', '')
                    }
                    
                    match_analysis = self.analyze_job_match(
                        job.get('title', ''),
                        job.get('snippet', ''),
                        job.get('link', ''),
                        resume,
                        user_experience,
                        job_roles
                    )
                    job_info['match_analysis'] = match_analysis
                    
                    all_jobs.append(job_info)
                
                progress_bar.progress((idx + 1) / len(companies))
        
        except Exception as e:
            st.error(f"❌ Error during search: {str(e)}")
            status_text.text(f"⚠️ Search interrupted")
        
        status_text.text("✅ Search complete! Now validating with experience filter...")
        
        # Validation phase with user experience
        original_count = len(all_jobs)
        
        with st.spinner(f"🔍 Validation Agent filtering for {user_experience} years experience..."):
            validated_jobs = self.validator.validate_job_batch(all_jobs, job_roles, user_experience)  # Pass user_experience
        
        filtered_count = original_count - len(validated_jobs)
        
        # Generate validation report with experience info
        filtering_reasons = {
            "Invalid URL": sum(1 for j in all_jobs if not Config.is_valid_job_url(j.get('link', ''))),
            "Not India Location": sum(1 for j in all_jobs if not j.get('match_analysis', {}).get('location_india', True)),
            "Experience Mismatch": sum(1 for j in all_jobs if not j.get('match_analysis', {}).get('experience_match', False)),
            "Low Confidence": sum(1 for j in all_jobs if j.get('validation', {}).get('confidence_score', 100) < 60),
            "Doesn't Match Role": filtered_count
        }
        
        validation_report = self.validator.generate_validation_report(
            original_count, 
            len(validated_jobs), 
            filtering_reasons,
            user_experience  # Pass user_experience
        )
        
        status_text.text(f"✅ Validation complete! {len(validated_jobs)} jobs match {user_experience} years experience")
        
        # Show company stats
        with st.expander("📊 Search Statistics by Company"):
            for company, count in sorted(company_job_count.items(), key=lambda x: x[1], reverse=True):
                verified = sum(1 for j in validated_jobs if j['company'] == company)
                st.write(f"• **{company}**: {count} found → {verified} verified (experience-matched)")
        
        return {
            "jobs": validated_jobs,
            "validation_report": validation_report,
            "stats": {
                "original_count": original_count,
                "validated_count": len(validated_jobs),
                "filtered_count": filtered_count
            }
        }

    
    def get_recommendations(self, jobs: List[Dict], user_experience: int = 0) -> str:
        """Generate AI recommendations"""
        if not jobs:
            return "No jobs found to analyze."
        
        sorted_jobs = sorted(
            jobs, 
            key=lambda x: x.get('match_analysis', {}).get('match_score', 0), 
            reverse=True
        )[:10]
        
        experience_matched = [j for j in sorted_jobs if j.get('match_analysis', {}).get('experience_match', False)]
        
        jobs_summary = "\n".join([
            f"- {job['company']}: {job['title']} (Score: {job.get('match_analysis', {}).get('match_score', 0)})"
            for job in sorted_jobs[:5]
        ])
        
        prompt = f"""
Career advisor analysis for candidate with {user_experience} years experience.

Top Verified Jobs:
{jobs_summary}

Total verified jobs: {len(jobs)}
Experience matches: {len(experience_matched)}

Provide:
1. **Top 3 Jobs to Apply** (specific reasons)
2. **Key Skills to Highlight**
3. **One Skill to Develop**
4. **Action Plan** for next 2 weeks

Be specific and actionable.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a senior career advisor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating recommendations: {e}"
