import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
from fpdf import FPDF
import datetime
from dateutil.relativedelta import relativedelta

# --- 1. GLOBAL PAGE CONFIGURATION ---
st.set_page_config(page_title="Avant Lookup CRM & Loan Portal", page_icon="💰", layout="wide")

st.title("Secure AVANT CRM & Underwriting Portal")
st.subheader("Phone • Email • Instant Loan Underwriting Machine")

EXPECTED_COLUMNS = ["email", "fname", "lname", "dob", "address", "city", "state", "zip", "phone", "bank"]

# ---------------------------------------------------------------------
# 2. Password Gating Interface
# ---------------------------------------------------------------------
st.sidebar.markdown("### System Access Portal")
entered_password = st.sidebar.text_input("Enter Passcode", type="password")

current_role = None
if entered_password and entered_password == st.secrets.get("ADMIN_PASSWORD"):
    current_role = "Admin"
elif entered_password and entered_password == st.secrets.get("TEAM_PASSWORD"):
    current_role = "Team"

if not current_role:
    st.info("← Please enter a valid Team or Admin passcode in the sidebar to unlock the database.")
    st.stop()

st.sidebar.success(f"Access Granted: **{current_role} Mode**")

# ---------------------------------------------------------------------
# 3. Initialize Google Sheets Connection
# ---------------------------------------------------------------------
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Could not initialize the Google Sheets connection. Check your secrets.toml [connections.gsheets] block. Details: {e}")
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
        st.warning(
            f"Could not read the Google Sheet yet (it may be empty, or the worksheet "
            f"name/permissions don't match) — starting from a blank table instead of crashing. "
            f"Details: {e}"
        )
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    for col in EXPECTED_COLUMNS:
        df[col] = df[col].apply(clean_cell)

    df["phone"] = df["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
    return df[EXPECTED_COLUMNS].reset_index(drop=True)


# Keep track of data states securely across session lifecycles
if "crm_data" not in st.session_state:
    st.session_state.crm_data = load_sheet()

# ---------------------------------------------------------------------
# 4. IMPLEMENT OPERATIONAL INTERFACES
# ---------------------------------------------------------------------
if current_role in ["Team", "Admin"]:
    if current_role == "Team":
        tab_crm, tab_loan = st.tabs(["🔍 Customer Detail Lookup", "🚀 Loan Generation Engine"])
    else:
        tab_crm, tab_bulk, tab_manual, tab_manage, tab_loan = st.tabs(
            ["🛠️ Master Directory", "📤 Bulk Upload", "➕ Add One Lead", "🗑️ Manage / Delete", "🚀 Loan Generation Engine"]
        )

    # ---- CORE WORKFLOW: CUSTOMER DETAIL LOOKUP & MASTER DIRECTORY ----
    with tab_crm:
        if current_role == "Team":
            st.write("Type or paste an email address OR phone number below to retrieve matching file details.")
            search_query = st.text_input("Enter Phone Number or Email Address").strip()

            if search_query:
                if any(char.isalpha() for char in search_query):
                    matched_records = st.session_state.crm_data[st.session_state.crm_data["email"].str.contains(search_query, case=False, na=False)]
                else:
                    search_phone = "".join(filter(str.isdigit, search_query))
                    matched_records = st.session_state.crm_data[st.session_state.crm_data["phone"].str.contains(search_phone, na=False)] if search_phone else pd.DataFrame()

                if not matched_records.empty:
                    st.success(f"Found {len(matched_records)} matching record(s):")
                    for index, row in matched_records.iterrows():
                        with st.container(border=True):
                            f_name = row.get('fname', '')
                            l_name = row.get('lname', '')
                            full_name_str = f"{f_name} {l_name}".strip() or "Unknown Client"
                            st.markdown(f"#### 👤 Client: {full_name_str}")

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
                            
                            if st.button(f"⚡ Populate Profile for Underwriting", key=f"pop_{index}"):
                                st.session_state["pre_fname"] = f_name
                                st.session_state["pre_lname"] = l_name
                                st.session_state["pre_email"] = row.get('email', '')
                                st.info("✅ Core data loaded into 'Loan Generation Engine' tab! Switch tabs above to process parameters.")
                else:
                    st.warning("⚠️ No records found matching that phone number or email.")
        else:
            admin_search = st.text_input("Quick Database Filter (Name, Email, or Phone)").strip()
            display_data = st.session_state.crm_data[
                st.session_state.crm_data["fname"].str.contains(admin_search, case=False, na=False) |
                st.session_state.crm_data["lname"].str.contains(admin_search, case=False, na=False) |
                st.session_state.crm_data["email"].str.contains(admin_search, case=False, na=False) |
                st.session_state.crm_data["phone"].str.contains(admin_search, case=False, na=False)
            ] if admin_search else st.session_state.crm_data
            st.dataframe(display_data, use_container_width=True, hide_index=True)

    # ---- ADMINISTRATIVE SUB-TABS ----
    if current_role == "Admin":
        with tab_bulk:
            st.markdown("### 📤 Bulk Import CSV or Excel Dataset")
            st.write("Rows are matched to existing records by **email** — a matching email updates that row, everything else is appended as a new lead.")
            
            with st.form("bulk_upload_sync_form", clear_on_submit=False):
                uploaded_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"], key="crm_bulk_file_uploader")
                submit_sync = st.form_submit_button("💾 Save and Sync Uploaded File to Google Sheets Database", type="primary")

                if submit_sync and uploaded_file is not None:
                    new_data = None
                    try:
                        if uploaded_file.name.lower().endswith(".csv"):
                            new_data = pd.read_csv(uploaded_file)
                        else:
                            new_data = pd.read_excel(uploaded_file)
                    except Exception as e:
                        st.error(f"Could not read that file: {e}")

                    if new_data is not None:
                        header_map = {
                            "first name": "fname", "firstname": "fname", "last name": "lname", "lastname": "lname",
                            "email address": "email", "e-mail": "email", "phone number": "phone", "mobile": "phone",
                            "cell": "phone", "date of birth": "dob", "birthdate": "dob", "street address": "address",
                            "street": "address", "zip code": "zip", "postal code": "zip", "zipcode": "zip", "bank name": "bank"
                        }
                        new_data.columns = [header_map.get(str(c).strip().lower(), str(c).strip().lower()) for c in new_data.columns]
                        valid_cols = [c for c in new_data.columns if c in EXPECTED_COLUMNS]
                        
                        if "email" not in valid_cols:
                            st.error("❌ Upload aborted: The file must contain an 'email' or 'email address' column header.")
                        else:
                            new_filtered = new_data[valid_cols].copy()
                            for col in EXPECTED_COLUMNS:
                                if col not in new_filtered.columns:
                                    new_filtered[col] = ""
                            for col in EXPECTED_COLUMNS:
                                new_filtered[col] = new_filtered[col].apply(clean_cell)
                            new_filtered["phone"] = new_filtered["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
                            
                            # Fresh load from cloud
                            updated_df = load_sheet()
                            new_count = 0
                            update_count = 0
                            
                            # FIXED: Strict lowercase and trailing whitespace cleaning to prevent email mismatches
                            for _, row in new_filtered.iterrows():
                                email_key = str(row["email"]).strip().lower()
