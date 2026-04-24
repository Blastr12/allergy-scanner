import streamlit as st
from curl_cffi import requests
from pyzbar.pyzbar import decode
from PIL import Image
import os
import pandas as pd

st.set_page_config(page_title="Allergy Scout Pro", page_icon="🛡️", layout="wide")

DB_FILE = "family_blacklist_whitelist.csv"

# --- THE ACCESS MAP ---
PASS_TO_USER = {
    "Joey": "Joey",
    "Brian": "Brian",
    "Chey": "Cheyenne", 
    "Andrina": "Andrina",
    "Brianna": "Brianna",
    "Micah": "Micah"
}

# --- DATABASE ENGINE ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE, dtype={'barcode': str})
            for col in ['name', 'reason', 'status', 'verified_by']:
                if col not in df.columns: df[col] = "Unknown"
            return df.set_index('barcode').to_dict('index')
        except: return {}
    return {}

if 'full_db' not in st.session_state:
    st.session_state.full_db = load_data()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.current_user = None

def save_to_file():
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)

def update_entry(barcode, name, reason, status, user):
    st.session_state.full_db[barcode] = {"name": name, "reason": reason, "status": status, "verified_by": user}
    save_to_file()
    st.toast(f"💾 {name} updated.")

# --- UI LOGIC ---
st.title("🛡️ Allergy Scout")

if not st.session_state.authenticated:
    # --- LOGIN VIEW ---
    with st.container(border=True):
        st.subheader("🔑 Family Access")
        secret_key = st.text_input("Enter Your Name (Password)", type="password")
        if st.button("Login"):
            user = PASS_TO_USER.get(secret_key)
            if user:
                st.session_state.authenticated = True
                st.session_state.current_user = user
                st.rerun()
            else:
                st.error("Invalid password. Please try again.")
else:
    # --- LOGGED IN VIEW ---
    top_col1, top_col2 = st.columns([0.8, 0.2])
    with top_col1:
        st.success(f"Logged in as: **{st.session_state.current_user}**")
    with top_col2:
        if st.button("Log Out 🚪"):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.rerun()

    st.divider()

    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode, user):
            barcode = str(barcode).strip()
            # Check family list first
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                emoji = "✅" if item['status'] == "Safe" else "❌"
                return f"{emoji} {item['status'].upper()}: {item['name']}", item['status'].lower(), f"Reason: {item['reason']} (By: {item.get('verified_by', 'System')})"
            
            # Web check
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                response = requests.get(url, impersonate="chrome", timeout=5)
                data = response.json()
                product = data.get("product", {})
                p_name = product.get("product_name", "Unknown Product").upper()
                raw_ingred = str(product.get("ingredients_text", "")).strip().lower()
                raw_allergens = product.get('allergens_hierarchy', [])

                if len(raw_ingred) < 5 or not raw_allergens or raw_allergens == []:
                    return f"⚠️ INCOMPLETE DATA: {p_name}", "warning", "No details found. Check label and save decision below."

                full_text = f"{raw_ingred} {str(raw_allergens)}"
                dangers = []
                if any(m in full_text for m in ["milk", "dairy", "butter", "whey", "casein", "lactylate"]):
                    if not any(p in full_text for p in ["coconut milk", "almond milk", "oat milk"]):
                        dangers.append("MILK")
                if ("soy" in full_text or "soya" in full_text) and not ("soy oil" in full_text or "soybean oil" in full_text or "elecare" in p_name.lower()):
                    dangers.append("SOY")

                status = "Safe" if not dangers else "Danger"
                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {p_name}", "error", full_text
                return f"✅ SAFE: {p_name}", "success", full_text
            except: return "⚠️ ERROR", "info", ""

        if st.session_state.frozen_barcode is None:
            img_file = st.camera_input("Scanner")
            if img_file:
                img_obj = Image.open(img_file)
                decoded = decode(img_obj)
                if decoded:
                    st.session_state.frozen_barcode = decoded[0].data.decode("utf-8")
                    st.rerun()
                else:
                    st.markdown("""
                        <div style="background-color: #ff4b4b; padding: 20px; border-radius: 10px; text-align: center;">
                            <h1 style="color: white; margin: 0;">❌ COULD NOT READ BARCODE</h1>
                            <h2 style="color: white; margin: 0;">TRY AGAIN</h2>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            if st.button("🔄 SCAN NEXT"):
                st.session_state.frozen_barcode = None
                st.rerun()
            
            res, alert, raw = check_allergy(st.session_state.frozen_barcode, st.session_state.current_user)
            st.markdown(f"### 🔢 Barcode: `{st.session_state.frozen_barcode}`")
            
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
                            update_entry(st.session_state.frozen_barcode, m_name, m_reason, "Safe", st.session_state.current_user)
                            st.session_state.frozen_barcode = None
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER ❌"):
                        if m_name and m_reason:
                            update_entry(st.session_state.frozen_barcode, m_name, m_reason, "Danger", st.session_state.current_user)
                            st.session_state.frozen_barcode = None
                            st.rerun()
            
            with st.expander("Details"): st.write(raw)

    with tab2:
        st.header("📋 Family List Management")
        st.session_state.full_db = load_data()
        search = st.text_input("🔍 Search List", "").lower()
        items = {k: v for k, v in st.session_state.full_db.items() if search in str(v['name']).lower() or search in str(k)}
        for bc, info in items.items():
            edit_key = f"is_editing_{bc}"
            if edit_key not in st.session_state: st.session_state[edit_key] = False
            with st.container(border=True):
                if st.session_state[edit_key]:
                    n_n = st.text_input("Edit Name", info['name'], key=f"n_{bc}")
                    n_r = st.text_input("Edit Reason", info['reason'], key=f"r_{bc}")
                    n_s = st.selectbox("Status", ["Safe", "Danger"], 0 if info['status']=="Safe" else 1, key=f"s_{bc}")
                    if st.button("Save Changes 💾", key=f"sv_{bc}"):
                        update_entry(bc, n_n, n_r, n_s, st.session_state.current_user)
                        st.session_state[edit_key] = False
                        st.rerun()
                else:
                    color = "green" if info['status'] == "Safe" else "red"
                    st.markdown(f"**{info['name']}**")
                    st.markdown(f"Status: :{color}[{info['status']}]")
                    st.caption(f"Barcode: `{bc}`")
                    st.caption(f"Reason: {info['reason']} | By: {info.get('verified_by', 'System')}")
                    if st.button("Edit ✏️", key=f"e_{bc}"):
                        st.session_state[edit_key] = True
                        st.rerun()

    with tab3:
        st.header("🕒 Trip History")
        # History code...
