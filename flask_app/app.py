from flask import Flask, render_template, request, redirect, url_for, session, make_response
import hashlib, uuid, json, os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATA_DIR = 'data'
IFRAME_FILE = os.path.join(DATA_DIR, 'iframe_data.json')
CODES_FILE = os.path.join(DATA_DIR, 'access_codes.json')
LOG_FILE = os.path.join(DATA_DIR, 'logs.json')

def load_data():
    global iframe_data, access_codes
    os.makedirs(DATA_DIR, exist_ok=True)
    iframe_data = json.load(open(IFRAME_FILE)) if os.path.exists(IFRAME_FILE) else []
    access_codes = json.load(open(CODES_FILE)) if os.path.exists(CODES_FILE) else {}

def save_data():
    json.dump(iframe_data, open(IFRAME_FILE, 'w'), indent=2)
    json.dump(access_codes, open(CODES_FILE, 'w'), indent=2)

def log_code_use(code, ip, title, start_time, expires_in):
    logs = json.load(open(LOG_FILE)) if os.path.exists(LOG_FILE) else []
    logs.append({
        'code': code,
        'ip': ip,
        'title': title,
        'start_time': start_time.isoformat(),
        'expires_in': expires_in
    })
    json.dump(logs, open(LOG_FILE, 'w'), indent=2)

def get_client_ip():
    return request.remote_addr

load_data()

@app.route('/', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == 'adminonly' and request.form['password'] == 'a1d2m3i4n5':
            session['admin'] = True
            return redirect('/admin')
    return render_template('admin.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'admin' not in session:
        return redirect('/')
    generated_codes = []
    if request.method == 'POST':
        if 'site_url' in request.form:
            iframe_data.append({
                'title': request.form['title'],
                'iframe_url': request.form['site_url'],
                'link': request.form['merchant_link']
            })
            save_data()
        elif 'subtitle' in request.form and 'selected_title' in request.form:
            title = request.form['selected_title']
            for _ in range(int(request.form['count'])):
                code = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:10]
                access_codes[code] = {
                    'title': title,
                    'subtitle': request.form['subtitle'],
                    'expires_in': int(request.form['duration']),
                    'used_by': None,
                    'start_time': None
                }
                generated_codes.append(code)
            save_data()
    return render_template('admin.html', iframe_data=iframe_data, access_codes=access_codes, generated_codes=generated_codes)

@app.route('/delete-title', methods=['POST'])
def delete_title():
    if 'admin' not in session:
        return redirect('/')
    title = request.form['title_to_delete']
    global iframe_data, access_codes
    iframe_data = [d for d in iframe_data if d['title'] != title]
    access_codes = {k: v for k, v in access_codes.items() if v['title'] != title}
    save_data()
    return redirect('/admin')

@app.route('/unlock', methods=['GET', 'POST'])
def unlock():
    user_ip = get_client_ip()
    code_input = request.form.get('access_code') if request.method == 'POST' else request.cookies.get('code_used')
    code_valid, iframe_url, remaining_time, expired, error_msg = False, None, None, False, None

    if request.method == 'POST' and request.form.get('email'):
        return "Bot detected", 403

    if code_input and code_input in access_codes:
        code_data = access_codes[code_input]
        if not code_data['used_by']:
            code_data['used_by'] = user_ip
            code_data['start_time'] = datetime.utcnow()
            log_code_use(code_input, user_ip, code_data['title'], code_data['start_time'], code_data['expires_in'])
            save_data()
        elif code_data['used_by'] != user_ip:
            error_msg = "This code is already used by another IP."
        else:
            elapsed = (datetime.utcnow() - datetime.fromisoformat(code_data['start_time'])).total_seconds()
            if elapsed < code_data['expires_in'] * 60:
                remaining_time = int(code_data['expires_in'] * 60 - elapsed)
                code_valid = True
                iframe_url = next((i['iframe_url'] for i in iframe_data if i['title'] == code_data['title']), None)
            else:
                expired = True
                del access_codes[code_input]
                save_data()
    response = make_response(render_template(
        'unlock.html',
        code_valid=code_valid,
        iframe_url=iframe_url,
        remaining_time=remaining_time,
        expired=expired,
        error_msg=error_msg
    ))
    if code_valid and request.method == 'POST':
        response.set_cookie('code_used', code_input, max_age=86400)
    return response