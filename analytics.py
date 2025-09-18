import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from functools import lru_cache
import time
import asyncio
import aiohttp
from bs4 import BeautifulSoup

# Cache expensive computations
@lru_cache(maxsize=128)
def _cached_numeric_conversion(series_str):
    """Cache numeric conversions for repeated operations"""
    return pd.to_numeric(series_str, errors='coerce')

@st.cache_data(ttl=600)  # Cache individual results for 10 minutes
def fetch_individual_student_result(base_url, registration_no):
    """Fetch detailed result for a specific student"""
    try:
        import requests
        url = f"{base_url}{registration_no}"
        
        # Create session with timeout
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        
        # Check if valid result page
        if not soup.select_one("#ContentPlaceHolder1_DataList1_RegistrationNoLabel_0"):
            return None
            
        # Extract detailed student information
        student_info = {
            "Registration No.": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_RegistrationNoLabel_0", str(registration_no)),
            "Student Name": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_StudentNameLabel_0"),
            "Father's Name": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_FatherNameLabel_0"),
            "Mother's Name": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_MotherNameLabel_0"),
            "College Name": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_CollegeNameLabel_0"),
            "Branch": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_BranchLabel_0"),
            "Semester": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList1_SemesterLabel_0"),
            "Current SGPA": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList5_GROSSTHEORYTOTALLabel_0"),
            "Current CGPA": _safe_extract_text(soup, "#ContentPlaceHolder1_DataList5_Label1_0")
        }
        
        # Extract semester-wise results from the grid
        semester_results = []
        grid_table = soup.select_one("#ContentPlaceHolder1_GridView3")
        if grid_table:
            rows = grid_table.select("tr")
            if len(rows) >= 2:
                headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
                values = [td.get_text(strip=True) for td in rows[1].find_all("td")]
                
                for header, value in zip(headers, values):
                    if header and value:
                        semester_results.append({
                            "Semester": header,
                            "Grade/SGPA": value
                        })
        
        # Extract subject-wise results if available
        subject_results = []
        subject_table = soup.select_one("#ContentPlaceHolder1_GridView1")
        if subject_table:
            rows = subject_table.select("tr")
            if len(rows) > 1:
                # Get headers
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
                
                # Get data rows
                for row in rows[1:]:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= len(headers):
                        subject_data = {}
                        for i, header in enumerate(headers):
                            if i < len(cells):
                                subject_data[header] = cells[i].get_text(strip=True)
                        if subject_data:
                            subject_results.append(subject_data)
        
        session.close()
        return {
            "student_info": student_info,
            "semester_results": semester_results,
            "subject_results": subject_results
        }
        
    except Exception as e:
        st.error(f"Failed to fetch detailed result: {str(e)}")
        return None

def _safe_extract_text(soup, selector, default="N/A"):
    """Safely extract text from soup with fallback"""
    try:
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else default
    except:
        return default

@st.cache_data(ttl=300)  # Cache for 5 minutes
def process_analytics_data(df_records):
    """Process and cache analytics data for better performance"""
    # Handle both DataFrame records and string input
    if isinstance(df_records, str):
        # If string is passed, we need to reconstruct from the original DataFrame
        return None  # Signal to use direct DataFrame processing
    df = pd.DataFrame(df_records)
    
    # Convert SGPA to numeric once
    df["Current SGPA"] = pd.to_numeric(df["Current SGPA"], errors='coerce')
    
    # Get semester columns
    sem_cols = [col for col in df.columns if col.startswith("Sem ")]
    
    # Pre-calculate performance categories
    def grade_bucket(sgpa):
        if pd.isna(sgpa): return "No Data"
        elif sgpa >= 9: return "Excellent (9.0+)"
        elif sgpa >= 8: return "Very Good (8.0-8.9)"
        elif sgpa >= 7: return "Good (7.0-7.9)"
        elif sgpa >= 6: return "Average (6.0-6.9)"
        else: return "Needs Improvement (<6.0)"

    df["SGPA Category"] = df["Current SGPA"].apply(grade_bucket)
    
    # Pre-calculate semester statistics if available
    sem_stats = None
    if sem_cols:
        sem_df = df[sem_cols].apply(pd.to_numeric, errors="coerce")
        sem_stats = pd.DataFrame({
            'Semester': [col.replace("Sem ", "") for col in sem_cols],
            'Average': sem_df.mean().values,
            'Highest': sem_df.max().values,
            'Lowest': sem_df.min().values,
            'Students': sem_df.count().values
        })
    
    # Pre-calculate top and bottom performers
    top_performers = df.nlargest(10, "Current SGPA")[["Student Name", "Registration No.", "Current SGPA"]]
    bottom_performers = df.nsmallest(10, "Current SGPA")[["Student Name", "Registration No.", "Current SGPA"]]
    
    return {
        'df': df,
        'sem_cols': sem_cols,
        'sem_stats': sem_stats,
        'top_performers': top_performers,
        'bottom_performers': bottom_performers
    }

