from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import mysql.connector
from datetime import datetime
import os
from werkzeug.utils import secure_filename

# ==================== 关键修改在这里 ====================
# static_folder='.'   : 告诉 Flask 静态文件就在当前目录
# static_url_path=''  : 告诉 Flask 不要加 /static 前缀，直接用 /文件名 访问
app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
CORS(app)

# 图片与视频上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'avi', 'webm'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 数据库配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456', # 记得确认密码
    'database': 'melody_db'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to DB: {err}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== 路由配置 ====================

@app.route('/')
def index():
    return render_template('Melody.html')

# 专门处理上传文件的访问
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==================== 用户认证 API ====================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password: return jsonify({"error": "缺少信息"}), 400
    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB Error"}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone(): return jsonify({"error": "用户已存在"}), 409
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        return jsonify({"success": True, "user": {"id": cursor.lastrowid, "username": username}})
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: cursor.close(); conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB Error"}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        if user: return jsonify({"success": True, "user": user, "token": f"token-{user['id']}"})
        else: return jsonify({"error": "账号密码错误"}), 401
    finally: cursor.close(); conn.close()

# ==================== 留言板 API ====================
@app.route('/api/messages', methods=['GET'])
def get_messages():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username, content, created_at FROM messages ORDER BY created_at DESC")
        msgs = cursor.fetchall()
        for m in msgs:
            if isinstance(m['created_at'], datetime): m['created_at'] = m['created_at'].strftime('%Y-%m-%d %H:%M')
        return jsonify(msgs)
    finally: cursor.close(); conn.close()

@app.route('/api/messages', methods=['POST'])
def post_message():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("INSERT INTO messages (user_id, username, content) VALUES (%s, %s, %s)",
                      (data['user_id'], data['username'], data['content']))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: cursor.close(); conn.close()

# ==================== 朋友圈 (Moments) API ====================
@app.route('/api/moments', methods=['GET'])
def get_moments():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username, content, image_url, created_at FROM moments ORDER BY created_at DESC")
        moments = cursor.fetchall()
        for m in moments:
            if isinstance(m['created_at'], datetime):
                m['date_str'] = m['created_at'].strftime('%Y-%m-%d')
                m['time_str'] = m['created_at'].strftime('%H:%M')
                m['day'] = m['created_at'].day
                m['month'] = m['created_at'].strftime('%m月')
        return jsonify(moments)
    finally: cursor.close(); conn.close()

@app.route('/api/moments', methods=['POST'])
def add_moment():
    user_id = request.form.get('user_id')
    username = request.form.get('username')
    content = request.form.get('content')
    file = request.files.get('file')
    if not user_id: return jsonify({"error": "未登录"}), 401
    image_url = None
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_url = f"/uploads/{filename}"
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("INSERT INTO moments (user_id, username, content, image_url) VALUES (%s, %s, %s, %s)",
            (user_id, username, content, image_url))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: cursor.close(); conn.close()

# ==================== 日历待办 (Calendar Todos) API ====================
@app.route('/api/todos', methods=['GET'])
def get_todos():
    date_str = request.args.get('date')
    if not date_str: return jsonify([])
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM calendar_todos WHERE todo_date = %s ORDER BY created_at ASC", (date_str,))
        todos = cursor.fetchall()
        return jsonify(todos)
    finally: cursor.close(); conn.close()

@app.route('/api/todos', methods=['POST'])
def add_todo():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("INSERT INTO calendar_todos (user_id, username, todo_date, content) VALUES (%s, %s, %s, %s)",
                       (data['user_id'], data['username'], data['date'], data['content']))
        conn.commit()
        return jsonify({"success": True, "id": cursor.lastrowid})
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: cursor.close(); conn.close()

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM calendar_todos WHERE id = %s", (todo_id,))
        conn.commit()
        return jsonify({"success": True})
    finally: cursor.close(); conn.close()

if __name__ == '__main__':
    print("Backend running on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)