# 图书借阅管理系统

这是一个基于Flask和MySQL的简单图书借阅管理系统，支持不同用户角色（管理员、老师、学生）的登录和相应的功能操作。

## 功能特点

- 用户认证：支持不同角色用户登录
- 图书管理：查看、添加图书
- 借阅管理：借阅和归还图书
- 权限控制：基于用户角色的权限控制
- 借阅限制：不同角色有不同的最大借阅数量限制

## 系统角色

- **管理员**：可以管理用户、图书和查看所有借阅记录，可以借阅最多10本书
- **老师**：可以借阅最多5本书
- **学生**：可以借阅最多3本书

## 安装与设置

### 前提条件

- Python 3.6+
- MySQL 5.7+

### 安装步骤

1. 克隆或下载项目到本地

2. 安装依赖包
   ```
   pip install -r requirements.txt
   ```

3. 配置数据库
   - 在MySQL中创建数据库并导入初始SQL脚本

     ```sql
     -- 创建数据库（如果需要的话）
     CREATE DATABASE IF NOT EXISTS LibraryDB;
     USE LibraryDB;
     
     -- 1. 身份权限表
     CREATE TABLE roles (
         role_id INT PRIMARY KEY AUTO_INCREMENT,
         role_name VARCHAR(20) NOT NULL UNIQUE, -- 管理员、老师、学生
         max_borrow INT NOT NULL DEFAULT 0      -- 每种身份的最大借书数
     );
     
     -- 插入默认三种身份
     INSERT INTO roles (role_name, max_borrow) VALUES
     ('管理员', 10),
     ('老师', 5),
     ('学生', 3);
     
     -- 2. 用户表
     CREATE TABLE users (
         user_id INT PRIMARY KEY AUTO_INCREMENT,
         username VARCHAR(50) NOT NULL UNIQUE,
         password VARCHAR(255) NOT NULL,
         role_id INT,
         FOREIGN KEY (role_id) REFERENCES roles(role_id)
     );
     
     -- 3. 图书表
     CREATE TABLE books (
         book_id INT PRIMARY KEY AUTO_INCREMENT,
         title VARCHAR(255) NOT NULL,
         author VARCHAR(100),
         total_copies INT DEFAULT 0,   -- 总藏书量
         available_copies INT DEFAULT 0 -- 当前可用数量
     );
     
     -- 4. 用户借书记录表（简化版）
     CREATE TABLE borrow_records (
         record_id INT PRIMARY KEY AUTO_INCREMENT,
         user_id INT,
         book_id INT,
         is_returned BOOLEAN DEFAULT FALSE, -- 是否已归还的状态
         FOREIGN KEY (user_id) REFERENCES users(user_id),
         FOREIGN KEY (book_id) REFERENCES books(book_id)
     );
     
     -- 视图：图书余量视图
     CREATE VIEW book_availability AS
     SELECT
         book_id,
         title,
         author,
         total_copies,
         available_copies,
         (total_copies - available_copies) AS borrowed_count
     FROM books;
     
     -- 视图：用户借书视图
     CREATE VIEW user_borrow_info AS
     SELECT
         u.user_id,
         u.username,
         b.title AS book_title,
         br.is_returned
     FROM borrow_records br
     JOIN users u ON br.user_id = u.user_id
     JOIN books b ON br.book_id = b.book_id;
     
     -- 触发器：防止用户借书超过其身份允许的最大数量
     DELIMITER $$
     
     CREATE TRIGGER before_borrow_check_limit
     BEFORE INSERT ON borrow_records
     FOR EACH ROW
     BEGIN
         DECLARE current_borrow_count INT;
         DECLARE user_role_max_borrow INT;
     
         -- 获取当前用户已借未还的数量
         SELECT COUNT(*) INTO current_borrow_count
         FROM borrow_records
         WHERE user_id = NEW.user_id AND is_returned = FALSE;
     
         -- 获取该用户所属角色的最大借书数
         SELECT r.max_borrow INTO user_role_max_borrow
         FROM users u
         JOIN roles r ON u.role_id = r.role_id
         WHERE u.user_id = NEW.user_id;
     
         -- 如果已借数量 >= 最大允许数量，则抛出错误
         IF current_borrow_count >= user_role_max_borrow THEN
             SIGNAL SQLSTATE '45000'
             SET MESSAGE_TEXT = '无法借书：已达到该身份的最大借书限额';
         END IF;
     END$$

         -- 触发器：禁止删除未归还的借阅记录
      CREATE TRIGGER before_delete_borrow_record
      BEFORE DELETE ON borrow_records
      FOR EACH ROW
      BEGIN
         IF OLD.is_returned = FALSE THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = '无法删除：此记录对应的书籍尚未归还';
         END IF;
      END$$
     
     DELIMITER ;
     ```
   - 修改`app.py`中的数据库连接配置

   ```python
   db_config = {
       'host': 'localhost',
       'user': '你的MySQL用户名',
       'password': '你的MySQL密码',
       'database': 'LibraryDB',
       'charset': 'utf8mb4',
       'cursorclass': pymysql.cursors.DictCursor
   }
   ```

4. 本地化前端依赖
   - 本项目前端样式和JS依赖已本地化，相关文件位于`static/css/`目录，无需额外下载。

5. 运行应用
   ```
   python app.py
   ```

6. 在浏览器中访问 `http://127.0.0.1:5000`

## 初始用户

系统需要手动添加初始管理员用户：

1. 登录MySQL并执行以下SQL语句：

```sql
INSERT INTO users (username, password, role_id) VALUES ('admin', 'admin123', 1);
```

2. 使用以下凭据登录系统：
   - 用户名：admin
   - 密码：admin123

## 使用说明

1. 管理员登录后可以：
   - 添加新用户（管理员、老师或学生）
   - 删除非管理员用户（仅当该用户无未归还图书时，且不能删除管理员账户）
   - 添加新图书
   - 查看所有借阅记录
   - 删除借阅记录（仅限管理员）

2. 所有用户都可以：
   - 查看图书列表
   - 借阅图书（受最大借阅数量限制）
   - 归还已借阅的图书
   - 查看个人借阅记录

## 注意事项

- 本系统仅用于学习演示，生产环境使用需增强安全性
- 密码存储采用明文方式，实际应用中应使用加密存储
- 数据库触发器已实现借阅数量限制功能
- 管理员删除用户时，若该用户有未归还图书则无法删除，且管理员账户不可被删除
- 前端依赖已本地化，无需外部CDN