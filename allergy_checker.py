import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 

# --- APP SETUP ---
st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Hands-Free Allergy Scout")

# 1. Initialize "Scan State" to handle the freezing
if 'last_barcode' not in st.session_state:
    st.session_state.last_barcode = None
if 'personal_db' not in st.session_state:
    st.session_state.personal_db = {}

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    # [Internal check_allergy function remains the same as our previous 'Super Override' version]
    def check_allergy(barcode):
        barcode = barcode.strip()
        if barcode in st.session_state.personal_db:
            data = st.session_state.personal_db[barcode]
            return f"✅ {data['status'].upper()} (Memory): {data['name']}", data['status'].lower(), "", None

        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            if data.get("status") == 0 or "product" not in data:
                return "❓ NOT FOUND", "not_found", "", None

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            ingredients = str(product.get("ingredients_text", "")).lower()
            tags = str(product.get("allergens_hierarchy", [])).lower()
            traces = str(product.get("traces", "")).lower()
            full_text = f"{ingredients} {tags} {traces}"

            oil_percent = None
            percent_match = re.search(r'(\d+)\s*%', full_text)
            if percent_match: oil_percent = f"{percent_match.group(1)}%"

            is_elecare = "elecare" in name.lower()
            has_soy_oil = "soy oil" in full_text or "soybean oil" in full_text
            
            dangers = []
            if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein"]):
                if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                    dangers.append("MILK")
            if ("soy" in full_text or "soya" in full_text) and not (is_elecare or has_soy_oil):
                dangers.append("SOY")

            if dangers: return f"❌ DANGER: {', '.join(dangers)} in {name}", "error", full_text, None
            if is_elecare or has_soy_oil: return f"✅ SAFE (Soy Oil): {name}", "success", full_text, oil_percent
            if not ingredients: return f"⚠️ NO DATA: {name}", "warning", full_text, None
            return f"✅ SAFE: {name}", "success", full_text, None
        except: return "⚠️ CONNECTION ERROR", "info", "", None

    # --- THE LIVE SCANNER UI ---
    
    # If we HAVEN'T found a barcode yet, show the camera
    if st.session_state.last_barcode is None:
        st.subheader("Point camera at barcode...")
        img_file = st.camera_input("Scanner Active", label_visibility="collapsed")
        
        if img_file:
            img = Image.open(img_file)
            decoded = decode(img)
            if decoded:
                # BINGO! We found one. Save it to session state to "Freeze" the view.
                st.session_state.last_barcode = decoded[0].data.decode("utf-8")
                st.rerun() 

    # If we HAVE a barcode, hide the camera and show the results (The "Freeze")
    else:
        barcode = st.session_state.last_barcode
        result, alert_type, raw_text, percent = check_allergy(barcode)
        
        st.button("🔄 SCAN NEXT ITEM", on_click=lambda: st.session_state.update({"last_barcode": None}))
        
        if alert_type == "error": st.error(result)
        elif alert_type == "success": st.success(result)
        else: st.warning(result)

        if percent: st.warning(f"📊 SOY OIL: {percent}")
        
        if alert_type in ["warning", "not_found"]:
            p_name = st.text_input("Name this item:", value="Manual Entry")
            if st.button("Mark Safe ✅"):
                st.session_state.personal_db[barcode] = {"status": "Safe", "name": p_name}
                st.session_state.last_barcode = None # Unfreeze after saving
                st.rerun()

        with st.expander("Show Detailed Ingredients"):
            st.write(raw_text)

else:
    st.info("Enter password.")
