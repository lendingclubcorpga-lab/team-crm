import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# --- 1. GLOBAL PAGE CONFIGURATION ---
st.set_page_config(page_title="Avant Simple CRM", page_icon="📞", layout="wide")

st.title("📞 Avant Simple CRM Portal")
st.subheader("Instant Customer Search & Direct Database Sync Machine")
st.divider()

EXPECTED_COLUMNS = ["email", "fname", "lname", "dob", "address", "city", "state", "zip", "phone", "bank"]

# --- 2. INITIALIZE GOOGLE SHEETS CONNECTION ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Verify your secrets.toml tracking keys. Details: {e}")
    st.stop()


def clean_cell(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def load_sheet():
    try:
        df = conn.read(worksheet="MASTER FILE ID", ttl=0)
        df = df.dropna(how="all")
    except Exception as e:
        st.warning(f"Starting from an empty table structure because reading failed. Details: {e}")
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].apply(clean_cell)

    df["phone"] = df["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
    return df[EXPECTED_COLUMNS].reset_index(drop=True)


# Cache tracking states in Streamlit memory context
if "crm_data" not in st.session_state:
    st.session_state.crm_data = load_sheet()

# --- 3. CREATE OPERATION WORKFLOW TABS ---
tab_search, tab_upload = st.tabs(["🔍 Search Customer Database", "📤 Bulk Upload & Sync File"])

# ---- TAB 1: INSTANT LOOKUP ROUTINE (BY PHONE OR EMAIL) ----
with tab_search:
    st.markdown("### 🔍 Customer Profile Lookup")
    st.write("Type or paste an email address OR a phone number below to fetch matched records instantly.")
    
    search_query = st.text_input("Enter Phone Number or Email Address Signature", placeholder="e.g. john@example.com or 1234567890").strip()

    if search_query:
        if any(char.isalpha() for char in search_query):
            query_clean = search_query.lower()
            matched_records = st.session_state.crm_data[st.session_state.crm_data["email"].str.strip().str.lower().str.contains(query_clean, na=False)]
        else:
            query_clean = "".join(filter(str.isdigit, search_query))
            matched_records = st.session_state.crm_data[st.session_state.crm_data["phone"].str.contains(query_clean, na=False)] if query_clean else pd.DataFrame()

        if not matched_records.empty:
            st.success(f"🎉 Found {len(matched_records)} matching file records:")
            for index, row in matched_records.iterrows():
                with st.container(border=True):
                    full_name_str = f"{row.get('fname', '')} {row.get('lname', '')}".strip() or "Unknown Client"
                    st.markdown(f"#### 👤 Customer: {full_name_str}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**📧 Email:** {row.get('email') or 'N/A'}")
                        st.markdown(f"**🎂 DOB:** {row.get('dob') or 'N/A'}")
                    with col2:
                        st.markdown(f"**📞 Phone:** {row.get('phone') or 'N/A'}")
                        st.markdown(f"**🏦 Bank:** `{row.get('bank') or 'N/A'}`")
                    with col3:
                        full_address = f"{row.get('address', '')}, {row.get('city', '')}, {row.get('state', '')} {row.get('zip', '')}"
                        st.markdown(f"**📍 Address:**\n{full_address.strip(', ')}")
        else:
            st.warning("⚠️ No consumer listings found matching that query parameter.")

# ---- TAB 2: DIRECT BULK FILE UPLOAD & GOOGLE SHEETS SYNC ----
with tab_upload:
    st.markdown("### 📤 Bulk Import CSV or Excel Data Rows")
    st.write("Uploaded rows are matched against existing records by **email**. Matching profiles will be updated, and fresh entries will be appended to the bottom.")

    # 1. File Uploader sits outside the form logic to process entries in real-time
    uploaded_file = st.file_uploader("Select Spreadsheet File (CSV or XLSX)", type=["csv", "xlsx"], key="file_upload_bucket")

    new_filtered = None

    if uploaded_file is not None:
        new_data = None
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                new_data = pd.read_csv(uploaded_file)
            else:
                new_data = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Failed to read file formatting parameters: {e}")

        if new_data is not None:
            # Map columns instantly
            header_map = {
                "first name": "fname", "firstname": "fname", "last name": "lname", "lastname": "lname",
                "email address": "email", "e-mail": "email", "phone number": "phone", "mobile": "phone",
                "cell": "phone", "date of birth": "dob", "birthdate": "dob", "street address": "address",
                "street": "address", "zip code": "zip", "postal code": "zip", "zipcode": "zip", "bank name": "bank"
            }
            new_data.columns = [header_map.get(str(c).strip().lower(), str(c).strip().lower()) for c in new_data.columns]
            valid_cols = [c for c in new_data.columns if c in EXPECTED_COLUMNS]
            
            if "email" not in valid_cols:
                st.error("❌ Action Aborted: The file requires an 'email' or 'email address' column header to map rows properly.")
            else:
                new_filtered = new_data[valid_cols].copy()
                for col in EXPECTED_COLUMNS:
                    if col not in new_filtered.columns:
                        new_filtered[col] = ""
                for col in EXPECTED_COLUMNS:
                    new_filtered[col] = new_filtered[col].apply(clean_cell)
                new_filtered["phone"] = new_filtered["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
                
                # FIXED: Instantly displays row counts to the administrator on upload file drop
                st.info(f"📂 File verified! Found `{len(new_filtered)}` customer entry rows ready for synchronization.")

    # 2. Form submission wrapper ensures file states do not drop on button click updates
    with st.form("secure_bulk_sync_form", clear_on_submit=False):
        submit_sync = st.form_submit_button("💾 Save and Upload File Directly to Google Sheets", type="primary")

        if submit_sync:
            if new_filtered is not None:
                # Load the current cloud dataset to prevent dirty overrides
                updated_df = load_sheet()
                new_count = 0
                update_count = 0
                
                for _, row in new_filtered.iterrows():
                    email_key = str(row["email"]).strip().lower()
                    if not email_key:
                        continue
                    
                    target_match_series = updated_df["email"].str.strip().str.lower()
                    match_idx = updated_df[target_match_series == email_key].index
                    
                    if not match_idx.empty:
                        for col in EXPECTED_COLUMNS:
                            if row[col]:
                                updated_df.at[match_idx, col] = row[col]
                        update_count += 1
                    else:
                        new_lead_row = {col: row[col] for col in EXPECTED_COLUMNS}
                        updated_df = pd.concat([updated_df, pd.DataFrame([new_lead_row])], ignore_index=True)
                        new_count += 1
                        
                try:
                    clean_final_df = updated_df[EXPECTED_COLUMNS].copy()
                    
                    # Force execution write back to remote server Google Sheet link
                    conn.update(worksheet="MASTER FILE ID", data=clean_final_df)
                    st.session_state.crm_data = clean_final_df
                    st.success(f"🚀 Success! Stored directly to your Google Sheet. Updated {update_count} rows and added {new_count} records.")
                except Exception as sheets_err:
                    st.error(f"❌ Google Sheets Connection Interrupted: Check your access permissions. Details: {sheets_err}")
            else:
                st.warning("⚠️ Choose a valid spreadsheet file template above before clicking the sync button.")
