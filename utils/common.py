import streamlit as st

def render_filters_form(options):
    """
    Renderuje rozbudowany formularz filtrów (Podstawowe, Marketingowe, SEO).
    """
    # Helper to safe get options
    def get_opts(key):
        o = options.get(key, {})
        return list(o.keys()) if isinstance(o, dict) else []

    # Helper for formatting labels from the options dict
    def fmt_opts(key, val):
        o = options.get(key, {})
        return o.get(val, val)

    filters = {}
    
    st.subheader("Filtrowanie Portali")

    # --- 1. FILTRY PODSTAWOWE ---
    with st.expander("🔹 Filtry Podstawowe", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            filters['name_search'] = st.text_input("Nazwa portalu / URL")
            filters['region'] = st.selectbox("Region", ["Wszystkie"] + get_opts('portal_region'))
        
        with c2:
            # Tematyka - Multiselect
            raw_cats = options.get('portal_category', {})
            filters['categories'] = st.multiselect("Tematyka", options=list(raw_cats.keys()), format_func=lambda x: raw_cats[x])
            
            # Cena
            sc1, sc2 = st.columns(2)
            filters['price_min'] = sc1.number_input("Cena od", min_value=0, step=10)
            filters['price_max'] = sc2.number_input("Cena do", min_value=0, value=5000, step=10)

        with c3:
            filters['country'] = st.selectbox("Kraj", ["Polska (domyślny)", "Inny"]) # Placeholder if opts missing
            filters['keywords'] = st.text_input("Szukaj po słowach kluczowych")
        
        with c4:
            filters['type'] = st.selectbox("Rodzaj portalu", ["Wszystkie", "Portal", "Blog", "Serwis"])
            filters['min_traffic'] = st.number_input("Min. unikalnych użyt.", step=1000)

        # Row 2
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        with r2c1:
            filters['dofollow'] = st.selectbox("Linki dofollow", ["Wszystkie", "Tak", "Nie"], index=0)
        with r2c2:
            filters['link_type'] = st.selectbox("Rodzaj linków", ["Wszystkie", "W treści", "Stopka", "Site-wide"])
        with r2c3:
            filters['content_links_count'] = st.selectbox("Liczba linków w treści", ["Dowolna", "1", "2", "3+"])
        with r2c4:
            filters['article_marking'] = st.selectbox("Oznaczanie art.", ["Wszystkie", "Brak", "Sponsorowany", "Reklama"])

        # Row 3
        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        with r3c1:
            filters['min_content_grade'] = st.number_input("Min. ocena merytoryczna (1-10)", 0, 10, 0)
        with r3c2:
            filters['min_tech_grade'] = st.number_input("Min. ocena techniczna (1-10)", 0, 10, 0)
        with r3c3:
            filters['only_promo'] = st.checkbox("Tylko promocje")
        with r3c4:
             filters['favorites'] = st.checkbox("Ulubione")

    # --- 2. FILTRY MARKETINGOWE ---
    with st.expander("📢 Filtry Marketingowe", expanded=False):
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            filters['social_promo'] = st.selectbox("Promocja w social mediach", ["Nieistotne", "Tak", "Nie"])
            filters['guarantee_36'] = st.checkbox("Gwarancja 36 mies.")
        with m2:
            filters['promo_duration'] = st.number_input("Min. długość promocji (dni)", 0)
            filters['persistence'] = st.selectbox("Trwałość publikacji", ["Wszystkie", "1 rok", "Bezterminowo"])
        with m3:
            filters['tracking_traffic'] = st.checkbox("Śledzenie ruchu")
            filters['publisher_writes'] = st.selectbox("Wydawca pisze treść", ["Nieistotne", "Tak", "Nie"])
        with m4:
            filters['traffic_guarantee'] = st.checkbox("Oferty z gwarancją ruchu")

    # --- 3. FILTRY SEO ---
    with st.expander("🚀 Filtry SEO", expanded=False):
        s1, s2, s3, s4 = st.columns(4)
        
        # Row 1
        with s1: filters['min_tf'] = st.number_input("Min. Trust Flow", 0)
        with s2: filters['min_pr'] = st.number_input("Min. Page Rating", 0) # Placeholder name
        with s3: filters['min_dr'] = st.number_input("Min. Domain Rating", 0)
        with s4: filters['min_cf'] = st.number_input("Min. Citation Flow", 0)
        
        # Row 2
        ss1, ss2, ss3, ss4 = st.columns(4)
        with ss1: filters['min_senuto'] = st.number_input("Min. ruch SENUTO", 0)
        with ss2: filters['min_semstorm'] = st.number_input("Min. ruch Semstorm", 0)
        with ss3: filters['min_ur'] = st.number_input("Min. średni UR", 0)
        with ss4: filters['max_ahrefs_rank'] = st.number_input("Maks. Ahrefs Rank", 0) # 0 = no limit

        # Row 3
        sss1, sss2, sss3, sss4 = st.columns(4)
        with sss1: filters['min_ahrefs_traffic'] = st.number_input("Min. ruch AHREFS", 0)
        with sss2: filters['min_semrush'] = st.number_input("Min. ruch Semrush", 0)
        with sss3: filters['min_auth_score'] = st.number_input("Min. Authority Score", 0)
        with sss4: filters['min_da'] = st.number_input("Min. Domain Authority", 0)

    # Clean up and return only set values if needed, or mapping logic handles it
    return filters
