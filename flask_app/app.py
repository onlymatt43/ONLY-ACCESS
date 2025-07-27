import json
import os
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps

# --- Configuration ---
ADMIN_USER = 'admin'
ADMIN_PASS = 'password'
SECRET_KEY = os.environ.get('SECRET_KEY', 'change_me')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'tokens.json')

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = SECRET_KEY

# --- Helpers to load and save data ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {'families': []}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# --- Authentication decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rate limiting for unlock ---
ATTEMPTS = {}
MAX_ATTEMPTS = 10
WINDOW_SECONDS = 60

def check_brute_force(ip):
    now = datetime.utcnow()
    ATTEMPTS.setdefault(ip, [])
    ATTEMPTS[ip] = [t for t in ATTEMPTS[ip] if (now - t).total_seconds() < WINDOW_SECONDS]
    if len(ATTEMPTS[ip]) >= MAX_ATTEMPTS:
        return False
    ATTEMPTS[ip].append(now)
    return True

# --- Routes ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('dashboard.html', error='Mauvais identifiants', familles=load_data().get('families', []), session=session)
    return render_template('dashboard.html', familles=load_data().get('families', []), session=session)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    error = None
    data = load_data()
    familles = data.get('families', [])

    # Gestion connexion admin
    if not session.get('logged_in'):
        if request.method == 'POST' and 'username' in request.form:
            if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
                session['logged_in'] = True
                return redirect(url_for('dashboard'))
            else:
                error = "Mauvais identifiants"
        return render_template('dashboard.html', familles=familles, error=error, session=session)

    # Création famille
    if request.method == 'POST' and 'site' in request.form:
        site = request.form.get('site', '').strip()
        specificite = request.form.get('specificite', '').strip()
        import random
        random_digits = str(random.randint(1000, 9999))
        family_code = f"{site}_{specificite}_{random_digits}"
        family_id = str(uuid.uuid4())
        family = {
            'family_id': family_id,
            'site': site,
            'specificite': specificite,
            'family_code': family_code,
            'children': []
        }
        data['families'].append(family)
        save_data(data)
        return redirect(url_for('dashboard'))

    # Ajout code enfant
    if request.method == 'POST' and 'child_code' in request.form:
        family_id = request.form.get('family_id')
        child_code = request.form.get('child_code', '').strip()
        child_specificite = request.form.get('child_specificite', '').strip()
        try:
            child_duration = int(request.form.get('child_duration', '60'))
        except ValueError:
            child_duration = 60
        family = next((f for f in familles if f['family_id'] == family_id), None)
        if family and child_code:
            code_hash = hashlib.sha256(child_code.encode()).hexdigest()
            child = {
                'id': str(uuid.uuid4()),
                'code': child_code,
                'specificite': child_specificite,
                'hash': code_hash,
                'duration': child_duration,
                'used': False,
                'used_ip': None,
                'activation': None,
                'expiration': None
            }
            family['children'].append(child)
            save_data(data)
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', familles=familles, error=error, session=session)

@app.route('/export')
@login_required
def export():
    data = load_data()
    return jsonify(data)

@app.route('/unlock')
def unlock_page():
    return render_template('unlock.html')

@app.route('/api/unlock', methods=['POST'])
def api_unlock():
    if not check_brute_force(request.remote_addr):
        return jsonify({'success': False, 'message': 'Trop de tentatives. Réessayez plus tard.'}), 429

    code = request.json.get('code', '')
    family_id = request.json.get('family_id')
    if not family_id:
        return jsonify({'success': False, 'message': 'Famille manquante'}), 400

    code_hash = hashlib.sha256(code.encode()).hexdigest()
    data = load_data()
    family = next((f for f in data['families'] if f['family_id'] == family_id), None)
    if not family:
        return jsonify({'success': False, 'message': 'Famille inconnue'}), 400

    for child in family['children']:
        if child['hash'] == code_hash:
            if child['used']:
                return jsonify({'success': False, 'message': 'Code déjà utilisé'}), 400
            child['used'] = True
            child['used_ip'] = request.remote_addr
            now = datetime.utcnow()
            child['activation'] = now.isoformat()
            child['expiration'] = (now + timedelta(minutes=child['duration'])).isoformat()
            save_data(data)
            resp = jsonify({'success': True})
            resp.set_cookie('token_id', child['id'], httponly=True, samesite='Lax')
            return resp

    return jsonify({'success': False, 'message': 'Ce code ne correspond pas à ce groupe'}), 400

@app.route('/api/validate_cookie')
def validate_cookie():
    token_id = request.cookies.get('token_id')
    if not token_id:
        return jsonify({'valid': False})
    data = load_data()
    for family in data['families']:
        for child in family['children']:
            if child['id'] == token_id:
                if not child['used']:
                    return jsonify({'valid': False})
                if child['used_ip'] != request.remote_addr:
                    return jsonify({'valid': False})
                if datetime.fromisoformat(child['expiration']) < datetime.utcnow():
                    return jsonify({'valid': False})
                return jsonify({'valid': True, 'expires': child['expiration']})
    return jsonify({'valid': False})

@app.route('/api/reset_cookie')
def reset_cookie():
    resp = jsonify({'success': True})
    resp.set_cookie('token_id', '', expires=0)
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