def show_analytics(df):
    start_time = time.time()
    st.markdown("## 📊 Analytics Summary")
    
    # Convert DataFrame to dict for caching
    df_records = df.to_dict('records')
    
    # Get processed data (cached)
    with st.spinner("⚡ Processing analytics data..."):
        analytics_data = process_analytics_data(df_records)
        
        # If caching failed, process directly
        if analytics_data is None:
            df_work = df.copy()
            # Process data directly without caching
            df_work["Current SGPA"] = pd.to_numeric(df_work["Current SGPA"], errors='coerce')
            
            # Get semester columns
            sem_cols = [col for col in df_work.columns if col.startswith("Sem ")]
            
            # Pre-calculate performance categories
            def grade_bucket(sgpa):
                if pd.isna(sgpa): return "No Data"
                elif sgpa >= 9: return "Excellent (9.0+)"
                elif sgpa >= 8: return "Very Good (8.0-8.9)"
                elif sgpa >= 7: return "Good (7.0-7.9)"
                elif sgpa >= 6: return "Average (6.0-6.9)"
                else: return "Needs Improvement (<6.0)"

            df_work["SGPA Category"] = df_work["Current SGPA"].apply(grade_bucket)
            
            # Pre-calculate semester statistics if available
            sem_stats = None
            if sem_cols:
                sem_df = df_work[sem_cols].apply(pd.to_numeric, errors="coerce")
                sem_stats = pd.DataFrame({
                    'Semester': [col.replace("Sem ", "") for col in sem_cols],
                    'Average': sem_df.mean().values,
                    'Highest': sem_df.max().values,
                    'Lowest': sem_df.min().values,
                    'Students': sem_df.count().values
                })
            
            # Pre-calculate top and bottom performers
            top_performers = df_work.nlargest(10, "Current SGPA")[["Student Name", "Registration No.", "Current SGPA"]]
            bottom_performers = df_work.nsmallest(10, "Current SGPA")[["Student Name", "Registration No.", "Current SGPA"]]
        else:
            df_work = analytics_data['df']
            sem_cols = analytics_data['sem_cols']
            sem_stats = analytics_data['sem_stats']
            top_performers = analytics_data['top_performers']
            bottom_performers = analytics_data['bottom_performers']
    
    # Create tabs for organized analytics
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "📋 Detailed Results", "🎯 Individual Analysis", "📊 Semester Trends"])
    
    with tab1:
        # === 1. Metric Cards ===
        st.subheader("📌 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        # Pre-calculated metrics for speed
        total_students = len(df_work)
        avg_sgpa = df_work["Current SGPA"].mean()
        max_sgpa = df_work["Current SGPA"].max()
        min_sgpa = df_work["Current SGPA"].min()
        
        col1.metric("Total Students", total_students)
        col2.metric("Average SGPA", f"{avg_sgpa:.2f}" if not pd.isna(avg_sgpa) else "N/A")
        col3.metric("Highest SGPA", f"{max_sgpa:.2f}" if not pd.isna(max_sgpa) else "N/A")
        col4.metric("Lowest SGPA", f"{min_sgpa:.2f}" if not pd.isna(min_sgpa) else "N/A")

        # === 2. Enhanced Histogram (optimized) ===
        st.subheader("📈 SGPA Distribution")
        
        # Use numpy for faster histogram calculation
        sgpa_values = df_work["Current SGPA"].dropna()
        if len(sgpa_values) > 0:
            fig1 = px.histogram(
                x=sgpa_values,
                nbins=15,
                title="SGPA Distribution",
                color_discrete_sequence=['#1f77b4']
            )
            fig1.update_layout(
                bargap=0.1,
                xaxis_title="SGPA",
                yaxis_title="Number of Students",
                showlegend=False
            )
            st.plotly_chart(fig1, width='stretch')

        # === 3. Performance Categories Pie Chart (optimized) ===
        st.subheader("📊 Performance Categories")
        category_counts = df_work["SGPA Category"].value_counts()
        
        fig4 = px.pie(
            values=category_counts.values,
            names=category_counts.index,
            title="Result Distribution by Performance Category"
        )
        st.plotly_chart(fig4, width='stretch')

    with tab2:
        # === 4. Detailed Student Results Table (optimized filtering) ===
        st.subheader("📋 Complete Student Results")
        
        # Optimized search and filter
        col1, col2 = st.columns(2)
        with col1:
            search_name = st.text_input("🔍 Search by Student Name", placeholder="Enter student name...", key="analytics_search_name")
        with col2:
            category_filter = st.selectbox(
                "Filter by Performance Category", 
                ["All"] + list(df_work["SGPA Category"].unique()),
                key="analytics_category_filter"
            )
        
        # Efficient filtering using vectorized operations
        filtered_df = df_work.copy()
        
        if search_name:
            mask = df_work["Student Name"].str.contains(search_name, case=False, na=False)
            filtered_df = df_work[mask]
            
        if category_filter != "All":
            filtered_df = filtered_df[filtered_df["SGPA Category"] == category_filter]
        
        st.write(f"Showing {len(filtered_df)} of {len(df_work)} students")
        
        # Optimized display columns
        display_cols = ["Registration No.", "Student Name", "Father's Name", "Current SGPA", "SGPA Category"]
        if sem_cols:
            display_cols.extend(sem_cols[:6])  # Show up to 6 semesters
        
        # Display with optimized configuration
        st.dataframe(
            filtered_df[display_cols],
            width='stretch',
            hide_index=True,
            column_config={
                "Registration No.": st.column_config.TextColumn("Reg No.", width="small"),
                "Student Name": st.column_config.TextColumn("Name", width="medium"),
                "Current SGPA": st.column_config.NumberColumn("Current SGPA", format="%.2f"),
                "SGPA Category": st.column_config.TextColumn("Category", width="medium")
            }
        )

    with tab3:
        # === 5. Individual Student Analysis (optimized) ===
        st.subheader("🎯 Individual Student Performance")
        
        if len(df_work) > 0:
            # Use selectbox with search capability
            student_names = df_work["Student Name"].tolist()
            selected_student = st.selectbox(
                "Select a student for detailed analysis:",
                options=student_names,
                index=0,
                key="analytics_student_selector"
            )
            
            # Efficient student data lookup
            student_data = df_work[df_work["Student Name"] == selected_student].iloc[0]
            reg_no = student_data['Registration No.']
            student_sgpa = pd.to_numeric(student_data['Current SGPA'], errors='coerce')
            
            # Calculate rankings
            df_numeric = df_work.copy()
            df_numeric["Current SGPA"] = pd.to_numeric(df_numeric["Current SGPA"], errors='coerce')
            df_numeric = df_numeric.dropna(subset=["Current SGPA"])
            
            # Overall class rank by CGPA
            df_ranked = df_numeric.sort_values("Current SGPA", ascending=False).reset_index(drop=True)
            df_ranked['Rank'] = df_ranked.index + 1
            student_rank = df_ranked[df_ranked["Student Name"] == selected_student]["Rank"].iloc[0] if len(df_ranked[df_ranked["Student Name"] == selected_student]) > 0 else "N/A"
            total_ranked_students = len(df_ranked)
            
            # Get topper information
            topper_info = df_ranked.iloc[0] if len(df_ranked) > 0 else None
            topper_sgpa = topper_info["Current SGPA"] if topper_info is not None else None
            
            # Calculate percentile
            if student_rank != "N/A" and total_ranked_students > 0:
                percentile = ((total_ranked_students - student_rank + 1) / total_ranked_students) * 100
            else:
                percentile = None
            
            # Create columns for layout
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Basic student information
                st.info(f"""
                **Student Details (From Batch Data):**
                - **Name:** {student_data['Student Name']}
                - **Registration No.:** {student_data['Registration No.']}
                - **Father's Name:** {student_data['Father\'s Name']}
                - **Current SGPA:** {student_data['Current SGPA']}
                - **Performance Category:** {student_data['SGPA Category']}
                """)
                
                # Ranking information
                rank_color = "🥇" if student_rank == 1 else "🥈" if student_rank == 2 else "🥉" if student_rank == 3 else "📊"
                st.success(f"""
                **🏆 Class Ranking Analysis:**
                - **Class Rank:** {rank_color} {student_rank} out of {total_ranked_students}
                - **Percentile:** {percentile:.1f}% if percentile else "N/A"
                - **Above Average:** {"✅ Yes" if student_sgpa and not pd.isna(student_sgpa) and student_sgpa > df_numeric["Current SGPA"].mean() else "❌ No"}
                """)
                
                # Comparison with topper
                if topper_info is not None and student_sgpa and not pd.isna(student_sgpa):
                    sgpa_gap = topper_sgpa - student_sgpa
                    st.warning(f"""
                    **👑 Comparison with Class Topper:**
                    - **Topper:** {topper_info['Student Name']} ({topper_sgpa:.2f} SGPA)
                    - **Your SGPA:** {student_sgpa:.2f}
                    - **Gap:** {sgpa_gap:.2f} points {"🎯" if sgpa_gap <= 0.5 else "📈" if sgpa_gap <= 1.0 else "🚀"}
                    - **Status:** {"🏆 You are the topper!" if sgpa_gap <= 0 else f"📊 {sgpa_gap:.2f} points behind topper"}
                    """)
                
                # Add button to fetch detailed result
                if st.button("🔍 Fetch Detailed Result from Website", key="fetch_detailed_result"):
                    # Get base URL from session state (assuming it's stored there)
                    if 'base_url' in st.session_state:
                        base_url = st.session_state.base_url
                        
                        with st.spinner(f"Fetching detailed result for {selected_student}..."):
                            detailed_result = fetch_individual_student_result(base_url, reg_no)
                            
                            if detailed_result:
                                st.session_state[f'detailed_result_{reg_no}'] = detailed_result
                                st.success("✅ Detailed result fetched successfully!")
                            else:
                                st.error("❌ Failed to fetch detailed result. Please check the registration number.")
                    else:
                        st.warning("⚠️ Base URL not found. Please run a fresh scraping operation first.")

            with col2:
                # Optimized semester progression chart
                if sem_cols:
                    student_sems = []
                    student_grades = []
                    
                    for col in sem_cols:
                        if pd.notna(student_data[col]):
                            try:
                                grade = float(student_data[col])
                                student_sems.append(col.replace("Sem ", ""))
                                student_grades.append(grade)
                            except:
                                continue
                    
                    if student_sems:
                        fig_student = px.line(
                            x=student_sems, 
                            y=student_grades,
                            title=f"{selected_student}'s Semester Progression",
                            markers=True
                        )
                        fig_student.update_layout(
                            xaxis_title="Semester",
                            yaxis_title="Grade",
                            yaxis=dict(range=[0, 10])
                        )
                        st.plotly_chart(fig_student, width='stretch')
            
            # Display detailed result if available
            detailed_result_key = f'detailed_result_{reg_no}'
            if detailed_result_key in st.session_state:
                detailed_result = st.session_state[detailed_result_key]
                
                st.markdown("---")
                st.subheader("📄 Detailed Academic Record")
                
                # Create tabs for different result views
                detail_tab1, detail_tab2, detail_tab3 = st.tabs(["👤 Complete Info", "📊 Semester Wise", "📚 Subject Wise"])
                
                with detail_tab1:
                    st.markdown("### 📋 Complete Student Information")
                    info_df = pd.DataFrame.from_dict(detailed_result['student_info'], orient='index', columns=['Details'])
                    st.dataframe(info_df, width='stretch')
                
                with detail_tab2:
                    if detailed_result['semester_results']:
                        st.markdown("### 📈 Semester-wise Performance")
                        sem_df = pd.DataFrame(detailed_result['semester_results'])
                        st.dataframe(sem_df, width='stretch', hide_index=True)
                        
                        # Create a chart for semester progression
                        if len(sem_df) > 1:
                            # Try to extract numeric grades
                            numeric_grades = []
                            semester_names = []
                            
                            for _, row in sem_df.iterrows():
                                try:
                                    grade_text = str(row['Grade/SGPA'])
                                    # Extract numeric value (handle formats like "8.5", "8.5 (A)", etc.)
                                    import re
                                    numeric_match = re.search(r'(\d+\.?\d*)', grade_text)
                                    if numeric_match:
                                        grade = float(numeric_match.group(1))
                                        if 0 <= grade <= 10:  # Valid SGPA range
                                            numeric_grades.append(grade)
                                            semester_names.append(row['Semester'])
                                except:
                                    continue
                            
                            if numeric_grades:
                                fig_detailed = px.line(
                                    x=semester_names,
                                    y=numeric_grades,
                                    title="Detailed Semester Progression",
                                    markers=True
                                )
                                fig_detailed.update_layout(
                                    xaxis_title="Semester",
                                    yaxis_title="SGPA",
                                    yaxis=dict(range=[0, 10])
                                )
                                st.plotly_chart(fig_detailed, width='stretch')
                    else:
                        st.info("📝 No semester-wise data available in the detailed result.")
                
                with detail_tab3:
                    if detailed_result['subject_results']:
                        st.markdown("### 📚 Subject-wise Performance & Rankings")
                        subject_df = pd.DataFrame(detailed_result['subject_results'])
                        
                        # Display the subject results table
                        st.dataframe(subject_df, width='stretch', hide_index=True)
                        
                        # Subject-wise ranking analysis
                        st.markdown("#### 🏆 Subject-wise Class Position Analysis")
                        
                        # Create tabs for different ranking views
                        rank_tab1, rank_tab2 = st.tabs(["📊 Semester-wise Rankings", "📚 Subject-wise Rankings"])
                        
                        with rank_tab1:
                            # If we have semester data in the batch, try to calculate semester-wise rankings
                            if sem_cols:
                                st.info("📊 **Semester-wise ranking** based on semester SGPA from batch data.")
                                
                                # Create ranking comparison for available semesters
                                ranking_data = []
                                for sem_col in sem_cols:
                                    sem_name = sem_col.replace("Sem ", "Semester ")
                                    sem_data = df_work[[sem_col, "Student Name"]].copy()
                                    sem_data[sem_col] = pd.to_numeric(sem_data[sem_col], errors='coerce')
                                    sem_data = sem_data.dropna(subset=[sem_col])
                                    
                                    if len(sem_data) > 0:
                                        # Rank students for this semester
                                        sem_data_ranked = sem_data.sort_values(sem_col, ascending=False).reset_index(drop=True)
                                        sem_data_ranked['Rank'] = sem_data_ranked.index + 1
                                        
                                        # Find current student's rank
                                        student_sem_data = sem_data_ranked[sem_data_ranked["Student Name"] == selected_student]
                                        if len(student_sem_data) > 0:
                                            student_sem_rank = student_sem_data["Rank"].iloc[0]
                                            student_sem_grade = student_sem_data[sem_col].iloc[0]
                                            
                                            # Get topper for this semester
                                            sem_topper = sem_data_ranked.iloc[0]
                                            topper_sem_grade = sem_topper[sem_col]
                                            
                                            ranking_data.append({
                                                "Semester": sem_name,
                                                "Your Grade": f"{student_sem_grade:.2f}",
                                                "Your Rank": f"{student_sem_rank}/{len(sem_data_ranked)}",
                                                "Topper Grade": f"{topper_sem_grade:.2f}",
                                                "Gap from Topper": f"{topper_sem_grade - student_sem_grade:.2f}",
                                                "Percentile": f"{((len(sem_data_ranked) - student_sem_rank + 1) / len(sem_data_ranked)) * 100:.1f}%"
                                            })
                                
                                if ranking_data:
                                    ranking_df = pd.DataFrame(ranking_data)
                                    st.dataframe(ranking_df, width='stretch', hide_index=True)
                                    
                                    # Create visualization for semester-wise performance comparison
                                    fig_comparison = go.Figure()
                                    
                                    # Add student's grades
                                    student_grades = [float(row["Your Grade"]) for row in ranking_data]
                                    topper_grades = [float(row["Topper Grade"]) for row in ranking_data]
                                    semesters = [row["Semester"] for row in ranking_data]
                                    
                                    fig_comparison.add_trace(go.Scatter(
                                        x=semesters,
                                        y=student_grades,
                                        mode='lines+markers',
                                        name=f'{selected_student}',
                                        line=dict(color='blue', width=3),
                                        marker=dict(size=8)
                                    ))
                                    
                                    fig_comparison.add_trace(go.Scatter(
                                        x=semesters,
                                        y=topper_grades,
                                        mode='lines+markers',
                                        name='Class Topper',
                                        line=dict(color='gold', width=3),
                                        marker=dict(size=8)
                                    ))
                                    
                                    # Add class average
                                    avg_grades = []
                                    for sem_col in sem_cols[:len(ranking_data)]:
                                        sem_avg = pd.to_numeric(df_work[sem_col], errors='coerce').mean()
                                        avg_grades.append(sem_avg)
                                    
                                    fig_comparison.add_trace(go.Scatter(
                                        x=semesters,
                                        y=avg_grades,
                                        mode='lines+markers',
                                        name='Class Average',
                                        line=dict(color='red', width=2, dash='dash'),
                                        marker=dict(size=6)
                                    ))
                                    
                                    fig_comparison.update_layout(
                                        title="Semester-wise Performance Comparison",
                                        xaxis_title="Semester",
                                        yaxis_title="SGPA",
                                        yaxis=dict(range=[0, 10]),
                                        hovermode='x unified'
                                    )
                                    
                                    st.plotly_chart(fig_comparison, width='stretch')
                                else:
                                    st.warning("📝 No semester ranking data available for this student.")
                            else:
                                st.warning("📝 No semester data available for ranking calculation.")
                        
                        with rank_tab2:
                            # True subject-wise ranking from detailed results
                            st.info("📚 **Individual subject rankings** based on detailed scraped results. Click 'Fetch Detailed Result' first to see subject-wise rankings.")
                            
                            # Check if we have detailed results for other students to compare with
                            all_detailed_results = {}
                            for other_student in df_work["Student Name"]:
                                other_reg_no = df_work[df_work["Student Name"] == other_student]["Registration No."].iloc[0]
                                other_detailed_key = f'detailed_result_{other_reg_no}'
                                if other_detailed_key in st.session_state:
                                    all_detailed_results[other_student] = st.session_state[other_detailed_key]
                            
                            if len(all_detailed_results) > 1:
                                st.success(f"📊 Found detailed results for {len(all_detailed_results)} students. Calculating subject-wise rankings...")
                                
                                # Extract subject-wise data for all students
                                subject_ranking_data = {}
                                
                                for student_name, detailed_data in all_detailed_results.items():
                                    if detailed_data and 'subject_results' in detailed_data and detailed_data['subject_results']:
                                        subject_df = pd.DataFrame(detailed_data['subject_results'])
                                        
                                        # Find grade columns
                                        grade_columns = [col for col in subject_df.columns if any(keyword in col.lower() for keyword in ['grade', 'point', 'gp', 'marks'])]
                                        
                                        if grade_columns:
                                            grade_col = grade_columns[0]  # Use first grade column
                                            subject_col = subject_df.columns[0]  # Assume first column is subject name
                                            
                                            for _, row in subject_df.iterrows():
                                                subject_name = row[subject_col]
                                                try:
                                                    grade = float(row[grade_col])
                                                    if subject_name not in subject_ranking_data:
                                                        subject_ranking_data[subject_name] = []
                                                    subject_ranking_data[subject_name].append({
                                                        'Student': student_name,
                                                        'Grade': grade
                                                    })
                                                except:
                                                    continue
                                
                                if subject_ranking_data:
                                    # Calculate rankings for each subject
                                    subject_rankings = {}
                                    current_student_rankings = []
                                    
                                    for subject, students_grades in subject_ranking_data.items():
                                        if len(students_grades) > 1:  # Only rank if multiple students
                                            # Sort by grade descending
                                            sorted_students = sorted(students_grades, key=lambda x: x['Grade'], reverse=True)
                                            
                                            # Assign ranks
                                            for i, student_data in enumerate(sorted_students):
                                                rank = i + 1
                                                if student_data['Student'] == selected_student:
                                                    current_student_rankings.append({
                                                        'Subject': subject,
                                                        'Your Grade': student_data['Grade'],
                                                        'Your Rank': f"{rank}/{len(sorted_students)}",
                                                        'Topper Grade': sorted_students[0]['Grade'],
                                                        'Topper': sorted_students[0]['Student'],
                                                        'Gap': f"{sorted_students[0]['Grade'] - student_data['Grade']:.2f}",
                                                        'Percentile': f"{((len(sorted_students) - rank + 1) / len(sorted_students)) * 100:.1f}%"
                                                    })
                                            
                                            subject_rankings[subject] = sorted_students
                                    
                                    if current_student_rankings:
                                        st.markdown("##### 🏆 Your Subject-wise Rankings")
                                        ranking_df = pd.DataFrame(current_student_rankings)
                                        st.dataframe(ranking_df, width='stretch', hide_index=True)
                                        
                                        # Subject-wise performance visualization
                                        if len(current_student_rankings) > 0:
                                            subjects = [row['Subject'] for row in current_student_rankings]
                                            your_grades = [row['Your Grade'] for row in current_student_rankings]
                                            topper_grades = [row['Topper Grade'] for row in current_student_rankings]
                                            ranks = [int(row['Your Rank'].split('/')[0]) for row in current_student_rankings]
                                            
                                            # Create comparison chart
                                            fig_subject_comparison = go.Figure()
                                            
                                            fig_subject_comparison.add_trace(go.Bar(
                                                name='Your Grade',
                                                x=subjects,
                                                y=your_grades,
                                                marker_color='lightblue',
                                                text=[f'{g:.1f}' for g in your_grades],
                                                textposition='auto',
                                            ))
                                            
                                            fig_subject_comparison.add_trace(go.Bar(
                                                name='Topper Grade',
                                                x=subjects,
                                                y=topper_grades,
                                                marker_color='gold',
                                                text=[f'{g:.1f}' for g in topper_grades],
                                                textposition='auto',
                                            ))
                                            
                                            fig_subject_comparison.update_layout(
                                                title='Subject-wise Grade Comparison (You vs Topper)',
                                                xaxis_title='Subjects',
                                                yaxis_title='Grades',
                                                barmode='group',
                                                xaxis_tickangle=-45
                                            )
                                            
                                            st.plotly_chart(fig_subject_comparison, width='stretch')
                                            
                                            # Ranking visualization
                                            fig_ranks = go.Figure(data=go.Scatter(
                                                x=subjects,
                                                y=ranks,
                                                mode='markers+lines',
                                                marker=dict(
                                                    size=[20 if r == 1 else 15 if r <= 3 else 10 for r in ranks],
                                                    color=['gold' if r == 1 else 'silver' if r == 2 else 'bronze' if r == 3 else 'lightcoral' for r in ranks],
                                                    line=dict(width=2, color='darkblue')
                                                ),
                                                text=[f'Rank {r}' for r in ranks],
                                                textposition='top center'
                                            ))
                                            
                                            fig_ranks.update_layout(
                                                title='Your Subject-wise Rankings',
                                                xaxis_title='Subjects',
                                                yaxis_title='Rank Position',
                                                yaxis=dict(autorange='reversed'),  # Lower rank number = better position
                                                xaxis_tickangle=-45
                                            )
                                            
                                            st.plotly_chart(fig_ranks, width='stretch')
                                            
                                            # Performance summary
                                            st.markdown("##### 📊 Subject-wise Performance Summary")
                                            
                                            rank_1 = sum(1 for r in ranks if r == 1)
                                            rank_top3 = sum(1 for r in ranks if r <= 3)
                                            rank_top50 = sum(1 for r in ranks if r <= len(ranks) * 0.5)
                                            
                                            col1, col2, col3, col4 = st.columns(4)
                                            col1.metric("🥇 First Position", rank_1)
                                            col2.metric("🏆 Top 3 Positions", rank_top3)
                                            col3.metric("📊 Top 50%", rank_top50)
                                            col4.metric("📈 Total Subjects", len(ranks))
                                            
                                            # Best and worst subjects
                                            best_subject_idx = ranks.index(min(ranks))
                                            worst_subject_idx = ranks.index(max(ranks))
                                            
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.success(f"""
                                                **🏅 Best Subject:**
                                                - **Subject:** {subjects[best_subject_idx]}
                                                - **Rank:** {ranks[best_subject_idx]}
                                                - **Grade:** {your_grades[best_subject_idx]:.2f}
                                                """)
                                            
                                            with col2:
                                                st.warning(f"""
                                                **📈 Improvement Area:**
                                                - **Subject:** {subjects[worst_subject_idx]}
                                                - **Rank:** {ranks[worst_subject_idx]}
                                                - **Grade:** {your_grades[worst_subject_idx]:.2f}
                                                - **Gap to Topper:** {topper_grades[worst_subject_idx] - your_grades[worst_subject_idx]:.2f} points
                                                """)
                                    else:
                                        st.warning("📝 No subject ranking data found for the selected student.")
                                else:
                                    st.warning("📝 No comparable subject data found across students.")
                            else:
                                st.warning(f"""
                                📝 **Subject-wise ranking requires detailed results for multiple students.**
                                
                                Currently have detailed results for: {len(all_detailed_results)} student(s)
                                
                                To see subject-wise rankings:
                                1. Select different students and click 'Fetch Detailed Result' for each
                                2. Return to this student to see comparative subject rankings
                                3. Minimum 2 students with detailed results needed for ranking
                                """)
                        
                        # If there are specific subject grades, create detailed analysis
                        st.markdown("#### 📋 Individual Subject Analysis")
                        grade_columns = [col for col in subject_df.columns if any(keyword in col.lower() for keyword in ['grade', 'point', 'gp', 'marks'])]
                        if grade_columns:
                            st.markdown("#### 📋 Individual Subject Analysis")
                            for grade_col in grade_columns[:2]:  # Show up to 2 grade columns
                                try:
                                    # Try to create a bar chart for grades
                                    numeric_grades = pd.to_numeric(subject_df[grade_col], errors='coerce')
                                    if not numeric_grades.isna().all():
                                        valid_data = subject_df[numeric_grades.notna()]
                                        
                                        if len(valid_data) > 0:
                                            # Get subject names (usually first column)
                                            subject_col = subject_df.columns[0]
                                            
                                            # Create enhanced bar chart with color coding
                                            grades = numeric_grades[numeric_grades.notna()]
                                            subjects = valid_data[subject_col]
                                            
                                            # Color code based on performance
                                            colors = ['gold' if g >= 9 else 'lightgreen' if g >= 8 else 'orange' if g >= 7 else 'lightcoral' for g in grades]
                                            
                                            fig_subjects = go.Figure(data=[
                                                go.Bar(
                                                    x=subjects,
                                                    y=grades,
                                                    marker_color=colors,
                                                    text=[f'{g:.1f}' for g in grades],
                                                    textposition='auto',
                                                )
                                            ])
                                            
                                            fig_subjects.update_layout(
                                                title=f"Subject-wise {grade_col} Distribution",
                                                xaxis_title="Subjects",
                                                yaxis_title=grade_col,
                                                xaxis_tickangle=-45,
                                                showlegend=False
                                            )
                                            
                                            st.plotly_chart(fig_subjects, width='stretch')
                                            
                                            # Subject performance summary
                                            if len(grades) > 0:
                                                excellent = sum(1 for g in grades if g >= 9)
                                                good = sum(1 for g in grades if 8 <= g < 9)
                                                average = sum(1 for g in grades if 7 <= g < 8)
                                                poor = sum(1 for g in grades if g < 7)
                                                
                                                col1, col2, col3, col4 = st.columns(4)
                                                col1.metric("🥇 Excellent (9+)", excellent)
                                                col2.metric("🥈 Good (8-9)", good)
                                                col3.metric("🥉 Average (7-8)", average)
                                                col4.metric("📉 Below Average (<7)", poor)
                                            
                                            break
                                except:
                                    continue
                    else:
                        st.info("📝 No subject-wise data available in the detailed result.")
                        
                # Add export option for detailed result
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Export Detailed Result as JSON", key="export_detailed_json"):
                        import json
                        json_str = json.dumps(detailed_result, indent=2, ensure_ascii=False)
                        st.download_button(
                            label="📥 Download JSON",
                            data=json_str,
                            file_name=f"detailed_result_{reg_no}.json",
                            mime="application/json"
                        )
                
                with col2:
                    if st.button("🗑️ Clear Detailed Result", key="clear_detailed_result"):
                        if detailed_result_key in st.session_state:
                            del st.session_state[detailed_result_key]
                            st.rerun()

    with tab4:
        # === 6. Enhanced Semester Trends (pre-calculated) ===
        st.subheader("📉 Semester-wise Analysis")
        
        if sem_stats is not None:
            # Use pre-calculated semester statistics
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=sem_stats['Semester'], 
                y=sem_stats['Average'],
                mode='lines+markers',
                name='Average',
                line=dict(color='blue', width=3)
            ))
            fig_trend.add_trace(go.Scatter(
                x=sem_stats['Semester'], 
                y=sem_stats['Highest'],
                mode='lines+markers',
                name='Highest',
                line=dict(color='green', width=2)
            ))
            fig_trend.add_trace(go.Scatter(
                x=sem_stats['Semester'], 
                y=sem_stats['Lowest'],
                mode='lines+markers',
                name='Lowest',
                line=dict(color='red', width=2)
            ))
            
            fig_trend.update_layout(
                title="Semester-wise Grade Trends",
                xaxis_title="Semester",
                yaxis_title="Grade",
                yaxis=dict(range=[0, 10])
            )
            st.plotly_chart(fig_trend, width='stretch')
            
            # Display pre-calculated semester statistics
            st.subheader("📊 Semester Statistics")
            st.dataframe(
                sem_stats,
                width='stretch',
                hide_index=True,
                column_config={
                    "Average": st.column_config.NumberColumn("Average Grade", format="%.2f"),
                    "Highest": st.column_config.NumberColumn("Highest Grade", format="%.2f"),
                    "Lowest": st.column_config.NumberColumn("Lowest Grade", format="%.2f"),
                    "Students": st.column_config.NumberColumn("Students with Data")
                }
            )

        # === 7. Top and Bottom Performers (pre-calculated) ===
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏅 Top 10 Performers")
            st.dataframe(
                top_performers,
                width='stretch',
                hide_index=True,
                column_config={
                    "Current SGPA": st.column_config.NumberColumn("SGPA", format="%.2f")
                }
            )
        
        with col2:
            st.subheader("📉 Students Needing Support")
            st.dataframe(
                bottom_performers,
                width='stretch',
                hide_index=True,
                column_config={
                    "Current SGPA": st.column_config.NumberColumn("SGPA", format="%.2f")
                }
            )
    
    # Performance indicator
    processing_time = time.time() - start_time
    st.caption(f"⚡ Analytics processed in {processing_time:.2f} seconds")