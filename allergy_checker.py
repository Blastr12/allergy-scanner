import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import re 
import os
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️")
st.title("🛡️ Allergy Scout")

DB_FILE = "family_blacklist_whitelist.csv"

# --- ACCESS MAP ---
PASS_TO_USER = {
    "Joey": "Joey", "Brian": "Brian", "Cheyenne": "Cheyenne",
    "Andrina": "Andrina", "Brianna": "Brianna", "Micah": "Micah"
}

# --- DATABASE ENGINE ---
# This ensures the list is loaded correctly every single time the page refreshes
def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE, dtype={'barcode': str})
            if 'verified_by' not in df.columns: df['verified_by'] = "System"
            return df.set_index('barcode').to_dict('index')
        except:
            return {}
    return {}

if 'full_db' not in st.session_state:
    st.session_state.full_db = load_data()

if 'scan_history' not in st.session_state:
    st.session_state.scan_history = []

def save_to_permanent_memory(barcode, name, reason, status, user):
    # 1. Update the app's current brain
    st.session_state.full_db[barcode] = {
        "name": name, 
        "reason": reason, 
        "status": status, 
        "verified_by": user
    }
    # 2. Force write to the actual file
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)
    # 3. Success message
    st.toast(f"✅ Saved {name} to Family List forever!")

def delete_from_memory(barcode):
    if barcode in st.session_state.full_db:
        del st.session_state.full_db[barcode]
        df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
        df.rename(columns={'index': 'barcode'}, inplace=True)
        df.to_csv(DB_FILE, index=False)
        st.rerun()

# --- LOGIN ---
st.sidebar.header("🔑 Family Access")
secret_key = st.sidebar.text_input("Enter Your Name", type="password")
current_user = PASS_TO_USER.get(secret_key)

if current_user:
    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode, user):
            barcode = str(barcode).strip()
            
            # CHECK FAMILY LIST (The "Forever" memory)
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                emoji = "✅" if item['status'] == "Safe" else "❌"
                return f"{emoji} {item['status'].upper()}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']} (Verified by: {item.get('verified_by', 'System')})", None

            # WEB FETCH
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                product = data.get("product", {})
                p_name = product.get("product_name", "Unknown Product").upper()
                img = product.get("image_front_url") or product.get("image_url")
                
                raw_ingred = str(product.get("ingredients_text", "")).strip().lower()
                raw_allergens = product.get('allergens_hierarchy', [])
                
                # STRICT DATA CATCH (for those [] items)
                if len(raw_ingred) < 5 or not raw_allergens or raw_allergens == []:
                    return f"⚠️ INCOMPLETE DATA: {p_name}", "warning", "No data found. Check label and save your decision below.", img

                full_text = f"{raw_ingred} {str(raw_allergens)}"
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not ("soy oil" in full_text or "soybean oil" in full_text or "elecare" in p_name.lower()):
                    dangers.append("SOY")

                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {p_name}", "error", full_text, img
                return f"✅ SAFE: {p_name}", "success", full_text, img
            except: return "⚠️ CONNECTION ERROR", "info", "", None

        if st.session_state.frozen_barcode is None:
            img_file = st.camera_input("Scanner")
            if img_file:
                img_obj = Image.open(img_file)
                decoded = decode(img_obj)
                if decoded:
                    st.session_state.frozen_barcode = decoded[0].data.decode("utf-8")
                    st.rerun()
        else:
            if st.button("🔄 SCAN NEXT"):
                st.session_state.frozen_barcode = None
                st.rerun()
            
            res, alert, raw, official_img = check_allergy(st.session_state.frozen_barcode, current_user)
            if official_img: st.image(official_img, use_container_width=True)
            
            if alert == "error": st.error(res)
            elif alert == "success": st.success(res)
            else: st.warning(res)

            # SAVE DECISION SECTION (Triggers for empty [] data or new items)
            if alert in ["warning", "not_found", "info"]:
                st.markdown("### 💾 Save Your Decision Forever")
                m_name = st.text_input("Product Name:", value=res.split(':')[-1].strip() if ':' in res else "")
                m_reason = st.text_input("Why is it safe/danger?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark SAFE Forever ✅"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Safe", current_user)
                            st.session_state.frozen_barcode = None # Reset scanner
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER Forever ❌"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Danger", current_user)
                            st.session_state.frozen_barcode = None # Reset scanner
                            st.rerun()
            
            with st.expander("Details"): st.write(raw)

    with tab2:
        st.header("📋 Family List Management")
        # Reloading data here ensures the list is ALWAYS up to date
        st.session_state.full_db = load_data()
        
        search = st.text_input("🔍 Search List", "").lower()
        items = {k: v for k, v in st.session_state.full_db.items() if search in str(v['name']).lower() or search in str(k)}
        
        if not items:
            st.info("No items saved yet.")
        
        for bc, info in items.items():
            with st.container(border=True):
                color = "green" if info['status'] == "Safe" else "red"
                st.markdown(f"**{info['name']}**")
                st.markdown(f"Status: :{color}[{info['status']}]")
                st.caption(f"Verified by: **{info.get('verified_by', 'System')}** | BC: `{bc}`")
                if st.button("Delete 🗑️", key=f"del_{bc}"):
                    delete_from_memory(bc)

    with tab3:
        # Trip History stays the same
        st.header("🕒 Trip History")
        for item in st.session_state.scan_history:
            icon = "✅" if item['status'] == "Safe" else "❌"
            st.write(f"**{item['time']}** | {icon} {item['name']} | User: {item['user']}")

else:
    st.info("Enter your name to unlock.")
