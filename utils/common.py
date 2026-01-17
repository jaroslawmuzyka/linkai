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
        "Long-term": "Bezterminowo",
        "days": "dni",
        "months": "miesięcy",
        "month": "miesiąc",
        
        # Links
        "1 link": "1 link",
        "2 links": "2 linki",
        "3 links": "3 linki",
        "4 links": "4 linki",
        "links": "linki",
        "multiple links": "wiele linków",
        "multiple linki": "wiele linków", # catch partial
        "NOFOLLOW": "NOFOLLOW",
        "DOFOLLOW": "DOFOLLOW",
        
        # Types
        "All link types": "Wszystkie rodzaje linków",
        "Many types of links": "Różne rodzaje linków",
        "Many types of linki": "Różne rodzaje linków", # catch partial
        "Standard link": "Link standardowy",
        "Brand links": "Linki brandowe",
        "Generic links": "Linki generyczne",
        "Naked links": "Linki URL",
        "Graphic links": "Linki graficzne",
        "Mixed links": "Linki mieszane",
        "Exact Match Link": "EML - Exact Match Link",
        "Match Link": "Match Link",
        
        # Long Description Phrases
        "Long-term publication - maintained unchanged for at least": "Publikacja długoterminowa - bez zmian przez min.",
        "after this time, the Publisher aims to maintain it for as long as possible": "po tym czasie Wydawca utrzymuje tak długo jak to możliwe"
    }
    
    # Apply replacements (sorted by length to avoid partial matches first)
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    for k in sorted_keys:
        pattern = re.compile(re.escape(k), re.IGNORECASE)
        title = pattern.sub(replacements[k], title)
        
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
    
    data = {}
    def extract_val(pattern, text):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # Extraction Logic
    val = extract_val(r"Number of links to the Advertiser's website:\s*(.*?)(?=\s+Maximum|Minimum|$)", desc)
    if val: data['links_limit'] = val
    
    val = extract_val(r"Maximum number of links to pages other than the Advertiser's domain:\s*(.*?)(?=\s+Minimum|Maximum|$)", desc)
    if val: data['links_other'] = "nie zezwala" if "does not allow" in val.lower() else val
    
    val = extract_val(r"Minimum length of the article.*?:(\d+)\s*characters", desc) # Simplified regex
    if not val: val = extract_val(r"Minimum length of the article.*?:(\d+)", desc)
    if val: data['min_len'] = val
    
    val = extract_val(r"Maximum length of the article.*?:(\d+)", desc)
    if val: data['max_len'] = val
    
    val = extract_val(r"Promoting:\s*(.*?)(?=\s+Duration|Trwałość|$)", desc)
    if val: data['promotion'] = translate_offer_title(val)
    
    val = extract_val(r"Duration of articles.*?:(.*?)(?=\s+Main image|$)", desc)
    if val:
        if "maintained unchanged for at least" in val:
             data['duration'] = "Bezterminowo (gwarancja 12 mies.)"
        elif "deleted after 12 months" in val: 
            data['duration'] = "Artykuł jest kasowany po 12 miesiącach."
        elif "Permanent" in val or "lifetime" in val: 
            data['duration'] = "Bezterminowo"
        else: 
            data['duration'] = translate_offer_title(val)

    val = extract_val(r"Main image of the article:\s*(.*?)(?=\s+Number of images|$)", desc)
    if val:
        if "requires a main photo" in val: data['main_image'] = "Publikacja wymaga zdjęcia głównego"
        else: data['main_image'] = translate_offer_title(val)

    val = extract_val(r"Number of images in content:\s*(.*?)(?=\s+Possibility|$)", desc)
    if val:
        if "does not have to, but can have images" in val:
            nums = re.search(r"\(from (\d+) to (\d+)\)", val)
            if nums:
                data['images_content'] = f"Artykuł w treści nie musi, ale może mieć zdjęcia (od {nums.group(1)} do {nums.group(2)})."
            else:
                data['images_content'] = "Możliwość dodania zdjęć."
        else:
            data['images_content'] = val

    val = extract_val(r"Possibility of posting video content:\s*(.*?)(?=\s+Possibility|$)", desc)
    if val: data['video'] = translate_bool(val)

    val = extract_val(r"Possibility of placing external counting.*?:(.*?)$", desc)
    if val: data['scripts'] = translate_bool(val)
    
    return data

