import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import numpy as np

# --- APP SETUP ---
st.set_page_config(page_title="Family Allergy Scout", page_icon="🛡️")
st.title("🛡️ Son's Allergy Scanner")

# Simple Password Protection
password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        # Normalize: Ensure barcodes are standard 13-digit EAN format
        if len(barcode) == 12:
            barcode = "0" + barcode
        elif len(barcode) == 8:
            barcode = barcode.zfill(13)
        
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        
        try:
            # Impersonate chrome helps avoid being blocked by the API
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            
            if data.get("status") == 0 or "product" not in data:
                return "❌ NOT FOUND: Data is missing. Do not trust.", "error"

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            
            # Gather ingredient text and pre-analyzed allergen tags
            ingredients = product.get("ingredients_text", "").lower()
            allergen_tags = ", ".join(product.get("allergens_hierarchy", [])).lower()
            full_text = f"{ingredients} {allergen_tags}"

            # High-priority dairy flags
            dairy_flags = [
                "milk", "butter", "whey", "casein", "lactose", "cream", 
                "cheese", "ghee", "caseinate", "curd", "yogurt", "kefir"
            ]
            # Plant-based milks that might trigger a "false" milk flag
            plant_exceptions = ["coconut milk", "almond milk", "oat milk", "soy milk", "cashew milk"]

            # 1. Identify all dairy keywords found in the text
            found = [f.upper() for f in dairy_flags if f in full_text]

            # 2. Smart Filter: Check if 'MILK' is actually real dairy or just plant-based
            if "MILK" in found:
                has_real_dairy = False
                
                # If there is another dairy item (like butter or whey), it's definitely not safe
                other_dairy = [d for d in dairy_flags if d != "milk"]
                if any(d in full_text for d in other_dairy):
                    has_real_dairy = True
                
                # If 'milk' only appears inside a plant-based phrase, we can safely ignore the 'MILK' flag
                if not has_real_dairy:
                    temp_text = full_text
                    for plant in plant_exceptions:
                        temp_text = temp_text.replace(plant, "SAFE_PLANT")
                    
                    if "milk" not in temp_text:
                        found.remove("MILK")

            if found:
                return f"❌ DANGER: {', '.join(list(set(found)))} in {name}", "error"
            
            # Watch out for items with high cross-contamination or hidden ingredients
            if any(x in name for x in ["RAMEN", "NOODLE", "CHOCOLATE"]):
                return f"⚠️ CHECK LABEL: {name} may have hidden dairy or cross-contamination.", "warning"
                
            return f"✅ SAFE: {name}", "success"
            
        except Exception as e:
            return "⚠️ CONNECTION ERROR: Unable to reach database.", "info"

    # --- THE CAMERA INTERFACE ---
    st.subheader("Scan a Product")
    img_file = st.camera_input("Center the barcode and snap a photo")

    if img_file:
        # Convert the photo to a format Python can scan
        img = Image.open(img_file)
        decoded_objects = decode(img)

        if not decoded_objects:
            st.warning("No barcode detected. Try getting closer, keeping it steady, and ensuring good lighting.")
        else:
            for obj in decoded_objects:
                barcode_num = obj.data.decode("utf-8")
                st.info(f"Detected: {barcode_num}")
                
                # Run our updated logic
                result, alert_type = check_allergy(barcode_num)
                
                if alert_type == "error":
                    st.error(result)
                elif alert_type == "warning":
                    st.warning(result)
                else:
                    st.success(result)
                    
    if st.button("Clear Results"):
        st.rerun()

else:
    st.info("Please enter the password in the sidebar to use the scanner.")
