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

def add_to_history(name, status, barcode, user):
    now = datetime.now().strftime("%I:%M %p")
    if not st.session_state.scan_history or st.session_state.scan_history[0]['barcode'] != barcode:
        st.session_state.scan_history.insert(0, {
            "time": now, "name": name, "status": status, "barcode": barcode, "user": user
        })

def save_to_permanent_memory(barcode, name, reason, status, user):
    # This saves it to the CSV so it's there "forever"
    st.session_state.full_db[barcode] = {"name": name, "reason": reason, "status": status, "verified_by": user}
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

def delete_from_memory(barcode):
    if barcode in st.session_state.full_db:
        del st.session_state.full_db[barcode]
        df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
        df.rename(columns={'index': 'barcode'}, inplace=True)
        df.to_csv(DB_FILE, index=False)
        st.rerun()

# --- LOGIN ---
st.sidebar.header("🔑 Family Access")
secret_key = st.sidebar.text_input("Enter Your Name", type="password")
current_user = PASS_TO_USER.get(secret_key)

if current_user:
    st.sidebar.success(f"Logged in as: {current_user}")
    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode, user):
            barcode = barcode.strip()
            # 1. CHECK FAMILY LIST FIRST (This is the "Forever" check)
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                emoji = "✅" if item['status'] == "Safe" else "❌"
                add_to_history(item['name'], item['status'], barcode, user)
                # Show who made the decision and why
                return f"{emoji} {item['status'].upper()}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']} (Verified by: {item.get('verified_by', 'System')})", None
            
            # 2. WEB DATABASE CHECK
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                if data.get("status") == 0: return "❓ NOT FOUND", "not_found", "", None
                
                product = data.get("product", {})
                p_name = product.get("product_name", "Unknown Product").upper()
                ingred = str(product.get("ingredients_text", "")).strip().lower()
                img = product.get("image_front_url") or product.get("image_url")
                allergens = str(product.get('allergens_hierarchy', []))
                
                # --- MISSING DATA PROTECTION ---
                if not ingred or ingred in ["nan", "none", "[]"] or allergens == "[]":
                    # Force a decision from the user
                    return f"⚠️ NO DATA FOUND: {p_name}", "warning", "Database is empty. Check physical label and save your decision below.", img

                full_text = f"{ingred} {allergens}"
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not ("soy oil" in full_text or "soybean oil" in full_text or "elecare" in p_name.lower()):
                    dangers.append("SOY")

                status = "Safe" if not dangers else "Danger"
                add_to_history(p_name, status, barcode, user)
                
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
            st.info(f"🔢 Barcode: `{st.session_state.frozen_barcode}` | Logged by: **{current_user}**")
            
            # --- DISPLAY RESULT ---
            if alert == "error": st.error(res)
            elif alert == "success": st.success(res)
            elif alert == "warning": st.warning(res) # This triggers for the [] empty data
            else: st.warning(res)

            # --- MANUAL OVERRIDE / NEW ENTRY SECTION ---
            # This appears for "Not Found" OR "Warning" (Empty Data)
            if alert in ["warning", "not_found", "info"]:
                st.markdown("### 💾 Save Your Decision")
                st.caption("Once saved, this will show up for everyone scanning this item in the future.")
                m_name = st.text_input("Product Name:", value=res.split(':')[-1].strip() if ':' in res else "")
                m_reason = st.text_input("Reasoning (e.g. 'Checked label, contains no milk'):")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Save as SAFE ✅"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Safe", current_user)
                            add_to_history(m_name, "Safe", st.session_state.frozen_barcode, current_user)
                            st.rerun()
                with c2:
                    if st.button("Save as DANGER ❌"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Danger", current_user)
                            add_to_history(m_name, "Danger", st.session_state.frozen_barcode, current_user)
                            st.rerun()
            
            with st.expander("Database Details"): st.write(raw)

    # ... [Management and History tabs remain the same as before] ...
