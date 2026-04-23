import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import numpy as np
import re # Added for percentage scanning

# --- APP SETUP ---
st.set_page_config(page_title="Family Allergy Scout", page_icon="🛡️")
st.title("🛡️ Son's Allergy Scanner")

if 'personal_db' not in st.session_state:
    st.session_state.personal_db = {}

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        
        # 1. Check Session Memory
        if barcode in st.session_state.personal_db:
            data = st.session_state.personal_db[barcode]
            return f"✅ {data['status'].upper()} (Memory): {data['name']}", data['status'].lower(), ""

        # 2. Check Database
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            if data.get("status") == 0 or "product" not in data:
                return "❓ NOT FOUND: Not in database.", "not_found", ""

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            ingredients = product.get("ingredients_text", "").lower()
            allergen_tags = str(product.get("allergens_hierarchy", [])).lower()
            traces = str(product.get("traces", "")).lower()
            full_text = f"{ingredients} {allergen_tags} {traces}"

            # --- SEARCH FOR PERCENTAGES ---
            # This looks for numbers next to 'soy oil' or 'soybean oil'
            oil_percent = "Unknown %"
            match = re.search(r'(soy|soybean)\s*oil\s*\(?(\d+)%?\)?', ingredients)
            if match:
                oil_percent = f"{match.group(2)}%"

            # --- ALLERGY LOGIC ---
            red_flags = [
                "milk", "butter", "whey", "casein", "lactose", "cream", 
                "cheese", "ghee", "caseinate", "curd", "yogurt", "kefir", "dairy",
                "lactylate", "stearoyl", "soy", "soya", "lecithin", "edamame", "tofu"
            ]
            
            found = [f.upper() for f in red_flags if f in full_text]

            # SPECIAL EXCEPTIONS: Soy Oil and Safe Plant Milks
            if found:
                # Filter out "Soy" ONLY if it's strictly part of "Soy Oil"
                temp_text = full_text
                # Temporarily 'hide' the safe phrases
                safe_phrases = ["soy oil", "soybean oil", "coconut milk", "almond milk", "oat milk", "cashew milk"]
                for phrase in safe_phrases:
                    temp_text = temp_text.replace(phrase, "SAFE_ITEM")
                
                # Check if any DANGER words still exist after hiding safe items
                still_dangerous = False
                for flag in red_flags:
                    if flag in temp_text:
                        still_dangerous = True
                        break
                
                if not still_dangerous:
                    # If the only thing found was Soy Oil or Plant Milk, mark it SAFE
                    return f"✅ SAFE (Contains Soy Oil): {name}", "success", full_text, oil_percent

            if found:
                return f"❌ DANGER: {', '.join(list(set(found)))} in {name}", "error", full_text, None
            
            if not ingredients:
                return f"⚠️ NO DATA: {name} found, but list is empty.", "warning", full_text, None
                
            return f"✅ SAFE: {name}", "success", full_text, None
            
        except Exception:
            return "⚠️ CONNECTION ERROR", "info", "", None

    # --- UI ---
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
                
                # 1. Main Status
                if alert_type == "error": st.error(result)
                elif alert_type == "success": st.success(result)
                else: st.warning(result)

                # 2. YELLOW PERCENTAGE BOX (The new feature)
                if percent:
                    st.warning(f"📊 SOY OIL CONTENT: {percent}")

                # 3. Manual Override (if not found/warning)
                if alert_type in ["warning", "not_found"]:
                    p_name = st.text_input("Label this item:", value="Manual Entry")
                    c1, c2 = st.columns(2)
                    if c1.button("Mark Safe ✅"):
                        st.session_state.personal_db[barcode_num] = {"status": "Safe", "name": p_name}
                        st.rerun()
                    if c2.button("Mark Danger ❌"):
                        st.session_state.personal_db[barcode_num] = {"status": "Danger", "name": p_name}
                        st.rerun()
                
                if raw_text:
                    with st.expander("View Ingredient Text"):
                        st.write(raw_text)
                    
    if st.button("Clear Scanner"): st.rerun()

    # Sidebar Trip Summary
    if st.session_state.personal_db:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🛒 Trip History")
        for bc, data in st.session_state.personal_db.items():
            st.sidebar.write(f"{'✅' if data['status'] == 'Safe' else '❌'} {data['name']}")
else:
    st.info("Enter password in sidebar.")
