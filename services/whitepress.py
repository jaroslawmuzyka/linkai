import streamlit as st
import requests
import time

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
