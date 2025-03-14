import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Tạo thư mục lưu avatar nếu chưa có
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Model User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String(300), default='default-avatar.png')

# Model Task
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='Pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# Tạo database nếu chưa có
with app.app_context():
    db.create_all()

    # Kiểm tra và thêm cột `due_date` nếu chưa tồn tại
    result = db.session.execute(text("PRAGMA table_info(task)")).fetchall()
    column_names = [row[1] for row in result]
    if 'due_date' not in column_names:
        db.session.execute(text("ALTER TABLE task ADD COLUMN due_date DATETIME"))
        db.session.commit()

    # Tạo tài khoản admin mặc định nếu chưa có
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password=generate_password_hash('admin123'), is_admin=True)
        db.session.add(admin_user)
        db.session.commit()

# Kiểm tra định dạng file ảnh hợp lệ
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Upload avatar
@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('avatar')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        user = db.session.get(User, session['user_id'])
        user.avatar = filename
        db.session.commit()
        flash("Avatar đã được cập nhật!", "success")

    return redirect(url_for('dashboard'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        avatar = request.files.get('avatar')

        if User.query.filter_by(username=username).first():
            flash("Tên đăng nhập đã tồn tại!", "error")
            return redirect(url_for('register'))

        avatar_filename = 'default-avatar.png'
        if avatar and allowed_file(avatar.filename):
            avatar_filename = secure_filename(avatar.filename)
            avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))

        user = User(username=username, password=password, avatar=avatar_filename)
        db.session.add(user)
        db.session.commit()

        flash("Đăng ký thành công!", "success")
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
            session['is_admin'] = user.is_admin
            flash("Đăng nhập thành công!", "success")

            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        
        flash("Sai tên đăng nhập hoặc mật khẩu!", "error")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    current_time = datetime.utcnow()

    overdue_tasks = Task.query.filter(
        Task.user_id == user.id,
        Task.due_date.isnot(None),
        Task.due_date < current_time,
        Task.status != 'Completed'
    ).count()

    tasks = Task.query.filter_by(user_id=user.id).all()
    return render_template('dashboard.html', current_user=user, tasks=tasks, overdue_tasks=overdue_tasks, current_time=current_time)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Bạn không có quyền truy cập!", "error")
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    tasks = Task.query.all()
    return render_template('admin.html', users=users, tasks=tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    title = request.form['title']
    due_date_str = request.form.get('due_date')

    if not due_date_str:
        flash("Vui lòng chọn ngày hạn công việc!", "error")
        return redirect(url_for('dashboard'))
    
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
    except ValueError:
        flash("Định dạng ngày không hợp lệ!", "error")
        return redirect(url_for('dashboard'))

    new_task = Task(title=title, due_date=due_date, user_id=session['user_id'])
    db.session.add(new_task)
    db.session.commit()

    flash("Công việc đã được thêm!", "success")
    return redirect(url_for('dashboard'))

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = db.session.get(Task, task_id)
    if task and task.user_id == session['user_id']:
        db.session.delete(task)
        db.session.commit()
        flash("Công việc đã được xóa!", "success")
    else:
        flash("Bạn không có quyền xóa công việc này!", "error")

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    flash("Đã đăng xuất!", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
