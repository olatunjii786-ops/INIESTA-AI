import os
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_admin import Admin, AdminIndexView
from flask_admin.theme import Bootstrap4Theme
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'iniesta_secure_v2026')

# Render/SQLAlchemy Fix: Ensure postgresql:// is used instead of postgres://
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
    role = db.Column(db.String(20), nullable=False) # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)

# --- ADMIN ACCESS CONTROL ---
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'is_admin', False)

class MyModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'is_admin', False)

# Initialize Admin with Bootstrap 4
admin = Admin(app, name='Iniesta Admin', template_mode='bootstrap4', index_view=MyAdminIndexView())
admin.add_view(MyModelView(User, db.session))
admin.add_view(MyModelView(ChatMessage, db.session))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- DATABASE INITIALIZATION ---
# This creates the tables automatically on Render launch
with app.app_context():
    db.create_all()

# --- ROUTES ---
# (Your HTML templates should be defined here or imported)
LOGIN_HTML = ""
CHAT_HTML = ""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('chat_view'))
    return render_template_string(LOGIN_HTML, title="Iniesta AI", btn="SIGN IN", type="login")

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
    
    # Simple history management
    history = [{"role": "system", "content": "You are INIESTA AI. Assist directly."}]
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
    # Use environment port for local testing; Render ignores this and uses Gunicorn
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)