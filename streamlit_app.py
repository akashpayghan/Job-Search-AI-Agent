import streamlit as st
import pandas as pd
import os
from config import Config

# Page config
st.set_page_config(
    page_title="AI Job Search Agent",
    page_icon="🤖",
    layout="wide"
)

# Title with enhanced description
st.title("🤖 AI Job Search Agent")
st.markdown("**Intelligent job search with AI validation | India jobs only | Posted in last 15 days**")

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
        os.environ["CHROMA_OPENAI_API_KEY"] = openai_key
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

# Initialize database AFTER API keys are set
if 'db' not in st.session_state:
    from database import ResumeDatabase
    st.session_state.db = ResumeDatabase()
    st.session_state.resume_uploaded = False
else:
    if Config.OPENAI_API_KEY:
        st.session_state.db.update_embedding_function()

with st.sidebar:
    st.divider()
    
    # Upload Resume
    st.subheader("📋 Upload Resume")
    
    resume_exists = st.session_state.db.check_resume_exists()
    
    if resume_exists:
        st.success("✅ Resume already uploaded")
        if st.button("🗑️ Delete and Re-upload"):
            st.session_state.db.delete_resume()
            st.session_state.resume_uploaded = False
            st.rerun()
    
    uploaded_file = st.file_uploader("Upload PDF Resume", type=['pdf'])
    
    if uploaded_file:
        temp_file_path = "temp_resume.pdf"
        
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            resume_text = st.session_state.db.extract_text_from_pdf(temp_file_path)
            
            if resume_text and len(resume_text) > 50:
                st.session_state.db.store_resume(resume_text)
                st.session_state.resume_uploaded = True
                
                with st.expander("📄 Preview Resume"):
                    st.text(resume_text[:800] + "..." if len(resume_text) > 800 else resume_text)
                
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            else:
                st.error("❌ Resume is too short or empty.")
                st.session_state.resume_uploaded = False
                
        except Exception as e:
            st.error(f"❌ Error processing resume: {e}")
            st.session_state.resume_uploaded = False
    
    if st.session_state.db.check_resume_exists():
        current_resume = st.session_state.db.get_full_resume()
        if current_resume:
            st.info(f"📊 Resume: {len(current_resume)} characters")
            st.session_state.resume_uploaded = True
    
    st.divider()
    
    # Experience Level Input
    st.subheader("👤 Your Experience")
    user_experience = st.number_input(
        "Years of Experience",
        min_value=0,
        max_value=50,
        value=0,
        step=1,
        help="Enter your total years of professional experience"
    )
    
    if user_experience == 0:
        exp_level = "🌱 Entry Level / Fresher"
    elif user_experience <= 2:
        exp_level = "🌱 Entry Level"
    elif user_experience <= 5:
        exp_level = "🚀 Mid Level"
    elif user_experience <= 10:
        exp_level = "⭐ Senior Level"
    else:
        exp_level = "🏆 Expert Level"
    
    st.info(exp_level)
    
    st.divider()
    
    # Target Companies
    st.subheader("🎯 Target Companies")
    
    company_mode = st.radio(
        "Company Selection",
        ["Use Default List", "Enter Custom Companies"],
        help="Choose default companies or enter your own"
    )
    
    if company_mode == "Use Default List":
        target_companies = Config.DEFAULT_COMPANIES
        st.info(f"✅ Using {len(target_companies)} default companies")
        with st.expander("View Default Companies"):
            cols = st.columns(2)
            for i, company in enumerate(target_companies):
                with cols[i % 2]:
                    st.write(f"{i+1}. {company}")
    else:
        company_input = st.text_area(
            "Enter Company Names",
            placeholder="Google, Microsoft, Amazon, Tesla, Nvidia",
            help="Enter company names separated by commas",
            height=100
        )
        
        if company_input:
            target_companies = Config.parse_comma_separated(company_input)
            st.success(f"✅ {len(target_companies)} companies added")
            
            with st.expander("Your Companies"):
                for i, company in enumerate(target_companies, 1):
                    st.write(f"{i}. {company}")
        else:
            target_companies = []
            st.warning("⚠️ Please enter at least one company name")
    
    st.divider()
    
    # Job Roles Input - NEW: Multiple roles
    st.subheader("💼 Job Roles")
    job_roles_input = st.text_area(
        "Enter Job Roles",
        value="AI Engineer, Machine Learning Engineer",
        placeholder="AI Engineer, Data Scientist, ML Engineer",
        help="Enter multiple job roles separated by commas",
        height=80
    )
    
    if job_roles_input:
        job_roles = Config.parse_comma_separated(job_roles_input)
        st.success(f"✅ Searching for {len(job_roles)} role(s)")
        
        with st.expander("Your Job Roles"):
            for i, role in enumerate(job_roles, 1):
                st.write(f"{i}. {role}")
    else:
        job_roles = []
        st.warning("⚠️ Please enter at least one job role")
    
    st.divider()
    
    # Search Filters
    st.subheader("🔍 Search Filters")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📅 Date Range", f"{Config.DAYS_FILTER} days")
    with col2:
        st.metric("📍 Location", "India Only")
    
    with st.expander("⚙️ Advanced Settings"):
        region = st.selectbox("Search Region", ["in", "us", "uk"], index=0)
        language = st.selectbox("Language", ["en", "hi"], index=0)
        
        st.info(f"🔍 Jobs posted in last {Config.DAYS_FILTER} days will be prioritized")

