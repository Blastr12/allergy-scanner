import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Allergy Scout")

if 'frozen_barcode' not in st.session_state:
    st.session_state.frozen_barcode = None
if 'personal_db' not in st.session_state:
    st.session_state.personal_db = {}

password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    
    def check_allergy(barcode):
        barcode = barcode.strip()
        if barcode in st.session_state.personal_db:
            data = st.session_state.personal_db[barcode]
            return f"✅ {data['status'].upper()} (Memory): {data['name']}", data['status'].lower(), "", None, None
        
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        try:
            response = requests.get(url, impersonate="chrome", timeout=5)
            data = response.json()
            if data.get("status") == 0 or "product" not in data:
                return "❓ NOT FOUND", "not_found", "", None, None
            
            product = data.get("product", {})
            name = product.get("product_name", "Unknown Product").upper()
            ingredients = str(product.get("ingredients_text", "")).lower()
            
            # --- GET PHOTO ---
            img_url = (
                product.get("image_front_url") or 
                product.get("image_url") or 
                product.get("selected_images", {}).get("front", {}).get("display", {}).get("en")
            )
            
            full_text = f"{ingredients} {str(product.get('allergens_hierarchy', []))} {str(product.get('traces', ''))}"
            
            oil_percent = None
            match = re.search(r'(\d+)\s*%', full_text)
            if match: oil_percent = f"{match.group(1)}%"
            
            is_elecare = "elecare" in name.lower()
            has_soy_oil = "soy oil" in full_text or "soybean oil" in full_text
            
            dangers = []
            if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate", "stearoyl"]):
                if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk", "cashew milk"]):
                    dangers.append("MILK")
            
            if ("soy" in full_text or "soya" in full_text or "lecithin" in full_text) and not (is_elecare or has_soy_oil):
                dangers.append("SOY")

            if dangers: return f"❌ DANGER: {', '.join(dangers)} in {name}", "error", full_text, oil_percent, img_url
            if is_elecare or has_soy_oil: return f"✅ SAFE (Soy Oil): {name}", "success", full_text, oil_percent, img_url
            return f"✅ SAFE: {name}", "success", full_text, None, img_url
        except Exception as e:
            return f"⚠️ ERROR: {str(e)}", "info", "", None, None

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
        
        # DISPLAY PHOTO
        if official_img:
            try: st.image(official_img, use_container_width=True)
            except: st.info("📷 Image found but couldn't load.")
        
        # DISPLAY RESULTS
        if alert == "error": st.error(res)
        elif alert == "success": st.success(res)
        else: st.warning(res)
        
        # --- THE FIX: Changed 'percent' back to 'perc' ---
        if perc: 
            st.warning(f"📊 SOY OIL CONTENT: {perc}")
        
        with st.expander("Ingredients & Details"):
            st.write(raw)
else:
    st.info("Enter password.")
