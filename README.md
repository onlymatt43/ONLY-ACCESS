# Flask Unlock Project

This project provides a Flask-based system for selling time-limited access to protected web content via iframe embedding.

## 🔐 Features

- Admin panel to create folders (site + title + merchant link)
- Generate access codes linked to selected folders
- Codes have IP + duration restriction
- iframe protected with a semi-transparent overlay
- Cookie support for reconnecting users
- Data persistence via JSON files
- Bot protection via honeypot input
- Responsive mobile layout
- Render-ready deployment

## 🚀 Local Setup

1. Install dependencies:

```bash
pip install flask
```

2. Run the app:

```bash
python app.py
```

3. Open in browser:

```
http://localhost:5000
```

- Admin login: `adminonly`
- Password: `a1d2m3i4n5`

## 🌐 Deployment (Render)

1. Push this project to a GitHub repository
2. Go to [https://render.com](https://render.com)
3. Select "New Web Service" → Connect to your GitHub repo
4. Render detects `app.py` or `Procfile`
5. You’re live!

## 📁 File Structure

```
flask_unlock_project/
├── app.py
├── requirements.txt
├── render.yaml
├── Procfile
├── .gitignore
├── templates/
│   ├── admin.html
│   └── unlock.html
├── data/
│   ├── access_codes.json
│   ├── iframe_data.json
│   └── logs.json
```

> ⚠️ `data/*.json` is ignored by Git.