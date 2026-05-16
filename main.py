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
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@500;600;700;800&display=swap');
    
    :root {
        --bg: #030712;
        --surface: rgba(17, 24, 39, 0.7);
        --surface-solid: #111827;
        --surface-2: #1F2937;
        --surface-3: #374151;
        --card: rgba(255, 255, 255, 0.02);
        --border: rgba(255, 255, 255, 0.08);
        --border-hover: rgba(255, 255, 255, 0.16);
        --primary: #FF7A00;
        --primary-hover: #FF8F26;
        --text: #F9FAFB;
        --muted: #9CA3AF;
        --success: #10B981;
        --danger: #EF4444;
        --gradient: linear-gradient(135deg, #FF7A00 0%, #E65C00 100%);
    }

    #MainMenu, footer, header { display: none !important; }

    /* Immersive Radial Background */
    .stApp {
        background-color: var(--bg) !important;
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(255, 122, 0, 0.06), transparent 25%),
            radial-gradient(circle at 85% 30%, rgba(16, 185, 129, 0.03), transparent 25%) !important;
        color: var(--text);
        font-family: 'Inter', sans-serif;
    }
    
    .main { background: transparent !important; }

    /* Master Container Reset */
    .block-container {
        width: 100% !important;
        max-width: 1000px !important;
        margin: 0 auto !important;
        padding: 100px 24px 60px 24px !important;
    }

    /* Typography Hierarchy */
    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Poppins', sans-serif !important;
        color: var(--text) !important;
        letter-spacing: -0.03em;
        margin-bottom: 24px !important;
    }
    
    h1, .stMarkdown h1 { font-size: 48px !important; line-height: 1.1 !important; font-weight: 800 !important; }
    h2, .stMarkdown h2 { font-size: 28px !important; line-height: 1.3 !important; font-weight: 700 !important; }
    
    p, span, div { color: var(--text); font-size: 16px; line-height: 1.6; }
    
    /* True Full-Width Glassmorphic Navbar */
    .glass-nav {
        position: fixed;
        top: 0; left: 0; right: 0;
        height: 72px;
        background: rgba(17, 24, 39, 0.6);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        display: flex;
        justify-content: center;
        z-index: 1000;
    }
    .glass-nav-content {
        width: 100%;
        max-width: 1000px;
        padding: 0 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        height: 100%;
    }

    .brand-wrap { display: flex; align-items: center; gap: 12px; }
    .brand-flag { width: 32px; height: 24px; object-fit: cover; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
    .brand-text { display: flex; flex-direction: column; justify-content: center; }
    .brand-title { color: white; font-size: 20px; font-weight: 700; font-family: 'Poppins', sans-serif; line-height: 1; letter-spacing: -0.02em; }
    .brand-sub { color: var(--muted); font-size: 11px; font-weight: 500; font-family: 'Inter', sans-serif; margin-top: 2px; letter-spacing: 0.5px; text-transform: uppercase; }

    /* Hide the Streamlit column wrapper around the logout button so we can style the button directly */
    [data-testid="stHorizontalBlock"] { display: none !important; } /* We will inject custom HTML instead of columns for the header */

    /* The new invisible container trick for Streamlit buttons */
    .logout-btn-container {
        position: fixed;
        top: 18px;
        right: max(24px, calc(50vw - 500px + 24px));
        z-index: 1001;
    }
    
    .logout-btn-container button {
        height: 36px !important;
        min-height: 36px !important;
        padding: 0 16px !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        background: transparent !important;
        color: var(--muted) !important;
        border: 1px solid var(--border) !important;
        transition: all 0.2s ease !important;
    }
    .logout-btn-container button:hover {
        background: var(--card) !important;
        color: var(--text) !important;
        border-color: var(--border-hover) !important;
    }

    /* Asymmetric Hero Redesign */
    .hero-container {
        display: flex;
        flex-direction: column;
        gap: 32px;
        margin-bottom: 48px;
        margin-top: 24px;
    }
    @media (min-width: 768px) {
        .hero-container { flex-direction: row; align-items: center; justify-content: space-between; }
        .hero-left { flex: 1.2; padding-right: 48px; }
        .hero-right { flex: 0.8; display: flex; flex-direction: column; gap: 16px; align-items: flex-end; }
    }
    
    .hero-h1 {
        font-size: 56px;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        line-height: 1.05;
        letter-spacing: -0.04em;
        background: linear-gradient(180deg, #FFFFFF 0%, rgba(255,255,255,0.7) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 24px;
    }
    .hero-h1 span { color: var(--primary); -webkit-text-fill-color: var(--primary); }
    .hero-p { color: var(--muted); font-size: 18px; line-height: 1.6; margin-bottom: 32px; font-weight: 400; max-width: 480px; }
    
    .trust-pill {
        background: var(--surface);
        border: 1px solid var(--border);
        padding: 12px 20px;
        border-radius: 100px;
        display: inline-flex;
        align-items: center;
        gap: 12px;
        font-size: 14px;
        font-weight: 600;
        color: var(--text);
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .trust-pill:hover { transform: translateX(-4px); border-color: var(--border-hover); }
    .trust-pill.orange i { color: var(--primary); font-style: normal; font-size: 16px; }
    .trust-pill.green i { color: var(--success); font-style: normal; font-size: 16px; }

    /* Elevated Content Layouts */
    .layout-grid {
        display: flex;
        flex-direction: column;
        gap: 32px;
    }
    @media (min-width: 860px) {
        .layout-grid { flex-direction: row; align-items: flex-start; }
        .layout-main { flex: 1.5; }
        .layout-sidebar { flex: 1; position: sticky; top: 100px; }
    }

    /* Premium Form Surface */
    .premium-surface {
        background: var(--surface-solid);
        border: 1px solid var(--border);
        border-radius: 24px;
        padding: 32px;
        box-shadow: 0 24px 48px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
        position: relative;
        overflow: hidden;
    }
    .premium-surface::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,122,0,0.3), transparent);
    }

    /* Form Components */
    .stTextInput, .stSelectbox, .stTextArea { margin-bottom: 24px !important; }
    
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stTextArea textarea {
        background: #0A0F1A !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        color: white !important;
        border-radius: 16px !important;
        min-height: 56px !important;
        font-size: 16px !important;
        padding: 0 20px !important;
        margin-bottom: 0 !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.3) !important;
        transition: all 0.2s ease !important;
    }
    .stTextInput input::placeholder { color: #4B5563 !important; }
    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
        border-color: rgba(255, 122, 0, 0.5) !important;
        box-shadow: 0 0 0 1px rgba(255, 122, 0, 0.5), inset 0 2px 4px rgba(0,0,0,0.2) !important;
        background: rgba(0, 0, 0, 0.5) !important;
    }
    .stTextInput label, .stSelectbox label {
        color: var(--muted) !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        margin-bottom: 10px !important;
        letter-spacing: 0.01em;
    }

    /* Live Summary Panel */
    .live-summary-card {
        background: linear-gradient(145deg, #1C263B 0%, #111827 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 12px 32px rgba(0,0,0,0.3);
    }
    .summary-header { font-size: 13px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 20px; }
    .summary-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .summary-label { color: var(--muted); font-size: 15px; font-weight: 500; }
    .summary-value { color: var(--text); font-size: 15px; font-weight: 600; }
    .summary-accent { color: var(--success); font-weight: 600; background: rgba(16,185,129,0.1); padding: 4px 10px; border-radius: 8px; font-size: 13px; }
    .summary-divider { height: 1px; background: var(--border); margin: 24px 0; border: none; }
    .summary-total-label { color: var(--text); font-size: 18px; font-weight: 600; }
    .summary-total-value { color: var(--primary); font-size: 40px; font-weight: 800; font-family: 'Poppins', sans-serif; line-height: 1; letter-spacing: -0.02em; }

    /* Next Gen Tabs */
    div[data-testid="stTabs"] { background: transparent; margin-bottom: 40px; }
    div[data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(17,24,39,0.5);
        backdrop-filter: blur(12px);
        padding: 6px;
        border-radius: 100px;
        border: 1px solid rgba(255,255,255,0.05);
        min-height: 56px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
        display: inline-flex;
    }
    div[data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        border-radius: 100px !important;
        color: var(--muted) !important;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        padding: 10px 24px !important;
        height: 44px;
        display: flex;
        font-size: 15px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div[data-baseweb="tab"]:hover { color: var(--text) !important; }
    div[data-baseweb="tab"][aria-selected="true"] {
        background: var(--surface-3) !important;
        color: var(--text) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1) !important;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: var(--gradient) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
        font-family: 'Poppins', sans-serif !important;
        box-shadow: 0 8px 20px rgba(255, 122, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        padding: 16px 24px !important;
        min-height: 56px;
        width: 100%;
        font-size: 16px !important;
        letter-spacing: 0.5px;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(255, 122, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
        filter: brightness(1.1);
    }
    
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        padding: 16px 24px !important;
        min-height: 52px;
        width: 100%;
        font-size: 15px !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(255,255,255,0.06) !important;
        border-color: var(--border-hover) !important;
    }

    /* Override ugly Streamlit form borders completely */
    .stForm {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
    }

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
<div style="display: flex; justify-content: {justify_content}; margin-top: 16px;">
    <a href="{authorization_url}" target="_blank" style="background: linear-gradient(135deg, #FF7A00 0%, #FF9A3D 100%); color: #fff; text-decoration: none; text-align: center; font-size: 15px; cursor: pointer; padding: 14px 24px; border-radius: 10px; display: flex; align-items: center; justify-content: center; width: 100%; max-width: 340px; box-shadow: 0 8px 24px rgba(255, 122, 0, 0.25); transition: transform 0.2s ease; font-family: 'Poppins', sans-serif; font-weight: 600;">
        <img src="https://lh3.googleusercontent.com/COxitqgJr1sJnIDe8-jiKhxDx1FrYbtRHKJ9z_hELisAlapwE9LUPh6fcXIfb5vwpbMl4xl9H9TRFPc5NOO8Sb3VSgIBrfRYvW6cUA" alt="Google" style="margin-right: 14px; width: 28px; height: 28px; background: white; border-radius: 50%; padding: 4px;">
        Secure Login with Google
    </a>
</div>
<div style="text-align: center; margin-top: 32px; font-size: 14px; color: var(--muted); font-family: 'Inter', sans-serif;">
    <p>By continuing, you agree to SKE Pay's <br><b>Terms of Service</b> & <b>Privacy Policy</b></p>
    <div style="display: flex; justify-content: center; gap: 16px; margin-top: 20px; opacity: 0.8; font-weight: 500;">
        <span>🔒 256-bit Secure</span> • <span>🇮🇳 Made in India</span>
    </div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)

authenticator.login = patched_login
authenticator.check_authentification()

if not st.session_state.get('connected'):
    st.markdown(f"""
    <div style="text-align: center; padding: 60px 20px;">
        <img src="data:image/png;base64,{flag_base64}" style="width: 90px; height: 60px; object-fit: cover; border-radius: 6px; margin-bottom: 24px; box-shadow: 0 12px 24px rgba(0,0,0,0.3);">
        <h1 style="color: white; font-weight: 800; font-size: 48px; margin-bottom: 12px; font-family: 'Poppins', sans-serif; letter-spacing: -0.03em;">SKE Pay</h1>
        <p style="color: var(--primary); font-weight: 600; font-size: 18px; margin-top: 0; font-family: 'Poppins', sans-serif; letter-spacing: 0.5px; text-transform: uppercase;">India's Next-Gen Payments</p>
        <p style="color: var(--muted); font-size: 16px; margin-top: 24px; max-width: 320px; margin-left: auto; margin-right: auto; line-height: 1.6;">Lightning fast mobile recharges, trusted by millions of Indians.</p>
    </div>
    """, unsafe_allow_html=True)
    authenticator.login()
    st.stop()
else:
    st.session_state.logged_in = True
    user_info = st.session_state.get('user_info', {})
    st.session_state.user_phone = user_info.get('email', 'unknown@google.com')

# --- MAIN APP FLOW ---

# 1. TOP NAVIGATION BAR (Absolute Fixed Glassmorphism)
st.markdown(f"""
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
""", unsafe_allow_html=True)

st.markdown('<div class="logout-btn-container">', unsafe_allow_html=True)
if st.button("Logout", key="logout_btn", type="tertiary"):
    authenticator.logout()
    st.session_state.logged_in = False
    st.session_state.user_phone = ""
    st.session_state.checkout = None
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# 2. ASYMMETRIC HERO SECTION
st.markdown("""
<div class="hero-container">
    <div class="hero-left">
        <div class="hero-h1">Recharge Smarter.<br><span>Pay Faster.</span></div>
        <div class="hero-p">Secure, instant mobile recharges powered by modern UPI infrastructure. Join the future of Indian payments.</div>
    </div>
    <div class="hero-right">
        <div class="trust-pill orange"><i>⚡</i> Instant Processing</div>
        <div class="trust-pill green"><i>🔒</i> 256-bit Secure</div>
        <div class="trust-pill"><i>📱</i> UPI Ready</div>
    </div>
</div>
""", unsafe_allow_html=True)

if st.session_state.checkout:
    st.markdown("<h2 style='font-family: Poppins; margin-bottom: 32px;'>Secure Checkout</h2>", unsafe_allow_html=True)
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
    <div class="layout-grid">
        <div class="layout-main">
            <div class="premium-surface" style="padding: 40px;">
                <h3 style="font-size: 20px; font-weight: 700; margin-bottom: 24px;">Payment Summary</h3>
                <div class="live-summary-card" style="background: transparent; border: none; box-shadow: none; padding: 0;">
                    <div class="summary-row">
                        <span class="summary-label">Recharge Target</span>
                        <span class="summary-value" style="font-size: 18px;">{c['target']}</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Operator</span>
                        <span class="summary-value">{c['operator']}</span>
                    </div>
                    <div class="summary-row" style="margin-top: 24px;">
                        <span class="summary-label">MRP</span>
                        <span class="summary-value">₹{original_price:.2f}</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">⚡ Smart Discount ({c['discount_percent']}%)</span>
                        <span class="summary-accent">- ₹{discount:.2f}</span>
                    </div>
                    <div class="summary-divider"></div>
                    <div class="summary-total-row">
                        <span class="summary-total-label">Total Payable</span>
                        <span class="summary-total-value">₹{c['final_price']}</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="layout-sidebar">
    """, unsafe_allow_html=True)

    # UPI Only Flow
    if "current_txn_id" not in st.session_state:
        st.session_state.current_txn_id = f"UPI_{uuid.uuid4().hex[:10].upper()}"
    txn_id = st.session_state.current_txn_id
    
    merchant_vpa = "akgaya99@okaxis" 
    merchant_name = "SriKailashElectronics"
    transaction_note = f"Order+{txn_id}"
    upi_link = f"upi://pay?pa={merchant_vpa}&pn={merchant_name}&am={c['final_price']}&cu=INR&tn={transaction_note}"
    
    st.markdown(f"""
            <div class="premium-surface">
                <div class="summary-header" style="color: var(--text);">Complete Payment</div>
                <p style="color: var(--muted); font-size: 14px; margin-bottom: 24px;">Pay securely using Google Pay, PhonePe, or any UPI app.</p>
                <a href="{upi_link}" target="_blank" style="display: flex; justify-content: center; align-items: center; background: var(--gradient); color: white; padding: 16px 24px; border-radius: 14px; font-weight: 700; font-size: 16px; font-family: 'Poppins', sans-serif; text-decoration: none; box-shadow: 0 8px 20px rgba(255,122,0,0.25); transition: transform 0.2s ease; margin-bottom: 24px;">
                    Pay ₹{c["final_price"]} via UPI
                </a>
                <div style="text-align: center; color: var(--muted); font-size: 12px; margin-bottom: 32px; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px;">Order ID: <b style="color: var(--text);">{txn_id}</b></div>
                <hr class="summary-divider">
                <div style="font-size: 13px; color: var(--muted); margin-bottom: 16px; text-align: center;">Click below <b>after</b> completing payment.</div>
    """, unsafe_allow_html=True)
    
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
            del st.session_state.current_txn_id
            st.rerun()

    st.markdown("</div></div></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 24px; text-align: center;'>", unsafe_allow_html=True)
    if st.button("Cancel & Go Back", type="tertiary"):
        st.session_state.checkout = None
        if "current_txn_id" in st.session_state: del st.session_state.current_txn_id
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

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
        st.markdown("""
        <div class="layout-grid">
            <div class="layout-main">
                <div class="premium-surface">
                    <h2 style='margin-bottom:32px; font-size: 24px;'>Mobile Recharge</h2>
        """, unsafe_allow_html=True)
        
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
        
        st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown("""
            <div class="layout-sidebar">
                <div class="live-summary-card">
                    <div class="summary-header">Live Summary</div>
        """, unsafe_allow_html=True)
        
        preview_price = 0.00
        preview_discount = 0.00
        preview_total = 0.00
        if selected_plan_str != "Select a Plan":
            try:
                preview_price = float(selected_plan_str.split(" ")[-1][1:-1])
                preview_discount = preview_price * 0.0023  # Simulated visual constant 0.23%
                preview_total = preview_price - preview_discount
            except: pass
            
        st.markdown(f"""
                    <div class="summary-row">
                        <span class="summary-label">Target</span>
                        <span class="summary-value">{phone_number if phone_number else '—'}</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Operator</span>
                        <span class="summary-value">{operator if operator != "Select Operator" else '—'}</span>
                    </div>
                    <div class="summary-divider"></div>
                    <div class="summary-row">
                        <span class="summary-label">MRP</span>
                        <span class="summary-value">₹{preview_price:.2f}</span>
                    </div>
                    <div class="summary-row">
                        <span class="summary-label">Smart Discount</span>
                        <span class="summary-accent">- ₹{preview_discount:.2f}</span>
                    </div>
                    <div class="summary-divider"></div>
                    <div class="summary-total-row">
                        <span class="summary-total-label">Total</span>
                        <span class="summary-total-value">₹{preview_total:.2f}</span>
                    </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top: 32px;'>", unsafe_allow_html=True)
        if st.button("Continue to Secure Payment", key="mobile_btn", type="primary"):
            if not phone_number or not phone_number.isdigit() or len(phone_number) != 10: st.error("Enter a valid 10-digit mobile number.")
            elif operator == "Select Operator": st.error("Select an operator.")
            elif selected_plan_str == "Select a Plan": st.error("Select a recharge plan.")
            else:
                price_str = selected_plan_str.split(" ")[-1][1:-1]
                st.session_state.checkout = { "type": "mobile", "target": phone_number, "operator": operator, "price": price_str, "plan_str": selected_plan_str }
                st.rerun()
        st.markdown("</div></div></div></div>", unsafe_allow_html=True)

    with tab_orders:
        st.markdown("<div class='premium-surface'><h2 style='margin-bottom:32px; font-size: 24px;'>Activity History</h2>", unsafe_allow_html=True)
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
                    <div class="live-summary-card" style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
                            <div>
                                <div style="font-family: 'Poppins', sans-serif; font-weight: 700; color: var(--text); font-size: 18px;">{o['type']} • {o['operator']}</div>
                                <div style="color: var(--muted); font-size: 14px; font-weight: 500; margin-top: 4px;">{o['target']}</div>
                            </div>
                            <div class="status-badge {badge_class}">{o['status']}</div>
                        </div>
                        <div style="background: rgba(0,0,0,0.2); border-radius: 12px; padding: 16px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.03);">
                            <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 10px;">
                                <span style="color: var(--muted);">MRP</span><span style="font-weight: 600;">₹{o.get('mrp', o['amount'])}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 10px;">
                                <span style="color: var(--muted);">Smart Discount</span><span style="color: var(--success); font-weight: 600;">-₹{o.get('discount', '0.00')}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 16px; margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 16px;">
                                <span style="color: var(--text); font-weight: 600;">Paid Amount</span><span style="color: var(--primary); font-weight: 800; font-family: 'Poppins', sans-serif;">₹{o['amount']}</span>
                            </div>
                        </div>
                        <div style="font-size: 12px; color: var(--muted); display: flex; flex-direction: column; gap: 6px;">
                            <div>Txn: <span style="color: var(--text);">{o['txn_id']}</span> • {o['date'][:10]}</div><div>Method: {o['method']}</div>
                    """
                    if "payment_utr" in o: html += f"<div>Pay UTR: <span style='color: var(--text);'>{o['payment_utr']}</span></div>"
                    if "recharge_utr" in o: html += f"<div>Rech UTR: <span style='color: var(--text);'>{o['recharge_utr']}</span></div>"
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
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_grievances:
        st.markdown("<div class='premium-surface'><h2 style='margin-bottom:32px; font-size: 24px;'>Support Tickets</h2>", unsafe_allow_html=True)
        grievances_db = load_grievances()
        user_grievances = grievances_db.get(st.session_state.user_phone, [])
        if not user_grievances: st.info("No active support tickets.")
        else:
            for g in user_grievances:
                html_content = f"""<div class="live-summary-card" style="margin-bottom: 24px;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
    <div style="font-family: 'Poppins', sans-serif; font-weight: 700; font-size: 16px; color: var(--text);">Ticket: {g['id']}</div>
    <div class="status-badge {'status-success' if g['status'] == 'Resolved' else 'status-pending'}">{g['status']}</div>
</div>
<div style="font-size: 13px; color: var(--muted); margin-bottom: 20px;">Txn: {g['txn_id']} • {g['date'][:10]}</div>
<div style="background: rgba(0,0,0,0.2); padding: 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.03); font-size: 14px; margin-bottom: 16px;">
    <span style="font-weight: 600; color: var(--text);">{g['issue_type']}</span><br>
    <span style="color: var(--muted); margin-top: 8px; display: inline-block; line-height: 1.5;">{g['details']}</span>
</div>
<div style="font-size: 14px; background: rgba(255,122,0,0.05); padding: 16px; border-radius: 12px; border: 1px solid rgba(255,122,0,0.1);">
    <span style="font-weight: 600; color: var(--primary);">Support Reply:</span><br>
    <span style="color: {'var(--text)' if g['admin_reply'] else 'var(--muted)'}; margin-top: 8px; display: inline-block; line-height: 1.5;">{g['admin_reply'] if g['admin_reply'] else 'Awaiting agent response...'}</span>
</div>
</div>"""
                st.markdown(html_content, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if is_admin:
        with tab_admin:
            st.markdown("<div class='premium-surface'><h2 style='margin-bottom:24px;'>🛠️ Admin Control Tower</h2>", unsafe_allow_html=True)
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
                            "Paid": f"₹{o['amount']}",
                            "Status": o['status']
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
            st.markdown("</div>", unsafe_allow_html=True)
