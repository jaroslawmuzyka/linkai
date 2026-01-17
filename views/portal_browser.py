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
                if st.form_submit_button("Załaduj"):
                    res = wp_api.search_portals(client['wp_project_id'], filters, fetch_all=True)
                    if filters.get('name_search'):
                        query = filters['name_search'].lower()
                        res = [r for r in res if query in r.get('name','').lower() or query in r.get('portal_url','').lower()]
                    
                    st.session_state['browse_res'] = res
            
            if 'browse_res' in st.session_state:
                res = st.session_state['browse_res']
                st.write(f"Wyników: {len(res)}")

                df_disp = []
                for r in res:
                    df_disp.append({
                        "Wybierz": False, "Nazwa": r['name'], "URL": r['portal_url'],
                        "Cena (od)": float(r.get('best_price',0)), "DR": r.get('portal_score_domain_rating'),
                        "id": r['id'], 
                        "_raw": r
                    })
                
                edited = st.data_editor(
                    pd.DataFrame(df_disp), 
                    column_config={
                        "Wybierz": st.column_config.CheckboxColumn(required=True), 
                        "_raw": None,
                        "id": None 
                    }, 
                    hide_index=True
                )
                
                sel_rows = edited[edited["Wybierz"]==True]
                
                if not sel_rows.empty:
                    st.divider()
                    st.subheader("🛍️ Wybierz Ofertę dla zaznaczonych portali")
                    
                    selected_offers = {}
                    
                    for index, row in sel_rows.iterrows():
                        r = row['_raw']
                        p_id = r['id']
                        p_name = r['name']
                        
                        with st.expander(f"Oferty dla: {p_name} ({r['portal_url']})", expanded=True):
                            # Fetch offers
                            offers = wp_api.get_portal_offers(client['wp_project_id'], p_id)
                            
                            if not offers:
                                st.warning("Brak dostępnych ofert.")
                                continue

                            # Enhanced Display Options
                            offer_opts = {}
                            for o in offers:
                                # Build a clear label
                                promo_text = f" [PROMO {o['promo_discount']}%]" if o.get('promo_discount') else ""
                                dofollow = "Dofollow" if o.get('offer_dofollow') else "Nofollow"
                                label = f"{o['offer_title']} | {o['best_price']} PLN | {dofollow}{promo_text}"
                                offer_opts[label] = o

                            
                            # Default to checking if there is a 'best_price' match or just first
                            default_idx = 0
                            
                            picked_label = st.selectbox(f"Wybierz ofertę dla {r['portal_url']}", list(offer_opts.keys()), key=f"off_{p_id}")
                            
                            if picked_label:
                                o = offer_opts[picked_label]
                                selected_offers[p_id] = o
                                
                                # Show details
                                c1, c2 = st.columns(2)
                                c1.caption(f"Opis: {o.get('offer_description', '-')}")
                                c2.caption(f"Trwałość: {o.get('offer_persistence_custom') or o.get('offer_persistence')} | Linki: {o.get('offer_allowed_link_types')}")

                    # --- Manual Campaign Creation Form ---
                    with st.form("manual_create_camp"):
                        camp_name_input = st.text_input("Nazwa Kampanii", f"Manualna {client_name}")
                        submit_camp = st.form_submit_button("Utwórz Kampanię z powyższymi ofertami")

                        if submit_camp:
                            # Calculate total cost based on SELECTED offers
                            total_cost = 0
                            final_items = []
                            
                            for index, row in sel_rows.iterrows():
                                r = row['_raw']
                                p_id = r['id']
                                
                                if p_id in selected_offers:
                                    offer = selected_offers[p_id]
                                    price = float(offer.get('best_price', 0))
                                    total_cost += price
                                    
                                    final_items.append({
                                        "wp_portal_id": p_id,
                                        "portal_name": r['name'],
                                        "portal_url": r['portal_url'],
                                        "price": price,
                                        "metrics": {"dr": r.get('portal_score_domain_rating')},
                                        "status": "planned",
                                        "pipeline_status": "planned",
                                        "offer_title": offer.get('offer_title'),
                                        "offer_description": offer.get('offer_description'),
                                        # "offer_id": offer.get('id')
                                    })
                            
                            if final_items:
                                camp = supabase.table("campaigns").insert({
                                    "client_id": client['id'],
                                    "name": camp_name_input,
                                    "budget_limit": total_cost,
                                    "status": "planned"
                                }).execute()
                                
                                cid = camp.data[0]['id']
                                for item in final_items:
                                    item['campaign_id'] = cid
                                
                                supabase.table("campaign_items").insert(final_items).execute()
                                st.success("Gotowe! Utworzono kampanię z wybranymi ofertami.")
                            else:
                                st.error("Nie wybrano ofert dla żadnego z zaznaczonych portali.")
