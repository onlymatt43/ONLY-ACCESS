# Gestion de codes uniques par famille (Flask)

Ce projet fournit une petite application **Python/Flask** permettant de générer et
valider des codes uniques regroupés par "familles". Un panneau d'administration
protégé par login permet de créer des familles de tokens, chaque famille
regroupant plusieurs codes enfants utilisables une seule fois.

L'objectif est d'intégrer facilement un formulaire de déverrouillage via un
`iframe` sur un site externe. Chaque iframe pointe vers `/unlock?family_id=...`
et ne valide que les codes appartenant à cette famille.

## Prérequis

- Python 3.10 ou supérieur
- `pip` pour installer les dépendances

## Installation locale

```bash
# clonage du dépôt puis
python3 -m venv venv
source venv/bin/activate
pip install -r flask_app/requirements.txt
```

## Lancement en développement

```bash
python flask_app/app.py
```

L'application sera alors disponible sur `http://localhost:5000`.
Accédez à `/admin_login` pour vous connecter.

## Lancement en production (gunicorn)

```bash
cd flask_app
gunicorn app:app
```

Le fichier `flask_app/Procfile` contient la commande pour un hébergement type
Heroku ou Render.

## Déploiement sur Render

1. Créer un nouveau **Web Service** sur [Render.com](https://render.com).
2. Choisir ce dépôt Git.
3. Comme Build command : `pip install -r flask_app/requirements.txt`
4. Comme Start command : `gunicorn app:app`
5. Définir la variable d'environnement `SECRET_KEY` (et idéalement les
   identifiants admin) dans les settings Render.
6. Déployer ! L'URL Render servira pour intégrer les iframes.

## API principale

### `POST /api/create_family`
Crée une nouvelle famille de codes.
Corps JSON :
```json
{ "label": "Nom du groupe", "count": 5, "duration": 15 }
```
Réponse :
```json
{ "success": true, "family_id": "...", "codes": ["code1", "code2", ...] }
```
Les codes en clair ne sont retournés qu'une seule fois.

### `POST /api/unlock`
Vérifie qu'un code appartient à la famille spécifiée et qu'il est encore
valide. Exemple de corps :
```json
{ "code": "xxxx", "family_id": "..." }
```
Réponse : `{ "success": true }` ou un message d'erreur.
Un cookie HTTP-only `token_id` est posé lors du succès.

## Intégration iframe

```html
<!-- Remplacer FAMILY_ID par l'identifiant reçu lors de la création -->
<iframe src="https://votre-app.onrender.com/unlock?family_id=FAMILY_ID"
        width="300" height="200" style="border:none"></iframe>
```
L'interface d'administration affiche automatiquement ce code iframe avec
la bonne URL et le `family_id` après chaque génération de famille.

## Sécurité

- Les identifiants admin sont définis en haut de `app.py`. Modifiez-les ou
  utilisez des variables d'environnement.
- Les tokens enfants sont stockés **hachés** dans `flask_app/data/tokens.json` et
  ne sont jamais renvoyés après leur création.
- Chaque token est à usage unique ; une fois utilisé il est marqué avec l'IP,
  l'heure d'activation et d'expiration.
- Le cookie `token_id` est `HttpOnly` et vérifié via `/api/validate_cookie`.
- Les tentatives de `/api/unlock` sont limitées à 10 par minute et par IP.

## Arborescence

```
flask_app/
  app.py               # application Flask principale
  Procfile             # commande gunicorn pour Render
  requirements.txt     # dépendances Python
  data/
    tokens.json        # stockage JSON des familles et tokens
  templates/
    admin_login.html   # formulaire de connexion admin
    index.html         # génération de familles
    unlock.html        # formulaire intégré via iframe
    iframe_example.html
```

---

## English version

### Overview
This project is a small **Flask** application that generates one-time tokens
organized in families. Administrators can create families via a secured panel
and embed a validation form on external sites using an `iframe` with the
`family_id` parameter.

### Requirements
- Python 3.10+
- `pip`

### Local setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r flask_app/requirements.txt
python flask_app/app.py
```

### Production / Render
Use `gunicorn app:app` (see `flask_app/Procfile`). On Render, set the build
command to `pip install -r flask_app/requirements.txt` and the start command to
`gunicorn app:app`.

### API
- `POST /api/create_family` – returns `family_id` and a list of child codes.
- `POST /api/unlock` – validates a code for the given family.

### iframe example
```html
<iframe src="https://your-app.onrender.com/unlock?family_id=FAMILY_ID"
        width="300" height="200"></iframe>
```

Tokens are hashed and single-use. Admin credentials should be changed before
deployment. The cookie `token_id` is `HttpOnly` and validated against the
requesting IP address.

