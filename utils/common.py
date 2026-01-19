import streamlit as st

#--- HELPERS ---
def get_option_label(options_dict, key, default="-"):
"""
Safely retrieves a label from an options dict (e.g. portal_type) using a string key.
Handles string/int conversion safely.
"""
if options_dict is None: return default
return str(options_dict.get(str(key), default))

def render_offer_row(offer, u_id, options={}, in_cart=False, show_actions=True):
"""
Renders the offer exactly as received from API without translation.
"""
# Layout based on typical data density
cols = st.columns([2, 4, 1, 1, 1, 1])


# 1. Title & URL
with cols[0]:
    st.markdown(f"**{offer.get('offer_title', 'No Title')}**")
    if offer.get('offer_url'):
        st.caption(offer['offer_url'])

# 2. Description & Details (Raw)
with cols[1]:
    # Basic flags
    flags = []
    if offer.get('offer_dofollow') == 1: flags.append("DOFOLLOW")
    else: flags.append("NOFOLLOW")
    
    if offer.get('offer_promoting'):
         flags.append(f"Promo: {offer['offer_promoting']} days")
    
    persistence = offer.get('offer_persistence') # Integer usually
    flags.append(f"Persistence ID: {persistence}")

    st.caption(" | ".join(flags))
    
    # Expandable Description
    with st.expander("Description"):
        st.text(offer.get('offer_description', ''))
        if offer.get('offer_allowed_link_types'):
             st.markdown(f"**Link Types:** {offer['offer_allowed_link_types']}")

# 3. Price
with cols[2]:
    price = float(offer.get('best_price', 0))
    st.markdown(f"**{price:.2f}**")
    if offer.get('promo_discount', 0) > 0:
         st.caption(f"-{offer['promo_discount']}%")

# 4. Metrics/Tech
with cols[3]:
    # Using raw fields from Offer object if available
    # Offer object usually has basic fields, Portal object has metrics. 
    # Here we just show what's in the Offer JSON you pasted.
    req_photo = offer.get('offer_require_photo')
    st.write(f"Req Photo: {req_photo}")

# 5. Tagging
with cols[4]:
    st.write(f"Tagging ID: {offer.get('offer_tagging')}")

# 6. Action
with cols[5]:
    if show_actions:
        if in_cart:
            if st.button("Remove", key=f"del_{u_id}", type="secondary"):
                return "REMOVE"
        else:
            if st.button("Select", key=f"add_{u_id}", type="primary"):
                return "ADD"
return None

def render_filters_form(options):
"""
Generates filters based on the 'options' dictionary provided by the API.
"""
filters = {}

st.subheader("Filters")

with st.expander("Search Parameters", expanded=True):
    """
    Generates filters based on the 'options' dictionary provided by the API.
    """
    filters = {}

    st.subheader("Filters")

    with st.expander("Search Parameters", expanded=True):
        c1, c2, c3 = st.columns(3)
        
        # --- Column 1: Text & Selects ---
        with c1:
            filters['portal_url'] = st.text_input("Portal URL / Name")
            
            # Portal Type
            type_opts = options.get('portal_type', {})
            type_choices = [("All", "All")] + [(k, v) for k, v in type_opts.items()]
            sel_type = st.selectbox("Portal Type", type_choices, format_func=lambda x: x[1])
            filters['portal_type'] = sel_type[0]

            # Portal Country
            country_opts = options.get('portal_country', {})
            country_choices = [("All", "All")] + [(k, v) for k, v in country_opts.items()]
            idx_c = 0
            for i, x in enumerate(country_choices):
                if x[0] == "161": idx_c = i
            sel_country = st.selectbox("Country", country_choices, index=idx_c, format_func=lambda x: x[1])
            filters['portal_country'] = sel_country[0]
            
            # Portal Region (if Poland or just list it)
            reg_opts = options.get('portal_region', {})
            # Region values are dicts in JSON? "1": {"label": "Dolnośląskie", "country": 161}
            # We need to handle that structure or simple KV.
            # User JSON: "1": {"label": "Dolnośląskie", "country": 161}
            # Helper to extract label
            reg_choices = [("All", "All")]
            for k, v in reg_opts.items():
                lab = v.get('label', str(v)) if isinstance(v, dict) else str(v)
                reg_choices.append((k, lab))
                
            sel_reg = st.selectbox("Region", reg_choices, format_func=lambda x: x[1])
            filters['portal_region'] = sel_reg[0]

        # --- Column 2: Metrics & Categories ---
        with c2:
            # Categories
            cat_opts = options.get('portal_category', {})
            filters['categories'] = st.multiselect(
                "Categories", 
                options=list(cat_opts.keys()), 
                format_func=lambda x: cat_opts[x]
            )

            filters['min_traffic'] = st.number_input("Min. Unique Users", step=1000)
            filters['min_dr'] = st.number_input("Min. Domain Rating (DR)", step=1)
            filters['min_tf'] = st.number_input("Min. Trust Flow (TF)", step=1)
            
            # Quality
            qual_opts = options.get('portal_quality', {})
            qual_choices = [("All", "All")] + [(k, v) for k, v in qual_opts.items()]
            sel_q = st.selectbox("Quality", qual_choices, format_func=lambda x: x[1])
            filters['portal_quality'] = sel_q[0]

        # --- Column 3: Price & Other ---
        with c3:
            sc1, sc2 = st.columns(2)
            filters['price_min'] = sc1.number_input("Price Min", value=0, step=10)
            filters['price_max'] = sc2.number_input("Price Max", value=5000, step=10)
            
            # Dofollow
            dof_map = {"All": None, "Yes (1)": "1", "No (0)": "0"}
            dof_sel = st.selectbox("Dofollow", list(dof_map.keys()))
            filters['offer_dofollow'] = dof_map[dof_sel] # Changed key to match API
            
            filters['only_promo'] = st.checkbox("Only Promo Offers")

        # --- Row 2: Offers Specifics ---
        with st.expander("Offer Details Filters"):
            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1:
                # Link Type
                lt_opts = options.get('offer_link_type', {})
                lt_choices = [("All", "All")] + [(k, v) for k, v in lt_opts.items()]
                sel_lt = st.selectbox("Link Type", lt_choices, format_func=lambda x: x[1])
                filters['offer_link_type'] = sel_lt[0]
                
            with r2c2:
                # Persistence
                per_opts = options.get('offer_persistence', {})
                per_choices = [("All", "All")] + [(k, v) for k, v in per_opts.items()]
                sel_per = st.selectbox("Persistence", per_choices, format_func=lambda x: x[1])
                filters['offer_persistence'] = sel_per[0]
                
            with r2c3:
                # Tagging
                tag_opts = options.get('offer_tagging', {})
                tag_choices = [("All", "All")] + [(k, v) for k, v in tag_opts.items()]
                sel_tag = st.selectbox("Article Marking", tag_choices, format_func=lambda x: x[1])
                filters['offer_tagging'] = sel_tag[0]

    return filters
```