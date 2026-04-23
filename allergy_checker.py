import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 

st.set_page_config(page_title="Family Allergy Scout", page_icon="🛡️")
st.title("🛡️ Son's Allergy Scanner")

if 'personal_db' not in st.session_state:
    st.session_state.personal_db = {}

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
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

            # Percentage Check
            oil_percent = None
            percent_match = re.search(r'(\d+)\s*%', full_text)
            if percent_match:
                oil_percent = f"{percent_match.group(1)}%"

            is_elecare = "elecare" in name.lower()
            has_soy_oil = "soy oil" in full_text or "soybean oil" in full_text
            
            dangers_found = []
            
            # --- STRICT DAIRY CHECK ---
            if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate", "stearoyl"]):
                safe_plants = ["coconut milk", "almond milk", "oat milk", "cashew milk"]
                if not any(p in full_text for p in safe_plants):
                    dangers_found.append("MILK/DAIRY")

            # --- STRICT SOY CHECK ---
            if "soy" in full_text or "soya" in full_text or "lecithin" in full_text:
                # If it has soy but NOT the oil/elecare exception, it's a danger
                if not (is_elecare or has_soy_oil):
                    dangers_found.append("SOY PROTEIN/LECITHIN")

            if dangers_found:
                return f"❌ DANGER: {', '.join(dangers_found)} in {name}", "error", full_text, None
            
            if is_elecare or has_soy_oil:
                return f"✅ SAFE (EXCEPTION): {name} (Confirmed Soy Oil Only)", "success", full_text, oil_percent
            
            if not ingredients:
                return f"⚠️ NO DATA: {name} found, but check label!", "warning", full_text, None
                
            return f"✅ SAFE: {name} (No Allergens Found)", "success", full_text, None
            
        except Exception:
            return "⚠️ CONNECTION ERROR", "info", "", None

    st.subheader("Scan a Product")
    img_file = st.camera_input("Scan Barcode")

    if img_file:
        img = Image.open(img_file)
        decoded_objects = decode(img)

        if not decoded_objects:
            st.warning("No barcode detected.")
        else:
            for obj in decoded_objects:
                barcode_num = obj.data.decode("utf-8")
                result, alert_type, raw_text, percent = check_allergy(barcode_num)
                
                if alert_type == "error": st.error(result)
                elif alert_type == "success": st.success(result)
                else: st.warning(result)

                if percent:
                    st.warning(f"📊 SOY OIL CONTENT: {percent}")
                elif "soy oil" in str(raw_text).lower() or "soybean oil" in str(raw_text).lower():
                    st.warning("📊 SOY OIL DETECTED")

                if alert_type in ["warning", "not_found"]:
                    p_name = st.text_input("Label this item:", value="Manual Entry")
                    if st.button("Mark Safe ✅"):
                        st.session_state.personal_db[barcode_num] = {"status": "Safe", "name": p_name}
                        st.rerun()
                
                with st.expander("Debug Data"):
                    st.write(raw_text)
                    
    if st.button("Clear Scanner"): st.rerun()
else:
    st.info("Enter password.")
