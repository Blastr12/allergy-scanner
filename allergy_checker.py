import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import numpy as np

# --- APP SETUP ---
st.set_page_config(page_title="Family Allergy Scout", page_icon="🛡️")
st.title("🛡️ Son's Allergy Scanner")

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        if len(barcode) == 12:
            barcode = "0" + barcode
        elif len(barcode) == 8:
            barcode = barcode.zfill(13)
        
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            
            if data.get("status") == 0 or "product" not in data:
                return "❌ NOT FOUND: Manual check required!", "error", ""

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            
            # --- DATA COLLECTION ---
            ingredients = product.get("ingredients_text", "").lower()
            allergen_tags = str(product.get("allergens_hierarchy", [])).lower()
            traces = str(product.get("traces", "")).lower()
            # Some entries use 'allergens_from_ingredients'
            extra_tags = str(product.get("allergens_from_ingredients", "")).lower()
            
            full_text = f"{ingredients} {allergen_tags} {traces} {extra_tags}"

            # --- THE ULTIMATE RED FLAG LIST ---
            red_flags = [
                # Dairy & Stealth Dairy
                "milk", "butter", "whey", "casein", "lactose", "cream", 
                "cheese", "ghee", "caseinate", "curd", "yogurt", "kefir", 
                "lactylate", "stearoyl", "dairy",
                # Soy & Stealth Soy
                "soy", "soya", "lecithin", "edamame", "tofu", "miso",
                "vegetable broth", "textured vegetable protein"
            ]
            
            # SAFE Plant Phrases (Still exclude Soy Milk)
            safe_plant_phrases = ["coconut milk", "almond milk", "oat milk", "cashew milk"]

            # 1. Identify all red flags
            found = [f.upper() for f in red_flags if f in full_text]

            # 2. Plant Milk Exception Logic
            if "MILK" in found:
                has_real_danger = False
                # Check if ANY other danger word is present (like Lactylate or Soy)
                other_dangers = [d for d in red_flags if d != "milk"]
                if any(d in full_text for d in other_dangers):
                    has_real_danger = True
                
                if not has_real_danger:
                    temp_text = full_text
                    for plant in safe_plant_phrases:
                        temp_text = temp_text.replace(plant, "SAFE_PLANT")
                    if "milk" not in temp_text:
                        found.remove("MILK")

            if found:
                return f"❌ DANGER: {', '.join(list(set(found)))} in {name}", "error", full_text
            
            if not ingredients:
                return f"⚠️ NO INGREDIENTS ON FILE: Check the physical label of {name}!", "warning", full_text
                
            return f"✅ SAFE: {name}", "success", full_text
            
        except Exception:
            return "⚠️ CONNECTION ERROR", "info", ""

    # --- THE CAMERA INTERFACE ---
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
                
                if alert_type == "error":
                    st.error(result)
                elif alert_type == "warning":
                    st.warning(result)
                else:
                    st.success(result)
                
                with st.expander("Show Scanned Data"):
                    st.write(raw_text)
                    
    if st.button("Clear Results"):
        st.rerun()
else:
    st.info("Enter password in sidebar.")
