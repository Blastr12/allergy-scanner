import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import numpy as np

# --- APP SETUP ---
st.set_page_config(page_title="Family Allergy Scout", page_icon="🛡️")
st.title("🛡️ Son's Allergy Scanner")

# Initialize "Memory" if it doesn't exist yet
if 'personal_db' not in st.session_state:
    st.session_state.personal_db = {}

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        # 1. Check our "Memory" first
        if barcode in st.session_state.personal_db:
            status = st.session_state.personal_db[barcode]
            if status == "Safe":
                return f"✅ SAFE (From Memory): This item was manually marked safe.", "success", ""
            else:
                return f"❌ DANGER (From Memory): This item was manually marked danger.", "error", ""

        # 2. If not in memory, check the Web Database
        if len(barcode) == 12:
            barcode = "0" + barcode
        elif len(barcode) == 8:
            barcode = barcode.zfill(13)
        
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            
            if data.get("status") == 0 or "product" not in data:
                return "❓ NOT FOUND: Product not in database.", "not_found", ""

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            ingredients = product.get("ingredients_text", "").lower()
            allergen_tags = str(product.get("allergens_hierarchy", [])).lower()
            traces = str(product.get("traces", "")).lower()
            extra_tags = str(product.get("allergens_from_ingredients", "")).lower()
            
            full_text = f"{ingredients} {allergen_tags} {traces} {extra_tags}"

            if not ingredients and not allergen_tags:
                return f"⚠️ NO DATA: {name} found, but list is empty.", "warning", ""

            red_flags = [
                "milk", "butter", "whey", "casein", "lactose", "cream", 
                "cheese", "ghee", "caseinate", "curd", "yogurt", "kefir", "dairy",
                "lactylate", "stearoyl", "soy", "soya", "lecithin", "edamame", "tofu"
            ]
            
            found = [f.upper() for f in red_flags if f in full_text]

            # Plant Milk Exception
            if "MILK" in found:
                safe_plant_phrases = ["coconut milk", "almond milk", "oat milk", "cashew milk"]
                has_real_danger = any(d in full_text for d in red_flags if d != "milk")
                if not has_real_danger:
                    temp_text = full_text
                    for plant in safe_plant_phrases:
                        temp_text = temp_text.replace(plant, "SAFE_PLANT")
                    if "milk" not in temp_text:
                        found.remove("MILK")

            if found:
                return f"❌ DANGER: {', '.join(list(set(found)))} in {name}", "error", full_text
                
            return f"✅ SAFE: {name}", "success", full_text
            
        except Exception:
            return "⚠️ CONNECTION ERROR", "info", ""

    # --- CAMERA & UI ---
    st.subheader("Scan a Product")
    img_file = st.camera_input("Snap barcode")

    if img_file:
        img = Image.open(img_file)
        decoded_objects = decode(img)

        if not decoded_objects:
            st.warning("No barcode detected.")
        else:
            for obj in decoded_objects:
                barcode_num = obj.data.decode("utf-8")
                st.info(f"Detected: {barcode_num}")
                result, alert_type, raw_text = check_allergy(barcode_num)
                
                # Display Results
                if alert_type == "error":
                    st.error(result)
                elif alert_type == "warning" or alert_type == "not_found":
                    if alert_type == "warning": st.warning(result)
                    else: st.info(result)
                    
                    # Manual Override Buttons
                    st.write("Would you like to save this for this session?")
                    col1, col2 = st.columns(2)
                    if col1.button("Mark as Safe ✅"):
                        st.session_state.personal_db[barcode_num] = "Safe"
                        st.rerun()
                    if col2.button("Mark as Danger ❌"):
                        st.session_state.personal_db[barcode_num] = "Danger"
                        st.rerun()
                else:
                    st.success(result)
                
                if raw_text:
                    with st.expander("Show Scanned Data"):
                        st.write(raw_text)
                    
    if st.button("Clear Scanner"):
        st.rerun()
    
    # Sidebar view of your manual list
    if st.session_state.personal_db:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Session Memory")
        for bc, val in st.session_state.personal_db.items():
            st.sidebar.write(f"{bc}: {val}")

else:
    st.info("Enter password in sidebar.")
