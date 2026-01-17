import streamlit as st

def render_filters_form(options):
    """
    Renderuje formularz filtrów i zwraca słownik wybranych wartości.
    """
    raw_cats = options.get('portal_category', {})
    if isinstance(raw_cats, list): raw_cats = {}
    
    st.subheader("Filtrowanie Portali")
    
    with st.expander("📊 Ustawienia Filtrów", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            min_dr = st.number_input("Min. Domain Rating (DR)", value=0, key="f_dr")
            min_tf = st.number_input("Min. Trust Flow (TF)", value=0, key="f_tf")
        with col2:
            min_traffic = st.number_input("Min. Ruch (UU)", value=0, key="f_traffic")
            max_price = st.number_input("Max. Cena (PLN)", value=5000, key="f_price")
        with col3:
            selected_categories_ids = st.multiselect(
                "Kategorie", 
                options=list(raw_cats.keys()), 
                format_func=lambda x: f"{raw_cats[x]}",
                key="f_cats"
            )
            dofollow = st.checkbox("Tylko Dofollow", value=False, key="f_dof")
            name_search = st.text_input("Szukaj w nazwie", key="f_search")

    filters = {
        "min_dr": min_dr, "min_tf": min_tf, "min_traffic": min_traffic, "price_max": max_price,
        "categories": selected_categories_ids, "dofollow": dofollow, "name_search": name_search
    }
    return filters
