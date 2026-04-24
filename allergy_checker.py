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

# --- THE SECRET KEY MAP ---
# Using the names as the actual passwords
PASS_TO_USER = {
    "Joey": "Joey",
    "Brian": "Brian",
    "Cheyenne": "Cheyenne",
    "Andrina": "Andrina",
    "Brianna": "Brianna",
    "Micah": "Micah"
}

# --- DATABASE ENGINE ---
if 'full_db' not in st.session_state:
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE, dtype={'barcode': str})
        if 'verified_by' not in df.columns:
            df['verified_by'] = "System"
        st.session_state.full_db = df.set_index('barcode').to_dict('index')
    else:
        st.session_state.full_db = {}

if 'scan_history' not in st.session_state:
    st.session_state.scan_history = []

# --- TRACKING FUNCTIONS ---
def add_to_history(name, status, barcode, user):
    now = datetime.now().strftime("%I:%M %p")
    if not st.session_state.scan_history or st.session_state.scan_history[0]['barcode'] != barcode:
        st.session_state.scan_history.insert(0, {
            "time": now, "name": name, "status": status, "barcode": barcode, "user": user
        })

def save_to_permanent_memory(barcode, name, reason, status, user):
    st.session_state.full_db[barcode] = {
        "name": name, "reason": reason, "status": status, "verified_by": user
    }
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

def delete_from_memory(barcode):
    if barcode in st.session_state.full_db:
        del st.session_state.full_db[barcode]
        df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
        df.rename(columns={'index': 'barcode'}, inplace=True)
        df.to_csv(DB_FILE, index=False)
        st.rerun()

# --- THE "NAME-ONLY" LOGIN ---
st.sidebar.header("🔑 Family Access")
# Note: This is case-sensitive (e.g., 'Joey' with a capital J)
secret_key = st.sidebar.text_input("Enter Your Name", type="password")

current_user = PASS_TO_USER.get(secret_key)

if current_user:
    st.sidebar.success(f"Welcome, {current_user}!")
    
    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode, user):
            barcode = barcode.strip()
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                emoji = "✅" if item['status'] == "Safe" else "❌"
                add_to_history(item['name'], item['status'], barcode, user)
                return f"{emoji} {item['status'].upper()}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']} (Verified by: {item.get('verified_by', 'System')})", None, None
            
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                if data.get("status") == 0: return "❓ NOT FOUND", "not_found", "", None, None
                
                product = data.get("product", {})
                p_name = product.get("product_name", "Unknown").upper()
                ingred = str(product.get("ingredients_text", "")).lower()
                img = product.get("image_front_url") or product.get("image_url")
                full_text = f"{ingred} {str(product.get('allergens_hierarchy', []))}"
                
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not ("soy oil" in full_text or "soybean oil" in full_text or "elecare" in p_name.lower()):
                    dangers.append("SOY")

                status = "Safe" if not dangers else "Danger"
                add_to_history(p_name, status, barcode, user)
                
                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {p_name}", "error", full_text, None, img
                return f"✅ SAFE: {p_name}", "success", full_text, None, img
            except: return "⚠️ ERROR", "info", "", None, None

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
            
            res, alert, raw, perc, official_img = check_allergy(st.session_state.frozen_barcode, current_user)
            if official_img: st.image(official_img, use_container_width=True)
            st.info(f"🔢 Barcode: `{st.session_state.frozen_barcode}` | Logged by: **{current_user}**")
            
            if alert == "error": st.error(res)
            elif alert in ["success", "safe"]: st.success(res)
            else:
                st.warning(res)
                st.markdown("### 📝 Manual Entry")
                m_name = st.text_input("Product Name:")
                m_reason = st.text_input("Reasoning:")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark SAFE ✅"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Safe", current_user)
                            add_to_history(m_name, "Safe", st.session_state.frozen_barcode, current_user)
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER ❌"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Danger", current_user)
                            add_to_history(m_name, "Danger", st.session_state.frozen_barcode, current_user)
                            st.rerun()
            
            with st.expander("Details"): st.write(raw)

    with tab2:
        st.header("📋 Family List Management")
        search = st.text_input("🔍 Search List", "").lower()
        items = {k: v for k, v in st.session_state.full_db.items() if search in v['name'].lower() or search in k}
        for bc, info in items.items():
            edit_key = f"edit_{bc}"
            if edit_key not in st.session_state: st.session_state[edit_key] = False
            color = "green" if info['status'] == "Safe" else "red"
            with st.container(border=True):
                if st.session_state[edit_key]:
                    n_n = st.text_input("Name", info['name'], key=f"nn_{bc}")
                    n_r = st.text_input("Reason", info['reason'], key=f"nr_{bc}")
                    n_s = st.selectbox("Status", ["Safe", "Danger"], 0 if info['status']=="Safe" else 1, key=f"ns_{bc}")
                    if st.button("Save 💾", key=f"s_{bc}"):
                        save_to_permanent_memory(bc, n_n, n_r, n_s, current_user)
                        st.session_state[edit_key]=False; st.rerun()
                else:
                    st.markdown(f"**{info['name']}**")
                    st.markdown(f"Status: :{color}[{info['status']}]")
                    st.caption(f"Verified by: **{info.get('verified_by', 'System')}**")
                    st.caption(f"Reason: {info['reason']}")
                    if st.button("Edit ✏️", key=f"e_{bc}"): st.session_state[edit_key]=True; st.rerun()
                    if st.button("Delete 🗑️", key=f"d_{bc}"): delete_from_memory(bc)

    with tab3:
        st.header("🕒 Trip History")
        if st.button("🗑️ Clear History"):
            st.session_state.scan_history = []
            st.rerun()
        for item in st.session_state.scan_history:
            icon = "✅" if item['status'] == "Safe" else "❌"
            st.write(f"**{item['time']}** | {icon} {item['name']} | Verified by: **{item['user']}**")

else:
    st.info("Enter your name (e.g., 'Joey', 'Brian') to unlock the scanner.")