def render_offer_row(offer, u_id, in_cart=False, show_actions=True):
    """
    Renders the offer as a wide row with multiple columns matching the WhitePress UI screenshot.
    Columns: [Name, Description (Wide), Price, Duration, Writing, Marking, Dofollow, Traffic, Persistence, Action]
    """
    # Parse description first
    d = parse_offer_description(offer.get('offer_description', ''))
    
    # Define Layout Ratios
    # Name=1.5, Desc=3.5, Price=0.8, PromoLen=0.8, Write=0.8, Mark=0.8, Dof=0.8, Traf=0.8, Pers=0.8, Act=1
    cols = st.columns([1.5, 3.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 1])
    
    # 1. Nazwa Oferty
    with cols[0]:
        st.markdown(format_offer_title_html(offer['offer_title']))
        if offer.get('offer_url'):
            st.caption(f"URL: {offer['offer_url']}")
        
    # 2. Opis Oferty (Wide)
    with cols[1]:
        # Top Icons Line
        # Swagger: offer_require_photo_source, portal_tracking (not in offer usually, but let's check keys)
        req_src = offer.get('offer_require_photo_source', False)
        # Tracking often property of Portal, not Offer, but sometimes passed down. 
        # If not present, don't show "Check" blindly.
        trk_code = offer.get('portal_tracking') # Boolean or None
        
        line1 = []
        line1.append(f"Wymaga źródła: {'✅' if req_src else '❌'}")
        if trk_code is not None:
             line1.append(f"Tracking: {'✅' if trk_code else '❌'}")
        
        # Stats cost? NOT in Swagger. Remove 0 zl if not found.
        if 'price_stats' in offer:
             line1.append(f"Statystyki: {offer['price_stats']} zł")

        if line1: st.caption(" | ".join(line1))
        
        # Link Guidelines
        limit = d.get('links_limit') or offer.get('offer_links_limit', '1') # Swagger doesn't specify limit field, relies on desc
        other = d.get('links_other') or "wg opisu"
        
        # Article Guidelines
        min_l = d.get('min_len', '1200')
        max_l = d.get('max_len', '20000')
        dur = d.get('duration', str(offer.get('offer_persistence_custom', offer.get('offer_persistence', '12 m.'))))
        
        st.markdown(f"**Linki:** Limit: {limit} | Inne: {other}")
        st.caption(f"Długość: {min_l}-{max_l} | Trwałość: {dur}")

        with st.expander("Pełny opis oferty", expanded=False):
            st.write(offer.get('offer_description', 'Brak opisu.'))
            if 'offer_allowed_link_types' in offer:
                st.write(f"**Typy linków**: {offer['offer_allowed_link_types']}")

    # 3. Cena Netto
    with cols[2]:
        price = float(offer.get('best_price', 0))
        st.markdown(f"**{price:.2f} zł**")
        if offer.get('promo_discount'):
             st.caption(f"-{offer['promo_discount']}%")

    # 4. Długość promocji (dni)
    with cols[3]:
        prom = offer.get('offer_promoting', 0)
        st.write(f"{prom} dni") 

    # 5. Napisanie artykułu
    with cols[4]:
        # Swagger doesn't have explicit copywriting allowed bool in offer?
        # Maybe 'content_writing' status? Assuming False if missing to avoid misleading.
        st.write("-")

    # 6. Oznaczanie
    with cols[5]:
        # Not in Swagger explicitly as simple field? 'article_marking'? 
        # Checking implementation plan/swagger again.
        # Swagger: offer_tagging from options?
        mark = offer.get('offer_tagging', '-')
        st.write(mark)

    # 7. Linki Dofollow
    with cols[6]:
        # Swagger: offer_dofollow is boolean
        dof = offer.get('offer_dofollow')
        if dof is None: dof = False
        # If it's 1/0 int
        if isinstance(dof, int): dof = (dof == 1)
        st.write("✅" if dof else "❌")

    # 8. Gwarancja ruchu
    with cols[7]:
        # Not in Swagger offer response?
        st.write("-")

    # 9. Wskaźnik trwałości
    with cols[8]:
        pers = offer.get('offer_persistence')
        st.write(f"{pers} m." if pers else "-")

    # 10. Button
    with cols[9]:
        if show_actions:
            if in_cart:
                if st.button("Usuń", key=f"del_{u_id}", type="secondary"):
                    return "REMOVE"
            else:
                if st.button("Wybierz", key=f"add_{u_id}", type="primary"):
                    return "ADD"
    
    return None

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
