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

# 🔄 FORCE STRUCTURE SYNCHRONIZATION: Wipe old tables to support expanded 11-column fields
with conn.session as init_session:
    try:
        init_session.execute(text("SELECT fname FROM clients LIMIT 1;"))
    except Exception:
        init_session.execute(text("DROP TABLE IF EXISTS clients;"))
        init_session.execute(text("DROP TABLE IF EXISTS crm_files;"))
        init_session.commit()

    init_session.execute(text("CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, fname TEXT DEFAULT '', lname TEXT DEFAULT '', email TEXT NOT NULL UNIQUE, dob TEXT DEFAULT '', address TEXT DEFAULT '', city TEXT DEFAULT '', state TEXT DEFAULT '', zip TEXT DEFAULT '', phone TEXT NOT NULL, bank TEXT DEFAULT '', status TEXT DEFAULT 'Lead', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
    init_session.execute(text("CREATE TABLE IF NOT EXISTS crm_files (id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT NOT NULL, file_extension TEXT NOT NULL, file_data BLOB NOT NULL, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
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
            query_str = "SELECT fname, lname, email, dob, address, city, state, zip, phone, bank, status FROM clients WHERE fname LIKE :param OR lname LIKE :param OR email LIKE :param OR phone LIKE :param ORDER BY id DESC;"
            data_ledger = conn.query(query_str, params={"param": f"%{search_input}%"}, ttl=0)

            if not data_ledger.empty:
                st.success(f"Record Found! Match total: {len(data_ledger)}")

                for index, row in data_ledger.iterrows():
                    with st.container(border=True):
                        st.markdown(f"### 👤 Profile: {row['fname']} {row['lname']}")

                        col_a, col_b, col_c = st.columns(3)
                        col_a.markdown(f"**📞 Phone Number:**  \n{row['phone']}")
                        col_b.markdown(f"**✉️ Email Address:**  \n{row['email']}")
                        col_c.markdown(f"**📅 Date of Birth:**  \n{row['dob']}")

                        st.markdown("---")

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
# BRANCH B: ADMIN WORKFLOW (Uses Stable Bulk-Import Native Tools)
# ----------------------------------------------------
else:
    tab1, tab2 = st.tabs(["🔍 Global Master Directory", "📦 Cloud Database Storage Ledger"])

    with tab1:
        st.subheader("📊 Master Customer Database View")
        admin_search = st.text_input("🔍 Filter Registry (Real-time tracking)")

        try:
            if admin_search:
                query_str = "SELECT id, fname, lname, email, dob, address, city, state, zip, phone, bank, status, created_at FROM clients WHERE fname LIKE :p OR lname LIKE :p OR email LIKE :p OR phone LIKE :p ORDER BY id DESC;"
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
                    # 1. Save raw file backup blob using a direct, flat execution stream
                    with conn.session as session:
                        session.execute(text("INSERT INTO crm_files (file_name, file_extension, file_data) VALUES (:name, :ext, :data);"), {
                            "name": file_name, "ext": file_extension, "data": binary_payload
                        })

                        rows_imported = 0

                        # 2. Extract and import matrix — done as a portable per-row
                        #    "check then insert-or-update" loop rather than SQLite's
                        #    ON CONFLICT...DO UPDATE upsert syntax, because Streamlit
                        #    Cloud's bundled sqlite3 library predates SQLite 3.24 and
                        #    doesn't understand that syntax at all (hence the earlier
                        #    "near DO: syntax error"). This loop works on any version.
                        if df_to_import is not None:
                            # Ensure every expected column exists first.
                            for col in ['fname', 'lname', 'email', 'dob', 'address', 'city', 'state', 'zip', 'phone', 'bank', 'status']:
                                if col not in df_to_import.columns:
                                    df_to_import[col] = "Lead" if col == "status" else ""

                            # sqlite3 can only bind plain Python types (str/int/float/None) —
                            # pandas gives us Timestamp objects for dates and numpy int64 for
                            # numeric-looking columns like phone/zip, both of which raise
                            # "Error binding parameter" if passed through as-is. Coerce every
                            # cell to a plain string (dates -> YYYY-MM-DD) up front.
                            def _clean_cell(v):
                                if pd.isna(v):
                                    return ""
                                if isinstance(v, pd.Timestamp):
                                    return v.strftime("%Y-%m-%d")
                                return str(v).strip()

                            for col in ['fname', 'lname', 'email', 'dob', 'address', 'city', 'state', 'zip', 'phone', 'bank', 'status']:
                                df_to_import[col] = df_to_import[col].apply(_clean_cell)

                            # Some source exports store email as a markdown link, e.g.
                            # "[name@example.com](mailto:name@example.com)" — pull the plain
                            # address back out wherever that pattern shows up.
                            extracted = df_to_import['email'].str.extract(r'([\w\.\-\+]+@[\w\.\-]+\.\w+)', expand=False)
                            df_to_import['email'] = extracted.fillna(df_to_import['email'])

                            df_final = df_to_import[['fname', 'lname', 'email', 'dob', 'address', 'city', 'state', 'zip', 'phone', 'bank', 'status']]

                            update_sql = text(
                                "UPDATE clients SET fname=:fname, lname=:lname, phone=:phone, dob=:dob, "
                                "address=:address, city=:city, state=:state, zip=:zip, bank=:bank, status=:status "
                                "WHERE email=:email;"
                            )
                            insert_sql = text(
                                "INSERT INTO clients (fname, lname, email, dob, address, city, state, zip, phone, bank, status) "
                                "VALUES (:fname, :lname, :email, :dob, :address, :city, :state, :zip, :phone, :bank, :status);"
                            )

                            for _, row in df_final.iterrows():
                                email = str(row["email"]).strip()
                                if not email:
                                    continue  # email is NOT NULL / UNIQUE — skip rows without one
                                params = {
                                    "fname": row["fname"], "lname": row["lname"], "email": email,
                                    "dob": row["dob"], "address": row["address"], "city": row["city"],
                                    "state": row["state"], "zip": row["zip"], "phone": row["phone"],
                                    "bank": row["bank"], "status": row["status"],
                                }
                                result = session.execute(update_sql, params)
                                if result.rowcount == 0:
                                    session.execute(insert_sql, params)
                                rows_imported += 1

                        # 3. Commit everything in this session — the file blob insert AND
                        #    (if applicable) the client upsert — as a single atomic unit.
                        session.commit()

                    # 4. Feedback to the user, and clear cached admin directory query so the
                    #    new/updated rows show up immediately in tab1 without a manual refresh.
                    st.cache_data.clear()
                    if df_to_import is not None:
                        st.success(f"✅ Commit complete: file archived and {rows_imported} client record(s) imported/updated.")
                    else:
                        st.success("✅ Commit complete: file archived to the vault (no spreadsheet rows to import).")

                except Exception as commit_err:
                    st.error(f"Commit Execution Fault: {commit_err}")
