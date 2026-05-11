import streamlit as st
import time
import json
import os
import uuid
import random
import tempfile
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
    # In Streamlit Cloud, st.secrets is automatically populated from the App Settings.
    # Locally, it reads from .streamlit/secrets.toml.
    try:
        if "web" in st.secrets:
            return {
                "ADMIN_EMAIL": st.secrets.get("ADMIN_EMAIL", "sri.kailash.electronics@gmail.com"),
                "EMAIL_PASSWORD": st.secrets.get("EMAIL_PASSWORD", ""),
                "GDRIVE_SERVICE_ACCOUNT": dict(st.secrets.get("GDRIVE_SERVICE_ACCOUNT", {})),
                "web": dict(st.secrets.get("web", {}))
            }
    except Exception:
        pass
        
    # Fallback for completely local execution without Streamlit runner (e.g. debugging)
    toml_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
    try:
        if os.path.exists(toml_path):
            with open(toml_path, "rb") as f:
                toml_secrets = tomllib.load(f)
            return {
                "ADMIN_EMAIL": toml_secrets.get("ADMIN_EMAIL", "sri.kailash.electronics@gmail.com"),
                "EMAIL_PASSWORD": toml_secrets.get("EMAIL_PASSWORD", ""),
                "GDRIVE_SERVICE_ACCOUNT": dict(toml_secrets.get("GDRIVE_SERVICE_ACCOUNT", {})),
                "web": dict(toml_secrets.get("web", {}))
            }
    except Exception as e:
        print(f"Failed to read TOML secrets: {e}")
        
    return {}

APP_SECRETS = get_app_secrets()
ADMIN_EMAIL = APP_SECRETS.get("ADMIN_EMAIL", "sri.kailash.electronics@gmail.com")
ADMIN_EMAILS = [ADMIN_EMAIL]

# streamlit_google_auth library *strictly* requires a file path for the client secrets.
# We create a temporary JSON file from our TOML/st.secrets dictionary to satisfy this requirement.
temp_secrets_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json', encoding='utf-8')
json.dump({"web": APP_SECRETS.get("web", {})}, temp_secrets_file)
temp_secrets_file.close()

def send_notification_email(receiver, subject, html_body):
    sender = ADMIN_EMAIL
    sender_pwd = APP_SECRETS.get("EMAIL_PASSWORD", "")
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    
    part1 = MIMEText(html_body, "html")
    msg.attach(part1)
    
    try:
        if sender_pwd:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login(sender, sender_pwd)
            server.sendmail(sender, receiver, msg.as_string())
            server.quit()
        else:
            print(f"Mock Email Sent -> Subject: {subject} | To: {receiver}")
    except Exception as e:
        print(f"Error sending email: {e}")

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

# Monkey patch to avoid "Missing code verifier" in streamlit-google-auth
original_from_client_secrets_file = google_auth_oauthlib.flow.Flow.from_client_secrets_file

def patched_from_client_secrets_file(*args, **kwargs):
    kwargs['autogenerate_code_verifier'] = False
    return original_from_client_secrets_file(*args, **kwargs)

google_auth_oauthlib.flow.Flow.from_client_secrets_file = patched_from_client_secrets_file

# Set page configuration for better mobile rendering
st.set_page_config(
    page_title="SKE Recharge",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better mobile appearance
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 25px;
        height: 50px;
        font-weight: bold;
        background-color: #1E88E5;
        color: white;
    }
    .stButton>button:hover {
        background-color: #1565C0;
        color: white;
        border-color: #1565C0;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 600px;
    }
    h1 {
        text-align: center;
        color: #1E88E5;
    }
    .order-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        background-color: #f9f9f9;
        color: #333;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions for data management & Google Drive Sync
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    gdrive_creds = APP_SECRETS.get("GDRIVE_SERVICE_ACCOUNT")
    if gdrive_creds and "type" in gdrive_creds:
        creds = service_account.Credentials.from_service_account_info(gdrive_creds, scopes=DRIVE_SCOPES)
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    return None

def find_file_in_drive(service, file_name, parent_folder_id=None):
    query = f"name='{file_name}' and trashed=false"
    if parent_folder_id:
        query += f" and '{parent_folder_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    return items[0]['id'] if items else None

