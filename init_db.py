import os
import pymysql
from app.config import settings

def get_db_connection_params(include_database=False):
    """
    获取数据库连接参数
    :param include_database: 是否包含数据库名称
    :return: 连接参数字典
    """
    params = {
        'host': settings.MYSQL_HOST,
        'port': settings.MYSQL_PORT,
        'user': settings.MYSQL_USER,
        'password': settings.MYSQL_PASSWORD,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    if include_database:
        params['database'] = settings.MYSQL_DATABASE
    return params

def create_database_if_not_exists():
    """
    检查数据库是否存在，如果不存在则创建
    返回 True 表示数据库已存在，False 表示是新创建的
    """
    try:
        # 先连接到 MySQL 服务器（不指定数据库）
        connection = pymysql.connect(**get_db_connection_params(include_database=False))
        
        try:
            with connection.cursor() as cursor:
                # 检查数据库是否存在
                cursor.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
                    (settings.MYSQL_DATABASE,)
                )
                result = cursor.fetchone()
                
                if result:
                    # 数据库已存在，检查是否有数据
                    cursor.execute(f"USE `{settings.MYSQL_DATABASE}`")
                    cursor.execute("SHOW TABLES")
                    tables = cursor.fetchall()
                    
                    if tables:
                        print(f"数据库 '{settings.MYSQL_DATABASE}' 已存在，且包含 {len(tables)} 个表")
                        return True
                    else:
                        print(f"数据库 '{settings.MYSQL_DATABASE}' 已存在，但为空")
                        return True
                else:
                    # 数据库不存在，使用 IF NOT EXISTS 创建它
                    cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                    connection.commit()
                    print(f"数据库 '{settings.MYSQL_DATABASE}' 创建成功！")
                    return False
                    
        finally:
            connection.close()
            
    except pymysql.Error as e:
        print(f"数据库创建/检查失败: {str(e)}")
        raise

def init_db():
    """
    自动创建数据库（如果不存在），然后使用 SQL 文件初始化数据库表
    使用 CREATE TABLE IF NOT EXISTS，支持重复执行
    """
    try:
        # 首先检查并创建数据库（如果不存在）
        create_database_if_not_exists()
        
        # 获取 SQL 文件路径
        sql_file_path = os.path.join(os.path.dirname(__file__), 'init.sql')
        
        # 读取 SQL 文件内容
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 连接到指定的数据库
        connection = pymysql.connect(**get_db_connection_params(include_database=True))
        
        try:
            # 执行 SQL 语句
            # 分割 SQL 语句（以分号分隔）
            with connection.cursor() as cursor:
                # 按分号分割 SQL 语句
                statements = []
                current_statement = []
                
                for line in sql_content.split('\n'):
                    # 移除行尾注释
                    if '--' in line:
                        line = line.split('--')[0]
                    line = line.strip()
                    
                    if line:
                        current_statement.append(line)
                        # 如果行以分号结尾，说明一个语句结束了
                        if line.rstrip().endswith(';'):
                            statement = ' '.join(current_statement).rstrip(';').strip()
                            if statement:
                                statements.append(statement)
                            current_statement = []
                
                # 执行每个 SQL 语句
                for statement in statements:
                    if statement:
                        cursor.execute(statement)
            
            # 提交事务
            connection.commit()
            print("数据库表初始化成功！")
            return True
            
        except Exception as e:
            # 回滚事务
            connection.rollback()
            raise
        finally:
            connection.close()
            
    except FileNotFoundError:
        print(f"错误: 找不到 SQL 文件 {sql_file_path}")
        raise
    except pymysql.Error as e:
        print(f"数据库表创建失败: {str(e)}")
        raise
    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")
        raise

if __name__ == "__main__":
    init_db() 