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

if password == "idaho2026": # Change this to your secret password
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        # Standardize barcode length
        if len(barcode) == 12:
            barcode = "0" + barcode
        
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            if data.get("status") == 0:
                return "❌ NOT FOUND: Data is missing. Do not trust.", "error"

            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            ingredients = product.get("ingredients_text", "").lower()
            tags = str(product.get("allergens_hierarchy", [])).lower()
            
            full_text = f"{ingredients} {tags}"

            # High-priority red flags
            dairy_flags = ["milk", "butter", "whey", "casein", "lactose", "cream", "cheese", "ghee", "caseinate"]
            plant_exceptions = ["coconut milk", "almond milk", "oat milk", "soy milk"]

            found = [f.upper() for f in dairy_flags if f in full_text]

            # Plant Milk Filter
            if "MILK" in found:
                for plant in plant_exceptions:
                    if plant in full_text:
                        remaining = full_text.replace(plant, "")
                        if not any(df in remaining for df in dairy_flags):
                            found.remove("MILK")

            if found:
                return f"❌ DANGER: {', '.join(list(set(found)))} in {name}", "error"
            
            if "RAMEN" in name or "NOODLE" in name:
                return f"⚠️ CHECK LABEL: {name} may have hidden Lactose.", "warning"
                
            return f"✅ SAFE: {name}", "success"
        except:
            return "⚠️ CONNECTION ERROR", "info"

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
                
                # Run our logic
                result, alert_type = check_allergy(barcode_num)
                
                if alert_type == "error":
                    st.error(result)
                elif alert_type == "warning":
                    st.warning(result)
                else:
                    st.success(result)
else:
    st.info("Please enter the password in the sidebar to use the scanner.")