def get_or_create_app_folder(service):
    folder_name = "SKE_Recharge_Data"
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
        
    # Create folder if it doesn't exist
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')
    
    # Share folder with admin
    permission = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': ADMIN_EMAIL
    }
    service.permissions().create(fileId=folder_id, body=permission).execute()
    return folder_id

def load_json_from_drive(file_name, default_val):
    try:
        service = get_drive_service()
        if not service:
            st.error("Google Drive service is unavailable. Cannot load data.")
            return default_val
            
        folder_id = get_or_create_app_folder(service)
        file_id = find_file_in_drive(service, file_name, folder_id)
        
        if not file_id:
            return default_val
            
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = googleapiclient.http.MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        return json.loads(fh.read().decode('utf-8'))
    except Exception as e:
        st.error(f"Error loading {file_name} from Drive: {e}. Using default/empty data.")
        return default_val

def save_json_to_drive(file_name, data):
    try:
        service = get_drive_service()
        if not service:
            st.error(f"Google Drive service unavailable. Could not save {file_name}.")
            return
            
        folder_id = get_or_create_app_folder(service)
        file_id = find_file_in_drive(service, file_name, folder_id)
        
        file_metadata = {'name': file_name}
        media = googleapiclient.http.MediaIoBaseUpload(
            io.BytesIO(json.dumps(data, indent=4).encode('utf-8')),
            mimetype='application/json',
            resumable=True
        )
        
        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata['parents'] = [folder_id]
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    except Exception as e:
        st.error(f"Drive upload error for {file_name}: {e}")

@st.cache_data
def load_operators():
    return load_json_from_drive('operators.json', {"mobile": {"operators": {}}, "wifi": {"providers": {}}})

def load_orders():
    return load_json_from_drive('orders.json', {})

def save_order(user_phone, order_details):
    orders = load_orders()
    if user_phone not in orders:
        orders[user_phone] = []
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

def load_grievances():
    return load_json_from_drive('grievances.json', {})

def save_grievance(user_phone, grievance_details):
    grievances = load_grievances()
    if user_phone not in grievances:
        grievances[user_phone] = []
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

# Initialize session states
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_phone" not in st.session_state:
    st.session_state.user_phone = ""
if "checkout" not in st.session_state:
    st.session_state.checkout = None

