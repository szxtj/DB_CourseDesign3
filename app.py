from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'user': 'root',  # 请修改为你的MySQL用户名
    'password': 'root',  # 请修改为你的MySQL密码
    'database': 'LibraryDB',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 创建数据库连接
def get_db_connection():
    return pymysql.connect(**db_config)

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 角色验证装饰器
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role_name' not in session or session['role_name'] not in allowed_roles:
                flash('您没有权限访问此页面', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 路由：首页
@app.route('/')
def index():
    return redirect(url_for('login'))

# 路由：登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 查询用户
                sql = "SELECT u.user_id, u.username, u.password, r.role_id, r.role_name FROM users u JOIN roles r ON u.role_id = r.role_id WHERE u.username = %s"
                cursor.execute(sql, (username,))
                user = cursor.fetchone()
                
                if user and user['password'] == password:  # 实际应用中应使用密码哈希
                    # 登录成功，保存用户信息到session
                    session['user_id'] = user['user_id']
                    session['username'] = user['username']
                    session['role_id'] = user['role_id']
                    session['role_name'] = user['role_name']
                    
                    flash(f'欢迎回来，{username}！', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('用户名或密码错误', 'danger')
        finally:
            conn.close()
            
    return render_template('login.html')

# 路由：注销
@app.route('/logout')
def logout():
    session.clear()
    flash('您已成功注销', 'info')
    return redirect(url_for('login'))

# 路由：控制面板
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# 路由：图书列表
@app.route('/books')
@login_required
def book_list():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM book_availability ORDER BY title")
            books = cursor.fetchall()
    finally:
        conn.close()
    return render_template('books.html', books=books)

# 路由：借书
@app.route('/borrow/<int:book_id>', methods=['POST'])
@login_required
def borrow_book(book_id):
    user_id = session['user_id']
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查图书是否可借
            cursor.execute("SELECT available_copies FROM books WHERE book_id = %s", (book_id,))
            book = cursor.fetchone()
            
            if not book or book['available_copies'] <= 0:
                flash('该图书当前无法借阅', 'danger')
                return redirect(url_for('book_list'))
            
            try:
                # 开始事务
                conn.begin()
                
                # 插入借书记录
                cursor.execute(
                    "INSERT INTO borrow_records (user_id, book_id, is_returned) VALUES (%s, %s, %s)",
                    (user_id, book_id, False)
                )
                
                # 更新图书可用数量
                cursor.execute(
                    "UPDATE books SET available_copies = available_copies - 1 WHERE book_id = %s",
                    (book_id,)
                )
                
                # 提交事务
                conn.commit()
                flash('借书成功！', 'success')
                
            except pymysql.MySQLError as e:
                # 回滚事务
                conn.rollback()
                flash(f'借书失败：{str(e)}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('my_books'))

# 路由：还书
@app.route('/return/<int:record_id>', methods=['POST'])
@login_required
def return_book(record_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取借书记录
            cursor.execute(
                "SELECT * FROM borrow_records WHERE record_id = %s AND user_id = %s",
                (record_id, session['user_id'])
            )
            record = cursor.fetchone()
            
            if not record or record['is_returned']:
                flash('无效的还书操作', 'danger')
                return redirect(url_for('my_books'))
            
            try:
                # 开始事务
                conn.begin()
                
                # 更新借书记录状态
                cursor.execute(
                    "UPDATE borrow_records SET is_returned = TRUE WHERE record_id = %s",
                    (record_id,)
                )
                
                # 更新图书可用数量
                cursor.execute(
                    "UPDATE books SET available_copies = available_copies + 1 WHERE book_id = %s",
                    (record['book_id'],)
                )
                
                # 提交事务
                conn.commit()
                flash('还书成功！', 'success')
                
            except pymysql.MySQLError as e:
                # 回滚事务
                conn.rollback()
                flash(f'还书失败：{str(e)}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('my_books'))

# 路由：我的借书
@app.route('/my-books')
@login_required
def my_books():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 查询用户的借书记录
            cursor.execute(
                """SELECT br.record_id, b.book_id, b.title, b.author, br.is_returned 
                   FROM borrow_records br 
                   JOIN books b ON br.book_id = b.book_id 
                   WHERE br.user_id = %s 
                   ORDER BY br.is_returned, br.record_id DESC""",
                (user_id,)
            )
            borrowed_books = cursor.fetchall()
            # 查询最大可借书数和当前未归还数量
            cursor.execute("""
                SELECT r.max_borrow, (
                    SELECT COUNT(*) FROM borrow_records WHERE user_id = %s AND is_returned = FALSE
                ) AS current_borrowed
                FROM users u JOIN roles r ON u.role_id = r.role_id WHERE u.user_id = %s
            """, (user_id, user_id))
            borrow_info = cursor.fetchone()
            if borrow_info:
                max_borrow = borrow_info['max_borrow']
                current_borrowed = borrow_info['current_borrowed']
                remain_borrow = max_borrow - current_borrowed
            else:
                max_borrow = 0
                remain_borrow = 0
    finally:
        conn.close()
    return render_template('my_books.html', borrowed_books=borrowed_books, max_borrow=max_borrow, remain_borrow=remain_borrow)

# 管理员路由：用户管理
@app.route('/admin/users')
@login_required
@role_required(['管理员'])
def admin_users():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT u.user_id, u.username, r.role_name, r.max_borrow, (
                        SELECT COUNT(*) FROM borrow_records br WHERE br.user_id = u.user_id AND br.is_returned = FALSE
                    ) AS current_borrowed
                   FROM users u 
                   JOIN roles r ON u.role_id = r.role_id 
                   ORDER BY u.user_id"""
            )
            users = cursor.fetchall()
            # 为每个用户计算剩余可借阅数
            for user in users:
                user['remain_borrow'] = user['max_borrow'] - user['current_borrowed']
    finally:
        conn.close()
    return render_template('admin/users.html', users=users)

# 管理员路由：添加用户
@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@role_required(['管理员'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role_id = request.form['role_id']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 检查用户名是否已存在
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    flash('用户名已存在', 'danger')
                else:
                    # 添加新用户
                    cursor.execute(
                        "INSERT INTO users (username, password, role_id) VALUES (%s, %s, %s)",
                        (username, password, role_id)
                    )
                    conn.commit()
                    flash('用户添加成功', 'success')
                    return redirect(url_for('admin_users'))
        finally:
            conn.close()
    
    # 获取所有角色
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM roles")
            roles = cursor.fetchall()
    finally:
        conn.close()
        
    return render_template('admin/add_user.html', roles=roles)

# 管理员路由：图书管理
@app.route('/admin/books')
@login_required
@role_required(['管理员'])
def admin_books():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM books ORDER BY title")
            books = cursor.fetchall()
    finally:
        conn.close()
        
    return render_template('admin/books.html', books=books)

# 管理员路由：添加图书
@app.route('/admin/books/add', methods=['GET', 'POST'])
@login_required
@role_required(['管理员'])
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        total_copies = int(request.form['total_copies'])
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO books (title, author, total_copies, available_copies) VALUES (%s, %s, %s, %s)",
                    (title, author, total_copies, total_copies)
                )
                conn.commit()
                flash('图书添加成功', 'success')
                return redirect(url_for('admin_books'))
        finally:
            conn.close()
            
    return render_template('admin/add_book.html')

# 管理员路由：借阅记录
@app.route('/admin/borrow-records')
@login_required
@role_required(['管理员'])
def admin_borrow_records():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT br.record_id, u.username, b.title, br.is_returned 
                   FROM borrow_records br 
                   JOIN users u ON br.user_id = u.user_id 
                   JOIN books b ON br.book_id = b.book_id 
                   ORDER BY br.record_id DESC"""
            )
            records = cursor.fetchall()
    finally:
        conn.close()
        
    return render_template('admin/borrow_records.html', records=records)

@app.route('/delete-borrow-record/<int:record_id>', methods=['POST'])
@login_required
def delete_borrow_record(record_id):
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查该记录是否属于当前用户
            cursor.execute("SELECT * FROM borrow_records WHERE record_id = %s AND user_id = %s", (record_id, user_id))
            record = cursor.fetchone()
            if not record:
                flash('无效的删除操作', 'danger')
                return redirect(url_for('my_books'))
            try:
                conn.begin()
                cursor.execute("DELETE FROM borrow_records WHERE record_id = %s", (record_id,))
                conn.commit()
                flash('借阅记录删除成功！', 'success')
            except pymysql.MySQLError as e:
                conn.rollback()
                if '此记录对应的书籍尚未归还' in str(e):
                    flash('无法删除：此记录对应的书籍尚未归还', 'danger')
                else:
                    flash(f'删除失败：{str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('my_books'))

@app.route('/admin/delete-borrow-record/<int:record_id>', methods=['POST'])
@login_required
@role_required(['管理员'])
def admin_delete_borrow_record(record_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM borrow_records WHERE record_id = %s", (record_id,))
            record = cursor.fetchone()
            if not record:
                flash('无效的删除操作', 'danger')
                return redirect(url_for('admin_borrow_records'))
            try:
                conn.begin()
                cursor.execute("DELETE FROM borrow_records WHERE record_id = %s", (record_id,))
                conn.commit()
                flash('借阅记录删除成功！', 'success')
            except pymysql.MySQLError as e:
                conn.rollback()
                if '此记录对应的书籍尚未归还' in str(e):
                    flash('无法删除：此记录对应的书籍尚未归还', 'danger')
                else:
                    flash(f'删除失败：{str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_borrow_records'))
if __name__ == '__main__':
    app.run(debug=True)