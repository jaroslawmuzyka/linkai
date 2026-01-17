import streamlit as st
import pandas as pd
from utils.common import render_filters_form, render_offer_row

def render(supabase, wp_api):
    st.title("Przeglądarka Portali")
    if not supabase: st.stop()
    
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    c_map = {c['name']: c for c in clients_resp.data} if clients_resp.data else {}
    client_name = st.selectbox("Wybierz Projekt (do cennika)", list(c_map.keys())) if c_map else None

    if client_name:
        client = c_map[client_name]
        opts = wp_api.get_portal_options(client['wp_project_id'])
        cat_map = opts.get('portal_category', {})
        
        # --- FILTERS STATE ---
        if 'filters' not in st.session_state: st.session_state['filters'] = {}
        if 'page' not in st.session_state: st.session_state['page'] = 1

        with st.form("browse_form"):
            new_filters = render_filters_form(opts)
            if st.form_submit_button("Szukaj"):
                st.session_state['filters'] = new_filters
                st.session_state['page'] = 1 # Reset page on new search
                st.rerun()

        # --- FETCH DATA ---
        with st.spinner("Pobieram dane..."):
            portals, meta = wp_api.search_portals(
                client['wp_project_id'], 
                st.session_state['filters'], 
                page=st.session_state['page'], 
                per_page=20
            )
            
            # Client-side Name Filter (API doesn't flexible-search names usually)
            q_name = st.session_state['filters'].get('name_search', '').lower()
            if q_name:
                portals = [p for p in portals if q_name in p.get('name', '').lower() or q_name in p.get('portal_url', '').lower()]

        # --- RESULTS ---
        st.markdown(f"**Wyniki**: {len(portals)} na tej stronie (Total: {meta.get('total_items', '?')})")
        
        if 'expanded_offers' not in st.session_state: st.session_state['expanded_offers'] = set()
        if 'cart_items' not in st.session_state: st.session_state['cart_items'] = []

        # --- TABLE HEADER (14 Cols) ---
        w = [2, 1, 1, 1.5, 1, 0.8, 0.8, 0.6, 0.8, 0.8, 0.6, 1.2, 1, 1]
        headers = ["Portal", "Rodzaj", "Kraj", "Tematyka", "Użytk.", "TF", "DR", "Dof.", "Indeks", "Widok", "Ocena", "Linki", "Cena", "Opcje"]
        cols = st.columns(w)
        for c, h in zip(cols, headers): c.caption(h)
        st.divider()

        for r in portals:
            pid = r['id']
            with st.container():
                c = st.columns(w)
                
                # Render Row
                c[0].write(f"**{r.get('portal_url', '')}**")
                c[1].write(r.get('portal_type', '-'))
                locs = [x for x in [r.get('portal_country')] if x]
                c[2].write("/".join(locs) if locs else "-")
                
                cats = r.get('portal_category', [])
                cat_txt = str(cat_map.get(str(cats[0]), cats[0])) if (isinstance(cats, list) and cats) else "-"
                c[3].write(cat_txt)
                
                c[4].write(f"{r.get('portal_unique_users', 0):,}")
                # Removed AS (Authority Score) and DA (Moz Domain Authority)
                c[5].write(f"{r.get('portal_score_trust_flow', '-')}")
                c[6].write(f"{r.get('portal_score_domain_rating', '-')}")
                c[7].write("✅" if r.get('offers_dofollow_count', 0) > 0 else "❌")
                c[8].write(f"{r.get('indexation_speed', '-')}") 
                c[9].write(f"{r.get('visibility_senuto', '-')}")
                c[10].write(f"{r.get('portal_score_quality', '-')}/10")
                c[11].write("Mieszane") 
                c[12].write(f"**{r.get('best_price', 0):.2f}**")
                
                if c[13].button("Wybierz ofertę", key=f"btn_{pid}"):
                    if pid in st.session_state['expanded_offers']: st.session_state['expanded_offers'].remove(pid)
                    else: st.session_state['expanded_offers'].add(pid)
                    st.rerun()

            if pid in st.session_state['expanded_offers']:
                # Nested Offer Table
                st.info("Oferty dla wybranego portalu:")
                
                oh_w = [1.5, 3.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 1]
                oh_n = ["Nazwa", "Opis", "Cena", "Dł. prom.", "Pisanie", "Oznacz.", "Dofollow", "Ruch", "Trwałość", "Wybór"]
                oh_cols = st.columns(oh_w)
                for oc, oh in zip(oh_cols, oh_n): oc.caption(oh)
                st.markdown("---")
                
                cache_key = f"offers_data_{pid}"
                if cache_key not in st.session_state:
                        st.session_state[cache_key] = wp_api.get_portal_offers(client['wp_project_id'], pid)
                
                my_offers = st.session_state[cache_key]
                if not my_offers:
                    st.warning("Brak ofert.")
                else:
                    for offer in my_offers:
                        u_id = f"{pid}_{offer.get('id', offer['offer_title'])}"
                        in_cart = u_id in [x['unique_id'] for x in st.session_state['cart_items']]
                        with st.container():
                            action = render_offer_row(offer, u_id, in_cart, show_actions=True)
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
            st.divider()

        # --- PAGINATION CONTROLS ---
        if meta['total_pages'] > 1:
            c_prev, c_info, c_next = st.columns([1, 2, 1])
            with c_prev:
                if st.session_state['page'] > 1:
                    if st.button("⬅️ Poprzednia"):
                        st.session_state['page'] -= 1
                        st.rerun()
            with c_info:
                st.markdown(f"<div style='text-align: center'>Strona {st.session_state['page']} z {meta['total_pages']}</div>", unsafe_allow_html=True)
            with c_next:
                if st.session_state['page'] < meta['total_pages']:
                    if st.button("Następna ➡️"):
                        st.session_state['page'] += 1
                        st.rerun()

        # --- CART ---
        if st.session_state['cart_items']:
            with st.expander("🛒 Koszyk Kampanii", expanded=True):
                st.markdown(f"**Oferty**: {len(st.session_state['cart_items'])} | **Razem**: {sum(x['price'] for x in st.session_state['cart_items']):.2f} PLN")
                
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
                            items_to_insert.append({
                                "campaign_id": cid, "wp_portal_id": ci['portal_id'],
                                "portal_name": ci['portal_name'], "portal_url": ci['portal_url'],
                                "price": ci['price'], "metrics": ci['metrics'],
                                "status": "planned", "pipeline_status": "planned",
                                "offer_title": ci['offer']['offer_title'], "offer_description": ci['offer']['offer_description']
                            })
                        supabase.table("campaign_items").insert(items_to_insert).execute()
                        st.success("Kampania utworzona!")
                        st.session_state['cart_items'] = []
                        st.rerun()
