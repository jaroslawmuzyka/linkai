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

            # --- MODIFICATION: Default campaign name with date and time ---
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
                            "budget": budget
                        }
            
            if 'campaign_candidates' in st.session_state and st.session_state.get('campaign_candidates'):
                sel = st.session_state['campaign_candidates']
                st.divider()
                st.write(f"Wybrano: {len(sel)} portali. Koszt: {sum(x['price'] for x in sel):.2f} PLN")
                st.dataframe(pd.DataFrame(sel)[['portal_name', 'portal_url', 'price', 'metrics']], use_container_width=True)
                
                if st.button("💾 Zapisz Kampanię", type="primary"):
                    meta = st.session_state['gen_meta']
                    camp = supabase.table("campaigns").insert({
                        "client_id": meta['client_id'],
                        "name": meta['name'],
                        "budget_limit": meta['budget'],
                        "status": "planned"
                    }).execute()
                    
                    camp_id = camp.data[0]['id']
                    items_db = []
                    for item in sel:
                        items_db.append({
                            "campaign_id": camp_id,
                            "wp_portal_id": item['wp_portal_id'],
                            "portal_name": item['portal_name'],
                            "portal_url": item['portal_url'],
                            "price": item['price'],
                            "metrics": item['metrics'],
                            "status": "planned",
                            "pipeline_status": "planned"
                        })
                    supabase.table("campaign_items").insert(items_db).execute()
                    st.success("Zapisano kampanię!")
                    del st.session_state['campaign_candidates']
