import streamlit as st
import base64
import time
import json
import os
import uuid
import random
from datetime import datetime
import streamlit_google_auth
import google_auth_oauthlib.flow
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
import googleapiclient.http
import tomllib

# ==========================================
# SECRETS & AUTHENTICATION LOGIC
# ==========================================

def get_app_secrets():
    secrets_path = os.path.join(os.path.dirname(__file__), 'app_secrets.json')
    toml_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
    if os.path.exists(secrets_path):
        with open(secrets_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    try:
        if os.path.exists(toml_path):
            with open(toml_path, "rb") as f:
                toml_secrets = tomllib.load(f)
            secrets_dict = {
                "ADMIN_EMAIL": toml_secrets.get("ADMIN_EMAIL", "sri.kailash.electronics@gmail.com"),
                "EMAIL_PASSWORD": toml_secrets.get("EMAIL_PASSWORD", ""),
                "GDRIVE_SERVICE_ACCOUNT": dict(toml_secrets.get("GDRIVE_SERVICE_ACCOUNT", {})),
                "web": dict(toml_secrets.get("web", {}))
            }
            with open(secrets_path, 'w', encoding='utf-8') as f:
                json.dump(secrets_dict, f, indent=4)
            return secrets_dict
    except Exception as e:
        print(f"Failed to read TOML secrets: {e}")
    return {}

APP_SECRETS = get_app_secrets()
ADMIN_EMAIL = APP_SECRETS.get("ADMIN_EMAIL", "sri.kailash.electronics@gmail.com")
ADMIN_EMAILS = [ADMIN_EMAIL]

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

flag_base64 = ""
if os.path.exists("india_flag.png"):
    flag_base64 = get_base64_image("india_flag.png")

# ==========================================
# EMAIL NOTIFICATIONS
# ==========================================

def send_notification_email(receiver, subject, html_body):
    sender = ADMIN_EMAIL
    sender_pwd = APP_SECRETS.get("EMAIL_PASSWORD", "")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(html_body, "html"))
    try:
        if sender_pwd:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login(sender, sender_pwd)
            server.sendmail(sender, receiver, msg.as_string())
            server.quit()
    except Exception:
        pass

def get_order_created_html(order):
    return f"<h2>Order Received</h2><p>Your {order['type']} recharge on {order['target']} has been received.</p><p><b>TXN ID:</b> {order['txn_id']}</p><p><b>Amount:</b> ₹{order['amount']}</p>"

def get_payment_confirmed_html(order):
    return f"<h2>Payment Confirmed</h2><p>Payment for order {order['txn_id']} is confirmed.</p><p>Your {order['type']} recharge on {order['target']} is processing.</p>"

def get_recharge_completed_html(order):
    return f"<h2>Recharge Successful</h2><p>Your {order['type']} recharge on {order['target']} is complete!</p><p><b>TXN ID:</b> {order['txn_id']}</p><p><b>UTR:</b> {order.get('recharge_utr', 'N/A')}</p>"

def get_grievance_created_html(grievance):
    return f"<h2>Grievance Submitted</h2><p>Grievance for TXN {grievance['txn_id']} received.</p><p><b>ID:</b> {grievance['id']}</p><p><b>Issue:</b> {grievance['issue_type']}</p>"

def get_grievance_resolved_html(grievance):
    return f"<h2>Grievance Resolved</h2><p>Grievance {grievance['id']} is resolved.</p><p><b>Admin Reply:</b> {grievance['admin_reply']}</p>"

# ==========================================
# GOOGLE DRIVE DATABASE LOGIC
# ==========================================

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    gdrive_creds = APP_SECRETS.get("GDRIVE_SERVICE_ACCOUNT")
    if gdrive_creds and "type" in gdrive_creds:
        creds = service_account.Credentials.from_service_account_info(gdrive_creds, scopes=DRIVE_SCOPES)
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    return None

def find_file_in_drive(service, file_name, parent_folder_id=None):
    query = f"name='{file_name}' and trashed=false"
    if parent_folder_id: query += f" and '{parent_folder_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    return items[0]['id'] if items else None

def get_or_create_app_folder(service):
    folder_name = "SKE_Recharge_Data"
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
    items = results.get('files', [])
    if items: return items[0]['id']
    folder_metadata = { 'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder' }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')
    permission = { 'type': 'user', 'role': 'writer', 'emailAddress': ADMIN_EMAIL }
    service.permissions().create(fileId=folder_id, body=permission).execute()
    return folder_id

def load_json_from_drive(file_name, default_val):
    try:
        service = get_drive_service()
        if not service: return default_val
        folder_id = get_or_create_app_folder(service)
        file_id = find_file_in_drive(service, file_name, folder_id)
        if not file_id: return default_val
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = googleapiclient.http.MediaIoBaseDownload(fh, request)
        done = False
        while not done: status, done = downloader.next_chunk()
        fh.seek(0)
        return json.loads(fh.read().decode('utf-8'))
    except Exception:
        return default_val

def save_json_to_drive(file_name, data):
    try:
        service = get_drive_service()
        if not service: return
        folder_id = get_or_create_app_folder(service)
        file_id = find_file_in_drive(service, file_name, folder_id)
        file_metadata = {'name': file_name}
        media = googleapiclient.http.MediaIoBaseUpload(
            io.BytesIO(json.dumps(data, indent=4).encode('utf-8')),
            mimetype='application/json', resumable=True
        )
        if file_id: service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata['parents'] = [folder_id]
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    except Exception:
        pass

