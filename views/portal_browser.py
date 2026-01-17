import streamlit as st
import pandas as pd
from utils.common import render_filters_form, translate_offer_title, format_offer_title_html, translate_bool, parse_offer_description

def render_offer_details(offer, u_id, in_cart):
    # Layout based on User Screenshot
    
    # 1. Title
    st.markdown(f"#### {format_offer_title_html(offer['offer_title'])}")
    
    # Parsing description for fallback/primary data
    desc_data = parse_offer_description(offer.get('offer_description', ''))
    
    # 2. Top Validations (Icons)
    # Using parsed data or API keys
    # Map parsed data to simple boolean logic if possible, or just display text?
    # User wanted "Wymagane... : Icon"
    # Usually these are specific flags in API, but if missing, hard to parse from text "Publication requires..." -> True
    
    req_src = offer.get('images_source_required', False)
    trk_code = offer.get('tracking_code', True)
    stats = offer.get('stats_from_publisher', True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"Wymagane podanie źródła zdjęć: {'✅' if req_src else '❌'}") 
    with c2:
        st.write(f"Kod śledzenia: {'✅' if trk_code else '❌'}")
    with c3:
        price_stats = offer.get('price_stats', 0)
        st.write(f"Statystyki od wydawcy: {'✅' if stats else '❌'}  ({price_stats:.2f} zł netto)")

    st.divider()
    
    # 3. Sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Wytyczne dot. linkowania:**")
        # Prefer parsed description data over raw keys if available (since raw keys might be empty/generic)
        limit = desc_data.get('links_limit') or offer.get('links_limit', '1')
        other = desc_data.get('links_other') or ("nie zezwala" if not offer.get('links_other_allowed') else "zezwala")
        
        st.markdown(f"""
        - Liczba linków do strony Reklamodawcy: **{limit}**
        - Maksymalna liczba linków do stron innych niż domena Reklamodawcy: **{other}**
        """)

    with col2:
        st.markdown("**Wytyczne dot. artykułu:**")
        
        min_len = desc_data.get('min_len') or offer.get('min_length', 1200)
        max_len = desc_data.get('max_len') or offer.get('max_length', 25000)
        place = desc_data.get('promotion') or translate_offer_title(offer.get('publication_place', 'Strona główna'))
        dur = desc_data.get('duration') or translate_offer_title(offer.get('offer_persistence_custom', '12 miesięcy'))
        
        img_txt = desc_data.get('images_content')
        if not img_txt:
            img_min = offer.get('images_limit_min', 0)
            img_max = offer.get('images_limit_max', 5)
            img_txt = f"Artykuł w treści nie musi, ale może mieć zdjęcia (od {img_min} do {img_max})."
            
        main_img = desc_data.get('main_image') or "Publikacja wymaga zdjęcia głównego"
        
        st.markdown(f"""
        - Minimalna długość artykułu: **{min_len} znaków**
        - Maksymalna długość artykułu: **{max_len} znaków**
        - Promowanie: **{place}**
        - Trwałość artykułu: **{dur}**
        - Zdjęcie główne artykułu: **{main_img}**
        - Liczba zdjęć w treści: **{img_txt}**
        """)

    with col3:
        st.markdown("**Pozostałe wytyczne:**")
        video = desc_data.get('video') or ("Tak" if offer.get('video_allowed') else "Nie")
        scripts = desc_data.get('scripts') or ("Tak" if offer.get('scripts_allowed') else "Nie")
        
        st.markdown(f"""
        - Możliwość zamieszczenia treści wideo: **{video}**
        - Możliwość zamieszczenia zewnętrznych kodów zliczających: **{scripts}**
        """)

    st.markdown("---")
    
    # Action Bar
    ac1, ac2 = st.columns([4, 1])
    with ac1:
        if offer.get('promo_discount'):
             st.info(f"🏷️ Promocja: -{offer['promo_discount']}%")
    with ac2:
        if in_cart:
            if st.button("Usuń", key=f"del_{u_id}", type="secondary"):
                return "REMOVE"
        else:
            if st.button("Wybierz", key=f"add_{u_id}", type="primary"):
                return "ADD"
    return None

