import streamlit as st
import pandas as pd
from utils.common import render_filters_form

# --- HELPER: TRANSLATION & FORMATTING ---
def format_offer_title(title):
    # Map common English phrases to Polish
    replacements = {
        "Home page": "Strona główna",
        "1 day": "1 dzień",
        "days": "dni",
        "1 link": "1 link",
        "links": "linki",
        "NOFOLLOW": "NOFOLLOW",
        "DOFOLLOW": "DOFOLLOW",
        "12 months": "12 miesięcy",
        "All link types": "Wszystkie rodzaje linków",
        "Mixed links": "Linki mieszane",
        "Brand links": "Linki brandowe",
        "Standard link": "Link standardowy",
        "Article": "Artykuł"
    }
    for k, v in replacements.items():
        title = title.replace(k, v)
    
    # Styled Output (Bold Red/Pinkish logic)
    # Streamlit limitation: markdown colors. using :red[] or HTML.
    return f":red[**{title}**]"

def translate_bool(val):
    return "Tak" if val else "Nie"

def render_offer_details(offer, u_id, in_cart):
    # Layout based on Screenshot 2
    # HEADER: Name + Price
    st.markdown(f"#### {format_offer_title(offer['offer_title'])}")
    
    # Top Checkmarks/Crosses
    # "Wymagane podanie źródła zdjęć", "Kod śledzenia", "Statystyki od wydawcy"
    # Mapping API fields (best guess based on common WhitePress attributes)
    
    # Example logic (adjust based on actual API response keys if debugged, assuming common names)
    req_source = offer.get('images_source_required', False)
    tracking = offer.get('tracking_code', False)
    stats = offer.get('stats_from_publisher', False) # Hypothetical key
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        icon = "✅" if not req_source else "❌" # Assuming 'required' is bad/strict? Or just info. Screenshot shows Red X for "Wymagane...".
        # Actually Screenshot show Red X next to "Wymagane podanie źródła zdjęć".
        # If it IS required -> Red X? Or typically "Require Source" is a constraint.
        st.write(f"{icon} Wymagane podanie źródła zdjęć")
    
    with c2:
        icon = "✅" if tracking else "❌"
        st.write(f"{icon} Kod śledzenia")
        
    with c3:
        # Check logic for stats
        st.write(f"✅ Statystyki od wydawcy ({offer.get('price_stats', 0):.2f} zł netto)")


    st.divider()
    
    # 3 Columns for Details
    # Col 1: Linkowanie, Col 2: Artykuł, Col 3: Pozostałe
    col_link, col_art, col_other = st.columns(3)
    
    with col_link:
        st.strong("Wytyczne dot. linkowania:")
        # Bullet points
        st.markdown(f"""
        - Liczba linków: **{offer.get('links_limit', '-')}**
        - Linki do innych stron: **{translate_bool(offer.get('links_other_allowed', False))}**
        - Typy linków: {offer.get('offer_allowed_link_types', 'Wszystkie')}
        """)

    with col_art:
        st.strong("Wytyczne dot. artykułu:")
        st.markdown(f"""
        - Min. długość: **{offer.get('min_length', '-')}** znaków
        - Max. długość: **{offer.get('max_length', '-')}** znaków
        - Promowanie: **{offer.get('publication_place', 'Strona główna')}**
        - Trwałość: **{offer.get('offer_persistence_custom', '12 miesięcy')}**
        - Zdjęcia: **{offer.get('images_limit_min', 0)}-{offer.get('images_limit_max', 5)}**
        """)

    with col_other:
        st.strong("Pozostałe wytyczne:")
        st.markdown(f"""
        - Wideo: **{translate_bool(offer.get('video_allowed', False))}**
        - Skrypty: **{translate_bool(offer.get('scripts_allowed', False))}**
        """)
        
    # Bottom Action Bar
    st.markdown("---")
    ac1, ac2 = st.columns([4, 1])
    with ac1:
        if offer.get('promo_discount'):
            st.success(f"🔥 PROMOCJA: -{offer['promo_discount']}% (Cena reg: {offer.get('price_regular','?')} zł)")
    with ac2:
        if in_cart:
            if st.button("Usuń z koszyka", key=f"del_{u_id}", type="secondary"):
                return "REMOVE"
        else:
            if st.button("Wybierz", key=f"add_{u_id}", type="primary"):
                return "ADD"
    return None

