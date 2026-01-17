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
            response = requests.request(method, url, headers=self.headers, params=params if method == "GET" else None, json=params if method == "POST" else None)
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
        """Pobiera listę projektów."""
        all_projects = []
        page = 1
        while True:
            data = self._request("/v1/projects", {"per_page": 25, "page": page})
            items = data.get('list') or data.get('data', {}).get('list') or []
            if not items: break
            all_projects.extend(items)
            
            total = data.get('totalPages') or data.get('data', {}).get('totalPages', 1)
            if page >= total: break
            page += 1
        return all_projects

    @st.cache_data(ttl=3600)
    def get_portal_options(_self, project_id):
        data = _self._request(f"/v1/seeding/{project_id}/portals", method="OPTIONS")
        return data.get('options') or data.get('data', {}).get('options') or {}
    
    def get_portal_offers(self, project_id, portal_id):
        data = self._request(f"/v1/seeding/{project_id}/portals/{portal_id}")
        return data.get('list') or data.get('data', {}).get('list') or []

    def search_portals(self, project_id, filters, page=1, per_page=20):
        """
        Wyszukuje portale z paginacją. Zwraca (items, meta).
        Meta zawiera: 'total_pages', 'total_items', 'current_page'
        """
        api_filters = {
            "per_page": per_page, 
            "page": page
        }
        
        # --- Mapping Filters ---
        if filters.get('price_max'): api_filters["filtering[offer_price_max]"] = filters['price_max']
        if filters.get('price_min'): api_filters["filtering[offer_price_min]"] = filters['price_min']
        
        if filters.get('min_dr'): api_filters["filtering[portal_score_domain_rating]"] = filters['min_dr']
        if filters.get('min_tf'): api_filters["filtering[portal_score_trust_flow]"] = filters['min_tf']
        if filters.get('min_traffic'): api_filters["filtering[portal_unique_users]"] = filters['min_traffic']
        
        if filters.get('categories'): 
            # API expects comma-separated categories if multiple
            api_filters["filtering[portal_category]"] = ",".join(map(str, filters['categories']))
        
        if filters.get('dofollow') == "Tak": api_filters["filtering[offer_dofollow]"] = 1
        elif filters.get('dofollow') == "Nie": api_filters["filtering[offer_dofollow]"] = 0
             
        if filters.get('only_promo'): api_filters["filtering[offer_promo]"] = 1 # Swagger says offer_promo, not offer_price_promo

        # --- Ext. Filters Mapping ---
        if filters.get('region') and filters['region'] != "Wszystkie": api_filters["filtering[portal_region]"] = filters['region']
        if filters.get('country') and filters['country'] != "Polska (domyślny)": api_filters["filtering[portal_country]"] = filters['country']
        if filters.get('keywords'): api_filters["filtering[portal]"] = filters['keywords']
        
        # Type enum mapping might be needed if UI sends "Portal" but API wants ID. 
        # Assuming UI options match API string/id or close enough.
        # But UI has "Wszystkie", "Portal", "Blog"...
        # Swagger options: portal_type: ["string"] - likely IDs or keys.
        # Without exact ID mapping from OPTIONS, we might send raw if it works, or skip.
        # Check if 'opts' were passed to filters? - Yes in View. But here in Service we just have dict.
        # We will try sending if not "Wszystkie"
        if filters.get('type') and filters['type'] != "Wszystkie": api_filters["filtering[portal_type]"] = filters['type']

        if filters.get('link_type') and filters['link_type'] != "Wszystkie": api_filters["filtering[offer_link_type]"] = filters['link_type']
        if filters.get('article_marking') and filters['article_marking'] != "Wszystkie": api_filters["filtering[offer_tagging]"] = filters['article_marking']

        if filters.get('min_content_grade'): api_filters["filtering[portal_score_content]"] = filters['min_content_grade']
        if filters.get('min_tech_grade'): api_filters["filtering[portal_score_technical]"] = filters['min_tech_grade']
        if filters.get('tracking_traffic'): api_filters["filtering[portal_tracking]"] = 1
        
        if filters.get('promo_duration'): api_filters["filtering[offer_promoting]"] = filters['promo_duration']
        if filters.get('persistence') and filters['persistence'] != "Wszystkie": api_filters["filtering[offer_persistence]"] = filters['persistence']

        if filters.get('min_senuto'): api_filters["filtering[portal_visibility_senuto]"] = filters['min_senuto']
        if filters.get('min_semstorm'): api_filters["filtering[portal_visibility_semstorm]"] = filters['min_semstorm']
        if filters.get('min_semrush'): api_filters["filtering[portal_visibility_semrush]"] = filters['min_semrush']
        if filters.get('min_ahrefs_traffic'): api_filters["filtering[portal_visibility_ahrefs]"] = filters['min_ahrefs_traffic']
        if filters.get('min_pr'): api_filters["filtering[portal_score_page_rating]"] = filters['min_pr']

        # Request
        data = self._request(f"/v1/seeding/{project_id}/portals", api_filters)
        
        items = data.get('list') or data.get('data', {}).get('list') or []
        
        # Parse Meta
        meta_src = data.get('data', data) # Sometimes root, sometimes details
        meta = {
            "total_items": meta_src.get('totalRows', 0) if 'totalRows' in meta_src else meta_src.get('total', 0), # Swagger says totalRows
            "total_pages": meta_src.get('totalPages', 1),
            "current_page": page
        }
        
        return items, meta

    def get_project_articles(self, project_id):
        all_articles = []
        page = 1
        while True:
            data = self._request(f"/v1/projects/{project_id}/articles", {"per_page": 100, "page": page})
            items = data.get('list') or data.get('data', {}).get('list') or []
            if not items: break
            all_articles.extend(items)
            total = data.get('totalPages') or data.get('data', {}).get('totalPages', 1)
            if page >= total: break
            page += 1
        return all_articles

    def publish_article(self, project_id, portal_id, title, content):
        return {"success": True, "message": "Artykuł wysłany do realizacji (Symulacja)"}
