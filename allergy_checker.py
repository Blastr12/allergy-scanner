import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 
import os
import pandas as pd

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Allergy Scout")

DB_FILE = "family_blacklist_whitelist.csv"

# --- DATABASE ENGINE ---
if 'personal_db' not in st.session_state:
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE, dtype={'barcode': str})
        st.session_state.personal_db = df.set_index('barcode').to_dict('index')
    else:
        st.session_state.personal_db = {}

def save_to_permanent_memory(barcode, name, reason, status):
    st.session_state.personal_db[barcode] = {"name": name, "reason": reason, "status": status}
    df = pd.DataFrame.from_dict(st.session_state.personal_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

def delete_from_memory(barcode):
    if barcode in st.session_state.personal_db:
        del st.session_state.personal_db[barcode]
        df = pd.DataFrame.from_dict(st.session_state.personal_db, orient='index').reset_index()
        df.rename(columns={'index': 'barcode'}, inplace=True)
        df.to_csv(DB_FILE, index=False)
        st.rerun()

# --- LOGIN ---
password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    tab1, tab2 = st.tabs(["🔍 Live Scanner", "📋 Manage Saved Lists"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode):
            barcode = barcode.strip()
            # 1. Check Family List First
            if barcode in st.session_state.personal_db:
                item = st.session_state.personal_db[barcode]
                status_emoji = "✅" if item['status'] == "Safe" else "❌"
                status_text = "TRUSTED" if item['status'] == "Safe" else "CONFIRMED DANGER"
                return f"{status_emoji} {status_text}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']}", None, None
            
            # 2. Check Web Database
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                if data.get("status") == 0 or "product" not in data:
                    return "❓ NOT FOUND", "not_found", "", None, None
                
                product = data.get("product", {})
                name = product.get("product_name", "Unknown Product").upper()
                ingredients = str(product.get("ingredients_text", "")).lower()
                img_url = product.get("image_front_url") or product.get("image_url")
                full_text = f"{ingredients} {str(product.get('allergens_hierarchy', []))}"
                
                oil_perc = None
                match =
