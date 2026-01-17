import streamlit as st
import pandas as pd

def render(supabase, wp_api):
    st.title("Publikacja w WhitePress")
    if not supabase: st.stop()
    
    # Pobieramy tylko gotowe
    items = supabase.table("campaign_items").select("*, campaigns(name)").eq("pipeline_status", "content_ready").execute()
    
    if not items.data:
        st.info("Brak gotowych artykułów do publikacji.")
    else:
        # Group by Campaign
        grouped = {}
        for item in items.data:
            c_name = item['campaigns']['name'] if item.get('campaigns') else "Bez kampanii"
            if c_name not in grouped: grouped[c_name] = []
            grouped[c_name].append(item)
            
        st.write(f"Do publikacji: {len(items.data)} art. w {len(grouped)} kampaniach.")
        
        for camp_name, camp_items in grouped.items():
            with st.expander(f"📦 {camp_name} ({len(camp_items)})", expanded=True):
                # Bulk Action per campaign
                if st.button(f"🚀 Opublikuj WSZYSTKIE z: {camp_name}", key=f"bulk_{camp_name}"):
                    progress = st.progress(0)
                    for idx, i in enumerate(camp_items):
                        wp_api.publish_article(123, i['wp_portal_id'], i['topic'], i.get('content_html') or i.get('content'))
                        supabase.table("campaign_items").update({"pipeline_status": "published", "status": "published"}).eq("id", i['id']).execute()
                        progress.progress((idx+1)/len(camp_items))
                    st.success(f"Wysłano {len(camp_items)} artykułów!")
                    st.rerun()

                st.markdown("---")
                # Individual Items
                for i in camp_items:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.subheader(i['topic'])
                        st.caption(f"Portal: {i['portal_url']}")
                        st.text_area("HTML Podgląd", i.get('content_html') or i.get('content'), height=100, key=f"txt_{i['id']}")
                    with col2:
                        if st.button(f"Opublikuj", key=f"pub_{i['id']}"):
                            wp_api.publish_article(123, i['wp_portal_id'], i['topic'], i.get('content_html') or i.get('content'))
                            supabase.table("campaign_items").update({"pipeline_status": "published", "status": "published"}).eq("id", i['id']).execute()
                            st.success("Wysłano!")
                            st.rerun()
                    st.divider()
