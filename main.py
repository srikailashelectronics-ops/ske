import streamlit as st
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

def get_grievance_reopened_html(grievance):
    return f"<h2>Grievance Reopened</h2><p>Grievance {grievance['id']} has been reopened.</p><p>We will re-evaluate your issue.</p>"

original_from_client_secrets_file = google_auth_oauthlib.flow.Flow.from_client_secrets_file
def patched_from_client_secrets_file(*args, **kwargs):
    kwargs['autogenerate_code_verifier'] = False
    return original_from_client_secrets_file(*args, **kwargs)
google_auth_oauthlib.flow.Flow.from_client_secrets_file = patched_from_client_secrets_file

st.set_page_config(
    page_title="SKE Pay - Digital India",
    page_icon="🇮🇳",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@500;600;700;800&display=swap');
    
    :root {
        --bg: #0B1120;
        --surface: #111827;
        --surface-2: #1F2937;
        --card: #182235;
        --border: rgba(255,255,255,0.06);
        --primary: #FF7A00;
        --primary-hover: #FF8F26;
        --text: #F9FAFB;
        --muted: #94A3B8;
        --success: #22C55E;
        --danger: #EF4444;
        --gradient: linear-gradient(135deg, #FF7A00 0%, #FF9A3D 100%);
    }

    #MainMenu, footer, header { display: none !important; }

    /* Basic App Background */
    .stApp, .main, .block-container {
        background-color: var(--bg) !important;
        color: var(--text);
        font-family: 'Inter', sans-serif;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Poppins', sans-serif !important;
        color: var(--text) !important;
        letter-spacing: -0.02em;
    }

    p, span, div {
        color: var(--text);
    }

    
    /* Streamlit block container reset and desktop width fix */
    .block-container {
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }

    .main .block-container {
        padding-top: 0rem !important;
        max-width: 1280px !important;
        padding: 16px !important;
        margin: 0 auto;
    }
    
    section.main > div {
        padding-top: 0rem !important;
    }

    @media (min-width: 768px) {
        .main .block-container {
            padding: 32px !important;
        }
        
        .content-column {
            max-width: 760px;
            margin: 0 auto;
        }
    }
    
    body {
        padding-bottom: env(safe-area-inset-bottom);
    }
    
    /* Brand Logo / Navbar */
    .ske-navbar {
        height: 72px;
        display: flex;
        
        justify-content: space-between;
        background: transparent;
        margin-bottom: 18px;
    }
    .brand-wrap {
        display: flex;
        
        gap: 10px;
    }
    .brand-flag {
        width: 28px;
        height: 20px;
        object-fit: cover;
        border-radius: 4px;
    }
    .brand-text {
        color: white;
        font-size: 22px;
        font-weight: 700;
        font-family: 'Poppins';
    }
    
    /* Dropdown Portal */
    div[data-baseweb="popover"] {
        background: #111827 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.45) !important;
    }

    /* Dropdown List */
    ul {
        background: #111827 !important;
    }

    /* Dropdown Options */
    li[role="option"] {
        background: #111827 !important;
        color: #F9FAFB !important;
        font-weight: 500 !important;
    }

    /* Hovered Option */
    li[role="option"]:hover {
        background: rgba(255,122,0,0.12) !important;
        color: #FFFFFF !important;
    }

    /* Selected Option */
    li[aria-selected="true"] {
        background: rgba(255,122,0,0.18) !important;
        color: #FF9A3D !important;
    }

    /* Forms & Inputs */
    .stTextInput input, 
    .stSelectbox div[data-baseweb="select"] > div,
    .stTextArea textarea {
        background: rgba(17,24,39,0.72) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        color: white !important;
        border-radius: 18px !important;
        min-height: 56px !important;
        font-size: 16px !important;
        backdrop-filter: blur(8px);
        margin-bottom: 14px !important;
    }
    .stTextInput input:focus, 
    .stSelectbox div[data-baseweb="select"] > div:focus-within,
    .stTextArea textarea:focus {
        border-color: #FF7A00 !important;
        box-shadow: 0 0 0 3px rgba(255,122,0,0.12) !important;
    }

    /* Buttons */
    .stButton > button {
        background: var(--gradient) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-family: 'Poppins', sans-serif !important;
        box-shadow: 0 4px 14px rgba(255, 122, 0, 0.25) !important;
        transition: all 0.2s ease !important;
        padding: 8px 16px !important;
        height: auto !important;
        min-height: 44px;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 122, 0, 0.35) !important;
    }

    /* Tabs */
    div[data-testid="stTabs"] {
        background: transparent;
        margin-bottom: 14px;
    }
    div[data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--surface);
        padding: 4px;
        border-radius: 16px;
        border: 1px solid var(--border);
        min-height: 56px;
        
    }
    div[data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        border-radius: 12px;
        color: var(--muted) !important;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        padding: 8px 12px !important;
        height: 48px;
        display: flex;
        
        
    }
    div[data-baseweb="tab"][aria-selected="true"] {
        background: var(--surface-2) !important;
        color: var(--text) !important;
        box-shadow: inset 0 -2px 0 var(--primary) !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: var(--surface) !important;
        color: var(--text) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
    }

    /* Hero */
    .hero-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 20px;
        text-align: center;
        position: relative;
        overflow: hidden;
        margin-bottom: 16px;
    }
    .hero-card::before {
        content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
        background: radial-gradient(circle, rgba(255,122,0,0.1) 0%, rgba(0,0,0,0) 70%);
        pointer-events: none;
    }
    .hero-label { font-size: 14px; color: var(--muted); font-weight: 500; text-transform: uppercase; letter-spacing: 1px; }
    .hero-amount { font-size: 28px; font-weight: 700; font-family: 'Poppins', sans-serif; color: var(--text); margin: 8px 0; }
    .hero-sub { font-size: 12px; color: var(--success); font-weight: 500; }

    /* Custom Cards */
    .dark-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 14px;
    }
    
    .status-badge { display: inline-flex;  padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; font-family: 'Inter', sans-serif; }
    .status-success { background: rgba(34, 197, 94, 0.1); color: var(--success); }
    .status-pending { background: rgba(255, 122, 0, 0.1); color: var(--primary); }