@st.cache_data
def load_operators():
    return load_json_from_drive('operators.json', {"mobile": {"operators": {}}})

def load_orders(): return load_json_from_drive('orders.json', {})
def save_order(user_phone, order_details):
    orders = load_orders()
    if user_phone not in orders: orders[user_phone] = []
    orders[user_phone].insert(0, order_details)
    save_json_to_drive('orders.json', orders)
def update_order(user_phone, txn_id, updates):
    orders = load_orders()
    if user_phone in orders:
        for o in orders[user_phone]:
            if o['txn_id'] == txn_id:
                o.update(updates)
                break
        save_json_to_drive('orders.json', orders)

def load_grievances(): return load_json_from_drive('grievances.json', {})
def save_grievance(user_phone, grievance_details):
    grievances = load_grievances()
    if user_phone not in grievances: grievances[user_phone] = []
    grievances[user_phone].insert(0, grievance_details)
    save_json_to_drive('grievances.json', grievances)
def update_grievance(user_phone, grievance_id, updates):
    grievances = load_grievances()
    if user_phone in grievances:
        for g in grievances[user_phone]:
            if g['id'] == grievance_id:
                g.update(updates)
                break
        save_json_to_drive('grievances.json', grievances)

# ==========================================
# AUTH PATCHING & STATE
# ==========================================

original_from_client_secrets_file = google_auth_oauthlib.flow.Flow.from_client_secrets_file
def patched_from_client_secrets_file(*args, **kwargs):
    kwargs['autogenerate_code_verifier'] = False
    return original_from_client_secrets_file(*args, **kwargs)
google_auth_oauthlib.flow.Flow.from_client_secrets_file = patched_from_client_secrets_file

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_phone" not in st.session_state: st.session_state.user_phone = ""
if "checkout" not in st.session_state: st.session_state.checkout = None

authenticator = streamlit_google_auth.Authenticate(
    secret_credentials_path='app_secrets.json',
    cookie_name='ske_cookie',
    cookie_key='ske_secret_key_must_be_at_least_32_bytes_long',
    redirect_uri=APP_SECRETS.get("web", {}).get("redirect_uris", ["https://ske-recharge.streamlit.app"])[0] if "https://ske-recharge.streamlit.app" not in APP_SECRETS.get("web", {}).get("redirect_uris", []) else "https://ske-recharge.streamlit.app",
)

