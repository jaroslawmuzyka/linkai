import streamlit as st
import pandas as pd
from datetime import datetime
from utils.common import render_filters_form

def render(supabase, wp_api):
    st.title("Generator Kampanii")
    
    if not supabase: st.stop()
        
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    if not clients_resp.data:
        st.warning("Brak klientów.")
    else:
        clients_map = {c['name']: c for c in clients_resp.data}
        selected_client_name = st.selectbox("Wybierz Klienta", list(clients_map.keys()))
        
        if selected_client_name:
            client = clients_map[selected_client_name]
            
            with st.spinner("Pobieranie opcji..."):
                options = wp_api.get_portal_options(client['wp_project_id'])

            now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            default_camp_name = f"Kampania {selected_client_name} - {now_str}"

            with st.form("campaign_form"):
                c1, c2 = st.columns(2)
                with c1:
                    campaign_name = st.text_input("Nazwa Kampanii", value=default_camp_name)
                with c2:
                    budget = st.number_input("Budżet (PLN)", value=2000, step=100)

                filters = render_filters_form(options)
                filters_submit = st.form_submit_button("🔎 Znajdź Portale", type="primary")

            if filters_submit:
                with st.spinner("Przeszukiwanie bazy WhitePress..."):
                    portals = wp_api.search_portals(client['wp_project_id'], filters)
                    
                    if filters.get('name_search'):
                        query = filters['name_search'].lower()
                        portals = [p for p in portals if query in p.get('name', '').lower() or query in p.get('portal_url', '').lower()]
                    
                    candidates = []
                    for p in portals:
                        price = float(p.get('best_price', 0))
                        if price <= 0: continue
                        
                        dr = int(p.get('portal_score_domain_rating', 0))
                        score = ((dr * 2)) / price
                        
                        candidates.append({
                            "wp_portal_id": p.get('id'),
                            "portal_name": p.get('name', 'Nieznany'),
                            "portal_url": p.get('portal_url', ''),
                            "price": price,
                            "metrics": {"dr": dr},
                            "score": score
                        })
                    
                    candidates.sort(key=lambda x: x['score'], reverse=True)
                    
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
                        st.session_state['gen_meta'] = {
                            "client_id": client['id'],
                            "name": campaign_name,
                            "budget": budget,
                            "wp_project_id": client['wp_project_id'] 
                        }
            
            # --- OFFER SELECTION LOGIC ---
            if 'campaign_candidates' in st.session_state and st.session_state.get('campaign_candidates'):
                candidates = st.session_state['campaign_candidates']
                meta = st.session_state['gen_meta']
                
                st.divider()
                st.subheader("🛍️ Dostosuj Oferty")
                
                # We need to track actual selected offers. Initialize if not present.
                if 'selected_offers_map' not in st.session_state:
                    st.session_state['selected_offers_map'] = {}
                
                total_cost = 0
                final_list = []
                
                for idx, item in enumerate(candidates):
                    pid = item['wp_portal_id']
                    pname = item['portal_name']
                    
                    with st.expander(f"{idx+1}. {pname} ({item['portal_url']}) - {item['price']} PLN", expanded=False):
                        # Fetch items lazily if not already done? 
                        # For better UX, we assume user wants to see options. But fetching 50 portals * 1 req = Slow.
                        # Solution: Fetch offers ONLY when expanded OR for top X?
                        # User wants to chose "right away".
                        # Let's try fetching offers for ALL candidates (usually < 20 in a campaign)
                        
                        # Cache offers in session state to avoid refetching on rerun
                        cache_key = f"offers_{pid}"
                        if cache_key not in st.session_state:
                             st.session_state[cache_key] = wp_api.get_portal_offers(meta['wp_project_id'], pid)
                        
                        offers = st.session_state[cache_key]
                        
                        if not offers:
                            st.warning("Brak ofert.")
                            current_price = item['price']
                            offer_title = "Standard"
                            offer_desc = "-"
                        else:
                            # Map offers for selectbox
                            # Default: find one closely matching the item['price'] (which is best_price)
                            # Logic: item['price'] came from 'best_price'
                            
                            offer_opts = {f"{o['offer_title']} ({o['best_price']} PLN)": o for o in offers}
                            
                            # Try to find default key
                            default_key = list(offer_opts.keys())[0]
                            for k, v in offer_opts.items():
                                if abs(float(v.get('best_price', 0)) - item['price']) < 0.01:
                                    default_key = k
                                    break
                                    
                            selected_key = st.selectbox("Wybierz ofertę:", list(offer_opts.keys()), index=list(offer_opts.keys()).index(default_key), key=f"sel_{pid}")
                            
                            sel_offer = offer_opts[selected_key]
                            current_price = float(sel_offer.get('best_price', 0))
                            offer_title = sel_offer.get('offer_title')
                            offer_desc = sel_offer.get('offer_description')
                            
                            st.info(f"Typ: {sel_offer.get('offer_allowed_link_types', '-')}")
                            if sel_offer.get('promo_discount'):
                                st.success(f"Promocja: {sel_offer.get('promo_discount')}%")

                    # Add to list with UPDATED price/offer info
                    item_copy = item.copy()
                    item_copy['price'] = current_price
                    item_copy['offer_title'] = offer_title
                    item_copy['offer_description'] = offer_desc
                    # item_copy['offer_id'] = sel_offer.get('id') if 'sel_offer' in locals() else None
                    
                    final_list.append(item_copy)
                    total_cost += current_price

                st.divider()
                st.metric("Całkowity Koszt", f"{total_cost:.2f} PLN", delta=f"{meta['budget'] - total_cost:.2f} PLN pozostalo")
                
                # Show summary
                st.dataframe(pd.DataFrame(final_list)[['portal_name', 'offer_title', 'price']], use_container_width=True)

                if st.button("💾 Zapisz Kampanię", type="primary"):
                    camp = supabase.table("campaigns").insert({
                        "client_id": meta['client_id'],
                        "name": campaign_name, # Use the input from form (might need to persist it if form clears)
                        # Re-read name from input? Form inputs are tricky on rerun. 
                        # Actually 'campaign_name' variable is available from the top scope if not inside form submit block? 
                        # Wait, 'campaign_name' is defined inside form. We stored it in meta, but user might have changed it?
                        # For simplicity, use meta['name'] or ask user to re-confirm if needed. 
                        # Let's hope meta['name'] is good enough or we add a text input here.
                        "budget_limit": total_cost,
                        "status": "planned"
                    }).execute()
                    
                    camp_id = camp.data[0]['id']
                    items_db = []
                    for item in final_list:
                        items_db.append({
                            "campaign_id": camp_id,
                            "wp_portal_id": item['wp_portal_id'],
                            "portal_name": item['portal_name'],
                            "portal_url": item['portal_url'],
                            "price": item['price'],
                            "metrics": item['metrics'],
                            "status": "planned",
                            "pipeline_status": "planned",
                            "offer_title": item.get('offer_title'),
                            "offer_description": item.get('offer_description'),
                            # "offer_id": item.get('offer_id')
                        })
                    supabase.table("campaign_items").insert(items_db).execute()
                    st.success("Zapisano kampanię i wybrane oferty!")
                    
                    # Cleanup
                    del st.session_state['campaign_candidates']
                    keys_to_del = [k for k in st.session_state.keys() if k.startswith("offers_")]
                    for k in keys_to_del: del st.session_state[k]