# --- MAIN RENDER ---
def render(supabase, wp_api):
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
                if st.form_submit_button("Załaduj Portale"):
                    with st.spinner("Pobieram dane..."):
                        res = wp_api.search_portals(client['wp_project_id'], filters, fetch_all=True)
                        if filters.get('name_search'):
                            query = filters['name_search'].lower()
                            res = [r for r in res if query in r.get('name','').lower() or query in r.get('portal_url','').lower()]
                        st.session_state['browse_res'] = res
            
            if 'browse_res' in st.session_state:
                res = st.session_state['browse_res']
                st.markdown(f"**Znaleziono**: {len(res)} portali")
                
                if 'expanded_offers' not in st.session_state: st.session_state['expanded_offers'] = set()
                if 'cart_items' not in st.session_state: st.session_state['cart_items'] = []

                # Header
                h1, h2, h3, h4, h5, h6, h7 = st.columns([2.5, 1, 1, 1, 1, 1, 1.5]) 
                h1.caption("Portal")
                h2.caption("Ruch (UU)")
                h3.caption("Trust Flow")
                h4.caption("Domain Rating")
                h5.caption("Dofollow")
                h6.caption("Cena od")
                h7.caption("Akcja")
                st.divider()
                
                for idx, r in enumerate(res):
                    pid = r['id']
                    with st.container():
                        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.5, 1, 1, 1, 1, 1, 1.5])
                        with c1:
                            st.subheader(r.get('portal_url', ''))
                            ctags = []
                            if r.get('portal_score_quality'): ctags.append(f"Jakość: {r.get('portal_score_quality')}/10")
                            if r.get('portal_country'): ctags.append(r.get('portal_country'))
                            if ctags: st.caption(" | ".join(ctags))
                        with c2: st.write(f"{r.get('portal_unique_users', 0):,}")
                        with c3: st.write(f"{r.get('portal_score_trust_flow', '-')}")
                        with c4: st.write(f"{r.get('portal_score_domain_rating', '-')}")
                        with c5: st.write("✅" if r.get('offers_dofollow_count', 0) > 0 else "❌")
                        with c6: st.write(f"**{r.get('best_price', 0):.2f} zł**")
                        with c7:
                            is_expanded = pid in st.session_state['expanded_offers']
                            if st.button("Ukryj" if is_expanded else "Zobacz oferty", key=f"btn_{pid}"):
                                if is_expanded: st.session_state['expanded_offers'].discard(pid)
                                else: st.session_state['expanded_offers'].add(pid)
                                st.rerun()

                    # EXPANDED SECTION with NEW DETAILED VIEW
                    if pid in st.session_state['expanded_offers']:
                        with st.container():
                            # st.info(f"Oferty dla {r.get('portal_url')}")
                            cache_key = f"offers_data_{pid}"
                            if cache_key not in st.session_state:
                                st.session_state[cache_key] = wp_api.get_portal_offers(client['wp_project_id'], pid)
                            
                            my_offers = st.session_state[cache_key]
                            
                            if not my_offers:
                                st.warning("Brak ofert.")
                            else:
                                for offer in my_offers:
                                    # Unique ID
                                    u_id = f"{pid}_{offer.get('id', offer['offer_title'])}"
                                    in_cart = u_id in [x['unique_id'] for x in st.session_state['cart_items']]
                                    
                                    # RENDER DETAILED CARD
                                    with st.container(border=True): # Use border to group offer
                                        action = render_offer_details(offer, u_id, in_cart)
                                        
                                        if action == "ADD":
                                            st.session_state['cart_items'].append({
                                                "unique_id": u_id,
                                                "portal_id": pid,
                                                "portal_url": r.get('portal_url'),
                                                "portal_name": r.get('name'),
                                                "metrics": {"dr": r.get('portal_score_domain_rating')},
                                                "offer": offer,
                                                "price": float(offer['best_price'])
                                            })
                                            st.rerun()
                                        elif action == "REMOVE":
                                            st.session_state['cart_items'] = [x for x in st.session_state['cart_items'] if x['unique_id'] != u_id]
                                            st.rerun()

                    st.markdown("---")

                # CART
                if st.session_state['cart_items']:
                    with st.expander("🛒 Koszyk (Utwórz Kampanię)", expanded=True):
                        st.write(f"Wybrano: {len(st.session_state['cart_items'])} ofert. Razem: {sum(x['price'] for x in st.session_state['cart_items']):.2f} zł")
                        
                        with st.form("create_camp_cart"):
                            cname = st.text_input("Nazwa Kampanii", f"Manualna {client_name}")
                            if st.form_submit_button("Utwórz Kampanię"):
                                total_cost = sum(x['price'] for x in st.session_state['cart_items'])
                                camp = supabase.table("campaigns").insert({
                                    "client_id": client['id'],
                                    "name": cname,
                                    "budget_limit": total_cost,
                                    "status": "planned"
                                }).execute()
                                cid = camp.data[0]['id']
                                
                                db_items = []
                                for ci in st.session_state['cart_items']:
                                    o = ci['offer']
                                    db_items.append({
                                        "campaign_id": cid,
                                        "wp_portal_id": ci['portal_id'],
                                        "portal_name": ci['portal_name'],
                                        "portal_url": ci['portal_url'],
                                        "price": ci['price'],
                                        "metrics": ci['metrics'],
                                        "status": "planned",
                                        "pipeline_status": "planned",
                                        "offer_title": o.get('offer_title'),
                                        "offer_description": o.get('offer_description')
                                    })
                                supabase.table("campaign_items").insert(db_items).execute()
                                st.success("Kampania utworzona!")
                                st.session_state['cart_items'] = [] 
                                st.rerun()
