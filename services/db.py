import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE"]["URL"]
        key = st.secrets["SUPABASE"]["KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Błąd konfiguracji Supabase: {e}")
        return None
