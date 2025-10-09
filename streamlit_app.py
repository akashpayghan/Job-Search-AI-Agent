import streamlit as st
import pandas as pd
import os
from agent import JobSearchAgent
from database import ResumeDatabase
from config import Config

# Page config
st.set_page_config(
    page_title="AI Job Search Agent",
    page_icon="🤖",
    layout="wide"
)

# Title
st.title("🤖 AI Job Search Agent")
st.markdown("Automatically search and match jobs from top companies")

# Initialize database in session state FIRST
if 'db' not in st.session_state:
    st.session_state.db = ResumeDatabase()
    st.session_state.resume_uploaded = False

# Sidebar for API Keys and Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Keys Section
    st.subheader("🔑 API Keys")
    
    openai_key = st.text_input(
        "OpenAI API Key", 
        value=Config.OPENAI_API_KEY,
        type="password",
        help="Get your key from platform.openai.com"
    )
    
    serper_key = st.text_input(
        "Serper API Key", 
        value=Config.SERPER_API_KEY,
        type="password",
        help="Get your key from serper.dev"
    )
    
    # Update config with entered keys
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key
        Config.OPENAI_API_KEY = openai_key
    
    if serper_key:
        os.environ["SERPER_API_KEY"] = serper_key
        Config.SERPER_API_KEY = serper_key
    
    # Validate API keys
    key_errors = Config.validate_keys()
    if key_errors:
        st.error("⚠️ Please enter both API keys to continue")
        for error in key_errors:
            st.warning(f"• {error}")
        st.stop()
    else:
        st.success("✅ API Keys configured")
    
    st.divider()
    
    # Upload Resume
    st.subheader("📋 Upload Resume")
    
    # Check if resume already exists
    resume_exists = st.session_state.db.check_resume_exists()
    
    if resume_exists:
        st.success("✅ Resume already uploaded")
        if st.button("🗑️ Delete and Re-upload"):
            st.session_state.db.delete_resume()
            st.session_state.resume_uploaded = False
            st.rerun()
    
    uploaded_file = st.file_uploader("Upload PDF Resume", type=['pdf'])
    
    if uploaded_file:
        # Save and process resume
        temp_file_path = "temp_resume.pdf"
        
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            # Extract text
            resume_text = st.session_state.db.extract_text_from_pdf(temp_file_path)
            
            if resume_text and len(resume_text) > 50:
                # Store in ChromaDB
                st.session_state.db.store_resume(resume_text)
                st.session_state.resume_uploaded = True
                
                # Show preview
                with st.expander("📄 Preview Resume"):
                    st.text(resume_text[:800] + "..." if len(resume_text) > 800 else resume_text)
                
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            else:
                st.error("❌ Resume is too short or empty. Please upload a valid resume.")
                st.session_state.resume_uploaded = False
                
        except Exception as e:
            st.error(f"❌ Error processing resume: {e}")
            st.session_state.resume_uploaded = False
    
    # Show current resume status
    if st.session_state.db.check_resume_exists():
        current_resume = st.session_state.db.get_full_resume()
        if current_resume:
            st.info(f"📊 Current resume: {len(current_resume)} characters")
            st.session_state.resume_uploaded = True
    
    st.divider()
    
    # Target Companies
    st.subheader("🎯 Target Companies")
    st.info(f"{len(Config.TARGET_COMPANIES)} companies")
    with st.expander("View Companies"):
        cols = st.columns(2)
        for i, company in enumerate(Config.TARGET_COMPANIES):
            with cols[i % 2]:
                st.write(f"{i+1}. {company}")
    
    st.divider()
    
    # Job Role Input
    job_role = st.text_input("Job Role", "AI Engineer", help="Enter your desired job role")
    
    # Advanced settings
    with st.expander("⚙️ Advanced Settings"):
        region = st.selectbox("Region", ["in", "us", "uk", "ca"], index=0)
        language = st.selectbox("Language", ["en", "hi"], index=0)

# Initialize session state variables
if 'jobs_searched' not in st.session_state:
    st.session_state.jobs_searched = False

# Main content
tab1, tab2, tab3 = st.tabs(["🔍 Search Jobs", "📊 Results", "💡 Recommendations"])

