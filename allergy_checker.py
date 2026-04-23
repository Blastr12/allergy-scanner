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

# Load the file with support for Name, Reason, and Status (Safe/Danger)
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

# --- APP LOGIC ---
if 'frozen_barcode' not in st.session_state:
    st.session_state.frozen_barcode = None

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        # Check Permanent Memory first
        if barcode in st.session_state.personal_db:
            item = st.session_state.personal_db[barcode]
            status_emoji = "✅" if item['status'] == "Safe" else "❌"
            status_text = "TRUSTED" if item['status'] == "Safe" else "CONFIRMED DANGER"
            return f"{status_emoji} {status_text}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']}", None, None
        
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
            
            oil_percent = None
            match = re.search(r'(\d+)\s*%', full_text)
            if match: oil_percent = f"{match.group(1)}%"
            
            is_elecare = "elecare" in name.lower()
            has_soy_oil = "soy oil" in full_text or "soybean oil" in full_text
            
            dangers = []
            if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein"]):
                if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                    dangers.append("MILK")
            if ("soy" in full_text or "soya" in full_text) and not (is_elecare or has_soy_oil):
                dangers.append("SOY")

            if dangers: return f"❌ DANGER: {', '.join(dangers)} in {name}", "error", full_text, oil_percent, img_url
            if is_elecare or has_soy_oil: return f"✅ SAFE (Soy Oil): {name}", "success", full_text, oil_percent, img_url
            return f"✅ SAFE: {name}", "success", full_text, None, img_url
        except: return "⚠️ ERROR", "info", "", None, None

    # --- UI ---
    if st.session_state.frozen_barcode is None:
        st.subheader("Snap barcode to scan")
        img_file = st.camera_input("Scanner")
        if img_file:
            img = Image.open(img_file)
            decoded = decode(img)
            if decoded:
                st.session_state.frozen_barcode = decoded[0].data.decode("utf-8")
                st.rerun()
    else:
        if st.button("🔄 SCAN NEXT ITEM"):
            st.session_state.frozen_barcode = None
            st.rerun()
        
        res, alert, raw, perc, official_img = check_allergy(st.session_state.frozen_barcode)
        
        if official_img:
            st.image(official_img, use_container_width=True)
        
        if alert == "error": st.error(res)
        elif alert == "success" or alert == "safe": st.success(res)
        else:
            st.warning(res)
            st.markdown("### 📝 Manual Record Entry")
            manual_name = st.text_input("Product Name:")
            manual_reason = st.text_input("Reasoning (e.g. 'Has hidden dairy', 'Verified Dairy-Free'):")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Mark SAFE Forever ✅"):
                    if manual_name and manual_reason:
                        save_to_permanent_memory(st.session_state.frozen_barcode, manual_name, manual_reason, "Safe")
                        st.success("Added to Safe List!")
                        st.rerun()
                    else: st.error("Fill out all fields!")
            with col2:
                if st.button("Mark DANGER Forever ❌"):
                    if manual_name and manual_reason:
                        save_to_permanent_memory(st.session_state.frozen_barcode, manual_name, manual_reason, "Danger")
                        st.error("Added to Danger List!")
                        st.rerun()
                    else: st.error("Fill out all fields!")

        if perc: st.warning(f"📊 SOY OIL CONTENT: {perc}")
        with st.expander("Detailed Information"):
            st.write(raw)

else:
    st.info("Enter password.")
