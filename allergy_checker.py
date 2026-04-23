import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 

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
            return f"✅ {data['status'].upper()} (Memory): {data['name']}", data['status'].lower(), "", None

        # 2. Check Database
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            if data.get("status") == 0 or "product" not in data:
                return "❓ NOT FOUND: Not in database.", "not_found", "", None

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            ingredients = product.get("ingredients_text", "").lower()
            allergen_tags = str(product.get("allergens_hierarchy", [])).lower()
            traces = str(product.get("traces", "")).lower()
            full_text = f"{ingredients} {allergen_tags} {traces}"

            # --- SEARCH FOR PERCENTAGES (Enhanced) ---
            oil_percent = None
            # Matches "Soy Oil 7%", "Soy Oil (7%)", "Soy Oil at 7 percent", etc.
            percent_match = re.search(r'(soy|soybean)\s*oil.*?(\d+)\s*%', full_text)
            if percent_match:
                oil_percent = f"{percent_match.group(2)}%"

            # --- THE LOGIC: STRIP OUT SAFE ITEMS FIRST ---
            # We create a "Clean Text" version that removes known safe phrases
            clean_text = full_text
            safe_items = ["soy oil", "soybean oil", "coconut milk", "almond milk", "oat milk", "cashew milk"]
            for item in safe_items:
                clean_text = clean_text.replace(item, "SAFE_PHRASE")

            # --- RED FLAGS (Search only in the CLEAN text) ---
            red_flags = [
                "milk", "butter", "whey", "casein", "lactose", "cream", 
                "cheese", "ghee", "caseinate", "curd", "yogurt", "kefir", "dairy",
                "lactylate", "stearoyl", "soy", "soya", "lecithin", "edamame", "tofu"
            ]
            
            found_danger = [f.upper() for f in red_flags if f in clean_text]

            # 3. RESULTS
            if found_danger:
                return f"❌ DANGER: {', '.join(list(set(found_danger)))} in {name}", "error", full_text, None
            
            # If nothing dangerous is left, but we found Soy Oil/Plant Milk in the original text
            if any(item in full_text for item in safe_items):
                return f"✅ SAFE (Check Oil %): {name}", "success", full_text, oil_percent
            
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
                
                # 1. Status Display
                if alert_type == "error": st.error(result)
                elif alert_type == "success": st.success(result)
                else: st.warning(result)

                # 2. THE YELLOW BOX (Should appear for EleCare)
                if percent:
                    st.warning(f"📊 SOY OIL CONTENT: {percent}")
                elif "soy oil" in str(raw_text).lower():
                    st.warning("📊 SOY OIL DETECTED: (Percentage not found in text)")

                # 3. Manual Override
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

else:
    st.info("Enter password in sidebar.")
