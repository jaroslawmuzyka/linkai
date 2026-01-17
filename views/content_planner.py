import streamlit as st
import pandas as pd
import time
from services.dify import run_dify_workflow, clean_and_parse_json

def render(supabase):
    st.title("Planowanie Treści 🏭")
    st.info("Zarządzaj procesem generowania treści dla wielu artykułów jednocześnie.")
    
    if not supabase: st.stop()
    
    # --- MODIFICATION: Fetch ALL campaigns ---
    # Pagination might be needed if hundreds of campaigns, but let's increase limit first.
    camps_resp = supabase.table("campaigns").select("id, name").order("created_at", desc=True).limit(100).execute()
    camps = camps_resp.data
    
    if not camps:
        st.warning("Brak kampanii.")
        st.stop()
    
    camp_map = {c['name']: c['id'] for c in camps}
    
    # --- MODIFICATION: Default to None ---
    sel_camp = st.selectbox("Wybierz Kampanię", ["-- Wszystkie --"] + list(camp_map.keys()), index=0)
    
    items_query = supabase.table("campaign_items").select("*").order("id")
    
    if sel_camp != "-- Wszystkie --":
        camp_id = camp_map[sel_camp]
        items_query = items_query.eq("campaign_id", camp_id)
        
    items = items_query.execute().data
    
    if not items:
        st.warning("Brak artykułów.")
        return # Exit if empty

    # PRZYGOTOWANIE TABELI DO EDYCJI
    df = pd.DataFrame(items)
    
    if "Wybierz" not in df.columns:
        df.insert(0, "Wybierz", False)
    
    # Check for new columns compatibility (graceful fallback)
    # status_research, status_structure, status_brief, status_writing
    new_cols = ["status_research", "status_structure", "status_brief", "status_writing"]
    for nc in new_cols:
        if nc not in df.columns:
            df[nc] = "pending" # Default if DB not updated yet (though we asked user to)

    cols_needed = ["id", "portal_url", "topic", "language", "pipeline_status", "extra_instructions", "frazy_senuto"]
    for c in cols_needed:
        if c not in df.columns: df[c] = None

    # Konfiguracja edytora
    col_config = {
        "Wybierz": st.column_config.CheckboxColumn(required=True),
        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "topic": st.column_config.TextColumn("Temat / Fraza Główna", width="large", required=True),
        "portal_url": st.column_config.TextColumn("Portal", disabled=True),
        "pipeline_status": None, # Hide global status, use granular
        "language": st.column_config.SelectboxColumn("Język", options=["pl", "en", "de"], default="pl", required=True),
        "extra_instructions": st.column_config.TextColumn("Instrukcje"),
        
        # New Granular Status Columns
        "status_research": st.column_config.TextColumn("Research Status", disabled=True),
        "status_structure": st.column_config.TextColumn("Structure Status", disabled=True),
        "status_brief": st.column_config.TextColumn("Brief Status", disabled=True),
        "status_writing": st.column_config.TextColumn("Writing Status", disabled=True),

        # Hidden cols
        "knowledge_graph": None, "info_graph": None, "content_brief": None, "content_html": None,
        "headings_extended": None, "headings_h2": None, "headings_questions": None, "headings_final": None,
        "keywords_serp": None, "frazy_senuto": None, 
        "created_at": None, "campaign_id": None, "wp_portal_id": None, 
        "portal_name": None, "price": None, "metrics": None, "status": None, "content": None
    }
    
    st.caption("Zaznacz artykuły (checkbox po lewej) i kliknij przycisk akcji na dole.")
    
    edited_df = st.data_editor(
        df, 
        column_config=col_config, 
        hide_index=True, 
        use_container_width=True, 
        key="mass_editor",
        disabled=["id", "portal_url", "status_research", "status_structure", "status_brief", "status_writing"]
    )
    
    if st.button("💾 Zapisz zmiany (Temat/Język/Instrukcje)"):
        changes = 0
        for index, row in edited_df.iterrows():
            orig = next((x for x in items if x['id'] == row['id']), None)
            if orig and (orig['topic'] != row['topic'] or orig['language'] != row['language'] or orig['extra_instructions'] != row['extra_instructions']):
                supabase.table("campaign_items").update({
                    "topic": row['topic'],
                    "language": row['language'],
                    "extra_instructions": row['extra_instructions']
                }).eq("id", row['id']).execute()
                changes += 1
        st.toast(f"Zaktualizowano {changes} rekordów.")
        time.sleep(1)
        st.rerun()

    st.divider()
    
    selected_rows = edited_df[edited_df["Wybierz"] == True]
    count_sel = len(selected_rows)
    
    st.subheader(f"Akcje dla zaznaczonych: {count_sel}")
    
    if count_sel > 0:
        c1, c2, c3, c4 = st.columns(4)
        
        # --- KROK 1: RESEARCH ---
        if c1.button("1. Research"):
            bar = st.progress(0)
            for i, (_, row) in enumerate(selected_rows.iterrows()):
                if not row['topic']: continue
                
                # Update status to processing
                supabase.table("campaign_items").update({"status_research": "processing"}).eq("id", row['id']).execute()
                
                res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_RESEARCH"], {
                    "keyword": row['topic'],
                    "language": row['language']
                })
                
                if res.get('data', {}).get('status') == 'succeeded':
                    out = res['data']['outputs']
                    frazy_serp = out.get('frazy') or out.get('frazy z serp') or out.get('keywords') or row['topic']
                    frazy_senuto_val = out.get('frazy_senuto', '')
                    graf_info = out.get('grafinformacji') or out.get('graf') or out.get('information_graph') or ""
                    graf_know = out.get('knowledge_graph') or out.get('graf wiedzy') or ""
                    
                    supabase.table("campaign_items").update({
                        "keywords_serp": frazy_serp,
                        "frazy_senuto": frazy_senuto_val,
                        "info_graph": graf_info,
                        "knowledge_graph": graf_know,
                        "status_research": "done",       # Update granular
                        "pipeline_status": "researched"  # Keep legacy for compatibility
                    }).eq("id", row['id']).execute()
                else:
                    supabase.table("campaign_items").update({"status_research": "error"}).eq("id", row['id']).execute()
                    st.error(f"Error {row['id']}")
                bar.progress((i+1)/count_sel)
            st.success("Research zakończony!")
            st.rerun()

        # --- KROK 2: STRUKTURA ---
        if c2.button("2. Struktura"):
            bar = st.progress(0)
            for i, (_, row) in enumerate(selected_rows.iterrows()):
                supabase.table("campaign_items").update({"status_structure": "processing"}).eq("id", row['id']).execute()
                
                db_item = supabase.table("campaign_items").select("keywords_serp, info_graph").eq("id", row['id']).single().execute().data
                frazy_val = db_item.get('keywords_serp') or row['topic']
                graf_val = db_item.get('info_graph') or "Brak danych"

                res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_HEADERS"], {
                    "keyword": row['topic'],
                    "language": row['language'],
                    "frazy": frazy_val,
                    "graf": graf_val
                })
                
                if res.get('data', {}).get('status') == 'succeeded':
                    out = res['data']['outputs']
                    extended = out.get('naglowki_rozbudowane', '')
                    supabase.table("campaign_items").update({
                        "headings_extended": extended,
                        "headings_h2": out.get('naglowki_h2'),
                        "headings_questions": out.get('naglowki_pytania'),
                        "headings_final": extended,
                        "status_structure": "done",
                        "pipeline_status": "structured"
                    }).eq("id", row['id']).execute()
                else:
                    supabase.table("campaign_items").update({"status_structure": "error"}).eq("id", row['id']).execute()
                bar.progress((i+1)/count_sel)
            st.success("Gotowe!")
            st.rerun()

        # --- KROK 3: BRIEF ---
        if c3.button("3. Brief"):
            bar = st.progress(0)
            for i, (_, row) in enumerate(selected_rows.iterrows()):
                supabase.table("campaign_items").update({"status_brief": "processing"}).eq("id", row['id']).execute()
                
                db_item = supabase.table("campaign_items").select("*").eq("id", row['id']).single().execute().data
                if not db_item.get('headings_final'):
                    continue

                keywords_input = db_item.get('keywords_serp') or row['topic']

                res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_BRIEF"], {
                    "keywords": keywords_input, 
                    "headings": db_item.get('headings_final', ''),
                    "knowledge_graph": db_item.get('knowledge_graph', 'Brak'),
                    "information_graph": db_item.get('info_graph', 'Brak'),
                    "keyword": row['topic']
                })
                
                if res.get('data', {}).get('status') == 'succeeded':
                    raw_brief = res['data']['outputs'].get('brief', '[]')
                    parsed = clean_and_parse_json(raw_brief)
                    if parsed:
                        supabase.table("campaign_items").update({
                            "content_brief": parsed,
                            "status_brief": "done",
                            "pipeline_status": "briefed"
                        }).eq("id", row['id']).execute()
                else:
                    supabase.table("campaign_items").update({"status_brief": "error"}).eq("id", row['id']).execute()
                bar.progress((i+1)/count_sel)
            st.success("Gotowe!")
            st.rerun()

        # --- KROK 4: TREŚĆ ---
        if c4.button("4. Pisanie"):
            status_ph = st.empty()
            main_bar = st.progress(0)
            
            for i, (_, row) in enumerate(selected_rows.iterrows()):
                status_ph.info(f"Piszę: {row['topic']}")
                supabase.table("campaign_items").update({"status_writing": "processing"}).eq("id", row['id']).execute()
                
                db_item = supabase.table("campaign_items").select("content_brief, headings_final").eq("id", row['id']).single().execute().data
                brief = db_item.get('content_brief')
                
                if not brief: continue
                    
                full_content = ""
                for section in brief:
                    res = run_dify_workflow(st.secrets["DIFY"]["API_KEY_WRITE"], {
                        "naglowek": section.get('heading'),
                        "knowledge": section.get('knowledge'),
                        "keywords": section.get('keywords'),
                        "language": row['language'],
                        "headings": db_item.get('headings_final'),
                        "done": full_content,
                        "keyword": row['topic'],
                        "instruction": row['extra_instructions'] or ""
                    })
                    if res.get('data', {}).get('status') == 'succeeded':
                        chunk = res['data']['outputs'].get('result') or res['data']['outputs'].get('text', '')
                        full_content += chunk + "\n\n"
                
                supabase.table("campaign_items").update({
                    "content_html": full_content,
                    "content": full_content,
                    "status_writing": "done",
                    "pipeline_status": "content_ready",
                    "status": "content_ready"
                }).eq("id", row['id']).execute()
                
                main_bar.progress((i+1)/count_sel)
            
            status_ph.success("Gotowe!")
            st.balloons()
            st.rerun()
