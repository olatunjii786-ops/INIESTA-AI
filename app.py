import os
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'iniesta_secure_v2026')

# Render PostgreSQL Fix
db_url = os.environ.get('DATABASE_URL', 'sqlite:///iniesta.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
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

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False) 
    content = db.Column(db.Text, nullable=False)

# --- DATABASE INITIALIZATION ---
with app.app_context():
    db.create_all()

# --- ADMIN ACCESS ---
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'is_admin', False)

admin = Admin(app, name='Iniesta Admin', template_mode='bootstrap4', index_view=MyAdminIndexView())
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(ChatMessage, db.session))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HTML TEMPLATES (RESTORED) ---
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body { background: #000; color: #fff; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .form-container { background: #111; padding: 30px; border-radius: 10px; border: 1px solid #333; width: 300px; }
        input { width: 100%; padding: 10px; margin: 10px 0; background: #222; border: 1px solid #444; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #fff; color: #000; border: none; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="form-container">
        <h2>{{ title }}</h2>
        <form method="POST">
            <input type="email" name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">{{ btn }}</button>
        </form>
    </div>
</body>
</html>
"""

CHAT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Iniesta AI Chat</title>
    <style>
        body { background: #000; color: #fff; font-family: sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; }
        .chat-box { flex: 1; overflow-y: auto; padding: 20px; }
        .msg { margin-bottom: 15px; padding: 10px; border-radius: 5px; max-width: 80%; }
        .user { background: #222; align-self: flex-end; margin-left: auto; }
        .ai { background: #111; border: 1px solid #333; }
        .input-area { padding: 20px; border-top: 1px solid #333; display: flex; }
        input { flex: 1; padding: 10px; background: #111; border: 1px solid #333; color: #fff; }
        button { padding: 10px 20px; background: #fff; color: #000; border: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="chat-box" id="chatBox">
        {% for msg in history %}
            <div class="msg {{ 'user' if msg.role == 'user' else 'ai' }}">
                <b>{{ 'You' if msg.role == 'user' else 'Iniesta' }}:</b> {{ msg.content }}
            </div>
        {% endfor %}
    </div>
    <div class="input-area">
        <input type="text" id="userInput" placeholder="Ask anything...">
        <button onclick="sendMsg()">Send</button>
    </div>

    <script>
        async function sendMsg() {
            const input = document.getElementById('userInput');
            const box = document.getElementById('chatBox');
            const msg = input.value;
            if(!msg) return;
            
            box.innerHTML += `<div class="msg user"><b>You:</b> ${msg}</div>`;
            input.value = '';

            const res = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg})
            });
            const data = await res.json();
            box.innerHTML += `<div class="msg ai"><b>Iniesta:</b> ${data.reply}</div>`;
            box.scrollTop = box.scrollHeight;
        }
    </script>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('chat_view'))
    return render_template_string(LOGIN_HTML, title="Iniesta AI", btn="SIGN IN")

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
    
    # History management for AI
    history = [{"role": "system", "content": "You are INIESTA AI. Assist directly. No narration."}]
    past_msgs = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.id.desc()).limit(12).all()
    for m in reversed(past_msgs):
        history.append({"role": m.role, "content": m.content})
        
    try:
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=history)
        reply = res.choices[0].message.content
        db.session.add(ChatMessage(user_id=current_user.id, role='assistant', content=reply))
        db.session.commit()
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