# Initialize Google Authenticator
authenticator = streamlit_google_auth.Authenticate(
    secret_credentials_path=temp_secrets_file.name,
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
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
        )
        html_content = f"""
<div style="display: flex; justify-content: {justify_content};">
    <a href="{authorization_url}" target="_blank" style="background-color: {'#fff' if color == 'white' else '#4285f4'}; color: {'#000' if color == 'white' else '#fff'}; text-decoration: none; text-align: center; font-size: 16px; margin: 4px 2px; cursor: pointer; padding: 8px 12px; border-radius: 4px; display: flex; align-items: center;">
        <img src="https://lh3.googleusercontent.com/COxitqgJr1sJnIDe8-jiKhxDx1FrYbtRHKJ9z_hELisAlapwE9LUPh6fcXIfb5vwpbMl4xl9H9TRFPc5NOO8Sb3VSgIBrfRYvW6cUA" alt="Google logo" style="margin-right: 8px; width: 26px; height: 26px; background-color: white; border: 2px solid white; border-radius: 4px;">
        Sign in with Google
    </a>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)

authenticator.login = patched_login

# Catch the Google redirect and check authentication
authenticator.check_authentification()

# --- LOGIN FLOW ---
if not st.session_state.get('connected'):
    st.title("⚡ SKE Recharge")
    st.markdown("<p style='text-align: center; color: gray;'><strong>Sri Kailash Electronics</strong><br>Fast and secure mobile and Wi-Fi recharges.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.subheader("Login / Register")
    st.write("Please sign in with your Google account to continue.")
    
    # Render the Google login button
    authenticator.login()
    
    st.stop() # Stop rendering the rest of the app until logged in
else:
    # If Google auth is successful, update our own session state flags
    st.session_state.logged_in = True
    # Retrieve user info provided by google-auth
    user_info = st.session_state.get('user_info', {})
    # Use their email as the identifier since we aren't collecting phone number via OTP anymore
    st.session_state.user_phone = user_info.get('email', 'unknown@google.com')

# --- MAIN APP FLOW (LOGGED IN) ---

# Header with Logout
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ SKE Recharge")
with col2:
    st.write("") # Spacing
    if st.button("Logout", key="logout_btn"):
        authenticator.logout()
        st.session_state.logged_in = False
        st.session_state.user_phone = ""
        st.session_state.checkout = None
        st.rerun()

st.markdown("<p style='text-align: center; color: gray;'><strong>Sri Kailash Electronics</strong></p>", unsafe_allow_html=True)
st.markdown("---")

# --- CHECKOUT FLOW ---
if st.session_state.checkout:
    st.subheader("Secure Checkout")
    c = st.session_state.checkout
    
    import re
    
    def get_validity_days(plan_str):
        match = re.search(r'(\d+)\s*Day', plan_str, re.IGNORECASE)
        if match: return int(match.group(1))
        lower_plan = plan_str.lower()
        if 'monthly' in lower_plan: return 30
        if 'quarterly' in lower_plan: return 90
        if 'half-yearly' in lower_plan: return 180
        if 'annually' in lower_plan: return 365
        if 'daily' in lower_plan: return 1
        return 30

    # Calculate Streak
    orders_db = load_orders()
    user_orders = orders_db.get(st.session_state.user_phone, [])
    
    target_orders = [o for o in user_orders if o.get('target') == c['target'] and o.get('status') == 'Recharge Completed']
    streak_count = 0
    
    if target_orders:
        last_order = target_orders[0]
        last_plan = last_order.get('plan_str', '')
        last_date_str = last_order.get('date', '')
        
        if last_plan == c.get('plan_str', '') and last_date_str:
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M:%S")
                validity_days = get_validity_days(last_plan)
                days_since_last = (datetime.now() - last_date).days
                if abs(days_since_last - validity_days) <= 5:
                    streak_count = last_order.get('streak', 0) + 1
            except Exception:
                pass

    original_price = float(c['price'].replace('₹', '').replace(',', '').strip())
    
    # 1% multiplier for streak (max 1%)
    discount_percent = min(streak_count * 0.01, 0.01)
    discount = original_price * discount_percent
    final_price = max(0.0, original_price - discount)
    
    c['final_price'] = f"{final_price:.2f}"
    c['mrp'] = f"{original_price:.2f}"
    c['discount'] = f"{discount:.2f}"
    c['streak'] = streak_count
    
    st.info(f"Recharging **{c['target']}** ({c['operator']}) for **MRP: ₹{original_price:.2f}**")
    if streak_count > 0:
        st.success(f"🔥 **Streak Bonus Active!** Streak count: {streak_count}. You got a {discount_percent*100:.1f}% discount of ₹{discount:.2f}!")
        st.write(f"**Final Amount to Pay: ₹{c['final_price']}**")
    
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
        
        st.markdown(f'<a href="{upi_link}" target="_blank" style="display:block; text-align:center; background-color:#1E88E5; color:white; padding:12px; border-radius:25px; text-decoration:none; font-weight:bold; margin-bottom: 20px;">Pay ₹{c["final_price"]} with UPI Apps</a>', unsafe_allow_html=True)
        
        st.write(f"**Transaction Note / Order ID:** `{txn_id}`")
        st.caption("Click the button below once you have successfully completed the payment on your app.")
        
        with st.form("upi_verify_form"):
            verify_btn = st.form_submit_button("I have made the payment")
            
            if verify_btn:
                with st.spinner("Submitting your request..."):
                    time.sleep(1.5)
                
                order = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "txn_id": txn_id,
                    "type": c['type'].capitalize(),
                    "target": c['target'],
                    "operator": c['operator'],
                    "plan_str": c.get('plan_str', ''),
                    "mrp": c.get('mrp', c['final_price']),
                    "discount": c.get('discount', '0.00'),
                    "streak": c.get('streak', 0),
                    "amount": c['final_price'],
                    "method": "UPI",
                    "status": "Order Created"
                }
                save_order(st.session_state.user_phone, order)
                send_notification_email(st.session_state.user_phone, f"Order Received: {txn_id}", get_order_created_html(order))
                for admin in ADMIN_EMAILS:
                    send_notification_email(admin, f"New Order: {txn_id}", get_order_created_html(order))
                
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
                with st.spinner("Processing payment securely..."):
                    time.sleep(2)
                
                txn_id = f"CARD_{uuid.uuid4().hex[:10].upper()}"
                order = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "txn_id": txn_id,
                    "type": c['type'].capitalize(),
                    "target": c['target'],
                    "operator": c['operator'],
                    "plan_str": c.get('plan_str', ''),
                    "mrp": c.get('mrp', c['final_price']),
                    "discount": c.get('discount', '0.00'),
                    "streak": c.get('streak', 0),
                    "amount": c['final_price'],
                    "method": "Card",
                    "status": "Order Created"
                }
                save_order(st.session_state.user_phone, order)
                send_notification_email(st.session_state.user_phone, f"Order Received: {txn_id}", get_order_created_html(order))
                for admin in ADMIN_EMAILS:
                    send_notification_email(admin, f"New Order: {txn_id}", get_order_created_html(order))
                
                st.success(f"Payment details submitted! TXN ID: {txn_id}")
                st.info("Your order is currently in 'Order Created' status. Please wait for an admin to confirm.")
                time.sleep(3)
                st.session_state.checkout = None
                st.rerun()
                
    st.markdown("---")
    if st.button("Cancel & Go Back"):
        st.session_state.checkout = None
        if "current_txn_id" in st.session_state:
            del st.session_state.current_txn_id
        st.rerun()

# --- TABS: MOBILE, WIFI, MY ORDERS, GRIEVANCES, CONTROL TOWER ---
else:
    is_admin = st.session_state.user_phone in ADMIN_EMAILS
    
    if is_admin:
        tabs = st.tabs(["📱 Mobile", "📶 Wi-Fi", "📦 My Orders", "🎧 Grievances", "🛠️ Control Tower"])
        tab1, tab2, tab3, tab4, tab5 = tabs
    else:
        tabs = st.tabs(["📱 Mobile", "📶 Wi-Fi", "📦 My Orders", "🎧 Grievances"])
        tab1, tab2, tab3, tab4 = tabs

    def get_operator(phone):
        if not phone or len(phone) < 2: return "Select Operator"
        prefix = phone[:2]
        mobile_ops_data = data.get("mobile", {}).get("operators", {})
        if isinstance(mobile_ops_data, dict):
            for op, op_info in mobile_ops_data.items():
                if prefix in op_info.get("prefixes", []):
                    return op
        return "Select Operator"

    # --- TAB 1: MOBILE ---
    with tab1:
        st.subheader("Mobile Recharge")
        
        if "last_phone_prefix" not in st.session_state:
            st.session_state.last_phone_prefix = ""
            
        phone_number = st.text_input("Phone Number", placeholder="e.g., 9876543210", max_chars=10, key="mobile_phone")
        
        mobile_ops_data = data.get("mobile", {}).get("operators", {})
        if isinstance(mobile_ops_data, dict):
            mobile_ops = ["Select Operator"] + list(mobile_ops_data.keys())
        else:
            mobile_ops = ["Select Operator"] + mobile_ops_data
            
        current_prefix = phone_number[:2] if phone_number else ""
        if current_prefix != st.session_state.last_phone_prefix:
            st.session_state.last_phone_prefix = current_prefix
            detected_op = get_operator(phone_number)
            if detected_op in mobile_ops:
                st.session_state.mobile_op = detected_op
            else:
                st.session_state.mobile_op = "Select Operator"
                
        operator = st.selectbox("Operator", mobile_ops, key="mobile_op")
        
        if operator != "Select Operator" and isinstance(mobile_ops_data, dict) and operator in mobile_ops_data:
            mobile_plans = mobile_ops_data[operator].get("plans", [])
        else:
            mobile_plans = []
            
        plan_options = [f"{p['type']} - {p['description']} (₹{p['price']})" for p in mobile_plans]
        plan_options.insert(0, "Select a Plan")
        
        selected_plan_str = st.selectbox("Select Plan", plan_options, key="mobile_plan")
        
        mobile_submit = st.button("Proceed to Pay", key="mobile_btn", use_container_width=True)
        
        if mobile_submit:
            if not phone_number or not phone_number.isdigit() or len(phone_number) != 10:
                st.error("Please enter a valid 10-digit Indian phone number.")
            elif operator == "Select Operator":
                st.error("Please select an operator.")
            elif selected_plan_str == "Select a Plan":
                st.error("Please select a recharge plan.")
            else:
                price_str = selected_plan_str.split(" ")[-1][1:-1]
                st.session_state.checkout = {
                    "type": "mobile",
                    "target": phone_number,
                    "operator": operator,
                    "price": price_str,
                    "plan_str": selected_plan_str
                }
                st.rerun()

    # --- TAB 2: WI-FI ---
    with tab2:
        st.subheader("Wi-Fi / Broadband Recharge")
        
        account_id = st.text_input("Account Number / User ID", placeholder="e.g., ACCT-12345")
        
        wifi_ops_data = data.get("wifi", {}).get("providers", {})
        if isinstance(wifi_ops_data, dict):
            wifi_ops = ["Select Provider"] + list(wifi_ops_data.keys())
        else:
            wifi_ops = ["Select Provider"] + wifi_ops_data
            
        provider = st.selectbox("Service Provider", wifi_ops)
        
        if provider != "Select Provider" and isinstance(wifi_ops_data, dict) and provider in wifi_ops_data:
            wifi_plans = wifi_ops_data[provider].get("plans", [])
        else:
            wifi_plans = []
            
        wifi_plan_options = [f"{p['type']} - {p['description']} (₹{p['price']})" for p in wifi_plans]
        wifi_plan_options.insert(0, "Select a Plan")
        
        selected_wifi_plan_str = st.selectbox("Select Plan", wifi_plan_options)
        
        wifi_submit = st.button("Proceed to Pay", key="wifi_btn", use_container_width=True)
        
        if wifi_submit:
            if not account_id:
                st.error("Please enter your account number.")
            elif provider == "Select Provider":
                st.error("Please select a provider.")
            elif selected_wifi_plan_str == "Select a Plan":
                st.error("Please select a recharge plan.")
            else:
                price_str = selected_wifi_plan_str.split(" ")[-1][1:-1]
                st.session_state.checkout = {
                    "type": "wifi",
                    "target": account_id,
                    "operator": provider,
                    "price": price_str,
                    "plan_str": selected_wifi_plan_str
                }
                st.rerun()

    # --- TAB 3: MY ORDERS ---
    with tab3:
        st.subheader(f"Orders for {st.session_state.user_phone}")
        orders_db = load_orders()
        user_orders = orders_db.get(st.session_state.user_phone, [])
        
        if not user_orders:
            st.info("You have no past recharges. Make a recharge to see it here!")
        else:
            if st.button("Refresh Orders"):
                st.rerun()
                
            for o in user_orders:
                status_color = "orange" if o['status'] == "Order Created" else ("blue" if o['status'] == "Payment Confirmed" else "green")
                
                with st.container():
                    st.markdown(f"**{o['type']} Recharge - {o['operator']}** &nbsp; | &nbsp; <span style='color: {status_color}; font-weight: bold;'>{o['status']}</span>", unsafe_allow_html=True)
                    st.caption(f"Target: {o['target']} | MRP: ₹{o.get('mrp', o['amount'])} | Discount: ₹{o.get('discount', '0.00')} | Paid: ₹{o['amount']}")
                    st.caption(f"{o['date']} | TXN: {o['txn_id']} | Method: {o['method']} | Streak: x{o.get('streak', 0)}")
                    if "payment_utr" in o:
                        st.caption(f"Payment UTR: {o['payment_utr']}")
                    if "recharge_utr" in o:
                        st.caption(f"Recharge UTR: {o['recharge_utr']}")
                    st.markdown("---")
                
                with st.expander(f"Raise Grievance for {o['txn_id']}"):
                    with st.form(f"grievance_form_{o['txn_id']}"):
                        issue_type = st.selectbox("Issue Type", ["Recharge Not Received", "Amount Deducted but Order Failed", "Wrong Target Recharge", "Other"])
                        details = st.text_area("Details", placeholder="Describe the issue...")
                        submit_grievance = st.form_submit_button("Submit Grievance")
                        if submit_grievance:
                            grievance = {
                                "id": f"GRV_{uuid.uuid4().hex[:8].upper()}",
                                "txn_id": o['txn_id'],
                                "issue_type": issue_type,
                                "details": details,
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "Open",
                                "admin_reply": ""
                            }
                            save_grievance(st.session_state.user_phone, grievance)
                            send_notification_email(st.session_state.user_phone, f"Grievance Submitted: {grievance['id']}", get_grievance_created_html(grievance))
                            for admin in ADMIN_EMAILS:
                                send_notification_email(admin, f"New Grievance: {grievance['id']}", get_grievance_created_html(grievance))
                            st.success("Grievance raised successfully. Check 'Grievances' tab.")
                            time.sleep(2)
                            st.rerun()

    # --- TAB 4: GRIEVANCES ---
    with tab4:
        st.subheader("My Grievances")
        grievances_db = load_grievances()
        user_grievances = grievances_db.get(st.session_state.user_phone, [])
        
        if not user_grievances:
            st.info("No grievances found.")
        else:
            for g in user_grievances:
                html_content = f"""<div class="order-card">
