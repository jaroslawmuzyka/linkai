import streamlit as st
import pandas as pd

def render(supabase):
    st.title("Kampanie")
    if supabase:
        camps = supabase.table("campaigns").select("*, clients(name)").order("created_at", desc=True).execute()
        for c in camps.data:
            # Check for granular statuses to show progress
            items = supabase.table("campaign_items").select("*").eq("campaign_id", c['id']).execute()
            
            with st.expander(f"{c['name']} | Status: {c['status']} | Ilość art: {len(items.data)}"):
                if items.data:
                    df = pd.DataFrame(items.data)
                    # Helper func to safely get col or dash
                    def get_col(row, col): return row.get(col) or '-'
                    
                    # Create readable status summary
                    df['Status Research'] = df.apply(lambda r: get_col(r, 'status_research'), axis=1)
                    df['Status Brief'] = df.apply(lambda r: get_col(r, 'status_brief'), axis=1)
                    df['Status Pisanie'] = df.apply(lambda r: get_col(r, 'status_writing'), axis=1)
                    
                    st.dataframe(df[['portal_url', 'topic', 'Status Research', 'Status Brief', 'Status Pisanie']], use_container_width=True)
