import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 
import os
import pandas as pd

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Allergy Scout")

# --- PERMANENT STORAGE SETUP ---
DB_FILE = "family_safe_list.csv"

# Load the permanent list from the file if it exists
if 'personal_db' not in st.session_state:
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE, dtype={'barcode': str})
        st.session_state.personal_db = df.set_index('barcode')['name'].to_dict()
    else:
        st.session_state.personal_db = {}

def save_to_permanent_memory(barcode, name):
    st.session_state.personal_db[barcode] = name
    # Save to CSV so it never disappears
    df = pd.DataFrame(list(st.session_state.personal_db.items()), columns=['barcode', 'name'])
    df.to_csv(DB_FILE, index=False)

# --- APP LOGIC ---
if 'frozen_barcode' not in st.session_state:
    st.session_state.frozen_barcode = None

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        # Check the Permanent Memory first
        if barcode in st.session_state.personal_db:
            return f"✅ TRUSTED (Family List): {st.session_state.personal_db[barcode]}", "success", "This item was manually verified by the family.", None, None
        
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
        elif alert == "success": st.success(res)
        else:
            st.warning(res)
            # --- THE "FOREVER" BUTTON ---
            manual_name = st.text_input("Product Name (e.g. Local Bread):")
            if st.button("Add to Family Safe List Forever ✅"):
                if manual_name:
                    save_to_permanent_memory(st.session_state.frozen_barcode, manual_name)
                    st.success(f"Saved {manual_name} to family records!")
                    st.rerun()
                else:
                    st.error("Please enter a name first.")

        if perc: st.warning(f"📊 SOY OIL CONTENT: {perc}")
        with st.expander("Ingredients & Details"):
            st.write(raw)

    # Optional: Show the full list at the bottom
    if st.sidebar.checkbox("Show Family Safe List"):
        st.sidebar.write(st.session_state.personal_db)

else:
    st.info("Enter password.")
