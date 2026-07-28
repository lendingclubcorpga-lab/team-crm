import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

st.set_page_config(page_title="Avant Lookup CRM", page_icon="📞", layout="wide")

st.title("Secure AVANT CRM")
st.subheader("Phone • Email • Custom Column Lookup")

EXPECTED_COLUMNS = ["email", "fname", "lname", "dob", "address", "city", "state", "zip", "phone", "bank"]

# ---------------------------------------------------------------------
# 1. Password Gating Interface
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
# 2. Initialize Google Sheets connection
# ---------------------------------------------------------------------
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Could not initialize the Google Sheets connection. Check your secrets.toml [connections.gsheets] block. Details: {e}")
    st.stop()


def clean_cell(v):
    """Coerce a cell to a plain, display-friendly string.
    Fixes the classic gsheets/pandas issue where a numeric-looking column
    (phone, zip) gets read back as a float, e.g. 1234567890 -> '1234567890.0'."""
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

    # Guarantee every expected column exists, no matter what came back from the sheet
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Clean every cell so numeric-looking phone/zip columns don't show ".0"
    for col in EXPECTED_COLUMNS:
        df[col] = df[col].apply(clean_cell)

    df["phone"] = df["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
    return df[EXPECTED_COLUMNS].reset_index(drop=True)


# Keep track of data state in memory so user actions refresh instantly
if "crm_data" not in st.session_state:
    st.session_state.crm_data = load_sheet()

existing_data = st.session_state.crm_data

# ---------------------------------------------------------------------
# 3. TEAM: Dual-mode phone & email lookup, read-only
# ---------------------------------------------------------------------
if current_role == "Team":
    st.markdown("### 🔍 Customer Detail Lookup")
    st.write("Type or paste an email address OR phone number below to retrieve matching file details.")

    search_query = st.text_input("Enter Phone Number or Email Address").strip()

    if search_query:
        # Check if the user input contains alphabetical letters (indicates an email lookup)
        if any(char.isalpha() for char in search_query):
            matched_records = existing_data[existing_data["email"].str.contains(search_query, case=False, na=False)]
        else:
            # Phone lookup: strip formatting rules to query bare numbers
            search_phone = "".join(filter(str.isdigit, search_query))
            if search_phone:
                matched_records = existing_data[existing_data["phone"].str.contains(search_phone, na=False)]
            else:
                matched_records = pd.DataFrame()

        # Display match cards
        if not matched_records.empty:
            st.success(f"Found {len(matched_records)} matching record(s):")

            for index, row in matched_records.iterrows():
                with st.container(border=True):
                    full_name = f"{row.get('fname', '')} {row.get('lname', '')}".strip() or "Unknown Client"
                    st.markdown(f"#### 👤 Client: {full_name}")

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

                    st.write("---")
        else:
            st.warning("⚠️ No records found matching that phone number or email.")

# ---------------------------------------------------------------------
# 4. ADMIN: view, bulk upload, manual add, delete
# ---------------------------------------------------------------------
elif current_role == "Admin":
    tab_view, tab_bulk, tab_manual, tab_manage = st.tabs(
        ["🛠️ Master Directory", "📤 Bulk Upload", "➕ Add One Lead", "🗑️ Manage / Delete"]
    )

    # ---- Master directory ----
    with tab_view:
        admin_search = st.text_input("Quick Database Filter (Name, Email, or Phone)").strip()
        if admin_search:
            display_data = existing_data[
                existing_data["fname"].str.contains(admin_search, case=False, na=False) |
                existing_data["lname"].str.contains(admin_search, case=False, na=False) |
                existing_data["email"].str.contains(admin_search, case=False, na=False) |
                existing_data["phone"].str.contains(admin_search, case=False, na=False)
            ]
        else:
            display_data = existing_data
        st.dataframe(display_data, use_container_width=True, hide_index=True)

    # ---- Bulk upload (auto-persists to the Google Sheet, upsert by email) ----
    with tab_bulk:
        st.markdown("### 📤 Bulk import a CSV or Excel file")
        st.write(
            "Rows are matched to existing records by **email** — a matching email updates "
            "that row, everything else is appended as a new lead."
        )
        uploaded_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"])

        if uploaded_file is not None:
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
                    "first name": "fname", "firstname": "fname",
                    "last name": "lname", "lastname": "lname",
                    "email address": "email", "e-mail": "email",
                    "phone number": "phone", "mobile": "phone", "cell": "phone",
                    "date of birth": "dob", "birthdate": "dob",
                    "street address": "address", "street": "address",
                    "zip code": "zip", "postal code": "zip", "zipcode": "zip",
                    "bank name": "bank", "financial institution": "bank",
                }
                new_data.columns = [
                    header_map.get(str(c).strip().lower(), str(c).strip().lower())
                    for c in new_data.columns
                ]

                valid_cols = [c for c in new_data.columns if c in EXPECTED_COLUMNS]
                new_data = new_data[valid_cols]

                for col in EXPECTED_COLUMNS:
                    if col not in new_data.columns:
                        new_data[col] = ""

                for col in EXPECTED_COLUMNS:
                    new_data[col] = new_data[col].apply(clean_cell)
                new_data["phone"] = new_data["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
                new_data = new_data.dropna(subset=["email"])
                new_data = new_data[new_data["email"] != ""]

                if st.button("Process & Save Bulk Upload", type="primary"):
                    master_dict = existing_data.drop_duplicates(subset=["email"]).set_index("email").to_dict(orient="index")
                    updated_count = 0
                    added_count = 0
                    for _, row in new_data.iterrows():
                        email_key = str(row["email"]).strip()
                        row_dict = row.to_dict()
                        if "email" in row_dict:
                            del row_dict["email"]

                        if email_key in master_dict:
                            for col in row_dict:
                                if row_dict[col]:
                                    master_dict[email_key][col] = row_dict[col]
                            updated_count += 1
                        else:
                            master_dict[email_key] = row_dict
                            added_count += 1

                    updated_df = pd.DataFrame.from_dict(master_dict, orient="index").reset_index()
                    updated_df = updated_df.rename(columns={"index": "email"})
                    updated_df = updated_df[EXPECTED_COLUMNS]

                    # Synchronize directly back to the cloud document table
