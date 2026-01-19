import streamlit as st
import pandas as pd
from datetime import datetime
from utils.common import render_filters_form, render_offer_row

def render(supabase, wp_api):
    st.title("Campaign Generator")
    
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
            
            # Use shared filter form
            filters = render_filters_form(options)
            
            st.markdown("### Strategia i Analiza")
            
            s1, s2 = st.columns(2)
            with s1:
                gen_strategy = st.selectbox("Strategia Generatora", [
                    ("Maksymalizuj Jakość (TF)", "seo_trust_flow"),
                    ("Zbalansowane (DR)", "portal_score_domain_rating"),
                    ("Najniższa Cena", "offer_price_min")
                ], format_func=lambda x: x[0])
            
            with s2:
                # Step 1: Check availability
                if st.form_submit_button("1. Sprawdź dostępność"):
                    st.session_state['check_filters'] = filters
                    st.session_state['check_done'] = True
            
            if st.session_state.get('check_done'):
                # Fetch only 1 item to get meta total
                _, meta_check = wp_api.search_portals(client['wp_project_id'], st.session_state.get('check_filters', filters), page=1, per_page=1)
                total_avail = meta_check.get('total_items', 0)
                st.info(f"Znaleziono {total_avail} portali spełniających kryteria.")
                
                # Step 2: Input Sample Size
                sample_size = st.number_input("Ile portali przeanalizować do strategii? (Im więcej, tym lepiej, ale wolniej)", min_value=10, max_value=500, value=50, step=10)
                
                # Step 3: Generate
                if st.form_submit_button("2. Generuj Propozycję", type="primary"):
                    with st.spinner(f"Pobieranie i analiza {sample_size} portali..."):
                        
                        # Fetch all pages needed to cover sample_size
                        per_page = 50 # Max chunk
                        import math
                        pages_needed = math.ceil(sample_size / per_page)
                        
                        candidates_pool = []
                        for p_idx in range(1, pages_needed + 1):
                            chunk, _ = wp_api.search_portals(
                                client['wp_project_id'], 
                                st.session_state.get('check_filters', filters), 
                                page=p_idx, 
                                per_page=per_page
                            )
                            candidates_pool.extend(chunk)
                            if len(candidates_pool) >= sample_size: break
                        
                        # Trim to sample size
                        candidates_pool = candidates_pool[:sample_size]
                        
                        # Local Sorting
                        sort_key = gen_strategy[1]
                        reverse = True
                        if sort_key == "offer_price_min": reverse = False # Cheapest first
                        
                        # Helper to safely get sort value
                        def get_val(item, key):
                            val = item.get(key)
                            if val is None: return 0
                            try: return float(val)
                            except: return 0

                        candidates_sorted = sorted(candidates_pool, key=lambda x: get_val(x, sort_key), reverse=reverse)
                        
                        # Greedy Selection
                        selected_items = []
                        current_spend = 0
                        
                        for item in candidates_sorted:
                            price = float(item.get('best_price', 0))
                            if price <= 0: continue
                            
                            if current_spend + price <= budget:
                                selected_items.append({
                                    "wp_portal_id": item.get('id'),
                                    "portal_name": item.get('name'),
                                    "portal_url": item.get('portal_url', ''),
                                    "price": price,
                                    "metrics": {
                                        "dr": int(item.get('portal_score_domain_rating', 0)),
                                        "tf": int(item.get('portal_score_trust_flow', 0)),
                                        "uu": item.get('portal_unique_users', 0)
                                    },
                                    "full_data": item
                                })
                                current_spend += price
                        
                        if not selected_items:
                            st.warning("Nie udało się dobrać portali do budżetu.")
                        else:
                            st.session_state['campaign_candidates'] = selected_items
                            st.session_state['gen_meta'] = { "client_id": client['id'], "name": campaign_name, "budget": budget, "wp_project_id": client['wp_project_id'] }
                            st.session_state['check_done'] = False # Reset flow
                            st.rerun()

        # --- SELECTION & TUNING ---
        if st.session_state.get('campaign_candidates'):
            candidates = st.session_state['campaign_candidates']
            meta = st.session_state['gen_meta']
            
            st.divider()
            st.subheader("🛍️ Twoja Kampania")
            st.info("Przejrzyj i dostosuj wybrane oferty.")

            final_list = []
            running_cost = 0
            
            for idx, item in enumerate(candidates):
                pid = item['wp_portal_id']
                p = item['full_data']
                
                title = f"{idx+1}. {item['portal_url']} | DR: {item['metrics']['dr']} | {item['price']:.2f} zł"
                with st.expander(title, expanded=(idx==0)):
                    
                    # 1. Condensed 9-col Info Row
                    # Portal | Type | UU | TF | DR | Dof | Index | Qual | Price
                    cw = [2, 1, 1, 1, 1, 1, 1, 1, 1]
                    cinfo = st.columns(cw)
                    cinfo[0].caption("Portal"); cinfo[0].write(f"**{p.get('portal_url')}**")
                    cinfo[1].caption("Rodzaj"); cinfo[1].write(p.get('portal_type', '-'))
                    cinfo[2].caption("UU"); cinfo[2].write(f"{p.get('portal_unique_users',0):,}")
                    cinfo[3].caption("TF"); cinfo[3].write(p.get('portal_score_trust_flow','-'))
                    cinfo[4].caption("DR"); cinfo[4].write(p.get('portal_score_domain_rating','-'))
                    cinfo[5].caption("Dof."); cinfo[5].write("✅" if p.get('offers_dofollow_count',0)>0 else "❌")
                    cinfo[6].caption("Index"); cinfo[6].write(p.get('indexation_speed', '-'))
                    cinfo[7].caption("Ocena"); cinfo[7].write(f"{p.get('portal_score_quality', '-')}/10")
                    cinfo[8].caption("Cena"); cinfo[8].write(f"{p.get('best_price',0):.2f}")
                    st.divider()
                    
                    # 2. Offer Selection & Tuning
                    cache_key = f"gen_offers_{pid}"
                    if cache_key not in st.session_state:
                         st.session_state[cache_key] = wp_api.get_portal_offers(meta['wp_project_id'], pid)
                    offers = st.session_state[cache_key]
                    
                    sel_o = None
                    if not offers:
                        sel_o = {"offer_title": "Standard", "best_price": item['price'], "offer_description": ""}
                        st.warning("Brak dodatkowych ofert.")
                    else:
                        offer_opts = {}
                        for o in offers:
                            label = f"{o['offer_title']} ({o['best_price']} zł)"
                            offer_opts[label] = o
                        
                        # Heuristic: Pick lowest price if not set, or maintain selection?
                        # Generator logic usually resets, so pick closest price to initial 'item.price'
                        def_key = next((k for k, v in offer_opts.items() if abs(float(v.get('best_price',0)) - item['price']) < 0.1), list(offer_opts.keys())[0])
                        
                        col_sel, _ = st.columns([1, 1])
                        with col_sel:
                             sel_k = st.selectbox("Zmień ofertę:", list(offer_opts.keys()), index=list(offer_opts.keys()).index(def_key), key=f"gen_sel_{pid}")
                             sel_o = offer_opts[sel_k]
                        
                        st.markdown("---")
                        
                        # 3. Render Detail Row
                        # We use 'render_offer_row' but maybe without 'Wybierz' button since the dropdown controls selection?
                        # Or we show button as active "Selected"?
                        # 'show_actions=False' hides the button.
                        render_offer_row(sel_o, u_id="dummy", options=options, in_cart=False, show_actions=False)

                # Add to final list
                final_item = item.copy()
                final_item['price'] = float(sel_o.get('best_price', item['price'])) if sel_o else item['price']
                final_item['offer_title'] = sel_o.get('offer_title') if sel_o else ""
                final_item['offer_description'] = sel_o.get('offer_description') if sel_o else ""
                final_list.append(final_item)
                running_cost += final_item['price']

            st.divider()
            st.metric("Razem", f"{running_cost:.2f} PLN", delta=f"{meta['budget'] - running_cost:.2f} PLN wolne")
            
            if st.button("💾 Zapisz Kampanię", type="primary"):
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
                del st.session_state['campaign_candidates'] # Clear state
                st.rerun()
