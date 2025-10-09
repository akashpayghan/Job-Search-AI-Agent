import requests
import json
from openai import OpenAI
from typing import List, Dict
from config import Config
from database import ResumeDatabase
import streamlit as st


class JobSearchAgent:
    """AI Agent for searching and matching jobs"""
    
    def __init__(self, skip_validation=False):
        """
        Initialize the agent
        skip_validation: Set to True to skip API validation (useful for initialization)
        """
        if not skip_validation:
            # Validate API keys
            key_errors = Config.validate_keys()
            if key_errors:
                st.error(f"❌ API Key Error: {', '.join(key_errors)}")
                st.stop()
        
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.serper_api_key = Config.SERPER_API_KEY
        self.db = ResumeDatabase()
        
        # Test API connectivity only if not skipping validation
        if not skip_validation:
            self._test_apis()
    
    def _test_apis(self):
        """Test if APIs are accessible"""
        # Test Serper API
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
        
        # Test OpenAI API
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
    
    def search_jobs_serper(self, company: str, job_title: str = "", region: str = "in", language: str = "en") -> List[Dict]:
        """Search for jobs using Serper API"""
        all_results = []
        seen_links = set()  # Track unique links
        
        # Define search queries
        queries = [
            f"{company} {job_title} jobs careers",
            f"{company} {job_title} openings site:naukri.com",
            f"{company} {job_title} jobs site:linkedin.com",
            f"{company} careers page"
        ]
        
        for query in queries:
            payload = {
                "q": query,
                "num": Config.MAX_RESULTS_PER_QUERY,
                "gl": region,
                "hl": language
            }
            
            try:
                response = self._make_serper_request(payload)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'organic' in data:
                        for result in data['organic'][:3]:  # Top 3 from each query
                            link = result.get('link', '')
                            # Avoid duplicates
                            if link and link not in seen_links:
                                seen_links.add(link)
                                all_results.append(result)
                else:
                    st.warning(f"⚠️ Search failed: Status {response.status_code}")
                    
            except Exception as e:
                st.error(f"❌ Error searching {company}: {str(e)}")
                continue
        
        return all_results
    
    def analyze_job_match(self, job_title: str, job_snippet: str, resume: str) -> Dict:
        """Use OpenAI to analyze job match with resume"""
        max_resume_length = 1500
        truncated_resume = resume[:max_resume_length]
        
        prompt = f"""
Analyze this job against the candidate's resume. Be concise and return valid JSON only.

Job Title: {job_title}
Job Description: {job_snippet}
Resume: {truncated_resume}

Return JSON in this exact format:
{{
    "match_score": 75,
    "matching_skills": ["Python", "AI"],
    "missing_skills": ["Docker"],
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
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Robust markdown code block removal
            result_text = result_text.strip('`').strip()
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()
            
            result = json.loads(result_text)
            
            # Validate required fields
            required_fields = {"match_score", "matching_skills", "missing_skills", "recommendation"}
            if not all(field in result for field in required_fields):
                return {
                    "match_score": 50,
                    "matching_skills": [],
                    "missing_skills": [],
                    "recommendation": "Review"
                }
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                "match_score": 50,
                "matching_skills": [],
                "missing_skills": [],
                "recommendation": "Review",
                "error": f"JSON Parse Error: {str(e)}"
            }
        except Exception as e:
            return {
                "match_score": 0,
                "matching_skills": [],
                "missing_skills": [],
                "recommendation": "Error",
                "error": str(e)
            }
    
    def search_all_companies(self, job_role: str = "AI Engineer", region: str = "in", language: str = "en") -> List[Dict]:
        """Search jobs across all target companies"""
        all_jobs = []
        resume = self.db.get_full_resume()
        
        if not resume:
            st.error("❌ No resume found! Please upload your resume first.")
            return []
        
        st.info(f"📄 Resume loaded: {len(resume)} characters")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            for idx, company in enumerate(Config.TARGET_COMPANIES):
                status_text.text(f"🔍 Searching jobs at {company}... ({idx+1}/{len(Config.TARGET_COMPANIES)})")
                
                jobs = self.search_jobs_serper(company, job_role, region, language)
                
                st.write(f"Found {len(jobs)} results for {company}")
                
                for job in jobs[:2]:  # Top 2 per company
                    job_info = {
                        "company": company,
                        "title": job.get('title', 'N/A'),
                        "link": job.get('link', 'N/A'),
                        "snippet": job.get('snippet', 'N/A')
                    }
                    
                    # Analyze match with OpenAI
                    match_analysis = self.analyze_job_match(
                        job.get('title', ''),
                        job.get('snippet', ''),
                        resume
                    )
                    job_info['match_analysis'] = match_analysis
                    
                    all_jobs.append(job_info)
                
                progress_bar.progress((idx + 1) / len(Config.TARGET_COMPANIES))
        
        except Exception as e:
            st.error(f"❌ Error during company search: {str(e)}")
            status_text.text(f"⚠️ Search interrupted: {str(e)}")
            return all_jobs
        
        status_text.text("✅ Search complete!")
        return all_jobs
    
    def get_recommendations(self, jobs: List[Dict]) -> str:
        """Generate AI recommendations based on job matches"""
        if not jobs:
            return "No jobs found to analyze."
        
        # Sort by match score
        sorted_jobs = sorted(
            jobs, 
            key=lambda x: x.get('match_analysis', {}).get('match_score', 0), 
            reverse=True
        )[:5]
        
        jobs_summary = "\n".join([
            f"- {job['company']}: {job['title']} (Score: {job.get('match_analysis', {}).get('match_score', 0)})"
            for job in sorted_jobs
        ])
        
        prompt = f"""
Based on these top job matches, provide:
1. Top 3 jobs to apply for (with reasons)
2. Key skills to highlight in applications
3. One skill to develop

Top Jobs:
{jobs_summary}

Be concise and actionable.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a career advisor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"❌ Error generating recommendations: {str(e)}")
            return f"Error generating recommendations: {e}"
