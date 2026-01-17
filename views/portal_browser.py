import streamlit as st
import pandas as pd
from utils.common import render_filters_form

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
                        
                        # Client-side filtering for things not in API
                        if filters.get('name_search'):
                            query = filters['name_search'].lower()
                            res = [r for r in res if query in r.get('name','').lower() or query in r.get('portal_url','').lower()]
                        
                        st.session_state['browse_res'] = res
            
            # --- WIDOK LISTY (ROW LAYOUT) ---
            if 'browse_res' in st.session_state:
                res = st.session_state['browse_res']
                st.markdown(f"**Znaleziono**: {len(res)} portali")
                
                # Setup session state for expanded rows if not exists
                if 'expanded_offers' not in st.session_state:
                    st.session_state['expanded_offers'] = set()
                
                # Header Row
                h1, h2, h3, h4, h5, h6, h7 = st.columns([2.5, 1, 1, 1, 1, 1, 1.5]) 
                h1.caption("Portal")
                h2.caption("Ruch (UU)")
                h3.caption("Trust Flow")
                h4.caption("Domain Rating")
                h5.caption("Dofollow")
                h6.caption("Cena od")
                h7.caption("Akcja")
                st.divider()
                
                # Initialize cart for manual campaign creation (if not exists)
                if 'cart_items' not in st.session_state:
                    st.session_state['cart_items'] = []

                # Pagination (Logic simplified: show first 50 or allow paging? Streamlit slow with many widgets)
                # Let's show all for now, but assume user knows limits.
                
                for idx, r in enumerate(res):
                    pid = r['id']
                    
                    # Row Layout
                    with st.container():
                        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.5, 1, 1, 1, 1, 1, 1.5])
                        
                        # C1: Portal Info (Name hidden per request? user said "remove portal_name because useless", but implies Domain is key)
                        # Display Domain prominently.
                        with c1:
                            st.subheader(r.get('portal_url', ''))
                            # Tag badges
                            ctags = []
                            if r.get('portal_score_quality'): ctags.append(f"Jakość: {r.get('portal_score_quality')}/10")
                            if r.get('portal_country'): ctags.append(r.get('portal_country'))
                            if ctags: st.caption(" | ".join(ctags))

                        with c2: st.write(f"{r.get('portal_unique_users', 0):,}")
                        with c3: st.write(f"{r.get('portal_score_trust_flow', '-')}")
                        with c4: st.write(f"{r.get('portal_score_domain_rating', '-')}")
                        
                        # Dofollow Icon
                        with c5:
                            # Usually dofollow is offer specific, but portal might have general flag
                            st.write("✅" if r.get('offers_dofollow_count', 0) > 0 else "❌")
                        
                        with c6: st.write(f"**{r.get('best_price', 0):.2f} zł**")
                        
                        # Action Button
                        with c7:
                            # Toggle button for offers
                            is_expanded = pid in st.session_state['expanded_offers']
                            btn_label = "Ukryj oferty" if is_expanded else "Zobacz oferty"
                            if st.button(btn_label, key=f"btn_exp_{pid}"):
                                if is_expanded:
                                    st.session_state['expanded_offers'].discard(pid)
                                else:
                                    st.session_state['expanded_offers'].add(pid)
                                st.rerun()

                    # --- EXPANDED OFFERS SECTION ---
                    if pid in st.session_state['expanded_offers']:
                        with st.container():
                            st.info(f"Oferty dla {r.get('portal_url')}")
                            # Fetch offers logic (cached)
                            cache_key = f"offers_data_{pid}"
                            if cache_key not in st.session_state:
                                st.session_state[cache_key] = wp_api.get_portal_offers(client['wp_project_id'], pid)
                            
                            my_offers = st.session_state[cache_key]
                            
                            if not my_offers:
                                st.warning("Brak ofert.")
                            else:
                                # Render Table-like layout for offers
                                # Cols: Name/Desc | Price | Duration | Dofollow | Action
                                oh1, oh2, oh3, oh4, oh5 = st.columns([4, 1, 1, 1, 1])
                                oh1.caption("Nazwa / Opis")
                                oh2.caption("Cena")
                                oh3.caption("Trwałość")
                                oh4.caption("Link")
                                oh5.caption("Wybór")
                                
                                for offer in my_offers:
                                    with st.container():
                                        oc1, oc2, oc3, oc4, oc5 = st.columns([4, 1, 1, 1, 1])
                                        with oc1:
                                            st.write(f"**{offer['offer_title']}**")
                                            desc_parts = []
                                            if offer.get('promo_discount'): desc_parts.append(f"PROMO -{offer['promo_discount']}%")
                                            if offer.get('offer_description'): desc_parts.append(offer['offer_description'][:100] + "...")
                                            st.caption(" | ".join(desc_parts))
                                        
                                        with oc2: st.write(f"{offer['best_price']} zł")
                                        with oc3: st.write(f"{offer.get('offer_persistence_custom', '-')}")
                                        with oc4: st.write("Dofollow" if offer.get('offer_dofollow') else "Nofollow")
                                        
                                        with oc5:
                                            # Check if in cart
                                            cart_ids = [x['unique_id'] for x in st.session_state['cart_items']]
                                            # Unique ID for cart item = pid + offer_id (if offer has ID) or random
                                            # Let's assume pid + offer_title is unique enough for now
                                            u_id = f"{pid}_{offer.get('id', offer['offer_title'])}"
                                            
                                            if u_id in cart_ids:
                                                if st.button("Usuń", key=f"del_{u_id}"):
                                                    st.session_state['cart_items'] = [x for x in st.session_state['cart_items'] if x['unique_id'] != u_id]
                                                    st.rerun()
                                            else:
                                                if st.button("Wybierz", key=f"add_{u_id}"):
                                                    st.session_state['cart_items'].append({
                                                        "unique_id": u_id,
                                                        "portal_id": pid,
                                                        "portal_url": r.get('portal_url'),
                                                        "portal_name": r.get('name'), # Keep for DB
                                                        "metrics": {"dr": r.get('portal_score_domain_rating')},
                                                        "offer": offer,
                                                        "price": float(offer['best_price'])
                                                    })
                                                    st.rerun()
                                        st.divider()

                    st.markdown("---") # Row separator
                
                # --- CART / CHECKOUT BAR ---
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
                                        # Add offer_id when DB supports it
                                    })
                                supabase.table("campaign_items").insert(db_items).execute()
                                st.success("Kampania utworzona!")
                                st.session_state['cart_items'] = [] # clear
                                st.rerun()
