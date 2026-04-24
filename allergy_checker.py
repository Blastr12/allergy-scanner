import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 
import os
import pandas as pd

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Allergy Scout")

DB_FILE = "family_blacklist_whitelist.csv"

# --- DATABASE ENGINE ---
if 'personal_db' not in st.session_state:
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE, dtype={'barcode': str})
        st.session_state.personal_db = df.set_index('barcode').to_dict('index')
    else:
        st.session_state.personal_db = {}

def save_to_permanent_memory(barcode, name, reason, status):
    st.session_state.personal_db[barcode] = {"name": name, "reason": reason, "status": status}
    df = pd.DataFrame.from_dict(st.session_state.personal_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

def delete_from_memory(barcode):
    if barcode in st.session_state.personal_db:
        del st.session_state.personal_db[barcode]
        df = pd.DataFrame.from_dict(st.session_state.personal_db, orient='index').reset_index()
        df.rename(columns={'index': 'barcode'}, inplace=True)
        df.to_csv(DB_FILE, index=False)
        st.rerun()

# --- LOGIN ---
password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    tab1, tab2 = st.tabs(["🔍 Live Scanner", "📋 Manage Saved Lists"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode):
            barcode = barcode.strip()
            # 1. Check Family List First
            if barcode in st.session_state.personal_db:
                item = st.session_state.personal_db[barcode]
                status_emoji = "✅" if item['status'] == "Safe" else "❌"
                status_text = "TRUSTED" if item['status'] == "Safe" else "CONFIRMED DANGER"
                return f"{status_emoji} {status_text}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']}", None, None
            
            # 2. Check Web Database
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                if data.get("status") == 0 or "product" not in data:
                    return "❓ NOT FOUND", "not_found", "", None, None
                
                product = data.get("product", {})
                name = product.get("product_name", "Unknown Product").upper()
                ingredients = str(product.get("ingredients_text", "")).lower()
                img_url = product.get("image_front_url") or product.get("image_url")
                full_text = f"{ingredients} {str(product.get('allergens_hierarchy', []))}"
                
                oil_perc = None
                match = re.search(r'(\d+)\s*%', full_text)
                if match: oil_perc = f"{match.group(1)}%"
                
                is_elecare = "elecare" in name.lower()
                has_soy_oil = "soy oil" in full_text or "soybean oil" in full_text
                
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not (is_elecare or has_soy_oil):
                    dangers.append("SOY")

                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {name}", "error", full_text, oil_perc, img_url
                if is_elecare or has_soy_oil: return f"✅ SAFE (Soy Oil): {name}", "success", full_text, oil_perc, img_url
                return f"✅ SAFE: {name}", "success", full_text, None, img_url
            except: return "⚠️ ERROR", "info", "", None, None

        # --- UI SCANNER ---
        if st.session_state.frozen_barcode is None:
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
            
            res, alert, raw, current_perc, official_img = check_allergy(st.session_state.frozen_barcode)
            
            if official_img: st.image(official_img, use_container_width=True)
            
            # --- NEW: DEDICATED BARCODE DISPLAY ---
            st.info(f"🔢 Scanned Barcode: `{st.session_state.frozen_barcode}`")
            
            if alert == "error": st.error(res)
            elif alert in ["success", "safe"]: st.success(res)
            else:
                st.warning(res)
                st.markdown("### 📝 Manual Record Entry")
                m_name = st.text_input("Product Name:")
                m_reason = st.text_input("Reasoning:")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark SAFE ✅"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Safe")
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER ❌"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Danger")
                            st.rerun()

            if current_perc: 
                st.warning(f"📊 SOY OIL CONTENT: {current_perc}")
            
            with st.expander("Detailed Information"):
                st.write(raw)

    with tab2:
        st.header("📋 Family List Management")
        if not st.session_state.personal_db:
            st.info("No items saved yet.")
        else:
            for bc, info in list(st.session_state.personal_db.items()):
                edit_key = f"is_editing_{bc}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                color = "green" if info['status'] == "Safe" else "red"
                with st.container(border=True):
                    if st.session_state[edit_key]:
                        new_name = st.text_input("Name", value=info['name'], key=f"name_{bc}")
                        new_reason = st.text_input("Reason", value=info['reason'], key=f"reason_{bc}")
                        new_status = st.selectbox("Status", ["Safe", "Danger"], index=0 if info['status'] == "Safe" else 1, key=f"status_{bc}")
                        
                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.button("Save Changes 💾", key=f"save_{bc}"):
                                save_to_permanent_memory(bc, new_name, new_reason, new_status)
                                st.session_state[edit_key] = False
                                st.rerun()
                        with cancel_col:
                            if st.button("Cancel 🚫", key=f"cancel_{bc}"):
                                st.session_state[edit_key] = False
                                st.rerun()
                    else:
                        st.markdown(f"**{info['name']}**")
                        st.markdown(f"Status: :{color}[{info['status']}]")
                        st.caption(f"Barcode: `{bc}`")
                        st.caption(f"Reason: {info['reason']}")
                        
                        edit_btn, del_btn = st.columns(2)
                        with edit_btn:
                            if st.button("Edit ✏️", key=f"edit_btn_{bc}"):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with del_btn:
                            if st.button(f"Delete 🗑️", key=f"del_{bc}"):
                                delete_from_memory(bc)

else:
    st.info("Enter password.")
