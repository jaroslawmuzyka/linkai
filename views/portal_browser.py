import streamlit as st
import pandas as pd
from utils.common import render_filters_form, render_offer_row, get_option_label


def render(supabase, wp_api):
    st.title("Przeglądarka Portali")
    if not supabase: st.stop()
    # Client Selection
    clients_resp = supabase.table("clients").select("id, name, wp_project_id").execute()
    c_map = {c['name']: c for c in clients_resp.data} if clients_resp.data else {}
    client_name = st.selectbox("Select Project", list(c_map.keys())) if c_map else None

    if client_name:
        client = c_map[client_name]
        
        # Fetch Options for Mapping
        opts = wp_api.get_portal_options(client['wp_project_id'])
        
        # --- STATE MANAGEMENT ---
        if 'filters' not in st.session_state: st.session_state['filters'] = {}
        if 'page' not in st.session_state: st.session_state['page'] = 1

        # --- FILTER FORM ---
        with st.form("browse_form"):
            new_filters = render_filters_form(opts)
            if st.form_submit_button("Search"):
                st.session_state['filters'] = new_filters
                st.session_state['page'] = 1
                st.rerun()

        # --- FETCH DATA ---
        with st.spinner("Fetching data..."):
            portals, meta = wp_api.search_portals(
                client['wp_project_id'], 
                st.session_state['filters'], 
                page=st.session_state['page'], 
                per_page=10
            )

        # --- RESULTS ---
        total_rows = meta.get('total_items', 0)
        st.write(f"Results: {len(portals)} (Total: {total_rows})")
        
        if 'expanded_offers' not in st.session_state: st.session_state['expanded_offers'] = set()
        if 'cart_items' not in st.session_state: st.session_state['cart_items'] = []

        # --- GRID HEADER ---
        # URL | Type | Cats | Users | TF | DR | Dof | Price | Action
        w = [2.5, 1.5, 2, 1, 1, 1, 0.8, 1, 1]
        headers = ["URL", "Type", "Categories", "UU", "TF", "DR", "Dof", "Best Price", "Action"]
        cols = st.columns(w)
        for c, h in zip(cols, headers): c.markdown(f"**{h}**")
        st.divider()

        # --- GRID ROWS ---
        for r in portals:
            pid = r.get('id')
            with st.container():
                c = st.columns(w)
                
                # 1. URL
                c[0].write(f"**{r.get('portal_url', 'No URL')}**")
                
                # 2. Type (Map ID to Label)
                type_id = r.get('portal_type')
                type_label = get_option_label(opts.get('portal_type'), type_id, str(type_id))
                c[1].write(type_label)
                
                # 3. Categories (List of IDs -> Labels)
                cat_ids = r.get('portal_categories', []) # Note: API returns 'portal_categories' list
                if isinstance(cat_ids, list):
                    cat_labels = [get_option_label(opts.get('portal_category'), cid, str(cid)) for cid in cat_ids]
                    c[2].caption(", ".join(cat_labels[:3])) # Show max 3
                else:
                    c[2].write("-")
                
                # 4. Users (UU)
                c[3].write(f"{r.get('portal_unique_users', 0):,}")
                
                # 5. TF
                c[4].write(f"{r.get('portal_score_trust_flow', 0)}")
                
                # 6. DR
                c[5].write(f"{r.get('portal_score_domain_rating', 0)}")
                
                # 7. Dofollow (1/0)
                dof = r.get('offer_dofollow')
                c[6].write("✅" if dof == 1 else "❌")
                
                # 8. Price
                c[7].write(f"{r.get('best_price', 0):.2f}")
                
                # 9. Button
                btn_label = "Hide" if pid in st.session_state['expanded_offers'] else "Offers"
                if c[8].button(btn_label, key=f"btn_{pid}"):
                    if pid in st.session_state['expanded_offers']: st.session_state['expanded_offers'].remove(pid)
                    else: st.session_state['expanded_offers'].add(pid)
                    st.rerun()

            # --- NESTED OFFERS ---
            if pid in st.session_state['expanded_offers']:
                st.info(f"Offers for ID: {pid}")
                
                cache_key = f"offers_{pid}"
                if cache_key not in st.session_state:
                     st.session_state[cache_key] = wp_api.get_portal_offers(client['wp_project_id'], pid)
                
                my_offers = st.session_state[cache_key]
                
                if not my_offers:
                    st.warning("No offers found.")
                else:
                    for offer in my_offers:
                        # Construct unique ID for cart
                        u_id = f"{pid}_{offer.get('id')}"
                        in_cart = u_id in [x['unique_id'] for x in st.session_state['cart_items']]
                        
                        action = render_offer_row(offer, u_id, options=opts, in_cart=in_cart, show_actions=True)
                        
                        if action == "ADD":
                            st.session_state['cart_items'].append({
                                "unique_id": u_id, 
                                "portal_id": pid, 
                                "portal_url": r.get('portal_url'),
                                "metrics": {"dr": r.get('portal_score_domain_rating')},
                                "offer_title": offer.get('offer_title'),
                                "price": float(offer.get('best_price', 0))
                            })
                            st.rerun()
                        elif action == "REMOVE":
                            st.session_state['cart_items'] = [x for x in st.session_state['cart_items'] if x['unique_id'] != u_id]
                            st.rerun()
                        
                        st.divider()
            st.markdown("---")

        # --- PAGINATION ---
        total_pages = meta.get('total_pages', 1)
        if total_pages > 1:
            c_prev, c_curr, c_next = st.columns([1, 1, 1])
            if st.session_state['page'] > 1:
                if c_prev.button("Previous"):
                    st.session_state['page'] -= 1
                    st.rerun()
            
            c_curr.markdown(f"<div style='text-align:center'>Page {st.session_state['page']} of {total_pages}</div>", unsafe_allow_html=True)
            
            if st.session_state['page'] < total_pages:
                if c_next.button("Next"):
                    st.session_state['page'] += 1
                    st.rerun()

        # --- CART ---
        if st.session_state['cart_items']:
            with st.sidebar.expander(f"🛒 Cart ({len(st.session_state['cart_items'])})", expanded=True):
                total = sum(x['price'] for x in st.session_state['cart_items'])
                st.write(f"Total: {total:.2f}")
                
                with st.form("create_camp"):
                    name = st.text_input("Campaign Name")
                    if st.form_submit_button("Save Campaign"):
                        # Save logic (simplified)
                        camp = supabase.table("campaigns").insert({
                            "client_id": client['id'], 
                            "name": name, 
                            "budget_limit": total, 
                            "status": "planned"
                        }).execute()
                        cid = camp.data[0]['id']
                        
                        items_db = []
                        for i in st.session_state['cart_items']:
                            items_db.append({
                                "campaign_id": cid,
                                "wp_portal_id": i['portal_id'],
                                "portal_url": i['portal_url'],
                                "price": i['price'],
                                "metrics": i['metrics'],
                                "offer_title": i['offer_title'],
                                "status": "planned",
                                "pipeline_status": "planned"
                            })
                        supabase.table("campaign_items").insert(items_db).execute()
                        st.success("Saved!")
                        st.session_state['cart_items'] = []
                        st.rerun()