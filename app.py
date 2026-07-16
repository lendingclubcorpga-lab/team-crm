import streamlit as st
import pandas as pd
import pymysql
import io

# Page Setup
st.set_page_config(page_title="Secure Corporate CRM", layout="wide", page_icon="🛡️")

# 🔄 CRASH-PROOF DATABASE ENGINE: Pure PyMySQL raw fallback connection
def get_raw_connection():
    try:
        return pymysql.connect(
            host=st.secrets["connections"]["mysql"]["host"],
            user=st.secrets["connections"]["mysql"]["username"],
            password=st.secrets["connections"]["mysql"]["password"],
            database=st.secrets["connections"]["mysql"]["database"],
            port=int(st.secrets["connections"]["mysql"]["port"]),
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        st.error(f"Infrastructure Link Blocked: Unable to handshaking Hostinger. Details: {e}")
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
    
    # Establish a completely dedicated, isolated read query stream
    db_conn = get_raw_connection()
    try:
        with db_conn.cursor() as cursor:
            if search_input:
                sql_str = """
                    SELECT id, name, email, phone, status, created_at 
                    FROM clients 
                    WHERE name LIKE %s OR email LIKE %s OR phone LIKE %s 
                    ORDER BY id DESC;
                """
                like_param = f"%{search_input}%"
                cursor.execute(sql_str, (like_param, like_param, like_param))
            else:
                cursor.execute("SELECT id, name, email, phone, status, created_at FROM clients ORDER BY id DESC;")
            
            raw_rows = cursor.fetchall()
            data_ledger = pd.DataFrame(raw_rows)
            
        if not data_ledger.empty:
            st.dataframe(data_ledger, use_container_width=True, hide_index=True)
            
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
        st.error(f"SQL Read Violation: Hostinger reset the active lookup stream. Error: {ex}")
    finally:
        db_conn.close() # Close immediately to free Hostinger pool threads

# ----------------------------------------------------
# TAB 2: SECURE UPLOAD & SYSTEM ENGINE
# ----------------------------------------------------
with tab2:
    st.subheader("🗄️ Hostinger Binary Object Repository")
    
    if not st.session_state["is_admin"]:
        st.error("⛔ Access Restriction Notice: Your operational tier does not possess database write permission.")
    else:
        st.markdown("#### 🚀 Admin Universal File Uploader")
        uploaded_file = st.file_uploader("Upload spreadsheet registry or binary file (Supports CSV, XLSX, PDF, etc.)")
        
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
                    
                    st.info(f"📊 Spreadsheet detected! Found {len(df_to_import)} row(s). Columns found: {', '.join(df_to_import.columns)}")
                    st.caption("⚠️ Requirements: Spreadsheet headers must be exactly lowercase: **name, email, phone, status**")
                except Exception as parse_err:
                    st.error(f"Could not parse spreadsheet text: {parse_err}")
            
            if st.button("Commit File & Process Registry Matrix"):
                write_conn = get_raw_connection()
                try:
                    with write_conn.cursor() as cursor:
                        # Step A: Save raw backup file into crm_files table
                        insert_file_query = """
                            INSERT INTO crm_files (file_name, file_extension, file_data)
                            VALUES (%s, %s, %s);
                        """
                        cursor.execute(insert_file_query, (file_name, file_extension, binary_payload))
                        
                        # Step B: If spreadsheet, unpack rows directly into searchable client table
                        rows_inserted = 0
                        if df_to_import is not None:
                            for _, row in df_to_import.iterrows():
                                r_name = str(row.get('name', '')).strip()
                                r_email = str(row.get('email', '')).strip()
                                r_phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
                                r_status = str(row.get('status', 'Lead')).strip()
                                
                                if not r_name or not r_email:
                                    continue
                                    
                                insert_client_query = """
                                    INSERT INTO clients (name, email, phone, status) 
                                    VALUES (%s, %s, %s, %s)
                                    ON DUPLICATE KEY UPDATE 
                                        name = VALUES(name), 
                                        phone = VALUES(phone), 
                                        status = VALUES(status);
                                """
                                cursor.execute(insert_client_query, (r_name, r_email, r_phone, r_status))
                                rows_inserted += 1
                        
                        write_conn.commit()
                        
                    st.success(f"✅ Success! File saved to database.")
                    if rows_inserted > 0:
                        st.success(f"📈 Registry Synced: Extracted and added {rows_inserted} contacts successfully!")
                    st.rerun()
                    
                except Exception as db_err:
                    st.error(f"Write Failure: Data rejected by MySQL. Details: {db_err}")
                finally:
                    write_conn.close()

    # View files permanently stored in MySQL (Accessible to everyone)
    st.markdown("---")
    st.subheader("🃟 Permanently Saved Files Registry")
    file_view_conn = get_raw_connection()
    try:
        with file_view_conn.cursor() as cursor:
            cursor.execute("SELECT id, file_name, file_extension, uploaded_at FROM crm_files ORDER BY id DESC;")
            saved_files_df = pd.DataFrame(cursor.fetchall())
            
        if not saved_files_df.empty:
            st.dataframe(saved_files_df, use_container_width=True, hide_index=True)
        else:
            st.info("No raw external attachments are currently stored inside the database.")
    except Exception as read_err:
        st.error(f"Could not load physical document logs: {read_err}")
    finally:
        file_view_conn.close()
