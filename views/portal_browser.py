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
        
        with st.form("browse_form"):
            filters = render_filters_form(opts)
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

            # --- COLUMN DEFINITION (16 Columns) ---
            # 1. Portal, 2. Rodzaj, 3. Kraj/Reg, 4. Tematyka, 5. UU, 6. AS, 7. TF, 8. DR, 9. DA, 10. Dofollow, 11. Indeks, 12. Widok, 13. Ocena, 14. Linki, 15. Cena, 16. Action
            # Total ~26 units
            w = [2, 1, 1, 1.5, 1, 0.8, 0.8, 0.8, 0.8, 0.6, 0.8, 0.8, 0.6, 1.2, 1, 1]
            
            headers = [
                "Portal", "Rodzaj", "Kraj/Reg", "Tematyka", 
                "Użytk.", "AS", "TF", "DR", "DA", 
                "Dof.", "Indeks", "Widok", "Ocena", "Linki", "Cena", "Opcje"
            ]
            cols = st.columns(w)
            for c, h in zip(cols, headers): 
                c.caption(h)
            st.divider()

            for r in res:
                pid = r['id']
                with st.container():
                    c = st.columns(w)
                    
                    # 1. Portal
                    c[0].write(f"**{r.get('portal_url', '')}**")
                    # 2. Rodzaj
                    c[1].write(r.get('portal_type', '-'))
                    # 3. Kraj / Region
                    locs = [x for x in [r.get('portal_country')] if x]
                    c[2].write("/".join(locs) if locs else "-")
                    # 4. Tematyka
                    cats = r.get('portal_category', [])
                    if isinstance(cats, list) and cats: 
                         c[3].write(str(cat_map.get(str(cats[0]), cats[0])))
                    else: 
                         c[3].write("-")
                    # 5. UU
                    c[4].write(f"{r.get('portal_unique_users', 0):,}")
                    # 6. AS
                    c[5].write(f"{r.get('portal_score_authority_score', '-')}")
                    # 7. TF
                    c[6].write(f"{r.get('portal_score_trust_flow', '-')}")
                    # 8. DR
                    c[7].write(f"{r.get('portal_score_domain_rating', '-')}")
                    # 9. DA
                    c[8].write(f"{r.get('portal_score_moz_domain_authority', '-')}")
                    # 10. Dofollow
                    c[9].write("✅" if r.get('offers_dofollow_count', 0) > 0 else "❌")
                    # 11. Indeksacja
                    c[10].write(f"{r.get('indexation_speed', '-')}") 
                    # 12. Widoczność
                    c[11].write(f"{r.get('visibility_senuto', '-')}")
                    # 13. Ocena
                    c[12].write(f"{r.get('portal_score_quality', '-')}/10")
                    # 14. Rodzaj linków
                    c[13].write("Mieszane") 
                    # 15. Cena
                    price = r.get('best_price', 0)
                    c[14].write(f"**{price:.2f}**")
                    
                    # 16. Button (Wybierz ofertę -> Expand)
                    is_expanded = pid in st.session_state['expanded_offers']
                    if c[15].button("Wybierz ofertę", key=f"btn_{pid}"):
                        if is_expanded: st.session_state['expanded_offers'].discard(pid)
                        else: st.session_state['expanded_offers'].add(pid)
                        st.rerun()

                # --- OFFERS (Expanded Table) ---
                if pid in st.session_state['expanded_offers']:
                    st.info("Oferty dla wybranego portalu:")
                    
                    # Headers for Offer Table
                    # Name, Desc, Price, Duration, Writing, Marking, Dofollow, Traffic, Persistence, Action
                    oh_w = [1.5, 3.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 1]
                    oh_n = ["Nazwa oferty", "Opis oferty", "Cena netto", "Dł. promocji", "Napisanie Art.", "Oznaczanie", "Linki Dofollow", "Gwarancja Ruchu", "Trwałość", "Wybór"]
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
                            
                            with st.container(): # Or no container to keep it table-like tight
                                action = render_offer_row(offer, u_id, in_cart, show_actions=True)
                                if action == "ADD":
                                    st.session_state['cart_items'].append({
                                        "unique_id": u_id,
                                        "portal_id": pid,
                                        "portal_url": r.get('portal_url'),
                                        "metrics": {"dr": r.get('portal_score_domain_rating')},
                                        "offer": offer,
                                        "price": float(offer['best_price']),
                                        "portal_name": r.get('name')
                                    })
                                    st.rerun()
                                elif action == "REMOVE":
                                    st.session_state['cart_items'] = [x for x in st.session_state['cart_items'] if x['unique_id'] != u_id]
                                    st.rerun()
                            st.divider()
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
