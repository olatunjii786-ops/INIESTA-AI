import os
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'iniesta_v2026_prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///iniesta_v21.db').replace("postgres://", "postgresql://")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
MODEL_ID = "llama-3.3-70b-versatile" 

client = Groq(api_key=GROQ_API_KEY)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin = Admin(app, name='INIESTA PANEL', index_view=MyAdminIndexView(), template_mode='bootstrap4')
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
        h2 { color: white; letter-spacing: 4px; text-transform: uppercase; font-size: 1rem; margin-bottom: 30px; }
        input { width: 100%; padding: 14px; margin: 10px 0; border-radius: 50px; border: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.5); color: white; box-sizing: border-box; outline: none; }
        button { width: 100%; padding: 14px; border-radius: 50px; border: none; background: var(--accent); color: white; font-weight: bold; cursor: pointer; }
        a { color: #555; text-decoration: none; font-size: 11px; display: block; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo-box"><svg width="30" height="30" viewBox="0 0 24 24" fill="white"><path d="M12 2c5.52 0 10 4.48 10 10s-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm0 18c4.41 0 8-3.59 8-8s-3.59-8-8-8-8 3.59-8 8 3.59 8 8 8zm-5-9h10v2H7z"/></svg></div>
        <h2>{{ title }}</h2>
        <form method="POST">
            {% if type == 'register' %}<input name="username" placeholder="Username" required><input name="email" type="email" placeholder="Email" required>{% else %}<input name="username" placeholder="Username" required>{% endif %}
            <input name="password" type="password" placeholder="Password" required>
            <button type="submit">{{ btn }}</button>
        </form>
        <a href="{{ '/login' if type == 'register' else '/register' }}">{{ 'SIGN IN' if type == 'register' else 'CREATE ACCOUNT' }}</a>
    </div>
</body>
</html>
"""

CHAT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>INIESTA AI</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --bg: #030303; --accent: #ff0055; --glass: rgba(255, 255, 255, 0.03); --text: #e0e0e0; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100dvh; overflow: hidden; }
        header { padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.8); border-bottom: 1px solid var(--glass); z-index: 10; }
        .logo-small { display: flex; align-items: center; gap: 10px; }
        .logo-small span { font-size: 0.75rem; letter-spacing: 4px; color: var(--accent); font-weight: 900; }
        .nav-links a { color: #555; text-decoration: none; font-size: 10px; margin-left: 15px; }
        #welcome-hero { position: absolute; top: 45%; left: 50%; transform: translate(-50%, -50%); text-align: center; width: 100%; z-index: 1; }
        .hero-logo { width: 80px; height: 80px; background: var(--accent); border-radius: 22px; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 0 40px rgba(255, 0, 85, 0.3); margin-bottom: 20px; }
        .hero-text { font-size: 2rem; font-weight: 900; letter-spacing: 12px; margin: 0; color: white; }
        #chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 20px; padding-bottom: 120px; z-index: 2; scrollbar-width: none; }
        .msg-wrapper { display: flex; gap: 12px; max-width: 90%; animation: fadeInUp 0.3s ease; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } }
        .user-wrapper { align-self: flex-end; flex-direction: row-reverse; }
        .msg { padding: 14px 20px; border-radius: 20px; font-size: 15px; line-height: 1.5; }
        .bot-msg { background: var(--glass); border-bottom-left-radius: 4px; border: 1px solid rgba(255,255,255,0.05); }
        .user-msg { background: var(--accent); color: white; border-bottom-right-radius: 4px; }
        .input-area { position: fixed; bottom: 0; width: 100%; padding: 20px; background: linear-gradient(0deg, var(--bg) 80%, transparent); z-index: 10; }
        .input-bar { background: rgba(255,255,255,0.05); border-radius: 50px; padding: 6px 6px 6px 20px; display: flex; border: 1px solid rgba(255,255,255,0.08); }
        input { flex: 1; background: transparent; border: none; color: white; outline: none; font-size: 16px; }
        button { background: var(--accent); border: none; width: 45px; height: 45px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }
    </style>
</head>
<body>
    <header>
        <div class="logo-small">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#ff0055"><path d="M12 2c5.52 0 10 4.48 10 10s-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm0 18c4.41 0 8-3.59 8-8s-3.59-8-8-8-8 3.59-8 8 3.59 8 8 8zm-5-9h10v2H7z"/></svg>
            <span>INIESTA</span>
        </div>
        <div class="nav-links">
            {% if current_user.is_admin %}<a href="/admin">ADMIN</a>{% endif %}
            <a href="/logout">LOGOUT</a>
        </div>
    </header>

    {% if not history %}
    <div id="welcome-hero">
        <div class="hero-logo"><svg width="40" height="40" viewBox="0 0 24 24" fill="white"><path d="M12 2c5.52 0 10 4.48 10 10s-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm0 18c4.41 0 8-3.59 8-8s-3.59-8-8-8-8 3.59-8 8 3.59 8 8 8zm-5-9h10v2H7z"/></svg></div>
        <h2 class="hero-text">INIESTA</h2>
    </div>
    {% endif %}

    <div id="chat-container">
        {% for chat in history %}
            {% if chat.role != 'system' %}
            <div class="msg-wrapper {{ 'user-wrapper' if chat.role == 'user' else '' }}">
                <div class="msg {{ 'user-msg' if chat.role == 'user' else 'bot-msg' }}">
                    {{ chat.content | safe }}
                </div>
            </div>
            {% endif %}
        {% endfor %}
    </div>

    <div class="input-area">
        <div class="input-bar">
            <input type="text" id="userInput" placeholder="Ask INIESTA..." autocomplete="off">
            <button onclick="sendMessage()"><svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
        </div>
    </div>

    <script>
        const container = document.getElementById('chat-container');
        const hero = document.getElementById('welcome-hero');
        container.scrollTop = container.scrollHeight;

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            if(!text) return;
            if(hero) { hero.style.opacity = '0'; setTimeout(() => hero.remove(), 500); }
            container.innerHTML += `<div class="msg-wrapper user-wrapper"><div class="msg user-msg">${text}</div></div>`;
            input.value = '';
            container.scrollTop = container.scrollHeight;
            const res = await fetch('/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ message: text }) });
            const data = await res.json();
            container.innerHTML += `<div class="msg-wrapper"><div class="msg bot-msg">${marked.parse(data.reply)}</div></div>`;
            container.scrollTop = container.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        is_first = User.query.count() == 0
        new_user = User(username=request.form['username'], email=request.form['email'], password=hashed, is_admin=is_first)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template_string(AUTH_HTML, title="Register", btn="CREATE ACCOUNT", type="register")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('chat_view'))
    return render_template_string(AUTH_HTML, title="Iniesta AI", btn="SIGN IN", type="login")

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
    history = [{"role": "system", "content": "You are INIESTA. Direct assistant. No narration."}]
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
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)