</style>
""", unsafe_allow_html=True)

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

data = load_operators()

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
        html_content = f"""
<div style="display: flex; justify-content: {justify_content}; margin-top: 30px;">
    <a href="{authorization_url}" target="_blank" style="background: linear-gradient(135deg, #FF7A00 0%, #FF9A3D 100%); color: #fff; text-decoration: none; text-align: center; font-size: 16px; cursor: pointer; padding: 16px 28px; border-radius: 16px; display: flex;   width: 100%; max-width: 320px; box-shadow: 0 8px 25px rgba(255, 122, 0, 0.25); transition: transform 0.3s ease; font-family: 'Poppins', sans-serif; font-weight: 600;">
        <img src="https://lh3.googleusercontent.com/COxitqgJr1sJnIDe8-jiKhxDx1FrYbtRHKJ9z_hELisAlapwE9LUPh6fcXIfb5vwpbMl4xl9H9TRFPc5NOO8Sb3VSgIBrfRYvW6cUA" alt="Google" style="margin-right: 14px; width: 28px; height: 28px; background: white; border-radius: 50%; padding: 4px;">
        Secure Login with Google
    </a>
</div>
<div style="text-align: center; margin-top: 25px; font-size: 13px; color: #94A3B8; font-family: 'Inter', sans-serif;">
    <p>By continuing, you agree to SKE Pay's <br><b>Terms of Service</b> & <b>Privacy Policy</b></p>
    <div style="display: flex;  gap: 10px; margin-top: 15px; opacity: 0.6;">
        <span>🔒 256-bit Secure</span> • <span>🇮🇳 Made in India</span>
    </div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)

authenticator.login = patched_login
authenticator.check_authentification()

if not st.session_state.get('connected'):
    st.markdown("""
    <div style="text-align: center; padding: 40px 20px 20px 20px;">
        <img src="https://upload.wikimedia.org/wikipedia/en/thumb/4/41/Flag_of_India.svg/2560px-Flag_of_India.svg.png" style="width: 80px; height: 50px; object-fit: cover; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 10px 20px rgba(0,0,0,0.3);">
        <h1 style="color: #F9FAFB; font-weight: 800; font-size: 32px; margin-bottom: 5px;">SKE Pay</h1>
        <p style="color: #FF7A00; font-weight: 600; font-size: 16px; margin-top: 0; font-family: 'Poppins', sans-serif;">India's Next-Gen Payments</p>
        <p style="color: #94A3B8; font-size: 14px; margin-top: 15px; max-width: 280px; margin-left: auto; margin-right: auto; line-height: 1.5;">Lightning fast mobile recharges, trusted by millions of Indians.</p>
    </div>
    """, unsafe_allow_html=True)
    authenticator.login()
    st.stop()