with tab1:
    st.header("Search for Jobs")
    
    # Display search configuration
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Job Role:** {job_role}")
        st.write(f"**Companies:** {len(Config.TARGET_COMPANIES)} tech companies")
    with col2:
        st.write(f"**Platforms:** Naukri, LinkedIn, Indeed, Career Pages")
        st.write(f"**Region:** India")
    
    st.divider()
    
    # Check resume status before search
    resume_ready = st.session_state.db.check_resume_exists()
    
    if not resume_ready:
        st.error("❌ No resume found! Please upload your resume in the sidebar first.")
    else:
        st.success("✅ Resume loaded and ready for matching")
    
    # Start Search Button
    if st.button("🚀 Start Search", type="primary", use_container_width=True, disabled=not resume_ready):
        if not resume_ready:
            st.error("❌ Please upload your resume first!")
        else:
            with st.spinner("🔍 Initializing AI Agent and searching jobs..."):
                try:
                    # Create a new agent instance
                    agent = JobSearchAgent()
                    
                    # Search jobs
                    jobs = agent.search_all_companies(
                        job_role=job_role,
                        region=region if 'region' in locals() else "in",
                        language=language if 'language' in locals() else "en"
                    )
                    
                    st.session_state.jobs = jobs
                    st.session_state.jobs_searched = True
                    
                    if jobs and len(jobs) > 0:
                        st.success(f"✅ Found {len(jobs)} job opportunities!")
                    else:
                        st.warning("⚠️ No jobs found. Try a different role or check your search parameters.")
                        
                except Exception as e:
                    st.error(f"❌ Error during search: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

with tab2:
    st.header("Job Search Results")
    
    if st.session_state.jobs_searched and 'jobs' in st.session_state:
        jobs = st.session_state.jobs
        
        if jobs and len(jobs) > 0:
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                min_score = st.slider("Minimum Match Score", 0, 100, 40)
            with col2:
                sort_by = st.selectbox("Sort By", ["Match Score", "Company", "Title"])
            
            # Convert to DataFrame
            df_data = []
            for job in jobs:
                match_score = job.get('match_analysis', {}).get('match_score', 0)
                if match_score >= min_score:
                    df_data.append({
                        "Company": job['company'],
                        "Title": job['title'],
                        "Match Score": match_score,
                        "Recommendation": job.get('match_analysis', {}).get('recommendation', 'N/A'),
                        "Link": job['link']
                    })
            
            if df_data:
                df = pd.DataFrame(df_data)
                
                # Sort
                if sort_by == "Match Score":
                    df = df.sort_values("Match Score", ascending=False)
                elif sort_by == "Company":
                    df = df.sort_values("Company")
                else:
                    df = df.sort_values("Title")
                
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.subheader(f"📋 Top {min(10, len(df_data))} Job Details")
                
                # Show detailed job cards
                filtered_jobs = [j for j in jobs if j.get('match_analysis', {}).get('match_score', 0) >= min_score]
                filtered_jobs.sort(key=lambda x: x.get('match_analysis', {}).get('match_score', 0), reverse=True)
                
                for idx, job in enumerate(filtered_jobs[:10], 1):
                    with st.expander(f"{idx}. {job['company']} - {job['title']}"):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**🔗 Link:** [{job['link']}]({job['link']})")
                            st.markdown(f"**📝 Description:**")
                            st.write(job['snippet'])
                        
                        with col2:
                            match_data = job.get('match_analysis', {})
                            st.metric("Match Score", f"{match_data.get('match_score', 0)}/100")
                            
                            st.markdown("**✅ Matching Skills:**")
                            for skill in match_data.get('matching_skills', [])[:5]:
                                st.write(f"• {skill}")
                            
                            st.markdown("**📚 Skills to Develop:**")
                            for skill in match_data.get('missing_skills', [])[:3]:
                                st.write(f"• {skill}")
                            
                            st.info(f"💡 {match_data.get('recommendation', 'Review')}")
                
                # Export option
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download Results as CSV",
                    csv,
                    "job_search_results.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.warning(f"No jobs found with match score >= {min_score}. Try lowering the threshold.")
        else:
            st.info("No jobs found. Try adjusting your search parameters or try a different job role.")
    else:
        st.info("👆 Click 'Start Search' in the Search Jobs tab to find opportunities")

with tab3:
    st.header("💡 AI Career Recommendations")
    
    if st.session_state.jobs_searched and 'jobs' in st.session_state and st.session_state.jobs:
        if st.button("🤖 Generate AI Recommendations", use_container_width=True, type="primary"):
            with st.spinner("🧠 Analyzing job matches and generating personalized recommendations..."):
                try:
                    agent = JobSearchAgent(skip_validation=True)
                    recommendations = agent.get_recommendations(st.session_state.jobs)
                    
                    st.markdown("---")
                    st.markdown(recommendations)
                    st.markdown("---")
                    
                except Exception as e:
                    st.error(f"❌ Error generating recommendations: {e}")
    else:
        st.info("🔍 Search for jobs first to get personalized AI recommendations")

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🔑 Powered by OpenAI")
with col2:
    st.caption("🔍 Serper Search API")
with col3:
    st.caption("💾 ChromaDB Vector Storage")