def render(supabase, wp_api):
    st.title("Przeglądarka Portali")
    if not supabase: st.stop()
    
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    c_map = {c['name']: c for c in clients_resp.data} if clients_resp.data else {}
    client_name = st.selectbox("Wybierz Projekt (do cennika)", list(c_map.keys())) if c_map else None

    if client_name:
        client = c_map[client_name]
        opts = wp_api.get_portal_options(client['wp_project_id'])
        
        with st.form("browse_form"):
            filters = render_filters_form(opts)
            # Add state to prevent rerun loop if needed, but form submit handles it
            if st.form_submit_button("Załaduj Portale"):
                with st.spinner("Pobieram dane..."):
                    res = wp_api.search_portals(client['wp_project_id'], filters, fetch_all=True)
                    if filters.get('name_search'):
                        q = filters['name_search'].lower()
                        res = [r for r in res if q in r.get('name','').lower() or q in r.get('portal_url','').lower()]
                    st.session_state['browse_res'] = res

        if 'browse_res' in st.session_state:
            res = st.session_state['browse_res']
            st.markdown(f"**Znaleziono**: {len(res)} portali")
            
            if 'expanded_offers' not in st.session_state: st.session_state['expanded_offers'] = set()
            if 'cart_items' not in st.session_state: st.session_state['cart_items'] = []

            # --- HEADER --- 
            h1, h2, h3, h4, h5, h6, h7 = st.columns([2.5, 1, 1, 1, 1, 1, 1.5]) 
            h1.caption("Portal")
            h2.caption("Ruch")
            h3.caption("TF")
            h4.caption("DR")
            h5.caption("Dofollow")
            h6.caption("Cena od")
            h7.caption("Opcje")
            st.divider()

            for r in res:
                pid = r['id']
                with st.container():
                    c1, c2, c3, c4, c5, c6, c7 = st.columns([2.5, 1, 1, 1, 1, 1, 1.5])
                    with c1:
                        st.subheader(r.get('portal_url', ''))
                        subs = []
                        if r.get('portal_score_quality'): subs.append(f"Jakość: {r.get('portal_score_quality')}/10")
                        if r.get('portal_country'): subs.append(r.get('portal_country'))
                        st.caption(" | ".join(subs))
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

                # --- OFFERS ---
                if pid in st.session_state['expanded_offers']:
                    cache_key = f"offers_data_{pid}"
                    if cache_key not in st.session_state:
                         st.session_state[cache_key] = wp_api.get_portal_offers(client['wp_project_id'], pid)
                    
                    my_offers = st.session_state[cache_key]
                    if not my_offers:
                        st.warning("Brak ofert dla tego portalu.")
                    else:
                        for offer in my_offers:
                            u_id = f"{pid}_{offer.get('id', offer['offer_title'])}"
                            in_cart = u_id in [x['unique_id'] for x in st.session_state['cart_items']]
                            
                            with st.container(border=True):
                                action = render_offer_details(offer, u_id, in_cart)
                                if action == "ADD":
                                    st.session_state['cart_items'].append({
                                        "unique_id": u_id, "portal_id": pid, "portal_url": r.get('portal_url'),
                                        "metrics": {"dr": r.get('portal_score_domain_rating')},
                                        "offer": offer, "price": float(offer['best_price']),
                                        "portal_name": r.get('name')
                                    })
                                    st.rerun()
                                elif action == "REMOVE":
                                    st.session_state['cart_items'] = [x for x in st.session_state['cart_items'] if x['unique_id'] != u_id]
                                    st.rerun()
                st.divider()

            # --- FOOTER / CART ---
            if st.session_state['cart_items']:
                with st.expander("🛒 Twoja Lista (Kliknij aby utworzyć kampanię)", expanded=True):
                    st.markdown(f"**Liczba ofert:** {len(st.session_state['cart_items'])}")
                    st.markdown(f"**Łączny koszt:** {sum(x['price'] for x in st.session_state['cart_items']):.2f} PLN")
                    
                    with st.form("final_camp_create"):
                        cname = st.text_input("Nazwa Kampanii", f"Manualna - {client_name}")
                        if st.form_submit_button("Utwórz Kampanię"):
                            camp = supabase.table("campaigns").insert({
                                "client_id": client['id'], "name": cname, 
                                "budget_limit": sum(x['price'] for x in st.session_state['cart_items']), 
                                "status": "planned"
                            }).execute()
                            cid = camp.data[0]['id']
                            
                            items_to_insert = []
                            for ci in st.session_state['cart_items']:
                                o = ci['offer']
                                items_to_insert.append({
                                    "campaign_id": cid, "wp_portal_id": ci['portal_id'],
                                    "portal_name": ci['portal_name'], "portal_url": ci['portal_url'],
                                    "price": ci['price'], "metrics": ci['metrics'],
                                    "status": "planned", "pipeline_status": "planned",
                                    "offer_title": o.get('offer_title'), 
                                    "offer_description": o.get('offer_description')
                                })
                            supabase.table("campaign_items").insert(items_to_insert).execute()
                            st.success("Kampania utworzona pomyślnie!")
                            st.session_state['cart_items'] = []
                            st.rerun()
