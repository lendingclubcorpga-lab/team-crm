import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Phone Lookup CRM", page_icon="📞", layout="wide")

st.title("Secure Google Sheets CRM")
st.subheader("Zero Local Data Storage • Custom Column Lookup")

# 1. Password Gating Interface
st.sidebar.markdown("### System Access Portal")
entered_password = st.sidebar.text_input("Enter Passcode", type="password")

current_role = None
if entered_password == st.secrets.get("TEAM_PASSWORD"):
    current_role = "Team"
elif entered_password == st.secrets.get("ADMIN_PASSWORD"):
    current_role = "Admin"

# Exit gracefully if no passcode or wrong passcode is supplied
if not current_role:
    st.info("← Please enter a valid Team or Admin passcode in the sidebar to unlock the database.")
    st.stop()

st.sidebar.success(f"Access Granted: **{current_role} Mode**")

# 2. Initialize Secure Live Google Sheet Connection
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Read the dataset fresh from your MASTER FILE ID tab
    existing_data = conn.read(worksheet="MASTER FILE ID", ttl=0)
    existing_data = existing_data.dropna(how="all")
except Exception as e:
    # This will print the exact deep text reason from the Google API
    st.error(f"Google Sheet Connection Error: {str(e)}")
    existing_data = pd.DataFrame(columns=[
        "email", "fname", "lname", "dob", "address", 
        "city", "state", "zip", "phone", "bank"
    ])
# Standardize Phone column format (remove spaces/dashes) for strict matching
existing_data["phone"] = existing_data["phone"].astype(str).str.replace(r"[\s\-\(\)]+", "", regex=True)

# =========================================================================
# 3. Handle ROLE ONE: Team View (Strict Phone Number Detail Lookup)
# =========================================================================
if current_role == "Team":
    st.markdown("### 🔍 Customer Detail Lookup")
    st.write("Type or paste a phone number below to retrieve matching file details.")
    
    # Clean user input to match database phone format
    raw_search = st.text_input("Enter Phone Number (e.g., 1234567890)").strip()
    search_phone = "".join(filter(str.isdigit, raw_search))
    
    if search_phone:
        # Search for phone matches
        matched_records = existing_data[existing_data["phone"].str.contains(search_phone, na=False)]
        
        if not matched_records.empty:
            st.success(f"Found {len(matched_records)} matching record(s):")
            
            # Display each match cleanly in structured data cards
            for index, row in matched_records.iterrows():
                with st.container():
                    # Combine first and last name for header display
                    full_name = f"{row.get('fname', '')} {row.get('lname', '')}".strip() or "Unknown Client"
                    st.markdown(f"#### 👤 Client: {full_name}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**📧 Email:** {row.get('email', 'N/A')}")
                        st.markdown(f"**🎂 DOB:** {row.get('dob', 'N/A')}")
                    with col2:
                        st.markdown(f"**📞 Phone:** {row.get('phone', 'N/A')}")
                        st.markdown(f"**🏦 Bank:** `{row.get('bank', 'N/A')}`")
                    with col3:
                        # Structured address block
                        full_address = f"{row.get('address', '')}, {row.get('city', '')}, {row.get('state', '')} {row.get('zip', '')}"
                        st.markdown(f"**📍 Address:**\n{full_address.strip(', ')}")
                    
                    st.write("---")
        else:
            st.warning("⚠️ No records found matching that phone number.")

# =========================================================================
# 4. Handle ROLE TWO: Admin View (Master CRM Grid & Manual Adding)
# =========================================================================
elif current_role == "Admin":
    st.markdown("### 🛠️ Administrative Master CRM")
    
    # Global search bar for administrative overrides
    admin_search = st.text_input("Quick Database Filter (Name, Email, or Phone)").strip()
    if admin_search:
        display_data = existing_data[
            existing_data["fname"].astype(str).str.contains(admin_search, case=False, na=False) |
            existing_data["lname"].astype(str).str.contains(admin_search, case=False, na=False) |
            existing_data["email"].astype(str).str.contains(admin_search, case=False, na=False) |
            existing_data["phone"].astype(str).str.contains(admin_search, case=False, na=False)
        ]
    else:
        display_data = existing_data

    # Display the complete database sheet with full details
    st.dataframe(display_data, use_container_width=True, hide_index=True)
    
    # Form layout to safely append new records directly to the sheet
    st.write("---")
    st.markdown("### Append New Lead Entry")
    
    with st.form(key="admin_crm_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fname = st.text_input("First Name")
            lname = st.text_input("Last Name")
            email = st.text_input("Email Address")
        with c2:
            phone = st.text_input("Phone Number")
            dob = st.text_input("Date of Birth (MM/DD/YYYY)")
            bank = st.text_input("Financial Institution / Bank")
        with c3:
            address = st.text_input("Street Address")
            city = st.text_input("City")
            state = st.text_input("State")
            zip_code = st.text_input("Zip Code")
            
        submit_button = st.form_submit_button(label="Push Updates to Google Cloud")
        
    if submit_button:
        if fname and phone:
            # Structuring the new payload row exactly to your column header layout
            clean_phone = "".join(filter(str.isdigit, str(phone)))
            new_lead = pd.DataFrame([{
                "email": email.strip(),
                "fname": fname.strip(),
                "lname": lname.strip(),
                "dob": dob.strip(),
                "address": address.strip(),
                "city": city.strip(),
                "state": state.strip(),
                "zip": zip_code.strip(),
                "phone": clean_phone,
                "bank": bank.strip()
            }])
            
            # Merge and upload data back to the MASTER FILE ID tab
            updated_df = pd.concat([existing_data, new_lead], ignore_index=True)
            conn.update(worksheet="MASTER FILE ID", data=updated_df)
            
            st.success(f"Entry for {fname} successfully added to Google Sheets!")
            st.rerun()
        else:
            st.error("Admin entries require at least a First Name and a Phone Number.")
