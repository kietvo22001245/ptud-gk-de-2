from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    avatar = db.Column(db.String(300), default='https://avatar-placeholder.iran.liara.run/')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            return "Username already exists!"
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('logout'))
    tasks = Task.query.filter_by(user_id=user.id).all()
    return render_template('dashboard.html', current_user=user, tasks=tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' in session:
        title = request.form['title']
        new_task = Task(title=title, user_id=session['user_id'])
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/update_task/<int:task_id>')
def update_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get(task_id)
    if task and task.user_id == session['user_id']:
        task.status = 'Completed'
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get(task_id)
    if task and task.user_id == session['user_id']:
        db.session.delete(task)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/upload_avatar', methods=['GET', 'POST'])
def upload_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('logout'))

    if request.method == 'POST' and 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename != '':
            upload_folder = 'static/uploads'
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            user.avatar = '/' + file_path  # Lưu đường dẫn ảnh
            db.session.commit()

    elif request.method == 'GET' and 'avatar' in request.args:
        avatar_url = request.args.get('avatar')
        user.avatar = avatar_url  # Cập nhật avatar từ URL
        db.session.commit()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)