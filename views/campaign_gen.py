import streamlit as st
import pandas as pd
from datetime import datetime
from utils.common import render_filters_form, translate_offer_title

def render(supabase, wp_api):
    st.title("Generator Kampanii")
    
    if not supabase: st.stop()
        
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    clients_map = {c['name']: c for c in clients_resp.data} if clients_resp.data else {}
    
    selected_client_name = st.selectbox("Wybierz Klienta", list(clients_map.keys())) if clients_map else None
    
    if selected_client_name:
        client = clients_map[selected_client_name]
        options = wp_api.get_portal_options(client['wp_project_id'])
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        with st.form("campaign_form"):
            c1, c2 = st.columns(2)
            with c1: campaign_name = st.text_input("Nazwa Kampanii", value=f"Kampania {selected_client_name} - {now_str}")
            with c2: budget = st.number_input("Budżet (PLN)", value=2000, step=100)
            filters = render_filters_form(options)
            filters_submit = st.form_submit_button("🔎 Znajdź Portale", type="primary")

        if filters_submit:
            with st.spinner("Przeszukiwanie bazy WhitePress..."):
                portals = wp_api.search_portals(client['wp_project_id'], filters)
                # Filter by name if needed
                if filters.get('name_search'):
                    q = filters['name_search'].lower()
                    portals = [p for p in portals if q in p.get('name', '').lower() or q in p.get('portal_url', '').lower()]
                
                # Logic to pick candidates
                candidates = []
                for p in portals:
                    price = float(p.get('best_price', 0))
                    if price <= 0: continue
                    dr = int(p.get('portal_score_domain_rating', 0))
                    candidates.append({
                        "wp_portal_id": p.get('id'),
                        "portal_name": p.get('name'),
                        "portal_url": p.get('portal_url', ''),
                        "price": price,
                        "metrics": {"dr": dr},
                        "score": (dr * 2) / price
                    })
                candidates.sort(key=lambda x: x['score'], reverse=True)
                
                # Budget Limit
                selected_items = []
                current_spend = 0
                for item in candidates:
                    if current_spend + item['price'] <= budget:
                        selected_items.append(item)
                        current_spend += item['price']
                
                if not selected_items:
                    st.warning("Brak portali spełniających kryteria.")
                else:
                    st.session_state['campaign_candidates'] = selected_items
                    st.session_state['gen_meta'] = { "client_id": client['id'], "name": campaign_name, "budget": budget, "wp_project_id": client['wp_project_id'] }

        # --- SELECTION & OFFER TUNING ---
        if st.session_state.get('campaign_candidates'):
            candidates = st.session_state['campaign_candidates']
            meta = st.session_state['gen_meta']
            
            st.divider()
            st.subheader("🛍️ Dostosuj Ofertę")
            st.info("System automatycznie dobrał najtańszą ofertę. Możesz ją zmienić poniżej.")
            
            final_list = []
            running_cost = 0
            
            for idx, item in enumerate(candidates):
                pid = item['wp_portal_id']
                
                # Cleaner Row
                with st.expander(f"{idx+1}. {item['portal_url']} (DR: {item['metrics']['dr']})", expanded=(idx==0)):
                    col_det, col_sel = st.columns([2, 1])
                    
                    with col_det:
                        st.caption(f"Portal URL: {item['portal_url']}")
                    
                    cache_key = f"gen_offers_{pid}"
                    if cache_key not in st.session_state:
                         st.session_state[cache_key] = wp_api.get_portal_offers(meta['wp_project_id'], pid)
                    offers = st.session_state[cache_key]
                    
                    if not offers:
                        sel_o = {"offer_title": "Standard", "best_price": item['price'], "offer_description": ""}
                        with col_sel: st.write("Brak ofert.")
                    else:
                        # Auto-match (simple logic)
                        offer_opts = {}
                        for o in offers:
                            # Use TRANSLATED title for dropdown
                            label = f"{translate_offer_title(o['offer_title'])} ({o['best_price']} zł)"
                            offer_opts[label] = o
                        
                        # Find closest match
                        def_key = next((k for k, v in offer_opts.items() if abs(float(v.get('best_price',0)) - item['price']) < 0.1), list(offer_opts.keys())[0])
                        
                        with col_sel:
                            sel_k = st.selectbox("Wybierz ofertę", list(offer_opts.keys()), index=list(offer_opts.keys()).index(def_key), key=f"gen_sel_{pid}")
                            sel_o = offer_opts[sel_k]
                            
                        # REMOVED UGLY DESCRIPTION CAPTION
                        # Instead, we can show key attributes if needed, or leave it clean.
                        # User complained "Opis: Number of links..." looked ugly.
                        # Better to show nothing than ugly text in this compacted view.
                        # Or maybe just "Promocja: -X%" if exists.
                        if sel_o.get('promo_discount'):
                             st.success(f"Promocja: -{sel_o['promo_discount']}%")

                # Add to final list
                final_item = item.copy()
                final_item['price'] = float(sel_o.get('best_price', item['price']))
                final_item['offer_title'] = sel_o.get('offer_title')
                final_item['offer_description'] = sel_o.get('offer_description')
                final_list.append(final_item)
                running_cost += final_item['price']

            st.divider()
            st.metric("Całkowity Koszt", f"{running_cost:.2f} PLN", delta=f"{meta['budget'] - running_cost:.2f} PLN wolne")
            
            if st.button("💾 Zapisz Kampanię", type="primary"):
                # Insert
                camp = supabase.table("campaigns").insert({
                    "client_id": meta['client_id'], "name": meta['name'], "budget_limit": running_cost, "status": "planned"
                }).execute()
                cid = camp.data[0]['id']
                db_items = []
                for fi in final_list:
                    db_items.append({
                        "campaign_id": cid, "wp_portal_id": fi['wp_portal_id'], "portal_name": fi['portal_name'],
                        "portal_url": fi['portal_url'], "price": fi['price'], "metrics": fi['metrics'],
                        "status": "planned", "pipeline_status": "planned",
                        "offer_title": fi.get('offer_title'), "offer_description": fi.get('offer_description')
                    })
                supabase.table("campaign_items").insert(db_items).execute()
                st.success("Zapisano!")
                del st.session_state['campaign_candidates']
                st.rerun()
