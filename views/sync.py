import streamlit as st
import pandas as pd

def render(supabase, wp_api):
    st.title("Synchronizacja Projektów")
    st.info("Pobiera listę projektów z WhitePress i zapisuje lokalnie w bazie.")
    
    if st.button("Pobierz projekty z WhitePress", type="primary"):
        if not supabase:
            st.error("Brak połączenia z bazą.")
        else:
            with st.spinner("Pobieranie danych z API WhitePress..."):
                projects = wp_api.get_projects()
                
                if not projects:
                    st.warning("API nie zwróciło żadnych projektów.")
                else:
                    count = 0
                    for p in projects:
                        project_title = p.get('title', p.get('name', 'Projekt bez nazwy'))
                        project_id = p.get('id')
                        project_url = p.get('url', '')

                        if project_id:
                            data = {
                                "wp_project_id": project_id,
                                "name": project_title,
                                "website": project_url
                            }
                            # Upsert clients
                            supabase.table("clients").upsert(data, on_conflict="wp_project_id").execute()
                            count += 1
                    
                    st.success(f"Pomyślnie zsynchronizowano {count} projektów!")
    
    if supabase:
        data = supabase.table("clients").select("*").execute()
        if data.data:
            df = pd.DataFrame(data.data)
            st.dataframe(df[['wp_project_id', 'name', 'website']], use_container_width=True)
