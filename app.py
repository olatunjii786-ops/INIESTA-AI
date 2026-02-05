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

# --- HARDCODED SETTINGS ---
app.config['SECRET_KEY'] = 'iniesta_secure_v2026'
# YOUR API KEY GOES HERE:
GROQ_API_KEY = "Gsk_JGruRfqpnAY1OTH9v4sYWGdyb3FYMbFsp1fWmExOZA0nKr3fjoL9"

# Database logic for Railway/Render
db_url = os.environ.get('DATABASE_URL', 'sqlite:///iniesta.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin Panel Security
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin = Admin(app, name='INIESTA PANEL', index_view=MyAdminIndexView(), theme=Bootstrap4Theme())
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(ChatMessage, db.session))

# --- INSERT YOUR AUTH_HTML AND CHAT_HTML STRINGS HERE ---

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
        return jsonify({"reply": "Error: " + str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
