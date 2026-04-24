import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 
import os
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Allergy Scout")

DB_FILE = "family_blacklist_whitelist.csv"

# --- ACCESS MAP ---
PASS_TO_USER = {
    "Joey": "Joey", "Brian": "Brian", "Cheyenne": "Cheyenne",
    "Andrina": "Andrina", "Brianna": "Brianna", "Micah": "Micah"
}

# --- DATABASE ENGINE ---
if 'full_db' not in st.session_state:
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE, dtype={'barcode': str})
        if 'verified_by' not in df.columns: df['verified_by'] = "System"
        st.session_state.full_db = df.set_index('barcode').to_dict('index')
    else: st.session_state.full_db = {}

if 'scan_history' not in st.session_state:
    st.session_state.scan_history = []

def save_to_permanent_memory(barcode, name, reason, status, user):
    st.session_state.full_db[barcode] = {"name": name, "reason": reason, "status": status, "verified_by": user}
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

# --- LOGIN ---
st.sidebar.header("🔑 Family Access")
secret_key = st.sidebar.text_input("Enter Your Name", type="password")
current_user = PASS_TO_USER.get(secret_key)

if current_user:
    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode, user):
            barcode = barcode.strip()
            
            # 1. PRIORITY: Check your saved list first
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                emoji = "✅" if item['status'] == "Safe" else "❌"
                return f"{emoji} {item['status'].upper()}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']} (Verified by: {item.get('verified_by', 'System')})", None

            # 2. WEB FETCH
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                product = data.get("product", {})
                p_name = product.get("product_name", "Unknown Product").upper()
                img = product.get("image_front_url") or product.get("image_url")
                
                # Extracting raw values for validation
                raw_ingred = str(product.get("ingredients_text", "")).strip().lower()
                raw_allergens = product.get('allergens_hierarchy', [])
                
                # --- THE STRICT DATA CATCH ---
                # This stops the code if ingredients are missing or too short to be real
                if len(raw_ingred) < 5 or not raw_allergens or raw_allergens == []:
                    return f"⚠️ INCOMPLETE DATA: {p_name}", "warning", f"Missing info in database. (Ingredients found: '{raw_ingred}')", img

                full_text = f"{raw_ingred} {str(raw_allergens)}"
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not ("soy oil" in full_text or "soybean oil" in full_text or "elecare" in p_name.lower()):
                    dangers.append("SOY")

                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {p_name}", "error", full_text, img
                return f"✅ SAFE: {p_name}", "success", full_text, img
            except: return "⚠️ CONNECTION ERROR", "info", "", None

        if st.session_state.frozen_barcode is None:
            img_file = st.camera_input("Scanner")
            if img_file:
                img_obj = Image.open(img_file)
                decoded = decode(img_obj)
                if decoded:
                    st.session_state.frozen_barcode = decoded[0].data.decode("utf-8")
                    st.rerun()
        else:
            if st.button("🔄 SCAN NEXT"):
                st.session_state.frozen_barcode = None
                st.rerun()
            
            res, alert, raw, official_img = check_allergy(st.session_state.frozen_barcode, current_user)
            if official_img: st.image(official_img, use_container_width=True)
            
            # Displaying based on strict status
            if alert == "error": st.error(res)
            elif alert == "success": st.success(res)
            else: st.warning(res) # Yellow box for Incomplete Data or Warnings

            if alert in ["warning", "not_found", "info"]:
                st.markdown("### 💾 Make a Permanent Decision")
                m_name = st.text_input("Name:", value=res.split(':')[-1].strip() if ':' in res else "")
                m_reason = st.text_input("Why is it safe/danger?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark SAFE Forever ✅"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Safe", current_user)
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER Forever ❌"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Danger", current_user)
                            st.rerun()
            
            with st.expander("Details"): st.write(raw)

# [Remaining tab logic...]