<strong>Grievance ID: {g['id']}</strong> (For TXN: {g['txn_id']})<br>
<span style="color: {'green' if g['status'] == 'Resolved' else 'red'}; font-weight: bold;">Status: {g['status']}</span><br>
<em>{g['issue_type']}</em>: {g['details']}<br>
<small>{g['date']}</small><hr>
<strong>Admin Reply:</strong> {g['admin_reply'] if g['admin_reply'] else 'Pending'}
</div>"""
                st.markdown(html_content, unsafe_allow_html=True)

    # --- TAB 5: CONTROL TOWER (ADMIN ONLY) ---
    if is_admin:
        with tab5:
            st.subheader("🛠️ Admin Control Tower")
            
            orders_db = load_orders()
            grievances_db = load_grievances()
            
            admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5 = st.tabs(["⏳ Pending Orders", "📋 All Orders", "🚨 Open Grievances", "📂 All Grievances", "⚙️ Operators Config"])
            
            with admin_tab1:
                st.write("### Pending Orders")
                
                # Table Header
                head_cols = st.columns([1.5, 1.5, 1, 1, 1.5, 2])
                head_cols[0].write("**User**")
                head_cols[1].write("**TXN ID**")
                head_cols[2].write("**Target**")
                head_cols[3].write("**Amount**")
                head_cols[4].write("**Status**")
                head_cols[5].write("**Action**")
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
                                            if not recharge_utr:
                                                st.error("UTR Required")
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
                if pending_count == 0:
                    st.info("No pending orders.")

            with admin_tab2:
                st.write("### All Orders")
                all_orders_list = []
                for user, user_orders in orders_db.items():
                    for o in user_orders:
                        all_orders_list.append({
                            "User": user,
                            "Date": o['date'],
                            "TXN ID": o['txn_id'],
                            "Target": o['target'],
                            "Operator": o['operator'],
                            "MRP": f"₹{o.get('mrp', o['amount'])}",
                            "Discount": f"₹{o.get('discount', '0.00')}",
                            "Paid": f"₹{o['amount']}",
                            "Streak": o.get('streak', 0),
                            "Method": o['method'],
                            "Status": o['status'],
                            "Pay UTR": o.get('payment_utr', 'N/A'),
                            "Rech UTR": o.get('recharge_utr', 'N/A')
                        })
                
                if all_orders_list:
                    # Sort by date descending
                    all_orders_list.sort(key=lambda x: x["Date"], reverse=True)
                    st.dataframe(all_orders_list, use_container_width=True)
                else:
                    st.info("No orders found.")
            
            with admin_tab3:
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
                if open_g_count == 0:
                    st.info("No open grievances.")

            with admin_tab4:
                st.write("### All Grievances")
                all_grievances_list = []
                for user, user_grievances in grievances_db.items():
                    for g in user_grievances:
                        all_grievances_list.append({
                            "User": user,
                            "Date": g.get('date', 'N/A'),
                            "Grievance ID": g['id'],
                            "TXN ID": g['txn_id'],
                            "Issue Type": g['issue_type'],
                            "Status": g['status']
                        })
                
                if all_grievances_list:
                    all_grievances_list.sort(key=lambda x: x["Date"], reverse=True)
                    st.dataframe(all_grievances_list, use_container_width=True)
                else:
                    st.info("No grievances found.")

            with admin_tab5:
                st.write("### Operators Configuration")
                operators_data = load_operators()
                
                # Initialize base structure if missing
                if "mobile" not in operators_data: operators_data["mobile"] = {"operators": {}}
                if "wifi" not in operators_data: operators_data["wifi"] = {"providers": {}}
                
                config_type = st.radio("Select Category", ["Mobile Operators", "Wi-Fi Providers"], horizontal=True)
                
                if config_type == "Mobile Operators":
                    mobile_ops = operators_data["mobile"]["operators"]
                    op_names = list(mobile_ops.keys())
                    
                    st.write("#### Add New Operator")
                    with st.form("add_op_form", clear_on_submit=True):
                        col1, col2 = st.columns([3, 1])
                        new_op_name = col1.text_input("New Operator Name")
                        submitted = col2.form_submit_button("Add")
                        if submitted and new_op_name and new_op_name not in mobile_ops:
                            operators_data["mobile"]["operators"][new_op_name] = {"prefixes": [], "plans": []}
                            save_json_to_drive('operators.json', operators_data)
                            st.cache_data.clear()
                            st.rerun()
                            
                    st.write("#### Edit Existing Operator")
                    if op_names:
                        selected_op = st.selectbox("Select Operator", op_names)
                        op_data = mobile_ops[selected_op]
                        
                        with st.form(f"edit_op_form_{selected_op}"):
                            current_prefixes = ", ".join(op_data.get("prefixes", []))
                            new_prefixes = st.text_input("Prefixes (comma-separated)", current_prefixes)
                            
                            st.write("**Plans**")
                            current_plans = op_data.get("plans", [])
                            if not current_plans:
                                current_plans = [{"type": "", "description": "", "price": 0}]
                            edited_plans = st.data_editor(current_plans, num_rows="dynamic", use_container_width=True, key=f"de_mob_{selected_op}")
                            
                            if st.form_submit_button("Save Changes"):
                                op_data["prefixes"] = [p.strip() for p in new_prefixes.split(",") if p.strip()]
                                cleaned_plans = [p for p in edited_plans if str(p.get("type", "")).strip() or str(p.get("description", "")).strip() or p.get("price")]
                                op_data["plans"] = cleaned_plans
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
                    else:
                        st.info("No mobile operators found.")
                        
                elif config_type == "Wi-Fi Providers":
                    wifi_ops = operators_data["wifi"]["providers"]
                    prov_names = list(wifi_ops.keys())
                    
                    st.write("#### Add New Provider")
                    with st.form("add_prov_form", clear_on_submit=True):
                        col1, col2 = st.columns([3, 1])
                        new_prov_name = col1.text_input("New Provider Name")
                        submitted = col2.form_submit_button("Add")
                        if submitted and new_prov_name and new_prov_name not in wifi_ops:
                            operators_data["wifi"]["providers"][new_prov_name] = {"plans": []}
                            save_json_to_drive('operators.json', operators_data)
                            st.cache_data.clear()
                            st.rerun()
                            
                    st.write("#### Edit Existing Provider")
                    if prov_names:
                        selected_prov = st.selectbox("Select Provider", prov_names)
                        prov_data = wifi_ops[selected_prov]
                        
                        with st.form(f"edit_prov_form_{selected_prov}"):
                            st.write("**Plans**")
                            current_plans = prov_data.get("plans", [])
                            if not current_plans:
                                current_plans = [{"type": "", "description": "", "price": 0}]
                            edited_plans = st.data_editor(current_plans, num_rows="dynamic", use_container_width=True, key=f"de_wifi_{selected_prov}")
                            
                            if st.form_submit_button("Save Changes"):
                                cleaned_plans = [p for p in edited_plans if str(p.get("type", "")).strip() or str(p.get("description", "")).strip() or p.get("price")]
                                prov_data["plans"] = cleaned_plans
                                operators_data["wifi"]["providers"][selected_prov] = prov_data
                                save_json_to_drive('operators.json', operators_data)
                                st.cache_data.clear()
                                st.success(f"Saved {selected_prov}!")
                                time.sleep(1)
                                st.rerun()
                                
                        if st.button(f"Delete {selected_prov}"):
                            del operators_data["wifi"]["providers"][selected_prov]
                            save_json_to_drive('operators.json', operators_data)
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.info("No Wi-Fi providers found.")

st.markdown("---")
st.caption("🔒 256-bit secure encryption. Your details are safe with us.")