def patched_login(color='blue', justify_content="center"):
    if not st.session_state.get('connected'):
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            authenticator.secret_credentials_path,
            scopes=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"],
            redirect_uri=authenticator.redirect_uri,
        )
        authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true")
        
        # FLUSH LEFT TO PREVENT MARKDOWN CODE BLOCK RENDERING
        html_content = f"""
<div style="display: flex; justify-content: center; margin-top: 16px;">
<a href="{authorization_url}" target="_blank" style="background: linear-gradient(135deg, #FF7A00 0%, #FF9A3D 100%); color: #fff; text-decoration: none; text-align: center; font-size: 15px; cursor: pointer; padding: 14px 24px; border-radius: 10px; display: flex; align-items: center; justify-content: center; width: 100%; max-width: 340px; box-shadow: 0 8px 24px rgba(255, 122, 0, 0.25); transition: transform 0.2s ease; font-family: 'Poppins', sans-serif; font-weight: 600;">
<img src="https://lh3.googleusercontent.com/COxitqgJr1sJnIDe8-jiKhxDx1FrYbtRHKJ9z_hELisAlapwE9LUPh6fcXIfb5vwpbMl4xl9H9TRFPc5NOO8Sb3VSgIBrfRYvW6cUA" alt="Google" style="margin-right: 12px; width: 24px; height: 24px; background: white; border-radius: 50%; padding: 4px;">
Secure Login with Google
</a>
</div>
<div style="text-align: center; margin-top: 32px; font-size: 14px; color: #9CA3AF; font-family: 'Inter', sans-serif;">
<p>By continuing, you agree to SKE Pay's <br><b>Terms of Service</b> & <b>Privacy Policy</b></p>
<div style="display: flex; justify-content: center; gap: 16px; margin-top: 20px; opacity: 0.8; font-weight: 500;">
<span>🔒 256-bit Secure</span> • <span>🇮🇳 Made in India</span>
</div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)

authenticator.login = patched_login

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="SKE Pay - Digital India",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# COMPONENT RENDER FUNCTIONS
# ==========================================

def render_css():
    css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@500;600;700;800;900&display=swap');

:root {
    --bg: #000000;
    --surface-solid: #0A0A0A;
    --surface-2: #111111;
    --border: rgba(255, 255, 255, 0.06);
    --border-hover: rgba(255, 255, 255, 0.12);
    --primary: #FF7A00;
    --primary-glow: rgba(255, 122, 0, 0.25);
    --success: #00D084;
    --success-glow: rgba(0, 208, 132, 0.2);
    --text: #FFFFFF;
    --muted: #888888;
    --gradient: linear-gradient(135deg, #FF7A00 0%, #E65C00 100%);
}

#MainMenu, footer, header { display: none !important; }

/* Aggressive Fintech Atmosphere */
.stApp {
    background-color: var(--bg) !important;
    background-image: 
        radial-gradient(circle at 50% 0%, rgba(255, 122, 0, 0.05), transparent 40%),
        radial-gradient(circle at 100% 100%, rgba(0, 208, 132, 0.03), transparent 40%) !important;
    color: var(--text);
    font-family: 'Inter', sans-serif;
}
.main { background: transparent !important; }

/* Massive Desktop Architecture Constraint */
.block-container {
    width: 100% !important;
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding: 120px 24px 80px 24px !important;
}

/* Violent Typography Hierarchy */
h1, h2, h3, h4, h5, h6 { font-family: 'Poppins', sans-serif !important; color: var(--text) !important; letter-spacing: -0.02em; margin: 0; }
.section-title { font-size: 36px !important; font-weight: 800 !important; margin-bottom: 32px !important; line-height: 1.1; letter-spacing: -0.03em; }

/* Form Group Rhythm */
.stTextInput, .stSelectbox, .stTextArea { margin-bottom: 20px !important; }

/* Tactile Compact Inputs */
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stTextArea textarea {
    background: #0D0D0D !important; border: 1px solid var(--border) !important;
    color: white !important; border-radius: 12px !important;
    min-height: 52px !important; height: 52px !important; font-size: 16px !important; font-weight: 500 !important;
    padding: 0 16px !important; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.stTextInput input::placeholder { color: #555555 !important; font-weight: 400 !important; }
.stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
    border-color: rgba(255, 122, 0, 0.6) !important;
    box-shadow: 0 0 0 1px rgba(255, 122, 0, 0.6), inset 0 2px 4px rgba(0,0,0,0.5) !important;
    background: #000000 !important;
}
.stTextInput label, .stSelectbox label {
    color: var(--muted) !important; font-size: 12px !important; font-weight: 600 !important;
    margin-bottom: 6px !important; text-transform: uppercase; letter-spacing: 0.8px;
}

/* Sticky Right Column Summary */
[data-testid="column"]:nth-of-type(2) {
    position: sticky;
    top: 100px;
    align-self: flex-start;
}

/* Navbar System */
.glass-nav {
    position: fixed; top: 0; left: 0; right: 0; height: 72px;
    background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05); display: flex; justify-content: center; z-index: 1000;
}
.glass-nav-content {
    width: 100%; max-width: 1200px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; height: 100%;
}
.brand-wrap { display: flex; align-items: center; gap: 12px; }
.brand-flag { width: 28px; height: 20px; object-fit: cover; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
.brand-title { color: white; font-size: 20px; font-weight: 800; font-family: 'Poppins', sans-serif; line-height: 1; letter-spacing: -0.02em; }
.brand-sub { color: var(--muted); font-size: 10px; font-weight: 600; font-family: 'Inter', sans-serif; margin-top: 2px; text-transform: uppercase; letter-spacing: 1px; }

/* Logout Anchor Hack */
.logout-anchor + div { position: fixed !important; top: 18px !important; right: max(24px, calc(50vw - 600px + 24px)) !important; z-index: 1001 !important; width: auto !important; }

/* Dominant Summary Card Architecture */
.dominant-summary {
    background: linear-gradient(160deg, #111111 0%, #050505 100%);
    border: 1px solid rgba(255,122,0,0.15); border-radius: 24px; padding: 40px;
    box-shadow: 0 24px 48px rgba(0,0,0,0.8), 0 0 80px rgba(255,122,0,0.05);
}
.summary-eyebrow { font-size: 12px; color: var(--primary); font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 24px; }
.summary-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.summary-label { color: var(--muted); font-size: 15px; font-weight: 500; }
.summary-value { color: var(--text); font-size: 15px; font-weight: 600; }

/* Giant Payable Anchor */
.giant-payable-wrap { margin: 32px 0; padding: 32px 0; border-top: 1px solid rgba(255,255,255,0.06); border-bottom: 1px solid rgba(255,255,255,0.06); }
.giant-payable-label { color: var(--muted); font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.giant-payable-amount { 
    color: var(--primary); font-size: 64px; font-weight: 900; font-family: 'Poppins', sans-serif; 
    line-height: 1; letter-spacing: -0.03em; text-shadow: 0 0 40px var(--primary-glow);
}

/* Savings Animation Emphasis */
.savings-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(0, 208, 132, 0.1); border: 1px solid rgba(0, 208, 132, 0.2);
    color: var(--success); font-weight: 700; font-size: 14px; padding: 8px 16px; border-radius: 8px;
    box-shadow: 0 0 20px var(--success-glow);
}

/* Trust Indicators */
.trust-row { display: flex; align-items: center; gap: 12px; font-size: 13px; color: #666; font-weight: 600; margin-bottom: 12px; }
.trust-row i { color: var(--success); font-style: normal; }

/* Streamlit Native CTA Overrides */
.stButton > button[kind="primary"] {
    background: var(--gradient) !important; color: #fff !important; border: none !important;
    border-radius: 12px !important; font-weight: 800 !important; font-family: 'Poppins', sans-serif !important;
    box-shadow: 0 8px 32px var(--primary-glow), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; padding: 0 24px !important; 
    height: 64px !important; width: 100% !important; font-size: 18px !important; letter-spacing: 0.5px;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px); box-shadow: 0 16px 40px rgba(255, 122, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    filter: brightness(1.1);
}
.stButton > button[kind="secondary"] {
    background: #111111 !important; border: 1px solid var(--border) !important;
    color: var(--text) !important; border-radius: 12px !important; font-weight: 700 !important; font-family: 'Inter', sans-serif !important;
    height: 56px !important; width: 100% !important; font-size: 16px !important; transition: all 0.2s ease !important;
}
.stButton > button[kind="secondary"]:hover { background: #1A1A1A !important; border-color: var(--border-hover) !important; }
.stButton > button[kind="tertiary"] {
    background: transparent !important; border: 1px solid var(--border) !important; color: var(--muted) !important;
    padding: 0 16px !important; border-radius: 8px !important; height: 36px !important; font-size: 12px !important; font-weight: 600 !important;
}
.stButton > button[kind="tertiary"]:hover { color: var(--text) !important; background: #111111 !important; border-color: var(--border-hover) !important; }

/* Segmented Tabs */
div[data-testid="stTabs"] { background: transparent; margin-bottom: 40px; }
div[data-baseweb="tab-list"] {
    gap: 8px; background: rgba(0,0,0,0.5); backdrop-filter: blur(12px); padding: 6px;
    border-radius: 100px; border: 1px solid rgba(255,255,255,0.05); box-shadow: inset 0 2px 4px rgba(0,0,0,0.5); display: inline-flex;
}
div[data-baseweb="tab"] {
    background: transparent !important; border: none !important; border-radius: 100px !important; color: var(--muted) !important;
    font-family: 'Inter', sans-serif; font-weight: 600; padding: 10px 24px !important; height: 44px; display: flex; font-size: 14px !important; transition: all 0.3s ease !important;
}
div[data-baseweb="tab"]:hover { color: var(--text) !important; }
div[data-baseweb="tab"][aria-selected="true"] {
    background: #1A1A1A !important; color: var(--text) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1) !important;
}

/* Remove default form styling */
.stForm { border: none !important; padding: 0 !important; background: transparent !important; box-shadow: none !important; }

/* Mobile Bottom Sticky CTA */
@media (max-width: 768px) {
    .mobile-sticky-cta {
        position: fixed; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.9);
        backdrop-filter: blur(20px); border-top: 1px solid rgba(255,255,255,0.1); padding: 16px 20px; z-index: 999;
    }
    .block-container { padding-bottom: 120px !important; }
}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def render_navbar():
    html = f"""
