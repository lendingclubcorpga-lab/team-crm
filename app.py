import streamlit as st
import pandas as pd
from sqlalchemy import text
import io

# Page Setup
st.set_page_config(page_title="Managed Corporate CRM", layout="wide", page_icon="🛡️")

# ⚡ CONNECT TO MANAGED STREAMLIT STORAGE
try:
    conn = st.connection("sqlite", type="sql")
except Exception as e:
    st.error(f"Storage Error: Failed to safely initiate backend connection pool. Details: {e}")
    st.stop()

# AUTOMATIC DATABASE INITIALIZATION (Runs once silently on startup)
with conn.session as init_session:
    init_session.execute(text("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'Lead',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    init_session.execute(text("""
        CREATE TABLE IF NOT EXISTS crm_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_extension TEXT NOT NULL,
            file_data BLOB NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    init_session.commit()

# ----------------------------------------------------
# LAYER 1: UNIFIED APP GATEWAY (Single-Password Barrier)
# ----------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["is_admin"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Secure CRM Terminal")
    entered_pass = st.text_input("Enter Corporate CRM Access Password", type="password")
    
    if st.button("Unlock Dashboard"):
        if entered_pass == st.secrets["auth_keys"]["admin_password"]:
            st.session_state["authenticated"] = True
            st.session_state["is_admin"] = True
            st.success("Admin clearance granted.")
            st.rerun()
        elif entered_pass == st.secrets["auth_keys"]["team_password"]:
            st.session_state["authenticated"] = True
            st.session_state["is_admin"] = False
            st.success("Team read-only clearance granted.")
            st.rerun()
        else:
            st.error("Invalid corporate access token. Access Denied.")
    st.stop()

# ----------------------------------------------------
# LAYER 2: AUTHENTICATED CORE DASHBOARD
# ----------------------------------------------------
st.title("🛡️ Secure Corporate CRM Node")
st.caption(f"Access Tier: {'👑 Super Admin (Full Read/Write/Upload)' if st.session_state['is_admin'] else '👥 Team Member (Single Search Mode)'}")

if st.sidebar.button("Logout of Terminal"):
    st.session_state["authenticated"] = False
    st.session_state["is_admin"] = False
    st.rerun()

# ----------------------------------------------------
# BRANCH A: STRICT TEAM WORKFLOW (Search Only, Files Hidden)
# ----------------------------------------------------
if not st.session_state["is_admin"]:
    st.subheader("📞 Customer Contact Pull-Up Terminal")
    search_input = st.text_input("Enter exact phone number or name to extract a profile")
    
    if search_input:
        try:
            query_str = """
                SELECT id, name, email, phone, status 
                FROM clients 
                WHERE name LIKE :param OR email LIKE :param OR phone LIKE :param 
                ORDER BY id DESC;
            """
            data_ledger = conn.query(query_str, params={"param": f"%{search_input}%"}, ttl=0)
            
            if not data_ledger.empty:
                st.success(f"Record Found! Match total: {len(data_ledger)}")
                
                for index, row in data_ledger.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**👤 Customer Name:**  \n{row['name']}")
                        c2.markdown(f"**📞 Phone Number:**  \n{row['phone']}")
                        c3.markdown(f"**✉️ Email Address:**  \n{row['email']}")
            else:
                st.warning("No matching profile exists inside the secure registry.")
        except Exception as ex:
            st.error(f"Search Execution Fault: {ex}")
    else:
        st.info("💡 Ready for use. Enter a phone number above to pull data.")

# ----------------------------------------------------
# BRANCH B: ADMIN WORKFLOW (Full Power Management Ledger)
# ----------------------------------------------------
else:
    tab1, tab2 = st.tabs(["🔍 Global Master Directory", "📦 Cloud Database Storage Ledger"])
    
    with tab1:
        st.subheader("📊 Master Customer Database View")
        admin_search = st.text_input("🔍 Filter Registry (Real-time tracking)")
        
        try:
            if admin_search:
                query_str = "SELECT id, name, email, phone, status, created_at FROM clients WHERE name LIKE :p OR email LIKE :p OR phone LIKE :p ORDER BY id DESC;"
                df_admin = conn.query(query_str, params={"p": f"%{admin_search}%"}, ttl=0)
            else:
                df_admin = conn.query("SELECT id, name, email, phone, status, created_at FROM clients ORDER BY id DESC;", ttl=0)
                
            st.dataframe(df_admin, use_container_width=True, hide_index=True)
        except Exception as ex:
            st.error(f"Admin Directory Error: {ex}")
            
    with tab2:
        st.subheader("🗄️ Streamlit Cloud Permanent Vault")
        st.markdown("#### 🚀 Admin Universal File Uploader")
        uploaded_file = st.file_uploader("Upload spreadsheet registry or backup file (Supports CSV, XLSX, PDF, etc.)")
        
        if uploaded_file is not None:
            file_name = uploaded_file.name
            file_extension = file_name.split(".")[-1].lower() if "." in file_name else "unknown"
            binary_payload = uploaded_file.read()
            
            st.warning(f"File Target Locked: {file_name} ({len(binary_payload)} bytes staging buffer)")
            
            is_spreadsheet = file_extension in ["csv", "xlsx"]
            df_to_import = None
            
            if is_spreadsheet:
                try:
                    uploaded_file.seek(0)
                    if file_extension == "csv":
                        df_to_import = pd.read_csv(uploaded_file)
                    else:
                        df_to_import = pd.read_excel(uploaded_file)
                    st.info(f"📊 Spreadsheet parsed successfully! Detected {len(df_to_import)} rows.")
                except Exception as parse_err:
                    st.error(f"Could not parse spreadsheet text: {parse_err}")
            
            if st.button("Commit File & Process Registry Matrix"):
                try:
                    with conn.session as session:
                        # Step A: Save raw backup file data
                        session.execute(text("INSERT INTO crm_files (file_name, file_extension, file_data) VALUES (:name, :ext, :data);"), {
                            "name": file_name, "ext": file_extension, "data": binary_payload
                        })
                        
                        # Step B: Merge columns and write to searchable client roster
                        rows_inserted = 0
                        if df_to_import is not None:
                            for _, row in df_to_import.iterrows():
                                if 'fname' in df_to_import.columns or 'lname' in df_to_import.columns:
                                    f_part = str(row.get('fname', '')).strip() if pd.notna(row.get('fname')) else ''
                                    l_part = str(row.get('lname', '')).strip() if pd.notna(row.get('lname')) else ''
                                    r_name = f"{f_part} {l_part}".strip()
                                else:
                                    r_name = str(row.get('name', '')).strip()
                                
                                r_email = str(row.get('email', '')).strip()
                                r_phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
                                r_status = str(row.get('status', 'Lead')).strip()
                                
                                if not r_name or not r_email:
                                    continue
                                    
                                session.execute(text("""
                                    INSERT INTO clients (name, email, phone, status) VALUES (:name, :email, :phone, :status)
                                    ON CONFLICT(email) DO UPDATE SET name=excluded.name, phone=excluded.phone, status=excluded.status;
                                """), {"name": r_name, "email": r_email, "phone": r_phone, "status": r_status})
                                rows_inserted += 1
                        session.commit()
                        
                    st.success("✅ File logged permanently and metrics unpacked successfully!")
                    st.rerun()
                except Exception as db_err:
                    st.error(f"Write Failure: {db_err}")

        # View uploaded file table records (Only accessible inside admin dashboard)
        st.markdown("---")
        st.subheader("🗃️ Permanently Saved Files Registry")
        try:
            saved_files_df = conn.query("SELECT id, file_name, file_extension, uploaded_at FROM crm_files ORDER BY id DESC;", ttl=0)
            if not saved_files_df.empty:
                st.dataframe(saved_files_df, use_container_width=True, hide_index=True)
            else:
                st.info("No raw external attachments are currently stored inside the database.")
        except Exception as read_err:
            st.error(f"Could not load file transaction logs: {read_err}")
