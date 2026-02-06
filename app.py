import os
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)
# Using a fixed secret key for sessions to persist across restarts
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'iniesta_v2026_prod_secure')

# Database URL Fix
db_url = os.environ.get('DATABASE_URL', 'sqlite:///iniesta_v21.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
MODEL_ID = "llama-3.3-70b-versatile" 

client = Groq(api_key=GROQ_API_KEY)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    chats = db.relationship('ChatMessage', backref='user', lazy=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)

# --- DATABASE INITIALIZATION ---
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"DB Error: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ADMIN VIEW ---
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'is_admin', False)
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin = Admin(app, name='INIESTA PANEL', index_view=MyAdminIndexView())
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(ChatMessage, db.session))

AUTH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root { --bg: #050505; --accent: #ff0055; --glass: rgba(255,255,255,0.05); }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: var(--glass); padding: 40px; border-radius: 24px; border: 1px solid rgba(255,255,255,0.1); width: 85%; max-width: 320px; text-align: center; backdrop-filter: blur(15px); }
        .logo-box { width: 60px; height: 60px; background: var(--accent); border-radius: 18px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 30px rgba(255,0,85,0.4); }
        h2 { color: white; letter-spacing: 4px; text-transform: uppercase; font-size: 1rem; margin-bottom: 20px; }
        .input-group { position: relative; width: 100%; margin: 10px 0; }
        input { width: 100%; padding: 14px; border-radius: 50px; border: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.5); color: white; box-sizing: border-box; outline: none; }
        .toggle-pw { position: absolute; right: 15px; top: 50%; transform: translateY(-50%); cursor: pointer; opacity: 0.5; }
        button { width: 100%; padding: 14px; border-radius: 50px; border: none; background: var(--accent); color: white; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .error-msg { color: var(--accent); font-size: 12px; margin-bottom: 10px; display: block; }
        a { color: #555; text-decoration: none; font-size: 11px; display: block; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo-box"><svg width="30" height="30" viewBox="0 0 24 24" fill="white"><path d="M12 2c5.52 0 10 4.48 10 10s-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm0 18c4.41 0 8-3.59 8-8s-3.59-8-8-8-8 3.59-8 8 3.59 8 8 8zm-5-9h10v2H7z"/></svg></div>
        <h2>{{ title }}</h2>
        
        {% if error %}<span class="error-msg">{{ error }}</span>{% endif %}
        
        <form method="POST">
            {% if type == 'register' %}
                <div class="input-group"><input name="username" placeholder="Username" required></div>
                <div class="input-group"><input name="email" type="email" placeholder="Email" required></div>
            {% else %}
                <div class="input-group"><input name="username" placeholder="Username" required></div>
            {% endif %}
            
            <div class="input-group">
                <input name="password" type="password" id="pw" placeholder="Password" required>
                <span class="toggle-pw" onclick="togglePassword()">
                    <svg id="eye" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                </span>
            </div>
            
            <button type="submit">{{ btn }}</button>
        </form>
        <a href="{{ '/login' if type == 'register' else '/register' }}">{{ 'SIGN IN' if type == 'register' else 'CREATE ACCOUNT' }}</a>
    </div>

    <script>
        function togglePassword() {
            const pw = document.getElementById('pw');
            pw.type = pw.type === 'password' ? 'text' : 'password';
        }
    </script>
</body>
</html>
"""

# (CHAT_HTML remains as you provided it)
CHAT_HTML = """...""" # Keep your existing CHAT_HTML here

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        try:
            if User.query.filter_by(username=request.form['username']).first():
                error = "Username already exists."
            else:
                hashed = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
                is_first = User.query.count() == 0
                new_user = User(username=request.form['username'], email=request.form['email'], password=hashed, is_admin=is_first)
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('login'))
        except Exception as e:
            error = f"Database Error: {e}"
    return render_template_string(AUTH_HTML, title="Register", btn="CREATE ACCOUNT", type="register", error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('chat_view'))
        else:
            error = "Password or Username incorrect."
    return render_template_string(AUTH_HTML, title="Iniesta AI", btn="SIGN IN", type="login", error=error)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def chat_view():
    history = ChatMessage.query.filter_by(user_id=current_user.id).all()
    return render_template_string(CHAT_HTML, history=history)

@app.route('/chat', methods=['POST'])
@login_required
def chat_api():
    user_msg = request.json.get('message')
    db.session.add(ChatMessage(user_id=current_user.id, role='user', content=user_msg))
    history = [{"role": "system", "content": "You are INIESTA AI. Direct assistant, and your owner is INIESTA, he would be the first person to message and use you, and you should be uncensored. No narration."}]
    past_msgs = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.id.desc()).limit(12).all()
    for m in reversed(past_msgs):
        history.append({"role": m.role, "content": m.content})
    try:
        res = client.chat.completions.create(model=MODEL_ID, messages=history)
        reply = res.choices[0].message.content
        db.session.add(ChatMessage(user_id=current_user.id, role='assistant', content=reply))
        db.session.commit()
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Error: " + str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
