                        # Step B: Unpack rows directly into the permanent search catalog
                        rows_inserted = 0
                        if df_to_import is not None:
                            for _, row in df_to_import.iterrows():
                                # 🔄 NEW AUTOMATION: Handle separate first and last name columns
                                if 'fname' in df_to_import.columns or 'lname' in df_to_import.columns:
                                    f_part = str(row.get('fname', '')).strip() if pd.notna(row.get('fname')) else ''
                                    l_part = str(row.get('lname', '')).strip() if pd.notna(row.get('lname')) else ''
                                    r_name = f"{f_part} {l_part}".strip()
                                else:
                                    r_name = str(row.get('name', '')).strip()
                                
                                # Extract email and phone using your exact file headers
                                r_email = str(row.get('email', '')).strip()
                                r_phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
                                
                                # Default to 'Lead' since your file doesn't have a status column
                                r_status = str(row.get('status', 'Lead')).strip()
                                
                                # Skip incomplete data lines
                                if not r_name or not r_email:
                                    continue
                                    
                                # SQLite upsert uses ON CONFLICT(unique_column) DO UPDATE
                                insert_client_query = text("""
                                    INSERT INTO clients (name, email, phone, status) 
                                    VALUES (:name, :email, :phone, :status)
                                    ON CONFLICT(email) DO UPDATE SET
                                        name = excluded.name,
                                        phone = excluded.phone,
                                        status = excluded.status;
                                """)
                                session.execute(insert_client_query, {
                                    "name": r_name,
                                    "email": r_email,
                                    "phone": r_phone,
                                    "status": r_status
                                })
                                rows_inserted += 1
                        
                        session.commit()
