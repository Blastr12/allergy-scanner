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
def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE, dtype={'barcode': str})
            # Ensure all columns exist
            for col in ['name', 'reason', 'status', 'verified_by']:
                if col not in df.columns: df[col] = "Unknown"
            return df.set_index('barcode').to_dict('index')
        except:
            return {}
    return {}

# Initialize session state
if 'full_db' not in st.session_state:
    st.session_state.full_db = load_data()

def save_to_file():
    """Helper to force-write the current session state to the CSV file"""
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

def update_entry(barcode, name, reason, status, user):
    st.session_state.full_db[barcode] = {
        "name": name, "reason": reason, "status": status, "verified_by": user
    }
    save_to_file()
    st.toast(f"💾 Changes to {name} saved forever!")

def delete_entry(barcode):
    if barcode in st.session_state.full_db:
        del st.session_state.full_db[barcode]
        save_to_file()
        st.rerun()

# --- LOGIN ---
st.sidebar.header("🔑 Family Access")
secret_key = st.sidebar.text_input("Enter Your Name", type="password")
current_user = PASS_TO_USER.get(secret_key)

if current_user:
    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        # [Scanner logic remains the same as the previous 'Strict Catch' version]
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode, user):
            barcode = str(barcode).strip()
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                emoji = "✅" if item['status'] == "Safe" else "❌"
                return f"{emoji} {item['status'].upper()}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']} (Verified by: {item.get('verified_by', 'System')})", None

            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                product = data.get("product", {})
                p_name = product.get("product_name", "Unknown Product").upper()
                img = product.get("image_front_url") or product.get("image_url")
                raw_ingred = str(product.get("ingredients_text", "")).strip().lower()
                raw_allergens = product.get('allergens_hierarchy', [])
                
                if len(raw_ingred) < 5 or not raw_allergens or raw_allergens == []:
                    return f"⚠️ INCOMPLETE DATA: {p_name}", "warning", "Missing info. Check label and save decision below.", img

                full_text = f"{raw_ingred} {str(raw_allergens)}"
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not ("soy oil" in full_text or "soybean oil" in full_text or "elecare" in p_name.lower()):
                    dangers.append("SOY")

                status = "Safe" if not dangers else "Danger"
                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {p_name}", "error", full_text, img
                return f"✅ SAFE: {p_name}", "success", full_text, img
            except: return "⚠️ ERROR", "info", "", None

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

            if alert in ["warning", "not_found", "info"]:
                st.markdown("### 💾 Save Your Decision")
                m_name = st.text_input("Product Name:", value=res.split(':')[-1].strip() if ':' in res else "")
                m_reason = st.text_input("Reasoning:")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark SAFE ✅"):
                        if m_name and m_reason:
                            update_entry(st.session_state.frozen_barcode, m_name, m_reason, "Safe", current_user)
                            st.session_state.frozen_barcode = None
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER ❌"):
                        if m_name and m_reason:
                            update_entry(st.session_state.frozen_barcode, m_name, m_reason, "Danger", current_user)
                            st.session_state.frozen_barcode = None
                            st.rerun()
            
            with st.expander("Details"): st.write(raw)

    with tab2:
        st.header("📋 Family List Management")
        
        # Ensure we are looking at the latest data
        st.session_state.full_db = load_data()
        
        search = st.text_input("🔍 Search List", "").lower()
        items = {k: v for k, v in st.session_state.full_db.items() if search in str(v['name']).lower() or search in str(k)}
        
        if not items:
            st.info("No items saved yet.")
        
        for bc, info in items.items():
            edit_mode_key = f"is_editing_{bc}"
            if edit_mode_key not in st.session_state:
                st.session_state[edit_mode_key] = False
            
            with st.container(border=True):
                if st.session_state[edit_mode_key]:
                    # --- EDITING UI ---
                    new_name = st.text_input("Edit Name", info['name'], key=f"edit_n_{bc}")
                    new_reason = st.text_input("Edit Reason", info['reason'], key=f"edit_r_{bc}")
                    new_status = st.selectbox("Status", ["Safe", "Danger"], index=0 if info['status']=="Safe" else 1, key=f"edit_s_{bc}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Save Changes 💾", key=f"save_{bc}"):
                            update_entry(bc, new_name, new_reason, new_status, current_user)
                            st.session_state[edit_mode_key] = False
                            st.rerun()
                    with col2:
                        if st.button("Cancel", key=f"cancel_{bc}"):
                            st.session_state[edit_mode_key] = False
                            st.rerun()
                else:
                    # --- VIEW UI ---
                    color = "green" if info['status'] == "Safe" else "red"
                    st.markdown(f"**{info['name']}**")
                    st.markdown(f"Status: :{color}[{info['status']}]")
                    st.caption(f"Reason: {info['reason']}")
                    st.caption(f"Verified by: **{info.get('verified_by', 'System')}** | BC: `{bc}`")
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Edit ✏️", key=f"btn_edit_{bc}"):
                            st.session_state[edit_mode_key] = True
                            st.rerun()
                    with b2:
                        if st.button("Delete 🗑️", key=f"btn_del_{bc}"):
                            delete_entry(bc)

    with tab3:
        # History logic...
        st.header("🕒 Today's Activity")
        # [History display remains same]
