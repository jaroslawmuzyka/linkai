import streamlit as st
import pandas as pd
import requests
from supabase import create_client, Client
import json
import time
import re

# --- 1. KONFIGURACJA STRONY I ZABEZPIECZENIE HASŁEM ---
st.set_page_config(page_title="LinkFlow AI - SEO 3.0", page_icon="🏭", layout="wide")

def check_password():
    """Wymusza logowanie hasłem zdefiniowanym w secrets."""
    if st.secrets.get("APP_PASSWORD") is None:
        # Jeśli nie ustawiono hasła w secrets, pozwalamy działać
        return True

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Nie przechowujemy hasła
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Pierwsze uruchomienie
        st.text_input("Podaj hasło dostępu:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Błędne hasło
        st.text_input("Podaj hasło dostępu:", type="password", on_change=password_entered, key="password")
        st.error("😕 Niepoprawne hasło")
        return False
    else:
        # Hasło poprawne
        return True

if not check_password():
    st.stop()

# --- 2. INICJALIZACJA SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE"]["URL"]
        key = st.secrets["SUPABASE"]["KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Błąd konfiguracji Supabase: {e}")
        return None

supabase = init_supabase()

# --- 3. KLASA API WHITEPRESS ---
class WhitePressAPI:
    def __init__(self):
        self.api_key = st.secrets["WHITEPRESS"]["API_KEY"]
        self.base_url = "https://www.whitepress.com/panel/api"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _request(self, endpoint, params=None, method="GET"):
        """Wykonuje zapytanie do API z Rate Limitingiem (1.1s)."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Używamy requests.request aby obsłużyć GET, POST i OPTIONS dynamicznie
            response = requests.request(method, url, headers=self.headers, params=params if method == "GET" else None, json=params if method == "POST" else None)
            
            # Rate Limiting
            time.sleep(1.1) 
            
            if response.status_code == 429:
                st.warning("Przekroczono limit zapytań (429). Czekam 5 sekund...")
                time.sleep(5)
                return self._request(endpoint, params, method)

            if response.status_code != 200:
                return {}
            
            return response.json()
        except Exception as e:
            st.error(f"Błąd połączenia z API WhitePress: {e}")
            return {}

    def get_projects(self):
        """Pobiera listę projektów (z paginacją)."""
        all_projects = []
        page = 1
        while True:
            data = self._request("/v1/projects", {"per_page": 25, "page": page})
            
            if 'list' in data:
                items = data['list']
            elif 'data' in data and 'list' in data['data']:
                items = data['data']['list']
            else:
                break
            
            if not items:
                break
                
            all_projects.extend(items)
            
            # Sprawdzamy czy jest więcej stron
            total_pages = data.get('totalPages', 1)
            if 'data' in data:
                total_pages = data['data'].get('totalPages', 1)
                
            if page >= total_pages:
                break
            page += 1
            
        return all_projects

    @st.cache_data(ttl=3600)
    def get_portal_options(_self, project_id):
        """
        Pobiera słowniki (kategorie, kraje, regiony) dla danego projektu.
        """
        data = _self._request(f"/v1/seeding/{project_id}/portals", method="OPTIONS")
        if 'options' in data:
            return data['options']
        if 'data' in data and 'options' in data['data']:
            return data['data']['options']
        return {}
    
    def get_portal_offers(self, project_id, portal_id):
        """Pobiera szczegóły ofert dla danego portalu."""
        data = self._request(f"/v1/seeding/{project_id}/portals/{portal_id}")
        if 'list' in data: return data['list']
        elif 'data' in data and 'list' in data['data']: return data['data']['list']
        return []

    def search_portals(self, project_id, filters, fetch_all=False):
        """Wyszukuje portale z pełnym zestawem filtrów."""
        api_filters = {
            "per_page": 50, 
            "sort": "seo_trust_flow", 
            "direction": "desc"
        }
        
        # Mapowanie filtrów
        if filters.get('price_max'): api_filters["filtering[offer_price_max]"] = filters['price_max']
        if filters.get('min_dr'): api_filters["filtering[portal_score_domain_rating]"] = filters['min_dr']
        if filters.get('min_tf'): api_filters["filtering[portal_score_trust_flow]"] = filters['min_tf']
        if filters.get('min_traffic'): api_filters["filtering[portal_unique_users]"] = filters['min_traffic']
        
        if filters.get('categories'): 
            api_filters["filtering[portal_category]"] = ",".join(map(str, filters['categories']))
        
        if filters.get('dofollow'): 
            api_filters["filtering[offer_dofollow]"] = 1

        all_portals = []
        page = 1
        
        while True:
            api_filters["page"] = page
            data = self._request(f"/v1/seeding/{project_id}/portals", api_filters)
            
            current_batch = []
            if 'list' in data: current_batch = data['list']
            elif 'data' in data and 'list' in data['data']: current_batch = data['data']['list']
            
            if not current_batch:
                break
                
            all_portals.extend(current_batch)
            
            if not fetch_all:
                break
            
            total_pages = 1
            if 'totalPages' in data: total_pages = data['totalPages']
            elif 'data' in data: total_pages = data['data'].get('totalPages', 1)
            
            if page >= total_pages:
                break
            page += 1
            
        return all_portals

    def get_project_articles(self, project_id):
        """Pobiera WSZYSTKIE opublikowane artykuły dla projektu."""
        all_articles = []
        page = 1
        
        while True:
            data = self._request(f"/v1/projects/{project_id}/articles", {"per_page": 100, "page": page})
            
            current_batch = []
            if 'list' in data: current_batch = data['list']
            elif 'data' in data and 'list' in data['data']: current_batch = data['data']['list']
            
            if not current_batch:
                break
            
            all_articles.extend(current_batch)
            
            total_pages = 1
            if 'totalPages' in data: total_pages = data['totalPages']
            elif 'data' in data: total_pages = data['data'].get('totalPages', 1)
            
            if page >= total_pages:
                break
            page += 1
            
        return all_articles

    def publish_article(self, project_id, portal_id, title, content):
        # Symulacja publikacji
        return {"success": True, "message": "Artykuł wysłany do realizacji (Symulacja)"}

wp_api = WhitePressAPI()

# --- 4. FUNKCJE POMOCNICZE (DIFY) ---

def run_dify_workflow(api_key, inputs):
    """
    Uruchamia workflow w Twojej instancji Dify.
    """
    base_url = st.secrets["DIFY"].get("BASE_URL", "https://api.dify.ai/v1")
    url = f"{base_url}/workflows/run"
    api_user = st.secrets["DIFY"].get("API_USER", "webinvest")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": inputs,
        "response_mode": "blocking",
        "user": api_user
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            return {"error": response.status_code, "message": response.text}
            
        return response.json()
    except Exception as e:
        return {"error": "Exception", "message": str(e)}

def clean_and_parse_json(text):
    """
    Czyści odpowiedź LLM z markdowna i parsuje do JSON.
    """
    try:
        # Usuń znaczniki markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        text = text.strip()
        return json.loads(text)
    except Exception as e:
        return []

def render_filters_form(options):
    """
    Renderuje formularz filtrów i zwraca słownik wybranych wartości.
    """
    raw_cats = options.get('portal_category', {})
    if isinstance(raw_cats, list): raw_cats = {}
    
    st.subheader("Filtrowanie Portali")
    
    with st.expander("📊 Ustawienia Filtrów", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            min_dr = st.number_input("Min. Domain Rating (DR)", value=0, key="f_dr")
            min_tf = st.number_input("Min. Trust Flow (TF)", value=0, key="f_tf")
        with col2:
            min_traffic = st.number_input("Min. Ruch (UU)", value=0, key="f_traffic")
            max_price = st.number_input("Max. Cena (PLN)", value=5000, key="f_price")
        with col3:
            selected_categories_ids = st.multiselect(
                "Kategorie", 
                options=list(raw_cats.keys()), 
                format_func=lambda x: f"{raw_cats[x]}",
                key="f_cats"
            )
            dofollow = st.checkbox("Tylko Dofollow", value=False, key="f_dof")
            name_search = st.text_input("Szukaj w nazwie", key="f_search")

    filters = {
        "min_dr": min_dr, "min_tf": min_tf, "min_traffic": min_traffic, "price_max": max_price,
        "categories": selected_categories_ids, "dofollow": dofollow, "name_search": name_search
    }
    return filters

# --- 5. INTERFEJS APLIKACJI ---

st.sidebar.title("LinkFlow AI 🏭")
menu = st.sidebar.radio("Nawigacja", ["Dashboard", "Synchronizacja (Projekty)", "Generator Kampanii", "Przeglądarka Portali", "Przegląd Kampanii", "Hub Treści (Masowy)", "Publikacja"])

# --- WIDOK: DASHBOARD ---
if menu == "Dashboard":
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

# --- WIDOK: SYNCHRONIZACJA ---
elif menu == "Synchronizacja (Projekty)":
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
                            supabase.table("clients").upsert(data, on_conflict="wp_project_id").execute()
                            count += 1
                    
                    st.success(f"Pomyślnie zsynchronizowano {count} projektów!")
    
    if supabase:
        data = supabase.table("clients").select("*").execute()
        if data.data:
            df = pd.DataFrame(data.data)
            st.dataframe(df[['wp_project_id', 'name', 'website']], use_container_width=True)

# --- WIDOK: GENERATOR KAMPANII ---
elif menu == "Generator Kampanii":
    st.title("Generator Kampanii")
    
    if not supabase: st.stop()
        
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    if not clients_resp.data:
        st.warning("Brak klientów.")
    else:
        clients_map = {c['name']: c for c in clients_resp.data}
        selected_client_name = st.selectbox("Wybierz Klienta", list(clients_map.keys()))
        
        if selected_client_name:
            client = clients_map[selected_client_name]
            
            with st.spinner("Pobieranie opcji..."):
                options = wp_api.get_portal_options(client['wp_project_id'])

            with st.form("campaign_form"):
                c1, c2 = st.columns(2)
                with c1:
                    campaign_name = st.text_input("Nazwa Kampanii", value=f"Kampania {selected_client_name}")
                with c2:
                    budget = st.number_input("Budżet (PLN)", value=2000, step=100)

                filters = render_filters_form(options)
                filters_submit = st.form_submit_button("🔎 Znajdź Portale", type="primary")

            if filters_submit:
                with st.spinner("Przeszukiwanie bazy WhitePress..."):
                    portals = wp_api.search_portals(client['wp_project_id'], filters)
                    
                    if filters.get('name_search'):
                        query = filters['name_search'].lower()
                        portals = [p for p in portals if query in p.get('name', '').lower() or query in p.get('portal_url', '').lower()]
                    
                    candidates = []
                    for p in portals:
                        price = float(p.get('best_price', 0))
                        if price <= 0: continue
                        
                        dr = int(p.get('portal_score_domain_rating', 0))
                        score = ((dr * 2)) / price
                        
                        candidates.append({
                            "wp_portal_id": p.get('id'),
                            "portal_name": p.get('name', 'Nieznany'),
                            "portal_url": p.get('portal_url', ''),
                            "price": price,
                            "metrics": {"dr": dr},
                            "score": score
                        })
                    
                    candidates.sort(key=lambda x: x['score'], reverse=True)
                    
                    selected_items = []
                    current_spend = 0
                    
                    for item in candidates:
                        if current_spend + item['price'] <= budget:
                            selected_items.append(item)
                            current_spend += item['price']
                    
                    if not selected_items:
                        st.warning("Brak portali spełniających kryteria.")
                    else:
                        st.session_state['campaign_candidates'] = selected_items
                        st.session_state['gen_meta'] = {
                            "client_id": client['id'],
                            "name": campaign_name,
                            "budget": budget
                        }
            
            if 'campaign_candidates' in st.session_state and st.session_state.get('campaign_candidates'):
                sel = st.session_state['campaign_candidates']
                st.divider()
                st.write(f"Wybrano: {len(sel)} portali. Koszt: {sum(x['price'] for x in sel):.2f} PLN")
                st.dataframe(pd.DataFrame(sel)[['portal_name', 'portal_url', 'price', 'metrics']], use_container_width=True)
                
                if st.button("💾 Zapisz Kampanię", type="primary"):
                    meta = st.session_state['gen_meta']
                    camp = supabase.table("campaigns").insert({
                        "client_id": meta['client_id'],
                        "name": meta['name'],
                        "budget_limit": meta['budget'],
                        "status": "planned"
                    }).execute()
                    
                    camp_id = camp.data[0]['id']
                    items_db = []
                    for item in sel:
                        items_db.append({
                            "campaign_id": camp_id,
                            "wp_portal_id": item['wp_portal_id'],
                            "portal_name": item['portal_name'],
                            "portal_url": item['portal_url'],
                            "price": item['price'],
                            "metrics": item['metrics'],
                            "status": "planned",
                            "pipeline_status": "planned"
                        })
                    supabase.table("campaign_items").insert(items_db).execute()
                    st.success("Zapisano kampanię!")
                    del st.session_state['campaign_candidates']

# --- WIDOK: PRZEGLĄDARKA PORTALI ---
elif menu == "Przeglądarka Portali":
    st.title("Przeglądarka Portali")
    if not supabase: st.stop()
    
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    if clients_resp.data:
        c_map = {c['name']: c for c in clients_resp.data}
        client_name = st.selectbox("Wybierz Projekt (do cennika)", list(c_map.keys()))
        
        if client_name:
            client = c_map[client_name]
            opts = wp_api.get_portal_options(client['wp_project_id'])
            
            with st.form("browse_form"):
                filters = render_filters_form(opts)
                if st.form_submit_button("Załaduj"):
                    res = wp_api.search_portals(client['wp_project_id'], filters, fetch_all=True)
                    if filters.get('name_search'):
                        query = filters['name_search'].lower()
                        res = [r for r in res if query in r.get('name','').lower() or query in r.get('portal_url','').lower()]
                    
                    st.session_state['browse_res'] = res
            
            if 'browse_res' in st.session_state:
                res = st.session_state['browse_res']
                st.write(f"Wyników: {len(res)}")
                
                df_disp = []
                for r in res:
                    df_disp.append({
                        "Wybierz": False, "Nazwa": r['name'], "URL": r['portal_url'],
                        "Cena": float(r.get('best_price',0)), "DR": r.get('portal_score_domain_rating'),
                        "_raw": r
                    })
                
                edited = st.data_editor(pd.DataFrame(df_disp), column_config={"Wybierz": st.column_config.CheckboxColumn(required=True), "_raw": None}, hide_index=True)
                
                if st.button("Utwórz Kampanię z zaznaczonych"):
                    sel_rows = edited[edited["Wybierz"]==True]
                    if not sel_rows.empty:
                        camp_name = st.text_input("Nazwa", f"Manualna {client_name}")
                        if st.button("Potwierdź"):
                            cost = sel_rows['Cena'].sum()
                            camp = supabase.table("campaigns").insert({"client_id": client['id'], "name": camp_name, "budget_limit": cost, "status": "planned"}).execute()
                            cid = camp.data[0]['id']
                            items = []
                            for _, row in sel_rows.iterrows():
                                r = row['_raw']
                                items.append({
                                    "campaign_id": cid, "wp_portal_id": r['id'], "portal_name": r['name'],
                                    "portal_url": r['portal_url'], "price": float(r.get('best_price',0)),
                                    "metrics": {"dr": r.get('portal_score_domain_rating')}, "status": "planned", "pipeline_status": "planned"
                                })
                            supabase.table("campaign_items").insert(items).execute()
                            st.success("Gotowe!")

                selected_rows_view = edited_df[edited_df["Wybierz"] == True]
                if not selected_rows_view.empty:
                    st.divider()
                    st.subheader("🔍 Szczegóły Ofert")
                    for idx, row in selected_rows_view.iterrows():
                        raw_p = row['_raw']
                        with st.expander(f"Oferty dla: {raw_p.get('portal_url')}"):
                            offers = wp_api.get_portal_offers(client_browse['wp_project_id'], raw_p.get('id'))
                            if offers:
                                st.dataframe(pd.DataFrame(offers)[['offer_title', 'best_price', 'offer_description']], use_container_width=True)

# --- WIDOK: PRZEGLĄD KAMPANII ---
elif menu == "Przegląd Kampanii":
    st.title("Kampanie")
    if supabase:
        camps = supabase.table("campaigns").select("*, clients(name)").order("created_at", desc=True).execute()
        for c in camps.data:
            with st.expander(f"{c['name']} | Status: {c['status']}"):
                items = supabase.table("campaign_items").select("*").eq("campaign_id", c['id']).execute()
                if items.data:
                    st.dataframe(pd.DataFrame(items.data)[['portal_url', 'topic', 'pipeline_status']], use_container_width=True)

# --- WIDOK: HUB TREŚCI (MASOWY GENERATOR) ---

elif menu == "Hub Treści (Masowy)":
    st.title("Fabryka Treści - Auto Pilot 🏭")
    st.info("Zarządzaj procesem generowania treści dla wielu artykułów jednocześnie.")
    
    if not supabase: st.stop()
    
    # 1. Wybór kampanii
    camps = supabase.table("campaigns").select("id, name").order("created_at", desc=True).execute().data
    if not camps:
        st.warning("Brak kampanii.")
        st.stop()
    
    camp_map = {c['name']: c['id'] for c in camps}
    sel_camp = st.selectbox("Wybierz Kampanię", list(camp_map.keys()))
    
    if sel_camp:
        camp_id = camp_map[sel_camp]
        # Pobranie danych
        items = supabase.table("campaign_items").select("*").eq("campaign_id", camp_id).order("id").execute().data
        
        if not items:
            st.warning("Brak artykułów w tej kampanii.")
        else:
            # PRZYGOTOWANIE TABELI DO EDYCJI
            df = pd.DataFrame(items)
            
            # Dodaj kolumnę do zaznaczania jeśli nie ma
            if "Wybierz" not in df.columns:
                df.insert(0, "Wybierz", False)
            
            # Upewniamy się że kolumny istnieją w DF (nawet puste)
            # USUNIĘTO: keywords, DODANO: frazy_senuto
            cols_needed = ["id", "portal_url", "topic", "language", "pipeline_status", "extra_instructions", "frazy_senuto"]
            for c in cols_needed:
                if c not in df.columns: df[c] = None

            # Konfiguracja edytora
            col_config = {
                "Wybierz": st.column_config.CheckboxColumn(required=True),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "topic": st.column_config.TextColumn("Temat / Fraza Główna (Kluczowe!)", width="large", required=True),
                "portal_url": st.column_config.TextColumn("Portal", disabled=True),
                "pipeline_status": st.column_config.TextColumn("Status", disabled=True),
                "language": st.column_config.SelectboxColumn("Język", options=["pl", "en", "de"], default="pl", required=True),
                "extra_instructions": st.column_config.TextColumn("Instrukcje"),
                # Ukrywamy techniczne kolumny z widoku (lub ustawiamy jako TextColumn, jeśli chcesz je widzieć)
                "knowledge_graph": None, "info_graph": None, "content_brief": None, "content_html": None,
                "headings_extended": None, "headings_h2": None, "headings_questions": None, "headings_final": None,
                "keywords_serp": None, "frazy_senuto": None, # Tutaj jest ukryta, zmień na st.column_config.TextColumn("Senuto") aby widzieć
                "created_at": None, "campaign_id": None, "wp_portal_id": None, 
                "portal_name": None, "price": None, "metrics": None, "status": None, "content": None
            }
            
            st.caption("Zaznacz artykuły (checkbox po lewej) i kliknij przycisk akcji na dole. Możesz edytować Temat i Język bezpośrednio w tabeli.")
            
            edited_df = st.data_editor(
                df, 
                column_config=col_config, 
                hide_index=True, 
                use_container_width=True, 
                key="mass_editor",
                disabled=["id", "portal_url", "pipeline_status", "frazy_senuto"]
            )
            
            # Zapis zmian w tematach
            if st.button("💾 Zapisz zmiany w tabeli (Tematy/Języki/Instrukcje)"):
                changes_count = 0
                for index, row in edited_df.iterrows():
                    # Porównanie z oryginałem dla optymalizacji
                    orig = next((x for x in items if x['id'] == row['id']), None)
                    if orig and (orig['topic'] != row['topic'] or orig['language'] != row['language'] or orig['extra_instructions'] != row['extra_instructions']):
                        supabase.table("campaign_items").update({
                            "topic": row['topic'],
                            "language": row['language'],
                            "extra_instructions": row['extra_instructions']
                        }).eq("id", row['id']).execute()
                        changes_count += 1
                st.toast(f"Zaktualizowano {changes_count} wierszy.")
                time.sleep(1)
                st.rerun()

            st.divider()
            
            # --- PANEL AKCJI MASOWYCH ---
            selected_rows = edited_df[edited_df["Wybierz"] == True]
            count_sel = len(selected_rows)
            
            st.subheader(f"Akcje dla zaznaczonych: {count_sel}")
            
            if count_sel > 0:
                c1, c2, c3, c4 = st.columns(4)
                
                # --- KROK 1: RESEARCH ---
                if c1.button("1. Research (Baza wiedzy + Senuto)"):
                    bar = st.progress(0)
                    for i, (_, row) in enumerate(selected_rows.iterrows()):
                        if not row['topic']:
                            st.error(f"ID {row['id']}: Brak tematu!")
                            continue
                            
                        res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_RESEARCH"], {
                            "keyword": row['topic'],
                            "language": row['language']
                        })
                        
                        if res.get('data', {}).get('status') == 'succeeded':
                            out = res['data']['outputs']
                            
                            # --- EKSTRAKCJA DANYCH ---
                            # Pobieramy frazy z SERP
                            frazy_serp = out.get('frazy') or out.get('frazy z serp') or out.get('keywords') or row['topic']
                            
                            # Pobieramy frazy z SENUTO (Nowość)
                            frazy_senuto_val = out.get('frazy_senuto', '')
                            
                            graf_info = out.get('grafinformacji') or out.get('graf') or out.get('information_graph') or ""
                            graf_know = out.get('knowledge_graph') or out.get('graf wiedzy') or ""
                            
                            # Zapisujemy do bazy
                            supabase.table("campaign_items").update({
                                "keywords_serp": frazy_serp,
                                "frazy_senuto": frazy_senuto_val,  # <--- ZAPIS DO NOWEJ KOLUMNY
                                "info_graph": graf_info,
                                "knowledge_graph": graf_know,
                                "pipeline_status": "researched"
                            }).eq("id", row['id']).execute()
                        else:
                            st.error(f"Błąd ID {row['id']}: {res}")
                        
                        bar.progress((i+1)/count_sel)
                    st.success("Research zakończony!")
                    time.sleep(1)
                    st.rerun()

                # --- KROK 2: STRUKTURA ---
                if c2.button("2. Struktura Nagłówków"):
                    bar = st.progress(0)
                    for i, (_, row) in enumerate(selected_rows.iterrows()):
                        # Pobieramy świeże dane z bazy (w tym keywords_serp i frazy_senuto)
                        db_item = supabase.table("campaign_items").select("keywords_serp, info_graph").eq("id", row['id']).single().execute().data
                        
                        frazy_val = db_item.get('keywords_serp')
                        if not frazy_val:
                            frazy_val = row['topic'] # Fallback
                        
                        graf_val = db_item.get('info_graph') or "Brak danych"

                        res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_HEADERS"], {
                            "keyword": row['topic'],
                            "language": row['language'],
                            "frazy": frazy_val,
                            "graf": graf_val
                        })
                        
                        if res.get('data', {}).get('status') == 'succeeded':
                            out = res['data']['outputs']
                            extended = out.get('naglowki_rozbudowane', '')
                            
                            supabase.table("campaign_items").update({
                                "headings_extended": extended,
                                "headings_h2": out.get('naglowki_h2'),
                                "headings_questions": out.get('naglowki_pytania'),
                                "headings_final": extended,
                                "pipeline_status": "structured"
                            }).eq("id", row['id']).execute()
                        else:
                            st.error(f"Błąd ID {row['id']}: {res}")
                        bar.progress((i+1)/count_sel)
                    st.success("Struktury wygenerowane!")
                    time.sleep(1)
                    st.rerun()

                # --- KROK 3: BRIEF ---
                if c3.button("3. Brief Contentowy"):
                    bar = st.progress(0)
                    for i, (_, row) in enumerate(selected_rows.iterrows()):
                        db_item = supabase.table("campaign_items").select("*").eq("id", row['id']).single().execute().data
                        
                        if not db_item.get('headings_final'):
                            st.warning(f"ID {row['id']}: Brak nagłówków. Pomiń.")
                            continue

                        keywords_input = db_item.get('keywords_serp')
                        if not keywords_input:
                            keywords_input = row['topic']

                        res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_BRIEF"], {
                            "keywords": keywords_input, 
                            "headings": db_item.get('headings_final', ''),
                            "knowledge_graph": db_item.get('knowledge_graph', 'Brak'),
                            "information_graph": db_item.get('info_graph', 'Brak'),
                            "keyword": row['topic']
                        })
                        
                        if res.get('data', {}).get('status') == 'succeeded':
                            raw_brief = res['data']['outputs'].get('brief', '[]')
                            parsed = clean_and_parse_json(raw_brief)
                            if parsed:
                                supabase.table("campaign_items").update({
                                    "content_brief": parsed,
                                    "pipeline_status": "briefed"
                                }).eq("id", row['id']).execute()
                        else:
                            st.error(f"Błąd ID {row['id']}: {res}")
                        bar.progress((i+1)/count_sel)
                    st.success("Briefy gotowe!")
                    time.sleep(1)
                    st.rerun()

                # --- KROK 4: PISANIE ---
                if c4.button("4. Generowanie Treści"):
                    status_ph = st.empty()
                    main_bar = st.progress(0)
                    
                    for i, (_, row) in enumerate(selected_rows.iterrows()):
                        status_ph.info(f"Piszę artykuł {i+1}/{count_sel}: {row['topic']}")
                        
                        db_item = supabase.table("campaign_items").select("content_brief, headings_final").eq("id", row['id']).single().execute().data
                        brief = db_item.get('content_brief')
                        
                        if not brief:
                            st.warning(f"ID {row['id']}: Brak briefu.")
                            continue
                            
                        full_content = ""
                        for section in brief:
                            res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_WRITE"], {
                                "naglowek": section.get('heading'),
                                "knowledge": section.get('knowledge'),
                                "keywords": section.get('keywords'),
                                "language": row['language'],
                                "headings": db_item.get('headings_final'),
                                "done": full_content,
                                "keyword": row['topic'],
                                "instruction": row['extra_instructions'] or ""
                            })
                            if res.get('data', {}).get('status') == 'succeeded':
                                chunk = res['data']['outputs'].get('result') or res['data']['outputs'].get('text', '')
                                full_content += chunk + "\n\n"
                            else:
                                st.error(f"Błąd w sekcji dla ID {row['id']}")
                        
                        supabase.table("campaign_items").update({
                            "content_html": full_content,
                            "pipeline_status": "content_ready",
                            "content": full_content,
                            "status": "content_ready"
                        }).eq("id", row['id']).execute()
                        
                        main_bar.progress((i+1)/count_sel)
                    
                    status_ph.success("Wszystkie artykuły napisane!")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()

            # --- AUTO PILOT (WSZYSTKO RAZEM) ---
            st.divider()
            if st.button("🚀 URUCHOM AUTO-PILOT (Wszystkie kroki dla zaznaczonych)", type="primary"):
                st.warning("To może potrwać kilka minut. Nie zamykaj karty przeglądarki.")
                master_bar = st.progress(0)
                log_container = st.container()
                
                for i, (_, row) in enumerate(selected_rows.iterrows()):
                    log_container.write(f"🔄 **Przetwarzam: {row['topic']}**")
                    
                    try:
                        # 1. RESEARCH
                        log_container.caption("Krok 1: Research (SERP + Senuto)...")
                        res1 = run_dify_workflow(st.secrets["DIFY"]["API_KEY_RESEARCH"], {"keyword": row['topic'], "language": row['language']})
                        out1 = res1.get('data', {}).get('outputs', {})
                        
                        # Pobieranie danych z Dify
                        frazy_serp = out1.get('frazy') or out1.get('frazy z serp') or out1.get('keywords') or row['topic']
                        frazy_senuto_val = out1.get('frazy_senuto', '') # <--- SENUTO
                        
                        graf_i = out1.get('grafinformacji') or out1.get('graf') or out1.get('information_graph') or "Brak"
                        graf_k = out1.get('knowledge_graph') or "Brak"
                        
                        # 2. STRUKTURA
                        log_container.caption("Krok 2: Struktura...")
                        res2 = run_dify_workflow(st.secrets["DIFY"]["API_KEY_HEADERS"], {
                            "keyword": row['topic'], "language": row['language'],
                            "frazy": frazy_serp, "graf": graf_i
                        })
                        headings_final = res2.get('data', {}).get('outputs', {}).get('naglowki_rozbudowane', 'H2: ' + row['topic'])
                        
                        # 3. BRIEF
                        log_container.caption("Krok 3: Brief...")
                        res3 = run_dify_workflow(st.secrets["DIFY"]["API_KEY_BRIEF"], {
                            "keywords": frazy_serp, "headings": headings_final,
                            "knowledge_graph": graf_k, "information_graph": graf_i,
                            "keyword": row['topic']
                        })
                        brief_raw = res3.get('data', {}).get('outputs', {}).get('brief', '[]')
                        brief_json = clean_and_parse_json(brief_raw)
                        
                        # 4. PISANIE
                        log_container.caption(f"Krok 4: Pisanie ({len(brief_json)} sekcji)...")
                        full_content = ""
                        for sec in brief_json:
                            res4 = run_dify_workflow(st.secrets["DIFY"]["API_KEY_WRITE"], {
                                "naglowek": sec.get('heading'), "knowledge": sec.get('knowledge'),
                                "keywords": sec.get('keywords'), "language": row['language'],
                                "headings": headings_final, "done": full_content,
                                "keyword": row['topic'], "instruction": row['extra_instructions'] or ""
                            })
                            chunk = res4.get('data', {}).get('outputs', {}).get('result') or res4.get('data', {}).get('outputs', {}).get('text', '')
                            full_content += chunk + "\n\n"
                        
                        # FINALNY ZAPIS Z UWZGLĘDNIENIEM FRAZ SENUTO
                        supabase.table("campaign_items").update({
                            "keywords_serp": frazy_serp, 
                            "frazy_senuto": frazy_senuto_val, # <--- ZAPIS
                            "info_graph": graf_i, 
                            "knowledge_graph": graf_k,
                            "headings_extended": headings_final, 
                            "headings_final": headings_final,
                            "content_brief": brief_json, 
                            "content_html": full_content, 
                            "content": full_content,
                            "pipeline_status": "content_ready", 
                            "status": "content_ready"
                        }).eq("id", row['id']).execute()
                        
                        log_container.success(f"✅ Zakończono: {row['topic']}")
                        
                    except Exception as e:
                        log_container.error(f"❌ Błąd przy {row['topic']}: {e}")
                    
                    master_bar.progress((i+1)/count_sel)
                
                st.success("Auto-Pilot zakończył pracę!")

# --- WIDOK: PUBLIKACJA ---
elif menu == "Publikacja":
    st.title("Publikacja w WhitePress")
    if not supabase: st.stop()
    
    # Pobieramy tylko gotowe
    items = supabase.table("campaign_items").select("*").eq("pipeline_status", "content_ready").execute()
    
    if not items.data:
        st.info("Brak gotowych artykułów.")
    else:
        for i in items.data:
            with st.expander(f"{i['topic']} ({i['portal_url']})"):
                st.text_area("HTML", i.get('content_html') or i.get('content'), height=200)
                if st.button(f"Opublikuj {i['id']}"):
                    wp_api.publish_article(123, i['wp_portal_id'], i['topic'], i.get('content_html') or i.get('content'))
                    supabase.table("campaign_items").update({"pipeline_status": "published", "status": "published"}).eq("id", i['id']).execute()
                    st.success("Wysłano!")
                    st.rerun()