<div class="glass-nav">
<div class="glass-nav-content">
<div class="brand-wrap">
<img src="data:image/png;base64,{flag_base64}" class="brand-flag">
<div class="brand-text">
<div class="brand-title">SKE Pay</div>
<div class="brand-sub">Next Gen Payments</div>
</div>
</div>
</div>
</div>
<div class="logout-anchor"></div>
"""
    st.markdown(html, unsafe_allow_html=True)
    if st.button("Logout", type="tertiary"):
        authenticator.logout()
        st.session_state.logged_in = False
        st.session_state.user_phone = ""
        st.session_state.checkout = None
        st.rerun()

def render_live_summary(phone, operator, plan_str, price, discount, total):
    plan_name = plan_str.split(' (')[0] if '(' in plan_str else 'No Plan Selected'
    
    # Conditional animation class rendering
    savings_html = f"""
<div class="savings-badge">
<span style="font-size: 16px;">⚡</span> 0.23% Smart Discount
</div>
""" if discount > 0 else ""

    html = f"""
<div class="dominant-summary">
<div class="summary-eyebrow">Transaction Summary</div>

<div style="font-size: 24px; font-weight: 800; font-family: 'Poppins', sans-serif; color: white; margin-bottom: 4px; line-height: 1.2;">{plan_name}</div>
<div style="color: #666; font-size: 14px; font-weight: 600; margin-bottom: 32px;">MRP: ₹{price:.2f}</div>

<div class="summary-row">
<span class="summary-label">Recharge Target</span>
<span class="summary-value" style="font-family: monospace; font-size: 16px;">{phone if phone else '—'}</span>
</div>
<div class="summary-row">
<span class="summary-label">Network Operator</span>
<span class="summary-value">{operator if operator != "Select Operator" else '—'}</span>
</div>

<div style="margin-top: 24px; margin-bottom: 8px;">
{savings_html}
</div>

<div class="giant-payable-wrap">
<div class="giant-payable-label">Total Payable</div>
<div class="giant-payable-amount">₹{total:.2f}</div>
</div>

<div class="trust-row"><i>✔</i> Instant Processing via UPI Infrastructure</div>
<div class="trust-row"><i>✔</i> 256-bit Secure Encryption</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ==========================================
# MAIN ROUTING
# ==========================================

data = load_operators()
authenticator.check_authentification()