# Initialize session state
if 'jobs_searched' not in st.session_state:
    st.session_state.jobs_searched = False

# Main content
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Search Jobs", "📊 Results", "✅ Validation Report", "💡 Recommendations"])

with tab1:
    st.header("Search for Jobs")
    
    # Search Configuration Summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Job Roles", len(job_roles) if 'job_roles' in locals() else 0)
    with col2:
        st.metric("Companies", len(target_companies) if 'target_companies' in locals() else 0)
    with col3:
        st.metric("Experience", f"{user_experience} years")
    with col4:
        st.metric("Days Filter", Config.DAYS_FILTER)
    
    st.divider()
    
    # Display search details
    if 'job_roles' in locals() and job_roles:
        st.write("**🎯 Searching for:**")
        st.info(" | ".join(job_roles))
    
    if 'target_companies' in locals() and target_companies:
        st.write(f"**🏢 Target Companies:** {len(target_companies)} companies")
    
    st.write("**📍 Location Filter:** India only")
    st.write("**📅 Date Filter:** Last 15 days")
    st.write("**🔍 Platforms:** Naukri, LinkedIn, Indeed, Glassdoor, Company Career Pages")
    
    st.divider()
    
    # Validation checks
    resume_ready = st.session_state.db.check_resume_exists()
    companies_ready = 'target_companies' in locals() and len(target_companies) > 0
    roles_ready = 'job_roles' in locals() and len(job_roles) > 0
    
    status_cols = st.columns(3)
    with status_cols[0]:
        if resume_ready:
            st.success("✅ Resume Ready")
        else:
            st.error("❌ Upload Resume")
    
    with status_cols[1]:
        if companies_ready:
            st.success(f"✅ {len(target_companies)} Companies")
        else:
            st.error("❌ Add Companies")
    
    with status_cols[2]:
        if roles_ready:
            st.success(f"✅ {len(job_roles)} Roles")
        else:
            st.error("❌ Add Job Roles")
    
    st.divider()
    
    search_ready = resume_ready and companies_ready and roles_ready
    
    if st.button("🚀 Start Intelligent Job Search", type="primary", use_container_width=True, disabled=not search_ready):
        if not search_ready:
            st.error("❌ Please complete all requirements above!")
        else:
            with st.spinner("🤖 AI Agent searching and validating jobs..."):
                try:
                    from agent import JobSearchAgent
                    
                    agent = JobSearchAgent()
                    
                    # Search with validation
                    result = agent.search_all_companies(
                        companies=target_companies,
                        job_roles=job_roles,
                        user_experience=user_experience,
                        region=region,
                        language=language
                    )
                    
                    st.session_state.jobs = result['jobs']
                    st.session_state.validation_report = result['validation_report']
                    st.session_state.stats = result['stats']
                    st.session_state.user_experience = user_experience
                    st.session_state.target_companies = target_companies
                    st.session_state.job_roles = job_roles
                    st.session_state.jobs_searched = True
                    
                    validated_count = len(result['jobs'])
                    original_count = result['stats']['original_count']
                    
                    if validated_count > 0:
                        st.success(f"✅ Found {validated_count} verified jobs (filtered {original_count - validated_count} invalid results)")
                        
                        exp_matched = sum(1 for j in result['jobs'] if j.get('match_analysis', {}).get('experience_match', False))
                        st.info(f"📊 {exp_matched} jobs match your experience level")
                    else:
                        st.warning("⚠️ No verified jobs found. Try different companies or roles.")
                        
                except Exception as e:
                    st.error(f"❌ Error during search: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

with tab2:
    st.header("📊 Verified Job Results")
    
    if st.session_state.jobs_searched and 'jobs' in st.session_state:
        jobs = st.session_state.jobs
        
        if jobs and len(jobs) > 0:
            # Filters
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                min_score = st.slider("Min Match Score", 0, 100, 40)
            with col2:
                experience_filter = st.selectbox(
                    "Experience Match",
                    ["All Jobs", "Matches My Experience", "Below My Level"]
                )
            with col3:
                role_filter = st.selectbox(
                    "Filter by Role",
                    ["All Roles"] + st.session_state.get('job_roles', [])
                )
            with col4:
                sort_by = st.selectbox("Sort By", ["Match Score", "Company", "Title"])
            
            # Apply filters
            filtered_jobs = jobs
            
            if experience_filter == "Matches My Experience":
                filtered_jobs = [j for j in filtered_jobs if j.get('match_analysis', {}).get('experience_match', False)]
            elif experience_filter == "Below My Level":
                filtered_jobs = [j for j in filtered_jobs if not j.get('match_analysis', {}).get('experience_match', False)]
            
            if role_filter != "All Roles":
                filtered_jobs = [j for j in filtered_jobs if role_filter.lower() in j.get('title', '').lower()]
            
            # Convert to DataFrame
            df_data = []
            for job in filtered_jobs:
                match_score = job.get('match_analysis', {}).get('match_score', 0)
                if match_score >= min_score:
                    validation = job.get('validation', {})
                    df_data.append({
                        "Job ID": job.get('job_id', 'N/A'),
                        "Company": job['company'],
                        "Title": job['title'],
                        "Role": job.get('search_role', 'N/A'),
                        "Required Exp": job.get('match_analysis', {}).get('required_experience', 'N/A'),
                        "Match Score": match_score,
                        "Exp Match": "✅" if job.get('match_analysis', {}).get('experience_match', False) else "❌",
                        "Verified": "✅" if validation.get('final_valid', True) else "❌",
                        "Confidence": validation.get('confidence_score', 100),
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
                
                # Summary metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Jobs", len(df_data))
                with col2:
                    avg_score = int(df["Match Score"].mean())
                    st.metric("Avg Match", f"{avg_score}%")
                with col3:
                    exp_matches = df["Exp Match"].value_counts().get("✅", 0)
                    st.metric("Exp Matches", exp_matches)
                with col4:
                    avg_confidence = int(df["Confidence"].mean())
                    st.metric("Avg Confidence", f"{avg_confidence}%")
                with col5:
                    apply_jobs = len([d for d in df_data if d["Recommendation"] == "Apply"])
                    st.metric("Recommended", apply_jobs)
                
                st.divider()
                
                # Display table
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Link": st.column_config.LinkColumn("Apply Link"),
                        "Match Score": st.column_config.ProgressColumn(
                            "Match Score",
                            format="%d%%",
                            min_value=0,
                            max_value=100,
                        ),
                        "Confidence": st.column_config.ProgressColumn(
                            "Confidence",
                            format="%d%%",
                            min_value=0,
                            max_value=100,
                        ),
                    }
                )
                
                st.subheader(f"📋 Detailed Job Information (Top {min(15, len(df_data))})")
                
                # Detailed job cards
                display_jobs = [j for j in filtered_jobs if j.get('match_analysis', {}).get('match_score', 0) >= min_score]
                display_jobs.sort(key=lambda x: x.get('match_analysis', {}).get('match_score', 0), reverse=True)
                
                for idx, job in enumerate(display_jobs[:15], 1):
                    match_data = job.get('match_analysis', {})
                    validation = job.get('validation', {})
                    match_score = match_data.get('match_score', 0)
                    
                    # Color code
                    if match_score >= 80:
                        emoji = "🟢"
                    elif match_score >= 60:
                        emoji = "🟡"
                    else:
                        emoji = "🔴"
                    
                    with st.expander(f"{emoji} {idx}. [{job.get('job_id', 'N/A')}] {job['company']} - {job['title']}"):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.markdown(f"**🆔 Job ID:** `{job.get('job_id', 'N/A')}`")
                            st.markdown(f"**🎯 Role Category:** {job.get('search_role', 'N/A')}")
                            st.markdown(f"**🔗 Apply Link:** [{job['link']}]({job['link']})")
                            
                            # Validation status
                            if validation.get('final_valid', True):
                                st.success(f"✅ Verified (Confidence: {validation.get('confidence_score', 100)}%)")
                            
                            st.markdown(f"**📝 Description:**")
                            st.write(job['snippet'])
                            
                            # AI validation reasoning
                            if validation.get('reasoning'):
                                with st.expander("🤖 AI Validation Reasoning"):
                                    st.info(validation['reasoning'])
                        
                        with col2:
                            st.metric("Match Score", f"{match_score}/100")
                            
                            st.write(f"**📅 Required Experience:**")
                            st.info(match_data.get('required_experience', 'N/A'))
                            
                            exp_match = match_data.get('experience_match', False)
                            location_india = match_data.get('location_india', True)
                            
                            st.write(f"**Experience Match:** {'✅ Yes' if exp_match else '❌ No'}")
                            st.write(f"**India Location:** {'✅ Yes' if location_india else '❌ No'}")
                            
                            st.markdown("**✅ Matching Skills:**")
                            for skill in match_data.get('matching_skills', [])[:5]:
                                st.write(f"• {skill}")
                            
                            st.markdown("**📚 Skills to Develop:**")
                            for skill in match_data.get('missing_skills', [])[:3]:
                                st.write(f"• {skill}")
                            
                            recommendation = match_data.get('recommendation', 'Review')
                            if recommendation == "Apply":
                                st.success(f"💡 {recommendation}")
                            elif recommendation == "Consider":
                                st.info(f"💡 {recommendation}")
                            else:
                                st.warning(f"💡 {recommendation}")
                
                # Export
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download Verified Jobs CSV",
                    csv,
                    f"verified_jobs_{'-'.join(st.session_state.get('job_roles', ['jobs']))}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.warning(f"No jobs found with current filters. Try adjusting minimum score or experience filter.")
        else:
            st.info("No verified jobs found. Try different companies or roles.")
    else:
        st.info("👆 Click 'Start Intelligent Job Search' in the Search Jobs tab")

with tab3:
    st.header("✅ Validation Report")
    
    if st.session_state.jobs_searched and 'validation_report' in st.session_state:
        st.markdown(st.session_state.validation_report)
        
        if 'stats' in st.session_state:
            stats = st.session_state.stats
            
            st.divider()
            st.subheader("📈 Detailed Statistics")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Jobs Found", stats['original_count'])
            with col2:
                st.metric("Jobs Verified", stats['validated_count'], 
                         delta=f"{stats['validated_count']-stats['original_count']}")
            with col3:
                accuracy = (stats['validated_count']/stats['original_count']*100) if stats['original_count'] > 0 else 0
                st.metric("Accuracy Rate", f"{accuracy:.1f}%")
            
            st.divider()
            
            st.info("🤖 **Validation Agent Features:**\n\n"
                   "✅ URL validation for direct job links\n\n"
                   "✅ Location verification (India only)\n\n"
                   "✅ Role matching confirmation\n\n"
                   "✅ AI confidence scoring\n\n"
                   "✅ Recent posting verification (15 days)")
    else:
        st.info("Run a job search to see validation report")

with tab4:
    st.header("💡 AI Career Recommendations")
    
    if st.session_state.jobs_searched and 'jobs' in st.session_state and st.session_state.jobs:
        user_exp = st.session_state.get('user_experience', 0)
        searched_roles = st.session_state.get('job_roles', [])
        
        st.info(f"👤 {user_exp} years experience | 💼 {len(searched_roles)} role(s) | 🏢 {len(st.session_state.jobs)} verified jobs")
        
        if st.button("🤖 Generate Personalized Career Recommendations", use_container_width=True, type="primary"):
            with st.spinner("🧠 AI analyzing your profile and job matches..."):
                try:
                    from agent import JobSearchAgent
                    agent = JobSearchAgent(skip_validation=True)
                    recommendations = agent.get_recommendations(
                        st.session_state.jobs,
                        user_exp
                    )
                    
                    st.markdown("---")
                    st.markdown(recommendations)
                    st.markdown("---")
                    
                    # Insights
                    st.subheader("📊 Career Insights")
                    total_jobs = len(st.session_state.jobs)
                    exp_matched = sum(1 for j in st.session_state.jobs if j.get('match_analysis', {}).get('experience_match', False))
                    high_match = sum(1 for j in st.session_state.jobs if j.get('match_analysis', {}).get('match_score', 0) >= 70)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Verified Jobs", total_jobs)
                    with col2:
                        st.metric("Experience Matches", exp_matched)
                    with col3:
                        st.metric("High Match (70+%)", high_match)
                    
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    else:
        st.info("🔍 Search for jobs first to get AI-powered career recommendations")

# Footer
st.divider()
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.caption("🔑 OpenAI")
with col2:
    st.caption("🔍 Serper API")
with col3:
    st.caption("💾 ChromaDB")
with col4:
    st.caption(f"📍 India Only")
with col5:
    st.caption(f"📅 {Config.DAYS_FILTER} Days")
