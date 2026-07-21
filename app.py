import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

st.set_page_config(page_title="Avant Lookup CRM", page_icon="📞", layout="wide")

st.title("Secure AVANT CRM")
st.subheader("Phone • Custom Column Lookup")

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

    # Guarantee every expected column exists, no matter what came back from the sheet,
    # so nothing downstream throws a KeyError on a missing column.
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Clean every cell so numeric-looking phone/zip columns don't show ".0", and so
    # every value is a plain, safely comparable string.
    for col in EXPECTED_COLUMNS:
        df[col] = df[col].apply(clean_cell)

    df["phone"] = df["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)
    return df[EXPECTED_COLUMNS].reset_index(drop=True)


existing_data = load_sheet()

# ---------------------------------------------------------------------
# 3. TEAM: phone-number lookup only, read-only
# ---------------------------------------------------------------------
if current_role == "Team":
    st.markdown("### 🔍 Customer Detail Lookup")
    st.write("Type or paste a phone number below to retrieve matching file details.")

    raw_search = st.text_input("Enter Phone Number (e.g., 1234567890)").strip()
    search_phone = "".join(filter(str.isdigit, raw_search))

    if search_phone:
        matched_records = existing_data[existing_data["phone"].str.contains(search_phone, na=False)]

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
            st.warning("⚠️ No records found matching that phone number.")

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
            "that row, everything else is appended as a new lead. The result is written "
            "straight back to your Google Sheet, so it stays there permanently until you "
            "delete it yourself in the tab to the right."
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
                # Normalize common header variants so files don't silently import blank
                # columns just because a header says "First Name" instead of "fname".
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

                for col in EXPECTED_COLUMNS:
                    if col not in new_data.columns:
                        new_data[col] = ""
                new_data = new_data[EXPECTED_COLUMNS]

                for col in EXPECTED_COLUMNS:
                    new_data[col] = new_data[col].apply(clean_cell)

                # Pull plain emails back out of markdown-link formatted cells,
                # e.g. "[name@x.com](mailto:name@x.com)" -> "name@x.com"
                extracted = new_data["email"].str.extract(r"([\w\.\-\+]+@[\w\.\-]+\.\w+)", expand=False)
                new_data["email"] = extracted.fillna(new_data["email"])
                new_data["phone"] = new_data["phone"].str.replace(r"[\s\-\(\)]+", "", regex=True)

                st.info(f"Parsed {len(new_data)} row(s) from your file.")
                st.dataframe(new_data, use_container_width=True, hide_index=True)

                if st.button("✅ Commit this file to the Google Sheet"):
                    merged = existing_data.copy()
                    merged["_email_lower"] = merged["email"].str.lower()
                    updated_count = 0
                    appended_count = 0

                    for _, new_row in new_data.iterrows():
                        email_lower = str(new_row["email"]).strip().lower()
                        if not email_lower:
                            continue  # nothing reliable to match/dedupe a blank email against
                        match_idx = merged.index[merged["_email_lower"] == email_lower]
                        if len(match_idx) > 0:
                            for col in EXPECTED_COLUMNS:
                                merged.loc[match_idx, col] = new_row[col]
                            updated_count += 1
                        else:
                            new_row_df = pd.DataFrame([new_row])
                            new_row_df["_email_lower"] = email_lower
                            merged = pd.concat([merged, new_row_df], ignore_index=True)
                            appended_count += 1

                    merged = merged.drop(columns=["_email_lower"])
                    try:
                        conn.update(worksheet="MASTER FILE ID", data=merged)
                        st.cache_data.clear()
                        st.success(f"Committed: {updated_count} record(s) updated, {appended_count} new record(s) added.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not write to the Google Sheet: {e}")

    # ---- Manual single-record add ----
    with tab_manual:
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

            submit_button = st.form_submit_button(label="Push Update to Google Sheet")

        if submit_button:
            if fname and phone:
                clean_phone = "".join(filter(str.isdigit, str(phone)))
                new_lead = pd.DataFrame([{
                    "email": email.strip(), "fname": fname.strip(), "lname": lname.strip(),
                    "dob": dob.strip(), "address": address.strip(), "city": city.strip(),
                    "state": state.strip(), "zip": zip_code.strip(), "phone": clean_phone,
                    "bank": bank.strip(),
                }])
                updated_df = pd.concat([existing_data, new_lead], ignore_index=True)
                try:
                    conn.update(worksheet="MASTER FILE ID", data=updated_df)
                    st.cache_data.clear()
                    st.success(f"Entry for {fname} successfully added to Google Sheets!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not write to the Google Sheet: {e}")
            else:
                st.error("Admin entries require at least a First Name and a Phone Number.")

    # ---- Delete ----
    with tab_manage:
        st.markdown("### 🗑️ Delete records")
        st.write("Records live in your Google Sheet permanently — nothing is removed unless you do it here.")
        del_search = st.text_input("Find records to delete (name, email, or phone)", key="del_search").strip()
        if del_search:
            del_view = existing_data[
                existing_data["fname"].str.contains(del_search, case=False, na=False) |
                existing_data["lname"].str.contains(del_search, case=False, na=False) |
                existing_data["email"].str.contains(del_search, case=False, na=False) |
                existing_data["phone"].str.contains(del_search, case=False, na=False)
            ]
        else:
            del_view = existing_data

        if not del_view.empty:
            del_view = del_view.copy()
            del_view.insert(0, "Delete?", False)
            edited = st.data_editor(
                del_view, hide_index=True, use_container_width=True,
                disabled=EXPECTED_COLUMNS, key="gsheet_delete_editor",
            )
            rows_to_delete = edited[edited["Delete?"]].index.tolist()
            if rows_to_delete:
                st.warning(f"{len(rows_to_delete)} record(s) selected for deletion.")
                if st.button("⚠️ Permanently delete selected record(s) from the Google Sheet"):
                    remaining = existing_data.drop(index=rows_to_delete)
                    try:
                        conn.update(worksheet="MASTER FILE ID", data=remaining)
                        st.cache_data.clear()
                        st.success(f"Deleted {len(rows_to_delete)} record(s).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not write to the Google Sheet: {e}")
        else:
            st.info("No records match.")
