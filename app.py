import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Role-Based CRM", page_icon="🔒", layout="wide")

st.title("Secure Google Sheets CRM")
st.subheader("Zero Local Data Storage • Role Restricted Views")

# 1. Password Gating Interface
st.sidebar.markdown("### System Access Portal")
entered_password = st.sidebar.text_input("Enter Passcode", type="password")

# Establish clear, zero-leak role logic
current_role = None
if entered_password == st.secrets["TEAM_PASSWORD"]:
    current_role = "Team"
elif entered_password == st.secrets["ADMIN_PASSWORD"]:
    current_role = "Admin"

# Exit gracefully if no passcode or wrong passcode is supplied
if not current_role:
    st.info("← Please enter a valid Team or Admin passcode in the sidebar to load the CRM pipeline.")
    st.stop()

st.sidebar.success(f"Access Granted: **{current_role} Mode**")

# 2. Initialize Secure Live Google Sheet Connection
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Read the dataset fresh on every refresh without memory caching
    existing_data = conn.read(worksheet="Sheet1", ttl=0)
    existing_data = existing_data.dropna(how="all")
except Exception:
    # Safe structure fallback if the spreadsheet is completely empty
    existing_data = pd.DataFrame(columns=["Name", "Phone", "Email", "Status", "Notes"])

# Ensure data types match expectations safely
existing_data["Phone"] = existing_data["Phone"].astype(str)

# 3. Handle ROLE ONE: Team View (Read and Fetch Phone Numbers Only)
if current_role == "Team":
    st.markdown("### 📋 Client Phone Registry")
    
    # Text input search bar to look up specific leads
    search_query = st.text_input("Search Contact by Name").strip().lower()
    
    # Filter the layout based on search queries
    if search_query:
        filtered_df = existing_data[existing_data["Name"].astype(str).str.lower().str.contains(search_query)]
    else:
        filtered_df = existing_data

    # Display read-only columns for the general team
    st.dataframe(
        filtered_df[["Name", "Phone", "Email"]], 
        use_container_width=True, 
        hide_index=True
    )

# 4. Handle ROLE TWO: Admin View (Full Read & Append Data Privileges)
elif current_role == "Admin":
    st.markdown("### 🛠️ Administrative Master CRM")
    
    # Display the complete database sheet with interaction notes
    st.dataframe(existing_data, use_container_width=True, hide_index=True)
    
    # Form layout to safely append data straight to the sheet
    st.write("---")
    st.markdown("### Append New Lead Entry")
    
    with st.form(key="admin_crm_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Contact Name")
            phone = st.text_input("Phone Number")
        with col2:
            email = st.text_input("Email Address")
            status = st.selectbox("Pipeline Stage", ["Lead", "Contacted", "Proposal", "Won", "Lost"])
            
        notes = st.text_area("Interaction Notes")
        submit_button = st.form_submit_button(label="Push Updates to Google Cloud")
        
    if submit_button:
        if name and phone:
            # Structuring the new payload row 
            new_lead = pd.DataFrame([{
                "Name": name,
                "Phone": str(phone),
                "Email": email,
                "Status": status,
                "Notes": notes
            }])
            
            # Concat the arrays and push straight up using CRUD Service Account connection
            updated_df = pd.concat([existing_data, new_lead], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            
            st.success(f"Entry for {name} successfully appended onto Google Sheets!")
            st.rerun()
        else:
            st.error("Admin entries require both a Name and a Phone Number.")
