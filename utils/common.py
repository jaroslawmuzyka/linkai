import streamlit as st
import re

# --- TRANSLATIONS HELPERS ---
def translate_offer_title(title):
    """Kompleksowe tłumaczenie nazwy oferty na polski"""
    if not title: return "-"
    
    replacements = {
        # Basics
        "Home page": "Strona główna",
        "Subpage": "Podstrona",
        "News": "News/Aktualności",
        "Article": "Artykuł",
        
        # Duration
        "1 day": "1 dzień",
        "12 months": "12 miesięcy",
        "Permanent": "Bezterminowo",
        "days": "dni",
        "months": "miesięcy",
        "month": "miesiąc",
        
        # Links
        "1 link": "1 link",
        "2 links": "2 linki",
        "3 links": "3 linki",
        "4 links": "4 linki",
        "links": "linki",
        "NOFOLLOW": "NOFOLLOW",
        "DOFOLLOW": "DOFOLLOW",
        
        # Types
        "All link types": "Wszystkie rodzaje linków",
        "Standard link": "Link standardowy",
        "Brand links": "Linki brandowe",
        "Generic links": "Linki generyczne",
        "Naked links": "Linki URL",
        "Graphic links": "Linki graficzne",
        "Mixed links": "Linki mieszane",
        "Exact Match Link": "EML - Exact Match Link",
        "Match Link": "Match Link"
    }
    
    # Apply replacements (sorted by length to avoid partial matches first)
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    for k in sorted_keys:
        # Case insensitive replace might be safer, but for now simple replace
        title = title.replace(k, replacements[k])
        
    return title

def format_offer_title_html(title):
    """Returns formatted :red[**Title**] string for Streamlit markdown"""
    translated = translate_offer_title(title)
    return f":red[**{translated}**]"

def translate_bool(val):
    if isinstance(val, bool):
        return "Tak" if val else "Nie"
    if str(val).lower() in ["yes", "true", "1"]: return "Tak"
    if str(val).lower() in ["no", "false", "0"]: return "Nie"
    return str(val)


def parse_offer_description(desc):
    """
    Parses the long English description string into a dictionary of known keys.
    Returns a dict with Polish keys ready for display.
    """
    if not desc: return {}
    
    # Define markers to split or regex extract
    # Map English phrase -> Polish Key
    
    data = {}
    
    # Helper regex extraction
    def extract_val(pattern, text):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # Mapping based on user provided text
    # "Number of links to the Advertiser's website: 1"
    val = extract_val(r"Number of links to the Advertiser's website:\s*(.*?)(?=\s+Maximum|Minimum|$)", desc)
    if val: data['links_limit'] = val
    
    # "Maximum number of links to pages other than the Advertiser's domain: does not allow"
    val = extract_val(r"Maximum number of links to pages other than the Advertiser's domain:\s*(.*?)(?=\s+Minimum|Maximum|$)", desc)
    if val: data['links_other'] = "nie zezwala" if "does not allow" in val.lower() else val
    
    # "Minimum length of the article (characters with spaces): 1200"
    val = extract_val(r"Minimum length of the article.*?:(\d+)\s*characters", desc) # Simplified regex
    if not val: val = extract_val(r"Minimum length of the article.*?:(\d+)", desc)
    if val: data['min_len'] = val
    
    # "Maximum length of the article (characters with spaces): 25000"
    val = extract_val(r"Maximum length of the article.*?:(\d+)", desc)
    if val: data['max_len'] = val
    
    # "Promoting: Home page"
    val = extract_val(r"Promoting:\s*(.*?)(?=\s+Duration|Trwałość|$)", desc)
    if val: data['promotion'] = translate_offer_title(val)
    
    # "Duration of articles... : The article is deleted after 12 months"
    # User example: "Artykuł jest kasowany po 12 miesiącach"
    val = extract_val(r"Duration of articles.*?:(.*?)(?=\s+Main image|$)", desc)
    if val:
        if "deleted after 12 months" in val: data['duration'] = "Artykuł jest kasowany po 12 miesiącach."
        elif "after 12 months" in val: data['duration'] = "12 miesięcy"
        elif "Permanent" in val or "lifetime" in val: data['duration'] = "Bezterminowo"
        else: data['duration'] = translate_offer_title(val)

    # "Main image of the article: Publication requires a main photo..."
    val = extract_val(r"Main image of the article:\s*(.*?)(?=\s+Number of images|$)", desc)
    if val:
        if "requires a main photo" in val: data['main_image'] = "Publikacja wymaga zdjęcia głównego"
        else: data['main_image'] = translate_offer_title(val)

    # "Number of images in content: The article does not have to, but can have images (from 1 to 5)."
    val = extract_val(r"Number of images in content:\s*(.*?)(?=\s+Possibility|$)", desc)
    if val:
        # Translate complex string
        if "does not have to, but can have images" in val:
            nums = re.search(r"\(from (\d+) to (\d+)\)", val)
            if nums:
                data['images_content'] = f"Artykuł w treści nie musi, ale może mieć zdjęcia (od {nums.group(1)} do {nums.group(2)})."
            else:
                data['images_content'] = "Możliwość dodania zdjęć."
        else:
            data['images_content'] = val

    # "Possibility of posting video content: No"
    val = extract_val(r"Possibility of posting video content:\s*(.*?)(?=\s+Possibility|$)", desc)
    if val: data['video'] = translate_bool(val)

    # "Possibility of placing external counting...: No"
    val = extract_val(r"Possibility of placing external counting.*?:(.*?)$", desc)
    if val: data['scripts'] = translate_bool(val)
    
    return data

# --- FILTER FORM ---
def render_filters_form(options):
    """
    Renderuje rozbudowany formularz filtrów (Podstawowe, Marketingowe, SEO).
    """
    # Helper to safe get options
    def get_opts(key):
        o = options.get(key, {})
        return list(o.keys()) if isinstance(o, dict) else []

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
