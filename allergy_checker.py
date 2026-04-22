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
        if len(barcode) == 12:
            barcode = "0" + barcode
        elif len(barcode) == 8:
            barcode = barcode.zfill(13)
        
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            
            if data.get("status") == 0 or "product" not in data:
                return "❌ NOT FOUND: Data is missing. Do not trust.", "error"

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            
            # --- COLLECT ALL TEXT SOURCES ---
            ingredients = product.get("ingredients_text", "").lower()
            allergen_tags = ", ".join(product.get("allergens_hierarchy", [])).lower()
            # NEW: Pulling in the 'traces' field for "May Contain" warnings
            traces = str(product.get("traces", "")).lower()
            
            # Combine everything into one text block for scanning
            full_text = f"{ingredients} {allergen_tags} {traces}"

            # --- ALLERGY SETTINGS ---
            red_flags = [
                "milk", "butter", "whey", "casein", "lactose", "cream", 
                "cheese", "ghee", "caseinate", "curd", "yogurt", "kefir",
                "soy", "soya", "lecithin", "edamame", "tofu", "miso"
            ]
            
            # Plant-based milks that are safe (excluding Soy)
            safe_plant_phrases = ["coconut milk", "almond milk", "oat milk", "cashew milk"]

            # 1. Identify all red flags found
            found = [f.upper() for f in red_flags if f in full_text]

            # 2. Smart Filter for Milk (Ensuring Almond/Oat/Coconut Milk stay SAFE)
            if "MILK" in found:
                has_real_danger = False
                
                # If there's soy or other dairy, it's a danger
                other_dangers = [d for d in red_flags if d != "milk"]
                if any(d in full_text for d in other_dangers):
                    has_real_danger = True
                
                # Check if 'milk' only appears in a safe plant-based phrase
                if not has_real_danger:
                    temp_text = full_text
                    for plant in safe_plant_phrases:
                        temp_text = temp_text.replace(plant, "SAFE_PLANT")
                    
                    if "milk" not in temp_text:
                        found.remove("MILK")

            # 3. Final Check: If anything is in 'traces', force it to RED
            if found:
                unique_found = list(set(found))
                return f"❌ DANGER (Contains or May Contain): {', '.join(unique_found)} in {name}", "error"
            
            # Extra Caution for notoriously risky categories
            if any(x in name for x in ["RAMEN", "NOODLE", "CHOCOLATE", "SPRAY", "BAKERY"]):
                return f"⚠️ CHECK LABEL: {name} often has cross-contamination.", "warning"
                
            return f"✅ SAFE: {name}", "success"
            
        except Exception as e:
            return "⚠️ CONNECTION ERROR: Unable to reach database.", "info"

    # --- THE CAMERA INTERFACE ---
    st.subheader("Scan a Product")
    img_file = st.camera_input("Center the barcode and snap a photo")

    if img_file:
        img = Image.open(img_file)
        decoded_objects = decode(img)

        if not decoded_objects:
            st.warning("No barcode detected. Try getting closer and ensuring good lighting.")
        else:
            for obj in decoded_objects:
                barcode_num = obj.data.decode("utf-8")
                st.info(f"Detected: {barcode_num}")
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
