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

# AUTOMATIC DATABASE INITIALIZATION (Expanded to hold all 10 custom columns)
with conn.session as init_session:
    init_session.execute(text("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fname TEXT DEFAULT '',
            lname TEXT DEFAULT '',
            email TEXT NOT NULL UNIQUE,
            dob TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            zip TEXT DEFAULT '',
            phone TEXT NOT NULL,
            bank TEXT DEFAULT '',
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
# BRANCH A: STRICT TEAM WORKFLOW (Displays All 10 Fields On Match)
# ----------------------------------------------------
if not st.session_state["is_admin"]:
    st.subheader("📞 Customer Contact Pull-Up Terminal")
    search_input = st.text_input("Enter exact phone number, name, or email to extract a profile")
    
    if search_input:
        try:
            query_str = """
                SELECT fname, lname, email, dob, address, city, state, zip, phone, bank, status 
                FROM clients 
                WHERE fname LIKE :param OR lname LIKE :param OR email LIKE :param OR phone LIKE :param 
                ORDER BY id DESC;
            """
            data_ledger = conn.query(query_str, params={"param": f"%{search_input}%"}, ttl=0)
            
            if not data_ledger.empty:
                st.success(f"Record Found! Match total: {len(data_ledger)}")
                
                for index, row in data_ledger.iterrows():
                    with st.container(border=True):
                        st.markdown(f"### 👤 Profile: {row['fname']} {row['lname']}")
                        
                        # Row 1: Core Contact Data
                        col_a, col_b, col_c = st.columns(3)
                        col_a.markdown(f"**📞 Phone Number:**  \n{row['phone']}")
                        col_b.markdown(f"**✉️ Email Address:**  \n{row['email']}")
                        col_c.markdown(f"**📅 Date of Birth:**  \n{row['dob']}")
                        
                        st.markdown("---")
                        
                        # Row 2: Location and Bank Details
                        col_d, col_e, col_f = st.columns(3)
                        col_d.markdown(f"**🏠 Street Address:**  \n{row['address']}")
                        col_e.markdown(f"**🏙️ City/State/Zip:**  \n{row['city']}, {row['state']} {row['zip']}")
                        col_f.markdown(f"**🏦 Bank Node:**  \n{row['bank']}")
            else:
                st.warning("No matching profile exists inside the secure registry.")
        except Exception as ex:
            st.error(f"Search Execution Fault: {ex}")
    else:
        st.info("💡 Ready for use. Enter a contact credential above to pull data.")

# ----------------------------------------------------
# BRANCH B: ADMIN WORKFLOW (Processes All 10 Headers)
# ----------------------------------------------------
else:
    tab1, tab2 = st.tabs(["🔍 Global Master Directory", "📦 Cloud Database Storage Ledger"])
    
    with tab1:
        st.subheader("📊 Master Customer Database View")
        admin_search = st.text_input("🔍 Filter Registry (Real-time tracking)")
        
        try:
            if admin_search:
                query_str = """
                    SELECT id, fname, lname, email, dob, address, city, state, zip, phone, bank, status, created_at 
                    FROM clients 
                    WHERE fname LIKE :p OR lname LIKE :p OR email LIKE :p OR phone LIKE :p 
                    ORDER BY id DESC;
                """
                df_admin = conn.query(query_str, params={"p": f"%{admin_search}%"}, ttl=0)
            else:
                df_admin = conn.query("SELECT id, fname, lname, email, dob, address, city, state, zip, phone, bank, status, created_at FROM clients ORDER BY id DESC;", ttl=0)
                
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
                        # Step A: Save raw file backup blob
                        session.execute(text("INSERT INTO crm_files (file_name, file_extension, file_data) VALUES (:name, :ext, :data);"), {
                            "name": file_name, "ext": file_extension, "data": binary_payload
                        })
                        
                        # Step B: Read and unpack all 10 columns accurately
                        rows_inserted = 0
                        if df_to_import is not None:
                            for _, row in df_to_import.iterrows():
                                r_email = str(row.get('email', '')).strip()
                                r_phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
                                
                                # Skip row if it doesn't have vital credentials
                                if not r_email or not r_phone:
                                    continue
                                
                                # Pull other attributes safely mapping defaults if missing
                                r_fname = str(row.get('fname', '')).strip() if pd.notna(row.get('fname')) else ''
                                r_lname = str(row.get('lname', '')).strip() if pd.notna(row.get('lname')) else ''
                                r_dob = str(row.get('dob', '')).strip() if pd.notna(row.get('dob')) else ''
                                r_address = str(row.get('address', '')).strip() if pd.notna(row.get('address')) else ''
                                r_city = str(row.get('city', '')).strip() if pd.notna(row.get('city')) else ''
                                r_state = str(row.get('state', '')).strip() if pd.notna(row.get('state')) else ''
                                r_zip = str(row.get('zip', '')).strip() if pd.notna(row.get('zip')) else ''
