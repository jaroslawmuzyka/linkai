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

                # --- NEW: Selection with Offer Details ---
                # Instead of just picking a portal, we might want to pick a portal AND an offer.
                # Since querying offers for ALL portals is expensive (N requests), we probably should allow selecting a portal first to inspect offers.
                # However, the user asked to see offers "next to" domains or select them.
                
                # To balance performance, we keep the main list, and allow expanding details or selecting a "default" offer from the list (which is usually the 'best_price').
                # User request: "Chciałbym móc wybierać to od razu w moim formularzu obok konkretnej domeny."

                # Implementation: We display the main list. User selects portals.
                # BELOW the list, for SELECTED portals, we show the offer selector.
                
                df_disp = []
                for r in res:
                    df_disp.append({
                        "Wybierz": False, "Nazwa": r['name'], "URL": r['portal_url'],
                        "Cena (od)": float(r.get('best_price',0)), "DR": r.get('portal_score_domain_rating'),
                        "id": r['id'], # Keep ID for reference
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
                
                # Filter selected
                sel_rows = edited[edited["Wybierz"]==True]
                
                if not sel_rows.empty:
                    st.divider()
                    st.subheader("🛍️ Wybierz Ofertę dla zaznaczonych portali")
                    
                    # Store selected offers map: portal_id -> selected_offer_obj
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

                            # Format offers for selectbox
                            offer_opts = {f"{o['offer_title']} - {o['best_price']} PLN": o for o in offers}
                            
                            # Default to the one matching 'best_price' if possible
                            default_idx = 0
                            
                            picked_label = st.selectbox(f"Wybierz ofertę dla {r['portal_url']}", list(offer_opts.keys()), key=f"off_{p_id}")
                            if picked_label:
                                selected_offers[p_id] = offer_opts[picked_label]
                                st.caption(f"Opis: {offer_opts[picked_label].get('offer_description', '-')}")

                    if st.button("Utwórz Kampanię z powyższymi ofertami", type="primary"):
                        camp_name = st.text_input("Nazwa Kampanii", f"Manualna {client_name}", key="manual_camp_name")
                        if st.button("Potwierdź Utworzenie"):
                            # Calculate total cost based on SELECTED offers
                            total_cost = 0
                            final_items = []
                            
                            for index, row in sel_rows.iterrows():
                                r = row['_raw']
                                p_id = r['id']
                                
                                if p_id in selected_offers:
                                    offer = selected_offers[p_id]
                                    price = float(offer.get('best_price', 0)) # Or promo_best_price? User sample says best_price.
                                    total_cost += price
                                    
                                    final_items.append({
                                        "wp_portal_id": p_id,
                                        "portal_name": r['name'],
                                        "portal_url": r['portal_url'],
                                        "price": price,
                                        "metrics": {"dr": r.get('portal_score_domain_rating')},
                                        "status": "planned",
                                        "pipeline_status": "planned",
                                        "offer_title": offer.get('offer_title'),   # Store which offer was chosen
                                        # "offer_id": offer.get('id') # If we want to store offer ID
                                    })
                            
                            if final_items:
                                camp = supabase.table("campaigns").insert({
                                    "client_id": client['id'],
                                    "name": camp_name,
                                    "budget_limit": total_cost,
                                    "status": "planned"
                                }).execute()
                                
                                cid = camp.data[0]['id']
                                for item in final_items:
                                    item['campaign_id'] = cid
                                
                                supabase.table("campaign_items").insert(final_items).execute()
                                st.success("Gotowe! Utworzono kampanię z wybranymi ofertami.")
                            else:
                                st.error("Nie wybrano żadnych ofert.")
