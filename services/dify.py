import streamlit as st
import requests
import json
import re

def run_dify_workflow(api_key, inputs):
    """
    Uruchamia workflow w Twojej instancji Dify.
    """
    base_url = st.secrets["DIFY"].get("BASE_URL", "https://api.dify.ai/v1")
    url = f"{base_url}/workflows/run"
    api_user = st.secrets["DIFY"].get("API_USER", "webinvest")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": inputs,
        "response_mode": "blocking",
        "user": api_user
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            return {"error": response.status_code, "message": response.text}
            
        return response.json()
    except Exception as e:
        return {"error": "Exception", "message": str(e)}

def clean_and_parse_json(text):
    """
    Czyści odpowiedź LLM z markdowna i parsuje do JSON.
    """
    try:
        # Usuń znaczniki markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        text = text.strip()
        return json.loads(text)
    except Exception as e:
        return []
