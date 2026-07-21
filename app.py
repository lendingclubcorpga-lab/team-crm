import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.title("Secure Google Sheets CRM")
st.subheader("Zero Local Data Storage")

# Initialize the secure connection using the correct GSheets driver
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch current CRM data safely (replaces the broken conn.session block)
try:
    existing_data = conn.read(worksheet="Sheet1", ttl=0)
    existing_data = existing_data.dropna(how="all")
except Exception:
    existing_data = pd.DataFrame(columns=["Name", "Email", "Status", "Notes"])

# Display current pipeline
st.dataframe(existing_data, use_container_width=True)

# Form to submit new leads straight to the cloud
st.write("---")
st.markdown("### Add New Lead")

with st.form(key="crm_form", clear_on_submit=True):
    name = st.text_input("Contact Name")
    email = st.text_input("Email Address")
    status = st.selectbox("Pipeline Stage", ["Lead", "Contacted", "Proposal", "Won", "Lost"])
    notes = st.text_area("Interaction Notes")
    
    submit_button = st.form_submit_button(label="Submit to Google Sheets")

if submit_button:
    if name and email:
        new_lead = pd.DataFrame([{
            "Name": name,
            "Email": email,
            "Status": status,
            "Notes": notes
        }])
        
        # Merge and update live onto the Google Sheet
        updated_df = pd.concat([existing_data, new_lead], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
        
        st.success(f"Successfully pushed {name} to Google Sheets!")
        st.rerun()
    else:
        st.error("Name and Email fields are required.")
