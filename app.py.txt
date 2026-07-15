import streamlit as st
import pandas as pd
from sqlalchemy import text
import mimetypes

# Page Setup
st.set_page_config(page_title="Secure Corporate CRM", layout="wide", page_icon="🛡️")

# Database Connection Pool Engine
try:
    conn = st.connection("mysql", type="sql")
except Exception as e:
    st.error("Infrastructure Error: Failed to safely initiate backend connection pool.")
    st.stop()

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
        # Match against configured secrets securely
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
st.caption(f"Access Tier: {'👑 Super Admin (Full Read/Write/Upload)' if st.session_state['is_admin'] else '👥 Team Member (Strict Read-Only)'}")

if st.sidebar.button("Logout of Terminal"):
    st.session_state["authenticated"] = False
    st.session_state["is_admin"] = False
    st.rerun()

tab1, tab2 = st.tabs(["🔍 Phone Pull-Up & Records", "📦 Database Storage Ledger"])

# ----------------------------------------------------
# TAB 1: SEARCH & READ-ONLY DATA VIEWER
# ----------------------------------------------------
with tab1:
    st.subheader("📞 Customer Contact Pull-Up Terminal")
    search_input = st.text_input("Search Customer Registry (Query by Name, Email, or Phone Number)")
    
    try:
        if search_input:
            query_str = """
                SELECT id, name, email, phone, status, created_at 
                FROM clients 
                WHERE name LIKE :param OR email LIKE :param OR phone LIKE :param 
                ORDER BY id DESC;
            """
            data_ledger = conn.query(query_str, params={"param": f"%{search_input}%"}, ttl=0)
        else:
            data_ledger = conn.query("SELECT id, name, email, phone, status, created_at FROM clients ORDER BY id DESC;", ttl=0)
            
        if not data_ledger.empty:
            st.dataframe(data_ledger, use_container_width=True, hide_index=True)
            
            # Contextual single profile selector card
            st.markdown("### 📋 Fast Profile Pull-Up Summary")
            selected_id = st.selectbox("Select profile ID to extract exact contact credentials", data_ledger["id"].tolist())
            matched_profile = data_ledger[data_ledger["id"] == selected_id].iloc[0]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Selected Contact Name", str(matched_profile["name"]))
            c2.metric("Extracted Phone Number", str(matched_profile["phone"]))
            c3.metric("Account Status", str(matched_profile["status"]))
        else:
            st.info("No matching records located inside the registry.")
            
    except Exception as ex:
        st.error(f"SQL Read Violation: Could not pull data from Hostinger. Details: {ex}")

# ----------------------------------------------------
# TAB 2: SECURE UPLOAD & SYSTEM ENGINE
# ----------------------------------------------------
with tab2:
    st.subheader("🗄️ Hostinger Binary Object Repository")
    
    # Check authorization layer
    if not st.session_state["is_admin"]:
        st.error("⛔ Access Restriction Notice: Your operational tier does not possess database write permission. File updates are strictly blocked.")
    else:
        st.markdown("#### 🚀 Admin Universal File Uploader")
        # Accept all formats implicitly via absence of restrictive extensions list
        uploaded_file = st.file_uploader("Upload analytical documents or pipelines directly to permanent MySQL storage (Supports CSV, XLSX, PDF, TXT, etc.)")
        
        if uploaded_file is not None:
            # Parse parameters
            file_name = uploaded_file.name
            file_extension = file_name.split(".")[-1] if "." in file_name else "unknown"
            binary_payload = uploaded_file.read() # Read file directly into binary RAM stream
            
            st.warning(f"File Target Locked: {file_name} ({len(binary_payload)} bytes staging buffer)")
            
            if st.button("Commit File Directly to MySQL Permanent Disk"):
                try:
                    with conn.session as session:
                        insert_query = text("""
                            INSERT INTO crm_files (file_name, file_extension, file_data)
                            VALUES (:name, :ext, :data);
                        """)
                        session.execute(insert_query, {
                            "name": file_name,
                            "ext": file_extension.lower(),
                            "data": binary_payload
                        })
                        session.commit()
                    st.success(f"✅ Success! File '{file_name}' written permanently into the Hostinger DB cluster.")
                    st.rerun()
                except Exception as db_err:
                    st.error(f"Write Failure: Data rejected by MySQL engine. Details: {db_err}")

    # View files permanently stored in MySQL (Accessible to everyone)
    st.markdown("---")
    st.subheader("🗃️ Permanently Saved Files Registry")
    try:
        saved_files_df = conn.query("SELECT id, file_name, file_extension, uploaded_at FROM crm_files ORDER BY id DESC;", ttl=0)
        if not saved_files_df.empty:
            st.dataframe(saved_files_df, use_container_width=True, hide_index=True)
            
            st.caption("ℹ️ Raw documents remain safely embedded inside Hostinger disk drives. Your team can review logs and run the application continuously without data loss.")
        else:
            st.info("No raw external attachments are currently stored inside the database.")
    except Exception as read_err:
        st.error(f"Could not load physical document logs: {read_err}")
