import streamlit as st

def render(supabase):
    st.title("Panel Główny")
    st.markdown("Witaj w systemie automatyzacji Link Building.")
    
    if supabase:
        try:
            clients_count = supabase.table("clients").select("*", count="exact").execute().count
            campaigns_count = supabase.table("campaigns").select("*", count="exact").execute().count
            articles_count = supabase.table("campaign_items").select("*", count="exact").execute().count
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Klienci", clients_count)
            col2.metric("Kampanie", campaigns_count)
            col3.metric("Zaplanowane Artykuły", articles_count)
                    
        except Exception as e:
            st.error(f"Nie można połączyć się z bazą danych: {e}")