else:
    st.session_state.logged_in = True
    user_info = st.session_state.get('user_info', {})
    st.session_state.user_phone = user_info.get('email', 'unknown@google.com')

# --- MAIN APP FLOW ---


st.markdown("""
    <style>
        .logout-wrapper {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            height: 72px;
            margin-bottom: 18px;
        }
        .logout-wrapper button {
            height: 40px !important;
            min-height: 40px !important;
            padding: 0 16px !important;
            border-radius: 12px !important;
            font-size: 14px !important;
            box-shadow: none !important;
            width: auto !important;
            background: rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border: none !important;
        }
        .logout-wrapper button:hover {
            background: rgba(255, 255, 255, 0.15) !important;
        }
    </style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1])
with col1:
    st.markdown("""
    <div class="ske-navbar">
        <div class="brand-wrap">
            <img src="https://upload.wikimedia.org/wikipedia/en/thumb/4/41/Flag_of_India.svg/2560px-Flag_of_India.svg.png" class="brand-flag">
            <div class="brand-text">SKE Pay</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown('<div class="logout-wrapper">', unsafe_allow_html=True)
    if st.button("Logout", key="logout_btn"):
        authenticator.logout()
        st.session_state.logged_in = False
        st.session_state.user_phone = ""
        st.session_state.checkout = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
# Apply the content column wrapper around the main body (excluding the top navbar)
st.markdown('<div class="content-column">', unsafe_allow_html=True)

st.markdown("""
<div class="hero-card">
    <div class="hero-label">Recharge & Pay Bills</div>
    <div class="hero-amount">Fast & Secure</div>
    <div class="hero-sub">Zero Convenience Fees • UPI Ready</div>
</div>
""", unsafe_allow_html=True)

if st.session_state.checkout:
    st.markdown("<h3 style='padding: 0 20px; font-family: Poppins;'>💳 Secure Checkout</h3>", unsafe_allow_html=True)
    c = st.session_state.checkout
    
    original_price = float(c['price'].replace('₹', '').replace(',', '').strip())
    discount_percent_val = round(random.uniform(0.1, 0.5), 2)
    discount = (original_price * discount_percent_val) / 100
    final_price = max(0.0, original_price - discount)
    
    c['discount_percent'] = f"{discount_percent_val:.2f}"
    c['final_price'] = f"{final_price:.2f}"
    c['mrp'] = f"{original_price:.2f}"
    c['discount'] = f"{discount:.2f}" 
    
    st.markdown(f"""
    <div style="padding: 0 20px;">
        <div style="background: var(--surface); border-radius: 16px; padding: 20px; border: 1px solid #EAECEF; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                <span style="color: #94A3B8; font-weight: 500;">Recharge Number</span>
                <span style="font-weight: 600; color: #F9FAFB;">{c['target']}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                <span style="color: #94A3B8; font-weight: 500;">Operator</span>
                <span style="font-weight: 600; color: #F9FAFB;">{c['operator']}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                <span style="color: #94A3B8; font-weight: 500;">MRP</span>
                <span style="font-weight: 600; color: #F9FAFB;">₹{original_price:.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 14px; color: #138808; font-weight: 600;">
                <span>⚡ Instant Smart Discount ({c['discount_percent']}%)</span>
                <span>- ₹{discount:.2f}</span>
            </div>
            <hr style="margin: 0 0 16px 0; border-top: 1px dashed #EAECEF;">
            <div style="display: flex; justify-content: space-between; ">
                <span style="font-size: 18px; font-weight: 700; color: #F9FAFB;">Total Payable</span>
                <span style="font-size: 24px; font-weight: 800; color: #FF7A00;">₹{c['final_price']}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    payment_method = st.radio("Select Payment Method", ["Google Pay / UPI", "Credit / Debit Card"])
    
    if payment_method == "Google Pay / UPI":
        st.write("Pay securely using Google Pay or any UPI app.")
        if "current_txn_id" not in st.session_state:
            st.session_state.current_txn_id = f"UPI_{uuid.uuid4().hex[:10].upper()}"
        txn_id = st.session_state.current_txn_id
        
        merchant_vpa = "akgaya99@okaxis" 
        merchant_name = "SriKailashElectronics"
        transaction_note = f"Order+{txn_id}"
        upi_link = f"upi://pay?pa={merchant_vpa}&pn={merchant_name}&am={c['final_price']}&cu=INR&tn={transaction_note}"
        
        st.markdown(f'<a href="{upi_link}" target="_blank" style="display:block; text-align:center; background: linear-gradient(135deg, #FF7A00 0%, #FF9A3D 100%); color:white; padding:16px; border-radius:12px; text-decoration:none; font-weight:600; font-family:\'Poppins\'; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255,122,0,0.3);">Pay ₹{c["final_price"]} with UPI Apps</a>', unsafe_allow_html=True)
        
        st.write(f"**Order ID:** `{txn_id}`")
        st.caption("Click the button below once you have successfully completed the payment.")
        
        with st.form("upi_verify_form"):
            verify_btn = st.form_submit_button("I have made the payment", type="primary")
            if verify_btn:
                with st.spinner("Submitting your request..."): time.sleep(1.5)
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
                st.success(f"Order Submitted! Order ID: {txn_id}")
                st.info("Your order is currently in 'Order Created' status. Please wait for an admin to verify your payment.")
                time.sleep(3)
                st.session_state.checkout = None
                del st.session_state.current_txn_id
                st.rerun()

    elif payment_method == "Credit / Debit Card":
        with st.form("card_payment_form"):
            st.text_input("Cardholder Name")
            st.text_input("Card Number", max_chars=16)
            col_a, col_b = st.columns(2)
            col_a.text_input("Expiry (MM/YY)", max_chars=5)
            col_b.text_input("CVV", max_chars=3, type="password")
            
            pay_btn = st.form_submit_button(f"Pay ₹{c['final_price']}")
            if pay_btn:
                with st.spinner("Processing payment securely..."): time.sleep(2)
                txn_id = f"CARD_{uuid.uuid4().hex[:10].upper()}"
                order = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "txn_id": txn_id, "type": c['type'].capitalize(),
                    "target": c['target'], "operator": c['operator'],
                    "plan_str": c.get('plan_str', ''), "mrp": c.get('mrp', c['final_price']),
                    "discount": c.get('discount', '0.00'),
                    "amount": c['final_price'], "method": "Card", "status": "Order Created"
                }
                save_order(st.session_state.user_phone, order)
                send_notification_email(st.session_state.user_phone, f"Order Received: {txn_id}", get_order_created_html(order))
                for admin in ADMIN_EMAILS: send_notification_email(admin, f"New Order: {txn_id}", get_order_created_html(order))
                st.success(f"Payment details submitted! TXN ID: {txn_id}")
                st.info("Your order is currently in 'Order Created' status. Please wait for an admin to confirm.")
                time.sleep(3)
                st.session_state.checkout = None
                st.rerun()
                
    st.markdown("---")
    if st.button("Cancel & Go Back"):
        st.session_state.checkout = None
        if "current_txn_id" in st.session_state: del st.session_state.current_txn_id
        st.rerun()

else:
    is_admin = st.session_state.user_phone in ADMIN_EMAILS
    
    if is_admin:
        tabs = st.tabs(["📱 Mobile", "📦 Orders", "🎧 Support", "🛠️ Admin"])
        tab1, tab_orders, tab_grievances, tab_admin = tabs
    else:
        tabs = st.tabs(["📱 Mobile", "📦 Orders", "🎧 Support"])
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
        st.markdown("<h3 style='margin-bottom:20px;'>Mobile Recharge</h3>", unsafe_allow_html=True)
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
        
        if st.button("Proceed to Pay", key="mobile_btn", type="primary"):
            if not phone_number or not phone_number.isdigit() or len(phone_number) != 10: st.error("Enter a valid 10-digit mobile number.")
            elif operator == "Select Operator": st.error("Select an operator.")
            elif selected_plan_str == "Select a Plan": st.error("Select a recharge plan.")
            else:
                price_str = selected_plan_str.split(" ")[-1][1:-1]
                st.session_state.checkout = { "type": "mobile", "target": phone_number, "operator": operator, "price": price_str, "plan_str": selected_plan_str }
                st.rerun()

    with tab_orders:
        st.markdown("<h3 style='margin-bottom:20px;'>My Orders</h3>", unsafe_allow_html=True)
        orders_db = load_orders()
        user_orders = orders_db.get(st.session_state.user_phone, [])
        if not user_orders:
            st.info("You have no past recharges. Make a recharge to see it here!")
        else:
            if st.button("Refresh Orders"): st.rerun()
            for o in user_orders:
                with st.container():
                    status_class = "success" if o['status'] == "Recharge Completed" else "pending"
                    badge_class = "status-success" if o['status'] == "Recharge Completed" else "status-pending"
                    html = f"""
                    <div class="dark-card">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <div>
                                <div style="font-family: 'Poppins', sans-serif; font-weight: 600; color: var(--text); font-size: 15px;">{o['type']} • {o['operator']}</div>
                                <div style="color: #94A3B8; font-size: 12px; font-weight: 500;">{o['target']}</div>
                            </div>
                            <div class="status-badge {badge_class}">{o['status']}</div>
                        </div>
                        <div style="background: var(--surface); border-radius: 8px; padding: 10px; margin-bottom: 10px; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                                <span style="color: #94A3B8;">MRP</span><span style="font-weight: 600;">₹{o.get('mrp', o['amount'])}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                                <span style="color: #94A3B8;">Smart Discount</span><span style="color: var(--success); font-weight: 600;">-₹{o.get('discount', '0.00')}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 14px; margin-top: 6px; border-top: 1px dashed var(--border); padding-top: 6px;">
                                <span style="color: var(--text); font-weight: 600;">Paid</span><span style="color: var(--text); font-weight: 700;">₹{o['amount']}</span>
                            </div>
                        </div>
                        <div style="font-size: 10px; color: #9CA3AF; display: flex; flex-direction: column; gap: 2px;">
                            <div>Txn: {o['txn_id']} • {o['date'][:10]}</div><div>Method: {o['method']}</div>
                    """
                    if "payment_utr" in o: html += f"<div>Pay UTR: {o['payment_utr']}</div>"
                    if "recharge_utr" in o: html += f"<div>Recharge UTR: {o['recharge_utr']}</div>"
                    html += "</div></div>"
                    st.markdown(html, unsafe_allow_html=True)
                
                with st.expander(f"Raise Grievance for {o['txn_id']}"):
                    with st.form(f"grievance_form_{o['txn_id']}"):
                        issue_type = st.selectbox("Issue Type", ["Recharge Not Received", "Amount Deducted but Order Failed", "Wrong Target Recharge", "Other"])
                        details = st.text_area("Details", placeholder="Describe the issue...")
                        if st.form_submit_button("Submit Grievance"):
                            grievance = {
                                "id": f"GRV_{uuid.uuid4().hex[:8].upper()}", "txn_id": o['txn_id'], "issue_type": issue_type,
                                "details": details, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "Open", "admin_reply": ""
                            }
                            save_grievance(st.session_state.user_phone, grievance)
                            send_notification_email(st.session_state.user_phone, f"Grievance Submitted: {grievance['id']}", get_grievance_created_html(grievance))
                            for admin in ADMIN_EMAILS: send_notification_email(admin, f"New Grievance: {grievance['id']}", get_grievance_created_html(grievance))
                            st.success("Grievance raised successfully. Check 'Grievances' tab.")
                            time.sleep(2)
                            st.rerun()

    with tab_grievances:
        st.markdown("<h3 style='margin-bottom:20px;'>My Grievances</h3>", unsafe_allow_html=True)
        grievances_db = load_grievances()
        user_grievances = grievances_db.get(st.session_state.user_phone, [])
        if not user_grievances: st.info("No grievances found.")
        else:
            for g in user_grievances:
                html_content = f"""<div class="dark-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
    <div style="font-family: 'Poppins', sans-serif; font-weight: 600; font-size: 14px; color: var(--text);">Ticket: {g['id']}</div>
    <div class="status-badge {'status-success' if g['status'] == 'Resolved' else 'status-pending'}">{g['status']}</div>
</div>
<div style="font-size: 12px; color: #94A3B8; margin-bottom: 8px;">Txn: {g['txn_id']} • {g['date'][:10]}</div>
<div style="background: var(--surface); padding: 10px; border-radius: 8px; border: 1px solid var(--border); font-size: 13px; margin-bottom: 10px;">
    <span style="font-weight: 600; color: var(--text);">{g['issue_type']}</span><br>
    <span style="color: #4B5563;">{g['details']}</span>
</div>
<div style="font-size: 13px;">
    <span style="font-weight: 600; color: var(--text);">Support Reply:</span><br>
    <span style="color: {'var(--success)' if g['admin_reply'] else '#9CA3AF'};">{g['admin_reply'] if g['admin_reply'] else 'Awaiting agent response...'}</span>
</div>
</div>"""
                st.markdown(html_content, unsafe_allow_html=True)

    if is_admin:
        with tab_admin:
            st.markdown("<h3 style='margin-bottom:20px;'>🛠️ Admin Control Tower</h3>", unsafe_allow_html=True)
            orders_db = load_orders()
            grievances_db = load_grievances()
            admin_tabs = st.tabs(["⏳ Pending Orders", "📋 All Orders", "🚨 Open Grievances", "📂 All Grievances", "⚙️ Operators Config"])
            
            with admin_tabs[0]:
                st.write("### Pending Orders")
                st.markdown("---")
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
                                        if st.form_submit_button("Confirm Payment"):
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
                                        if st.form_submit_button("Complete Recharge"):
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
                            "Discount": f"₹{o.get('discount', '0.00')}", "Paid": f"₹{o['amount']}",
                            "Method": o['method'], "Status": o['status'],
                            "Pay UTR": o.get('payment_utr', 'N/A'), "Rech UTR": o.get('recharge_utr', 'N/A')
                        })
                if all_orders_list:
                    all_orders_list.sort(key=lambda x: x["Date"], reverse=True)
                    st.dataframe(all_orders_list, use_container_width=True)
                else: st.info("No orders found.")
            
            with admin_tabs[2]:
                st.write("### Open Grievances")
                open_g_count = 0
                for user, user_grievances in grievances_db.items():
                    for g in user_grievances:
                        if g['status'] == "Open":
                            open_g_count += 1
                            st.markdown(f"#### Grievance: {g['id']} by {user}")
                            st.write(f"**TXN ID:** {g['txn_id']} | **Type:** {g['issue_type']}")
                            st.write(f"**Details:** {g['details']}")
                            with st.form(f"resolve_grievance_{g['id']}"):
                                reply = st.text_area("Reply to User")
                                if st.form_submit_button("Mark Resolved"):
                                    update_data = {"status": "Resolved", "admin_reply": reply}
                                    update_grievance(user, g['id'], update_data)
                                    g_updated = g.copy()
                                    g_updated.update(update_data)
                                    send_notification_email(user, f"Grievance Resolved: {g['id']}", get_grievance_resolved_html(g_updated))
                                    st.success("Grievance Resolved!")
                                    time.sleep(1)
                                    st.rerun()
                            st.markdown("---")
                if open_g_count == 0: st.info("No open grievances.")

            with admin_tabs[3]:
                st.write("### All Grievances")
                all_grievances_list = []
                for user, user_grievances in grievances_db.items():
                    for g in user_grievances:
                        all_grievances_list.append({
                            "User": user, "Date": g.get('date', 'N/A'), "Grievance ID": g['id'],
                            "TXN ID": g['txn_id'], "Issue Type": g['issue_type'], "Status": g['status']
                        })
                if all_grievances_list:
                    all_grievances_list.sort(key=lambda x: x["Date"], reverse=True)
                    st.dataframe(all_grievances_list, use_container_width=True)
                else: st.info("No grievances found.")

            with admin_tabs[4]:
                st.write("### Operators Configuration")
                operators_data = load_operators()
                if "mobile" not in operators_data: operators_data["mobile"] = {"operators": {}}
                
                mobile_ops = operators_data["mobile"]["operators"]
                op_names = list(mobile_ops.keys())
                st.write("#### Add New Operator")
                with st.form("add_op_form", clear_on_submit=True):
                    col1, col2 = st.columns([3, 1])
                    new_op_name = col1.text_input("New Operator Name")
                    if col2.form_submit_button("Add") and new_op_name and new_op_name not in mobile_ops:
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
                        if st.form_submit_button("Save Changes"):
                            op_data["prefixes"] = [p.strip() for p in new_prefixes.split(",") if p.strip()]
                            op_data["plans"] = [p for p in edited_plans if str(p.get("type", "")).strip() or str(p.get("description", "")).strip() or p.get("price")]
                            operators_data["mobile"]["operators"][selected_op] = op_data
                            save_json_to_drive('operators.json', operators_data)
                            st.cache_data.clear()
                            st.success(f"Saved {selected_op}!")
                            time.sleep(1)
                            st.rerun()
                    if st.button(f"Delete {selected_op}"):
                        del operators_data["mobile"]["operators"][selected_op]
                        save_json_to_drive('operators.json', operators_data)
                        st.cache_data.clear()
                        st.rerun()
                else: st.info("No mobile operators found.")

st.markdown('</div>', unsafe_allow_html=True)
