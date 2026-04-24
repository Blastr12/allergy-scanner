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

# --- DATABASE ENGINE ---
if 'personal_db' not in st.session_state:
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE, dtype={'barcode': str})
        st.session_state.personal_db = df.set_index('barcode')['name'].to_dict() # Simplified for lookup
        # Reloading full dict for management
        st.session_state.full_db = df.set_index('barcode').to_dict('index')
    else:
        st.session_state.personal_db = {}
        st.session_state.full_db = {}

# --- TRIP HISTORY ENGINE ---
if 'scan_history' not in st.session_state:
    st.session_state.scan_history = []

def add_to_history(name, status, barcode):
    now = datetime.now().strftime("%I:%M %p")
    st.session_state.scan_history.insert(0, {
        "time": now,
        "name": name,
        "status": status,
        "barcode": barcode
    })

def save_to_permanent_memory(barcode, name, reason, status):
    st.session_state.full_db[barcode] = {"name": name, "reason": reason, "status": status}
    df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
    df.rename(columns={'index': 'barcode'}, inplace=True)
    df.to_csv(DB_FILE, index=False)
    # Update simple lookup
    st.session_state.personal_db[barcode] = name

def delete_from_memory(barcode):
    if barcode in st.session_state.full_db:
        del st.session_state.full_db[barcode]
        del st.session_state.personal_db[barcode]
        df = pd.DataFrame.from_dict(st.session_state.full_db, orient='index').reset_index()
        df.rename(columns={'index': 'barcode'}, inplace=True)
        df.to_csv(DB_FILE, index=False)
        st.rerun()

# --- LOGIN ---
password = st.sidebar.text_input("Family Password", type="password")

if password == "idaho2026": 
    tab1, tab2, tab3 = st.tabs(["🔍 Live Scanner", "📋 Managed Saved Lists", "🕒 Trip History"])

    with tab1:
        if 'frozen_barcode' not in st.session_state:
            st.session_state.frozen_barcode = None

        def check_allergy(barcode):
            barcode = barcode.strip()
            # 1. Check Family List First
            if barcode in st.session_state.full_db:
                item = st.session_state.full_db[barcode]
                status_emoji = "✅" if item['status'] == "Safe" else "❌"
                status_text = "TRUSTED" if item['status'] == "Safe" else "CONFIRMED DANGER"
                add_to_history(item['name'], item['status'], barcode)
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

                final_status = "Safe" if not dangers else "Danger"
                add_to_history(name, final_status, barcode)

                if dangers: return f"❌ DANGER: {', '.join(dangers)} in {name}", "error", full_text, oil_perc, img_url
                if is_elecare or has_soy_oil: return f"✅ SAFE (Soy Oil): {name}", "success", full_text, oil_perc, img_url
                return f"✅ SAFE: {name}", "success", full_text, None, img_url
            except: return "⚠️ ERROR", "info", "", None, None

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
                            add_to_history(m_name, "Safe", st.session_state.frozen_barcode)
                            st.rerun()
                with c2:
                    if st.button("Mark DANGER ❌"):
                        if m_name and m_reason:
                            save_to_permanent_memory(st.session_state.frozen_barcode, m_name, m_reason, "Danger")
                            add_to_history(m_name, "Danger", st.session_state.frozen_barcode)
                            st.rerun()

            if current_perc: st.warning(f"📊 SOY OIL CONTENT: {current_perc}")
            with st.expander("Detailed Information"): st.write(raw)

    with tab2:
        st.header("📋 Family List Management")
        search_query = st.text_input("🔍 Search by Name or Barcode", "").lower()
        filtered_items = {k: v for k, v in st.session_state.full_db.items() if search_query in v['name'].lower() or search_query in k}
        for bc, info in filtered_items.items():
            edit_key = f"is_editing_{bc}"
            if edit_key not in st.session_state: st.session_state[edit_key] = False
            color = "green" if info['status'] == "Safe" else "red"
            with st.container(border=True):
                if st.session_state[edit_key]:
                    n_name = st.text_input("Name", value=info['name'], key=f"n_{bc}")
                    n_reason = st.text_input("Reason", value=info['reason'], key=f"r_{bc}")
                    n_status = st.selectbox("Status", ["Safe", "Danger"], index=0 if info['status'] == "Safe" else 1, key=f"s_{bc}")
                    if st.button("Save Changes 💾", key=f"sv_{bc}"):
                        save_to_permanent_memory(bc, n_name, n_reason, n_status)
                        st.session_state[edit_key] = False
                        st.rerun()
                else:
                    st.markdown(f"**{info['name']}**")
                    st.markdown(f"Status: :{color}[{info['status']}]")
                    st.caption(f"Barcode: `{bc}` | Reason: {info['reason']}")
                    if st.button("Edit ✏️", key=f"ed_{bc}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if st.button("Delete 🗑️", key=f"de_{bc}"): delete_from_memory(bc)

    with tab3:
        st.header("🕒 Today's Scans")
        if st.button("🗑️ Clear Trip History"):
            st.session_state.scan_history = []
            st.rerun()
        
        if not st.session_state.scan_history:
            st.info("No scans logged yet this trip.")
        else:
            for item in st.session_state.scan_history:
                icon = "✅" if item['status'] == "Safe" else "❌"
                st.write(f"**{item['time']}** | {icon} {item['name']} (`{item['barcode']}`)")

else:
    st.info("Enter password.")
