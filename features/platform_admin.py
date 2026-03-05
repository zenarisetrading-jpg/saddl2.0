"""
Platform Admin Dashboard
=======================
UI module for Super Admin operations.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from app_core.platform_service import PlatformService
from config.design_system import COLORS, TYPOGRAPHY

def render_platform_admin():
    """Render the main Platform Admin dashboard."""
    st.markdown(f"## Platform Admin Dashboard")
    st.markdown("Manage client organizations and platform settings.")

    service = PlatformService()

    # --- Actions Bar ---
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("➕ Add Client", type="primary", use_container_width=True):
            add_client_dialog()
            
    # --- PROVISIONAL: Data Migration Tool (For User Request) ---
    with st.expander("System Maintenance & Migration", expanded=False):
        st.caption("Tools to fix data consistency issues.")
        if st.button("Migrate Orphaned Accounts to Primary Org"):
            with st.spinner("Migrating accounts..."):
                try:
                    # Logic inline to avoid import issues
                    db = st.session_state.get('db_manager')
                    import uuid
                    # Deterministic ID for 'saddle.io' -> Primary Organization
                    primary_org_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "saddle.io"))
                    
                    ph = db.placeholder
                    updated_count = 0
                    
                    with db._get_connection() as conn:
                        cursor = conn.cursor()
                        # Move all accounts without an org to the Primary Org
                        cursor.execute(f"""
                            UPDATE accounts 
                            SET organization_id = {ph} 
                            WHERE organization_id IS NULL OR organization_id = ''
                        """, (primary_org_id,))
                        updated_count = cursor.rowcount
                        
                    st.success(f"Successfully migrated {updated_count} accounts to Primary Organization ({primary_org_id}).")
                except Exception as e:
                    st.error(f"Migration failed: {e}")

    # --- Organization List ---
    st.markdown("### Client Organizations")
    
    orgs = service.list_organizations()
    
    if not orgs:
        st.info("No organizations found.")
        return

    # Convert to DataFrame for easier display
    data = []
    for o in orgs:
        data.append({
            "Organization": o.name,
            "Status": o.status,
            "Users": o.user_count,
            "Admins": o.admin_count,
            "Created": o.created_at.strftime("%Y-%m-%d") if o.created_at else "Unknown",
            "ID": o.id
        })
    
    df = pd.DataFrame(data)
    
    # render basic table
    st.dataframe(
        df,
        column_config={
            "Organization": st.column_config.TextColumn("Organization", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Users": st.column_config.NumberColumn("Users", format="%d"),
            "Admins": st.column_config.NumberColumn("Admins", format="%d"),
            "Created": st.column_config.TextColumn("Created", width="small"),
            "ID": st.column_config.TextColumn("ID", width="large", disabled=True),
        },
        use_container_width=True,
        hide_index=True
    )


@st.dialog("Add New Client Organization")
def add_client_dialog():
    """Modal dialog for adding a new client org."""
    st.write("Create a new organization and invite the first admin.")
    
    with st.form("add_client_form"):
        org_name = st.text_input("Organization Name", placeholder="e.g. Zenarise Trading")
        admin_email = st.text_input("Client Admin Email", placeholder="e.g. client@example.com")
        
        # Confirmation
        st.markdown(f"""
            <div style="background: rgba(37, 99, 235, 0.1); padding: 10px; border-radius: 8px; font-size: 0.9em; margin-bottom: 10px;">
                This will create a new separate environment and send an 
                <b>OWNER</b> invitation to the email above.
            </div>
        """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button("Create & Invite", type="primary")
        
        if submitted:
            if not org_name or not admin_email:
                st.error("Please fill in all fields.")
            elif "@" not in admin_email:
                st.error("Invalid email address.")
            else:
                svc = PlatformService()
                
                # Get current user ID if available for auditing
                creator_id = str(st.session_state.current_user.id) if 'current_user' in st.session_state else None
                
                with st.spinner("Creating organization..."):
                    result = svc.create_organization(org_name, admin_email, creator_user_id=creator_id)
                
                if result.success:
                    st.success("Organization created successfully!")
                    st.balloons()
                    # Just rerun - the dialog will close and table will update
                    st.rerun()
                else:
                    st.error(f"Failed: {result.message}")
