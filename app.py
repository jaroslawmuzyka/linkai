import streamlit as st
from services.auth import check_password
from services.db import init_supabase
from services.whitepress import WhitePressAPI
from views import dashboard, sync, campaign_gen, portal_browser, campaign_overview, content_planner, publication

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="LinkFlow AI - SEO 3.0", page_icon="🏭", layout="wide")

# --- AUTH ---
if not check_password():
    st.stop()

# --- SERVICES ---
supabase = init_supabase()
wp_api = WhitePressAPI()

# --- SIDEBAR ---
st.sidebar.title("LinkFlow AI 🏭")
menu = st.sidebar.radio("Nawigacja", [
    "Dashboard", 
    "Synchronizacja (Projekty)", 
    "Generator Kampanii", 
    "Przeglądarka Portali", 
    "Przegląd Kampanii", 
    "Planowanie treści", 
    "Publikacja"
])

# --- ROUTING ---
if menu == "Dashboard":
    dashboard.render(supabase)
elif menu == "Synchronizacja (Projekty)":
    sync.render(supabase, wp_api)
elif menu == "Generator Kampanii":
    campaign_gen.render(supabase, wp_api)
elif menu == "Przeglądarka Portali":
    portal_browser.render(supabase, wp_api)
elif menu == "Przegląd Kampanii":
    campaign_overview.render(supabase)
elif menu == "Planowanie treści":
    content_planner.render(supabase)
elif menu == "Publikacja":
    publication.render(supabase, wp_api)