if not st.session_state.get('connected'):
    render_css()
    html_landing = f"""
<div style="text-align: center; padding: 100px 20px;">
<img src="data:image/png;base64,{flag_base64}" style="width: 100px; height: 70px; object-fit: cover; border-radius: 6px; margin-bottom: 32px; box-shadow: 0 16px 32px rgba(0,0,0,0.5);">
<h1 style="color: white; font-weight: 900; font-size: 64px; margin-bottom: 12px; font-family: 'Poppins', sans-serif; letter-spacing: -0.04em;">SKE Pay</h1>
<p style="color: #FF7A00; font-weight: 700; font-size: 20px; margin-top: 0; font-family: 'Poppins', sans-serif; letter-spacing: 1px; text-transform: uppercase;">India's Next-Gen Payments</p>
<p style="color: #888; font-size: 16px; margin-top: 32px; max-width: 360px; margin-left: auto; margin-right: auto; line-height: 1.6; font-weight: 500;">Lightning fast mobile recharges, trusted by millions of Indians.</p>
</div>
"""
    st.markdown(html_landing, unsafe_allow_html=True)
    authenticator.login()
    st.stop()
else:
    st.session_state.logged_in = True
    user_info = st.session_state.get('user_info', {})
    st.session_state.user_phone = user_info.get('email', 'unknown@google.com')

render_css()
render_navbar()

if st.session_state.checkout:
    c = st.session_state.checkout
    original_price = float(c['price'].replace('₹', '').replace(',', '').strip())
    discount_percent_val = round(random.uniform(0.1, 0.5), 2)
    discount = (original_price * discount_percent_val) / 100
    final_price = max(0.0, original_price - discount)
    c['discount_percent'] = f"{discount_percent_val:.2f}"
    c['final_price'] = f"{final_price:.2f}"
    c['mrp'] = f"{original_price:.2f}"
    c['discount'] = f"{discount:.2f}" 

    if "current_txn_id" not in st.session_state:
        st.session_state.current_txn_id = f"UPI_{uuid.uuid4().hex[:10].upper()}"
    txn_id = st.session_state.current_txn_id
    
    merchant_vpa = "akgaya99@okaxis" 
    merchant_name = "SriKailashElectronics"
    transaction_note = f"Order+{txn_id}"
    upi_link = f"upi://pay?pa={merchant_vpa}&pn={merchant_name}&am={c['final_price']}&cu=INR&tn={transaction_note}"

    col1, col2 = st.columns([4, 6], gap="large")
    
    with col1:
        html_checkout_header = f"""
<div class="section-title">Finalize<br>Payment</div>
<p style="color: #888; font-size: 15px; margin-bottom: 32px; font-weight: 500; line-height: 1.6;">Your transaction is securely locked. Pay via any UPI app to complete.</p>

<div style="background: rgba(0,0,0,0.5); padding: 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 32px;">
<div style="color: #666; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Transaction ID</div>
<div style="color: white; font-family: monospace; font-size: 16px; font-weight: 600;">{txn_id}</div>
</div>
"""
        st.markdown(html_checkout_header, unsafe_allow_html=True)
        
        st.markdown(f'<a href="{upi_link}" target="_blank" style="display: flex; justify-content: center; align-items: center; background: linear-gradient(135deg, #FF7A00 0%, #E65C00 100%); color: white; padding: 0 24px; height: 64px; border-radius: 12px; font-weight: 800; font-size: 18px; font-family: \'Poppins\', sans-serif; text-decoration: none; box-shadow: 0 8px 32px rgba(255, 122, 0, 0.25); transition: transform 0.2s ease, filter 0.2s ease; margin-bottom: 24px; letter-spacing: 0.5px;">Pay ₹{c["final_price"]} via UPI</a>', unsafe_allow_html=True)
        
        st.markdown("<div style='font-size: 13px; color: #666; margin-bottom: 16px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Step 2: Confirmation</div>", unsafe_allow_html=True)
        with st.form("upi_verify_form"):
            verify_btn = st.form_submit_button("I Have Paid", type="secondary")
            if verify_btn:
                with st.spinner("Verifying transaction..."): time.sleep(1.5)
                order = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "txn_id": txn_id, "type": c['type'].capitalize(),
                    "target": c['target'], "operator": c['operator'],
                    "plan_str": c.get('plan_str', ''), "mrp": c.get('mrp', c['final_price']),
                    "discount": c.get('discount', '0.00'),
                    "amount": c['final_price'], "method": "UPI", "status": "Order Created"
                }
                save_order(st.session_state.user_phone, order)
                send_notification_email(st.session_state.user_phone, f"Order Received: {txn_id}", get_order_created_html(order))
                for admin in ADMIN_EMAILS: send_notification_email(admin, f"New Order: {txn_id}", get_order_created_html(order))
                st.success(f"Order Submitted! Verification pending.")
                time.sleep(2)
                st.session_state.checkout = None
                if "current_txn_id" in st.session_state: del st.session_state.current_txn_id
                st.rerun()

        st.markdown("<div style='margin-top: 16px;'>", unsafe_allow_html=True)
        if st.button("Cancel & Go Back", type="tertiary"):
            st.session_state.checkout = None
            if "current_txn_id" in st.session_state: del st.session_state.current_txn_id
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        render_live_summary(c['target'], c['operator'], c['plan_str'], original_price, discount, final_price)

