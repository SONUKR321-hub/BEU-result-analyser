import streamlit as st
import pandas as pd
from scraper import fetch_all_results
from export_utils import export_to_pdf
from analytics import show_analytics
from PIL import Image
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add background styling
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, 
        rgba(74, 144, 226, 0.1) 0%, 
        rgba(80, 170, 200, 0.1) 25%, 
        rgba(120, 180, 220, 0.1) 50%, 
        rgba(100, 150, 200, 0.1) 75%, 
        rgba(90, 160, 210, 0.1) 100%);
    background-attachment: fixed;
}

.main .block-container {
    background: rgba(255, 255, 255, 0.95);
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-top: 1rem;
    backdrop-filter: blur(10px);
}

/* Custom styling for better readability */
.stSelectbox > div > div {
    background-color: rgba(255, 255, 255, 0.9);
}

.stNumberInput > div > div {
    background-color: rgba(255, 255, 255, 0.9);
}

.stButton > button {
    background: linear-gradient(90deg, #4a90e2, #50aac8);
    color: white;
    border: none;
    border-radius: 5px;
    padding: 0.5rem 1rem;
    font-weight: bold;
    transition: all 0.3s ease;
}

.stButton > button:hover {
    background: linear-gradient(90deg, #357abd, #3d8db3);
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

/* Enhance form appearance */
.stForm {
    background: rgba(255, 255, 255, 0.8);
    padding: 1.5rem;
    border-radius: 10px;
    border: 1px solid rgba(74, 144, 226, 0.3);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* Style metrics and cards */
.metric-container {
    background: rgba(255, 255, 255, 0.9);
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #4a90e2;
}

/* Header styling */
h1, h2, h3 {
    color: #2c3e50;
}
</style>
""", unsafe_allow_html=True)


# Branch and College mappings from tera data
branch_codes = {
    "101": "Civil Engineering (CE)",
    "102": "Mechanical Engineering (ME)",
    "103": "Electrical Engineering (EE)",
    "104": "Electronics & Communication Engineering (ECE)",
    "105": "Computer Science & Engineering (CSE)",
    "106": "Information Technology (IT)",
    "107": "Electronics & Instrumentation Engineering (EIE)",
    "108": "Production Engineering (PE)",
    "109": "Chemical Technology (CT)",
    "110": "Electrical and Electronics Engineering (EEE)",
    "111": "Biotechnology Engineering (BT)",
    "112": "Food Technology (FT)",
    "113": "Agriculture Engineering (AE)",
    "114": "Mining Engineering (ME)",
    "115": "Metallurgical Engineering (MET)"
}

college_codes = {
    "110": "Gaya College of Engineering, Gaya",
    "108": "Bhagalpur College of Engineering, Bhagalpur",
    "107": "Muzaffarpur Institute of Technology, Muzaffarpur",
    "109": "Nalanda College of Engineering, Nalanda",
    "111": "Darbhanga College of Engineering, Darbhanga",
    "113": "Motihari College Of Engineering, Mothihari",
    "117": "Lok Nayak Jai Prakash Institute of Technology, Chhapra",
    "124": "Sershah Engineering College, Sasaram, Rohtas",
    "125": "Rashtrakavi Ramdhari Singh Dinkar College of Engineering, Begusarai",
    "126": "Bakhtiyarpur College of Engineering, Patna",
    "127": "Sitamarhi Institute of Technology, Sitamarhi",
    "128": "B.P. Mandal College of Engineering, Madhepura",
    "129": "Katihar Engineering of College, Katihar",
    "130": "Supaul College of Engineering, Supaul",
    "131": "Purnea College of Engineering, Purnea",
    "132": "Saharsa College of Engineering, Saharsa",
    "133": "Government Engineering College, Jamui",
    "134": "Government Engineering College, Banka",
    "135": "Government Engineering College, Vaishali",
    "141": "Government Engineering College, Nawada",
    "142": "Government Engineering College, Kishanganj",
    "144": "Government Engineering College, Munger",
    "145": "Government Engineering College, Sheohar",
    "146": "Government Engineering College, West Champaran",
    "147": "Government Engineering College, Aurangabad",
    "148": "Government Engineering College, Kaimur",
    "149": "Government Engineering College, Gopalganj",
    "150": "Government Engineering College, Madhubani",
    "151": "Government Engineering College, Siwan",
    "152": "Government Engineering College, Jehanabad",
    "153": "Government Engineering College, Arwal",
    "154": "Government Engineering College, Khagaria",
    "155": "Government Engineering College, Buxar",
    "156": "Government Engineering College, Bhojpur",
    "157": "Government Engineering College, Sheikhpura",
    "158": "Government Engineering College, Lakhisarai",
    "159": "Government Engineering College, Samastipur",
    "165": "Shri Phanishwar Nath Renu Engineering College, Araria",
    "102": "Vidya Vihar Institute of Technology, Purnia",
    "103": "Netaji Subhash Institute of Technology, Patna",
    "106": "Sityog Institute of Technology, Aurangabad",
    "115": "Azmet Institute of Technology, Kishanganj",
    "118": "Buddha Institute of Technology, Gaya",
    "119": "Adwaita Mission Institute of Technology, Banka",
    "121": "Moti Babu Institute of Technology, Forbesganj",
    "122": "Exalt College of Engineering & Technology, Vaishali",
    "123": "Siwan Engineering & Technical Institute, Siwan",
    "136": "Mother's Institute of Technology, Bihta, Patna",
    "139": "R.P. Sharma Institute of Technology, Patna",
    "140": "Maulana Azad College of Engineering & Technology, Patna"
}

# Semester mappings
sem_words = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th",
    5: "5th", 6: "6th", 7: "7th", 8: "8th"
}

sem_romans = {
    1: "I", 2: "II", 3: "III", 4: "IV",
    5: "V", 6: "VI", 7: "VII", 8: "VIII"
}

lateral = {
    "No": False,
    "Yes": True
}

col1, col2 = st.columns([2, 5])

with col1:
    logo = Image.open("beu_logo.jpeg")
    st.image(logo, width=180)

with col2:
    # st.markdown(
    #     "<h1 style='padding-top: 20px;'>BEU RESULT ANALYSER by MITIANS</h1>", 
    #     unsafe_allow_html=True
    # )
    st.markdown(
    "<div style='font-size: 48px; font-weight: bold; padding-top: 20px;'>BEU RESULT ANALYSER by MITIANS</div>",
    unsafe_allow_html=True
    )
    st.markdown(
        """<p style='color: grey; font-size: 16px; margin-top: -10px;'>
        Visualize. Analyze. Automate. — A Data Project by 
        <span style='font-size: 16px;'><b>Sonu Kumar</b> from <b>MIT</b></span>
        </p>""",
        unsafe_allow_html=True
    )



with st.form("result_form"):
    semester = st.selectbox("Semester", options=list(range(1, 9)), format_func=lambda x: f"{x} ({sem_words[x]})")
    batch = st.number_input("Batch Year (Last two digits, e.g. 23 for 2023-27)", min_value=20, max_value=30, value=24)
    # year = st.number_input("Exam Year (e.g. 2024)", min_value=2020, max_value=2030, value=2024)
    
    # Set default to Civil Engineering (101)
    branch_options = list(branch_codes.keys())
    default_branch_index = branch_options.index("101") if "101" in branch_options else 0
    branch = st.selectbox("Branch", options=branch_options, index=default_branch_index, format_func=lambda x: branch_codes[x])
    
    # Set default to MIT Muzaffarpur (107)
    college_options = list(college_codes.keys())
    default_college_index = college_options.index("107") if "107" in college_options else 0
    college = st.selectbox("College", options=college_options, index=default_college_index, format_func=lambda x: college_codes[x])
    
    start_reg = st.number_input("Start Registration No. (Short Reg No.)", min_value=1, max_value=999, value=1)
    end_reg = st.number_input("End Registration No. (Short Reg No.)", min_value=1, max_value=999, value=10)
    is_lateral = st.selectbox("Are You Want to Combine LE Student Results also?", options=list(lateral.keys()))
    view_mode = st.selectbox("View Mode", options=["regno", "cgpa", "semester"], format_func=lambda x: {
        "regno": "Registration No. wise",
        "cgpa": "Sort by CGPA (High to Low)",
        "semester": "Sort by Latest Semester Grade"
    }[x])
    export_format = st.selectbox("Export Format", options=["pdf", "txt", "csv", "xlsx"], format_func=lambda x: x.upper())
    submitted = st.form_submit_button("Fetch Results")

# Initialize session state for storing results
if 'results_data' not in st.session_state:
    st.session_state.results_data = None
if 'fetch_params' not in st.session_state:
    st.session_state.fetch_params = None

if submitted:
    reg_batch = batch
    if start_reg > end_reg:
        st.error("Start Registration No. cannot be greater than End Registration No.")
        st.stop()

    # Store fetch parameters in session state
    st.session_state.fetch_params = {
        'semester': semester,
        'batch': batch,
        'branch': branch,
        'college': college,
        'start_reg': start_reg,
        'end_reg': end_reg,
        'is_lateral': is_lateral,
        'view_mode': view_mode,
        'export_format': export_format
    }

    st.info("Fetching results... This might take some time depending on the range.")
    year = int(2000 + batch + (0.5 * semester))

    start_full_reg_no = f"{reg_batch}{branch}{college}{start_reg:03d}"
    end_full_reg_no = f"{reg_batch}{branch}{college}{end_reg:03d}"

    # ---- START: NEW OPTIMIZED LOGIC ----

    # Define the two possible URL formats
    url_primary = f"https://results.beup.ac.in/ResultsBTech{sem_words[semester]}Sem{year}_B20{batch}Pub.aspx?Sem={sem_romans[semester]}&RegNo="
    url_secondary = f"https://results.beup.ac.in/ResultsBTech{sem_words[semester]}Sem{year}Pub.aspx?Sem={sem_romans[semester]}&RegNo="

    # Define a small test range (up to 5 students)
    test_end_no = min(int(start_full_reg_no) + 4, int(end_full_reg_no))

    # 1. Test the primary URL with the small range first
    # st.info(f"Testing primary URL with registration numbers {start_full_reg_no} to {test_end_no}...")
    test_results = fetch_all_results(url_primary, int(start_full_reg_no), test_end_no)

    # 2. Based on the test, decide which URL to use for the full scrape
    used_url = None  # Track which URL was used successfully
    if test_results:
        # st.success("Primary URL test successful! Fetching all results with this format.")
        # If the test passes, use the primary URL for the full range.
        results = fetch_all_results(url_primary, int(start_full_reg_no), int(end_full_reg_no))
        used_url = url_primary
        if semester > 2 and lateral[is_lateral]:
            le_start_full_reg_no = f"{reg_batch+1}{branch}{college}901"
            le_end_full_reg_no = f"{reg_batch+1}{branch}{college}930"
            le_results = fetch_all_results(url_primary, int(le_start_full_reg_no), int(le_end_full_reg_no))
    else:
        # st.warning("Primary URL test failed. Switching to secondary URL for all results.")
        # If the test fails, use the secondary URL for the full range directly.
        results = fetch_all_results(url_secondary, int(start_full_reg_no), int(end_full_reg_no))
        used_url = url_secondary
        if semester > 2:
            le_start_full_reg_no = f"{reg_batch+1}{branch}{college}901"
            le_end_full_reg_no = f"{reg_batch+1}{branch}{college}930"
            le_results = fetch_all_results(url_secondary, int(le_start_full_reg_no), int(le_end_full_reg_no))
        
    # ---- END: NEW OPTIMIZED LOGIC ----


    if not results:
        st.error("Data Not Found. Both primary and secondary URL formats failed to fetch results. Please verify your inputs and the current URL structure on the university website.")
        st.stop()

    df = pd.DataFrame(results)
    if semester > 2:
        le_df = pd.DataFrame(le_results)
        df = pd.concat([df, le_df], ignore_index=True)

    # Sort data if required
    if view_mode == "cgpa":
        df["Sem Cur. CGPA"] = pd.to_numeric(df["Sem Cur. CGPA"], errors='coerce')
        df = df.sort_values(by="Sem Cur. CGPA", ascending=False)
    elif view_mode == "semester":
        df["Current SGPA"] = pd.to_numeric(df["Current SGPA"], errors="coerce")
        df = df.sort_values(by="Current SGPA", ascending=False)

    # Store results in session state
    st.session_state.results_data = df
    st.session_state.base_url = used_url  # Store the successful URL for individual result fetching
    st.success("Results fetched successfully!")

# Display results if they exist in session state
if st.session_state.results_data is not None:
    df = st.session_state.results_data
    params = st.session_state.fetch_params
    
    # Show current fetch parameters
    with st.expander("📋 Current Fetch Parameters", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Semester:** {params['semester']}")
            st.write(f"**Batch:** {params['batch']}")
            st.write(f"**Branch:** {branch_codes.get(params['branch'], params['branch'])}")
        with col2:
            st.write(f"**College:** {college_codes.get(params['college'], params['college'])}")
            st.write(f"**Registration Range:** {params['start_reg']}-{params['end_reg']}")
        with col3:
            st.write(f"**Lateral Entry:** {params['is_lateral']}")
            st.write(f"**View Mode:** {params['view_mode']}")
        
        # Add a button to clear results and start fresh
        if st.button("🔄 Fetch New Results", type="secondary"):
            st.session_state.results_data = None
            st.session_state.fetch_params = None
            st.rerun()
    
    # Quick summary before detailed view
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Students", len(df))
    with col2:
        avg_sgpa = pd.to_numeric(df["Current SGPA"], errors='coerce').mean()
        st.metric("📈 Average SGPA", f"{avg_sgpa:.2f}" if not pd.isna(avg_sgpa) else "N/A")
    with col3:
        max_sgpa = pd.to_numeric(df["Current SGPA"], errors='coerce').max()
        st.metric("🏆 Highest SGPA", f"{max_sgpa:.2f}" if not pd.isna(max_sgpa) else "N/A")
    with col4:
        pass_students = len(df[pd.to_numeric(df["Current SGPA"], errors='coerce') >= 6.0])
        pass_rate = (pass_students / len(df)) * 100 if len(df) > 0 else 0
        st.metric("✅ Pass Rate", f"{pass_rate:.1f}%")
    
    # Enhanced dataframe display with search functionality
    st.subheader("📋 Student Results")
    search_term = st.text_input("🔍 Search students (by name or registration number):", key="main_search")
    
    display_df = df.copy()
    if search_term:
        mask = (df["Student Name"].str.contains(search_term, case=False, na=False) | 
                df["Registration No."].str.contains(search_term, case=False, na=False))
        display_df = df[mask]
        st.write(f"Found {len(display_df)} of {len(df)} students")
    
    st.dataframe(
        display_df, 
        use_container_width=True,
        column_config={
            "Registration No.": st.column_config.TextColumn("Reg No.", width="small"),
            "Student Name": st.column_config.TextColumn("Name", width="medium"),
            "Current SGPA": st.column_config.NumberColumn("SGPA", format="%.2f"),
        }
    )
    
    # Enhanced analytics
    show_analytics(df)

    # Export options - moved to results section
    st.subheader("📥 Export Results")
    export_format = params['export_format']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📄 Download CSV"):
            export_path = "results.csv"
            df.to_csv(export_path, index=False)
            with open(export_path, "rb") as f:
                st.download_button(label="Download CSV", data=f, file_name=export_path, key="csv_download")
            os.remove(export_path)
    
    with col2:
        if st.button("📊 Download Excel"):
            export_path = "results.xlsx"
            df.to_excel(export_path, index=False, engine="openpyxl")
            with open(export_path, "rb") as f:
                st.download_button(label="Download XLSX", data=f, file_name=export_path, key="xlsx_download")
            os.remove(export_path)
    
    with col3:
        if st.button("📝 Download TXT"):
            export_path = "results.txt"
            df.to_csv(export_path, sep="\t", index=False)
            with open(export_path, "rb") as f:
                st.download_button(label="Download TXT", data=f, file_name=export_path, key="txt_download")
            os.remove(export_path)
    
    with col4:
        if st.button("📋 Download PDF"):
            export_path = "results.pdf"
            export_to_pdf(df, export_path)
            with open(export_path, "rb") as f:
                st.download_button(label="Download PDF", data=f, file_name=export_path, key="pdf_download")
            os.remove(export_path)

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: grey;'>"
        "Made with ❤️ by <b>Sonu Kumar</b><br>"
        "Department of Civil Engineering<br>"
        "Muzaffarpur Institute of Technology (MIT), under BEU Patna"
        "</div>",
        unsafe_allow_html=True
    )


