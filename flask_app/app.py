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
# file where all families and child tokens are stored
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
# simple in-memory counter of attempts per IP
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
    """Simple login form to protect admin routes"""
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template('admin_login.html', error='Mauvais identifiants')
    return render_template('admin_login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/')
@login_required
def index():
    """Page d'administration affichant le formulaire de création."""
    return render_template('index.html')

@app.route('/create_family', methods=['POST'])
@login_required
def create_family():
    """Crée une famille de codes.

    Appeler cette route plusieurs fois pour générer des familles distinctes.
    """
    # number of child codes, duration in minutes and label are provided by admin
    count = int(request.form.get('count', 0))
    duration = int(request.form.get('duration', 0))
    label = request.form.get('label', '')

    data = load_data()
    family_id = str(uuid.uuid4())
    family = {
        'family_id': family_id,
        'label': label,
        'duration': duration,
        'children': []
    }
    codes_plain = []
    for _ in range(count):
        # generate a unique code, store only its hash
        code_plain = str(uuid.uuid4())
        code_hash = hashlib.sha256(code_plain.encode()).hexdigest()
        child_id = str(uuid.uuid4())
        family['children'].append({
            'id': child_id,
            'hash': code_hash,
            'used': False,
            'used_ip': None,
            'activation': None,
            'expiration': None
        })
        codes_plain.append(code_plain)

    # Chaque appel ajoute une nouvelle famille distincte dans le fichier JSON
    data['families'].append(family)
    save_data(data)
    # URL complète pour intégrer cette famille via iframe
    unlock_url = url_for('unlock_page', family_id=family_id, _external=True)
    # renvoyer la page admin avec les codes clairs et l'iframe de la famille
    return render_template('index.html', codes=codes_plain,
                           family_id=family_id, unlock_url=unlock_url)

# Route API pour génération via appel JavaScript
@app.route('/api/create_family', methods=['POST'])
@login_required
def api_create_family():
    """API JSON pour créer une famille de codes et renvoyer les codes clairs"""
    payload = request.get_json(force=True)
    count = int(payload.get('count', 0))
    duration = int(payload.get('duration', 0))
    label = payload.get('label', '')

    data = load_data()
    family_id = str(uuid.uuid4())
    family = {
        'family_id': family_id,
        'label': label,
        'duration': duration,
        'children': []
    }
    codes_plain = []
    for _ in range(count):
        code_plain = str(uuid.uuid4())
        code_hash = hashlib.sha256(code_plain.encode()).hexdigest()
        child_id = str(uuid.uuid4())
        family['children'].append({
            'id': child_id,
            'hash': code_hash,
            'used': False,
            'used_ip': None,
            'activation': None,
            'expiration': None
        })
        codes_plain.append(code_plain)

    data['families'].append(family)
    save_data(data)
    return jsonify({'success': True, 'family_id': family_id, 'codes': codes_plain})

@app.route('/export')
@login_required
def export():
    data = load_data()
    return jsonify(data)

@app.route('/unlock')
def unlock_page():
    """Page de saisie de code utilisable dans un iframe."""
    # La page lit elle-même le paramètre family_id via JavaScript
    return render_template('unlock.html')

@app.route('/api/unlock', methods=['POST'])
def api_unlock():
    """Déverrouille un code enfant d'une famille spécifique.

    Cette route attend un JSON contenant ``code`` et ``family_id``. Elle est
    protégée contre le bruteforce via ``check_brute_force`` et valide que le
    code appartient bien à la famille avant d'activer le token et de poser un
    cookie.
    """
    # rate limit unlock attempts per IP
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
            child['expiration'] = (now + timedelta(minutes=family['duration'])).isoformat()
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
                # token must be marked as used and IP must match
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
    # clear authentication cookie
    resp = jsonify({'success': True})
    resp.set_cookie('token_id', '', expires=0)
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