else:
    is_admin = st.session_state.user_phone in ADMIN_EMAILS
    if is_admin:
        tabs = st.tabs(["📱 Recharge", "📦 Activity", "🎧 Support", "🛠️ Admin"])
        tab1, tab_orders, tab_grievances, tab_admin = tabs
    else:
        tabs = st.tabs(["📱 Recharge", "📦 Activity", "🎧 Support"])
        tab1, tab_orders, tab_grievances = tabs

    def get_operator(phone):
        if not phone or len(phone) < 2: return "Select Operator"
        prefix = phone[:2]
        mobile_ops_data = data.get("mobile", {}).get("operators", {})
        if isinstance(mobile_ops_data, dict):
            for op, op_info in mobile_ops_data.items():
                if prefix in op_info.get("prefixes", []): return op
        return "Select Operator"

    with tab1:
        col1, col2 = st.columns([4, 6], gap="large")
        
        with col1:
            st.markdown("<div class='section-title'>Mobile<br>Recharge</div>", unsafe_allow_html=True)
            
            if "last_phone_prefix" not in st.session_state: st.session_state.last_phone_prefix = ""
            phone_number = st.text_input("Mobile Number", placeholder="e.g., 9876543210", max_chars=10, key="mobile_phone")
            
            mobile_ops_data = data.get("mobile", {}).get("operators", {})
            if isinstance(mobile_ops_data, dict): mobile_ops = ["Select Operator"] + list(mobile_ops_data.keys())
            else: mobile_ops = ["Select Operator"] + mobile_ops_data
                
            current_prefix = phone_number[:2] if phone_number else ""
            if current_prefix != st.session_state.last_phone_prefix:
                st.session_state.last_phone_prefix = current_prefix
                detected_op = get_operator(phone_number)
                st.session_state.mobile_op = detected_op if detected_op in mobile_ops else "Select Operator"
                    
            operator = st.selectbox("Select Operator", mobile_ops, key="mobile_op")
            
            mobile_plans = mobile_ops_data[operator].get("plans", []) if operator != "Select Operator" and isinstance(mobile_ops_data, dict) and operator in mobile_ops_data else []
            plan_options = [f"{p['type']} - {p['description']} (₹{p['price']})" for p in mobile_plans]
            plan_options.insert(0, "Select a Plan")
            selected_plan_str = st.selectbox("Select Plan", plan_options, key="mobile_plan")
            
            st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
            
            # Dynamic CTA logic
            preview_price = 0.00
            preview_discount = 0.00
            preview_total = 0.00
            if selected_plan_str != "Select a Plan":
                try:
                    preview_price = float(selected_plan_str.split(" ")[-1][1:-1])
                    preview_discount = preview_price * 0.0023
                    preview_total = preview_price - preview_discount
                except: pass
            
            btn_text = f"Pay ₹{preview_total:.2f} Securely" if preview_total > 0 else "Continue to Secure Payment"
            
            if st.button(btn_text, key="mobile_btn", type="primary"):
                if not phone_number or not phone_number.isdigit() or len(phone_number) != 10: st.error("Enter a valid 10-digit mobile number.")
                elif operator == "Select Operator": st.error("Select an operator.")
                elif selected_plan_str == "Select a Plan": st.error("Select a recharge plan.")
                else:
                    price_str = selected_plan_str.split(" ")[-1][1:-1]
                    st.session_state.checkout = { "type": "mobile", "target": phone_number, "operator": operator, "price": price_str, "plan_str": selected_plan_str }
                    st.rerun()

        with col2:
            render_live_summary(phone_number, operator, selected_plan_str, preview_price, preview_discount, preview_total)

    with tab_orders:
        st.markdown("<div class='section-title'>Activity History</div>", unsafe_allow_html=True)
        orders_db = load_orders()
        user_orders = orders_db.get(st.session_state.user_phone, [])
        if not user_orders:
            st.info("You have no past transactions.")
        else:
            if st.button("Refresh", type="secondary"): st.rerun()
            for o in user_orders:
                with st.container():
                    status_class = "success" if o['status'] == "Recharge Completed" else "pending"
                    badge_class = "status-success" if o['status'] == "Recharge Completed" else "status-pending"
                    html = f"""
<div style="background: #111111; border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 24px; margin-bottom: 24px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
<div>
<div style="font-family: 'Poppins', sans-serif; font-weight: 700; color: white; font-size: 18px;">{o['type']} • {o['operator']}</div>
<div style="color: #888; font-size: 14px; font-weight: 500; margin-top: 4px;">{o['target']}</div>
</div>
<div style="display: inline-flex; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 700; font-family: 'Inter', sans-serif; text-transform: uppercase; letter-spacing: 0.5px; background: rgba(16, 185, 129, 0.1); color: #00D084; border: 1px solid rgba(0, 208, 132, 0.2);">{o['status']}</div>
</div>
<div style="background: rgba(0,0,0,0.5); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.03);">
<div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 12px;">
<span style="color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">MRP</span><span style="font-weight: 600; color: white;">₹{o.get('mrp', o['amount'])}</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 12px;">
<span style="color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Smart Discount</span><span style="color: #00D084; font-weight: 700;">-₹{o.get('discount', '0.00')}</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 18px; margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 20px;">
<span style="color: white; font-weight: 600;">Paid Amount</span><span style="color: #FF7A00; font-weight: 800; font-family: 'Poppins', sans-serif;">₹{o['amount']}</span>
</div>
</div>
<div style="font-size: 12px; color: #666; display: flex; flex-direction: column; gap: 8px; font-family: monospace;">
<div>Txn: <span style="color: #AAA;">{o['txn_id']}</span> • {o['date'][:10]}</div><div>Method: {o['method']}</div>
"""
                    if "payment_utr" in o: html += f"<div>Pay UTR: <span style='color: #AAA;'>{o['payment_utr']}</span></div>"
                    if "recharge_utr" in o: html += f"<div>Rech UTR: <span style='color: #AAA;'>{o['recharge_utr']}</span></div>"
                    html += "</div></div>"
                    st.markdown(html, unsafe_allow_html=True)
                
                with st.expander(f"Raise Support Ticket"):
                    with st.form(f"grievance_form_{o['txn_id']}"):
                        issue_type = st.selectbox("Issue Type", ["Recharge Not Received", "Amount Deducted but Order Failed", "Wrong Target Recharge", "Other"])
                        details = st.text_area("Details", placeholder="Describe the issue...")
                        if st.form_submit_button("Submit Ticket", type="primary"):
                            grievance = {
                                "id": f"TKT_{uuid.uuid4().hex[:8].upper()}", "txn_id": o['txn_id'], "issue_type": issue_type,
                                "details": details, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "Open", "admin_reply": ""
                            }
                            save_grievance(st.session_state.user_phone, grievance)
                            send_notification_email(st.session_state.user_phone, f"Ticket Submitted: {grievance['id']}", get_grievance_created_html(grievance))
                            for admin in ADMIN_EMAILS: send_notification_email(admin, f"New Ticket: {grievance['id']}", get_grievance_created_html(grievance))
                            st.success("Ticket raised successfully. Check 'Support' tab.")
                            time.sleep(2)
                            st.rerun()

    with tab_grievances:
        st.markdown("<div class='section-title'>Support Tickets</div>", unsafe_allow_html=True)
        grievances_db = load_grievances()
        user_grievances = grievances_db.get(st.session_state.user_phone, [])
        if not user_grievances: st.info("No active support tickets.")
        else:
            for g in user_grievances:
                html = f"""
<div style="background: #111111; border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 24px; margin-bottom: 24px;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
<div style="font-family: 'Poppins', sans-serif; font-weight: 700; font-size: 18px; color: white;">Ticket: {g['id']}</div>
<div style="display: inline-flex; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 700; font-family: 'Inter', sans-serif; text-transform: uppercase; letter-spacing: 0.5px; background: rgba(255, 122, 0, 0.1); color: #FF7A00; border: 1px solid rgba(255, 122, 0, 0.2);">{g['status']}</div>
</div>
<div style="font-size: 13px; color: #888; font-family: monospace; margin-bottom: 24px;">Txn: {g['txn_id']} • {g['date'][:10]}</div>
<div style="background: rgba(0,0,0,0.5); padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.03); font-size: 14px; margin-bottom: 16px;">
<span style="font-weight: 700; color: white;">{g['issue_type']}</span><br>
<span style="color: #AAA; margin-top: 8px; display: inline-block; line-height: 1.6;">{g['details']}</span>
</div>
<div style="font-size: 14px; background: rgba(255,122,0,0.05); padding: 20px; border-radius: 12px; border: 1px solid rgba(255,122,0,0.1);">
<span style="font-weight: 700; color: #FF7A00; text-transform: uppercase; letter-spacing: 0.5px; font-size: 12px;">Support Reply:</span><br>
<span style="color: {'white' if g['admin_reply'] else '#888'}; margin-top: 8px; display: inline-block; line-height: 1.6; font-weight: 500;">{g['admin_reply'] if g['admin_reply'] else 'Awaiting agent response...'}</span>
</div>
</div>
"""
                st.markdown(html, unsafe_allow_html=True)

    if is_admin:
        with tab_admin:
            st.markdown("<div class='section-title'>🛠️ Admin Control Tower</div>", unsafe_allow_html=True)
            orders_db = load_orders()
            grievances_db = load_grievances()
            admin_tabs = st.tabs(["⏳ Pending", "📋 All Orders", "🚨 Tickets", "⚙️ Config"])
            
            with admin_tabs[0]:
                st.write("### Pending Orders")
                pending_count = 0
                for user, user_orders in orders_db.items():
                    for o in user_orders:
                        if o['status'] != "Recharge Completed":
                            pending_count += 1
                            cols = st.columns([1.5, 1.5, 1, 1, 1.5, 2])
                            cols[0].write(user)
                            cols[1].write(o['txn_id'])
                            cols[2].write(o['target'])
                            cols[3].write(f"₹{o['amount']}")
                            cols[4].write(o['status'])
                            with cols[5]:
                                if o['status'] == "Order Created":
                                    with st.form(f"pay_form_{o['txn_id']}", clear_on_submit=True):
                                        payment_id = st.text_input("Payment ID (Optional)", placeholder="Bank Ref")
                                        if st.form_submit_button("Confirm Payment", type="primary"):
                                            update_data = {"status": "Payment Confirmed"}
                                            if payment_id: update_data["payment_utr"] = payment_id
                                            update_order(user, o['txn_id'], update_data)
                                            o_updated = o.copy()
                                            o_updated.update(update_data)
                                            send_notification_email(user, f"Payment Confirmed: {o['txn_id']}", get_payment_confirmed_html(o_updated))
                                            st.success("Confirmed!")
                                            time.sleep(1)
                                            st.rerun()
                                elif o['status'] == "Payment Confirmed":
                                    with st.form(f"rech_form_{o['txn_id']}", clear_on_submit=True):
                                        recharge_utr = st.text_input("Recharge UTR", placeholder="Required")
                                        if st.form_submit_button("Complete Recharge", type="primary"):
                                            if not recharge_utr: st.error("UTR Required")
                                            else:
                                                update_data = {"status": "Recharge Completed", "recharge_utr": recharge_utr}
                                                update_order(user, o['txn_id'], update_data)
                                                o_updated = o.copy()
                                                o_updated.update(update_data)
                                                send_notification_email(user, f"Recharge Successful: {o['txn_id']}", get_recharge_completed_html(o_updated))
                                                st.success("Completed!")
                                                time.sleep(1)
                                                st.rerun()
                            st.markdown("---")
                if pending_count == 0: st.info("No pending orders.")

            with admin_tabs[1]:
                st.write("### All Orders")
                all_orders_list = []
                for user, user_orders in orders_db.items():
                    for o in user_orders:
                        all_orders_list.append({
                            "User": user, "Date": o['date'], "TXN ID": o['txn_id'], "Target": o['target'],
                            "Operator": o['operator'], "MRP": f"₹{o.get('mrp', o['amount'])}",
                            "Paid": f"₹{o['amount']}", "Status": o['status']
                        })
                if all_orders_list:
                    all_orders_list.sort(key=lambda x: x["Date"], reverse=True)
                    st.dataframe(all_orders_list, use_container_width=True)
                else: st.info("No orders found.")
            
            with admin_tabs[2]:
                st.write("### Open Tickets")
                open_g_count = 0
                for user, user_grievances in grievances_db.items():
                    for g in user_grievances:
                        if g['status'] == "Open":
                            open_g_count += 1
                            st.markdown(f"#### Ticket: {g['id']} by {user}")
                            st.write(f"**TXN ID:** {g['txn_id']} | **Type:** {g['issue_type']}")
                            st.write(f"**Details:** {g['details']}")
                            with st.form(f"resolve_grievance_{g['id']}"):
                                reply = st.text_area("Reply to User")
                                if st.form_submit_button("Mark Resolved", type="primary"):
                                    update_data = {"status": "Resolved", "admin_reply": reply}
                                    update_grievance(user, g['id'], update_data)
                                    g_updated = g.copy()
                                    g_updated.update(update_data)
                                    send_notification_email(user, f"Grievance Resolved: {g['id']}", get_grievance_resolved_html(g_updated))
                                    st.success("Resolved!")
                                    time.sleep(1)
                                    st.rerun()
                            st.markdown("---")
                if open_g_count == 0: st.info("No open tickets.")

            with admin_tabs[3]:
                st.write("### Operators Configuration")
                operators_data = load_operators()
                if "mobile" not in operators_data: operators_data["mobile"] = {"operators": {}}
                mobile_ops = operators_data["mobile"]["operators"]
                op_names = list(mobile_ops.keys())
                st.write("#### Add New Operator")
                with st.form("add_op_form", clear_on_submit=True):
                    col1, col2 = st.columns([3, 1])
                    new_op_name = col1.text_input("New Operator Name")
                    if col2.form_submit_button("Add", type="secondary") and new_op_name and new_op_name not in mobile_ops:
                        operators_data["mobile"]["operators"][new_op_name] = {"prefixes": [], "plans": []}
                        save_json_to_drive('operators.json', operators_data)
                        st.cache_data.clear()
                        st.rerun()
                        
                st.write("#### Edit Existing Operator")
                if op_names:
                    selected_op = st.selectbox("Select Operator", op_names)
                    op_data = mobile_ops[selected_op]
                    with st.form(f"edit_op_form_{selected_op}"):
                        new_prefixes = st.text_input("Prefixes (comma-separated)", ", ".join(op_data.get("prefixes", [])))
                        st.write("**Plans**")
                        current_plans = op_data.get("plans", []) or [{"type": "", "description": "", "price": 0}]
                        edited_plans = st.data_editor(current_plans, num_rows="dynamic", use_container_width=True, key=f"de_mob_{selected_op}")
                        if st.form_submit_button("Save Changes", type="primary"):
                            op_data["prefixes"] = [p.strip() for p in new_prefixes.split(",") if p.strip()]
                            op_data["plans"] = [p for p in edited_plans if str(p.get("type", "")).strip() or str(p.get("description", "")).strip() or p.get("price")]
                            operators_data["mobile"]["operators"][selected_op] = op_data
                            save_json_to_drive('operators.json', operators_data)
                            st.cache_data.clear()
                            st.success(f"Saved {selected_op}!")
                            time.sleep(1)
                            st.rerun()
                    if st.button(f"Delete {selected_op}", type="tertiary"):
                        del operators_data["mobile"]["operators"][selected_op]
                        save_json_to_drive('operators.json', operators_data)
                        st.cache_data.clear()
                        st.rerun()
                else: st.info("No mobile operators found.")
