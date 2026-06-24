"""
数据库连接模块（MySQL 版本）
"""
import pymysql
import logging
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger('Database')

# 数据库配置 - 从环境变量读取
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'api')

def get_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"获取数据库连接失败：{str(e)}")
        raise

def _convert_date_to_string(data):
    """将 datetime/date 对象转换为字符串"""
    if isinstance(data, dict):
        for key, value in data.items():
            if hasattr(value, 'strftime'):  # 检查是否是日期时间对象
                data[key] = value.strftime('%Y-%m-%d %H:%M:%S') if hasattr(value, 'hour') else value.strftime('%Y-%m-%d')
    return data

def query_one(sql, params=None):
    """查询单条记录"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            result = cursor.fetchone()
        conn.close()
        if result:
            result = _convert_date_to_string(result)
        return result
    except Exception as e:
        logger.error(f"数据库查询失败：{str(e)}, SQL: {sql}")
        return None

def query_all(sql, params=None):
    """查询多条记录"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            results = cursor.fetchall()
        conn.close()
        if results:
            results = [_convert_date_to_string(row) for row in results]
        return results
    except Exception as e:
        logger.error(f"数据库查询失败：{str(e)}, SQL: {sql}")
        return []

def execute(sql, params=None):
    """执行 SQL 语句（INSERT/UPDATE/DELETE）"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            conn.commit()
            last_insert_id = cursor.lastrowid
        conn.close()
        return last_insert_id
    except Exception as e:
        logger.error(f"数据库执行失败：{str(e)}, SQL: {sql}")
        return None

def execute_many(sql, params_list):
    """批量执行 SQL 语句"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.executemany(sql, params_list)
            conn.commit()
            affected_rows = cursor.rowcount
        conn.close()
        return affected_rows
    except Exception as e:
        logger.error(f"数据库批量执行失败：{str(e)}, SQL: {sql}")
        return None

class Transaction:
    """事务管理器"""
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def __enter__(self):
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        return self.cursor
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.cursor.close()
        self.conn.close()
        return False

def transaction():
    """获取事务上下文"""
    return Transaction()

def init_db():
    """初始化数据库（创建表）"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 创建深信服设备维保表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_warranty_sangfor (
            id INT PRIMARY KEY AUTO_INCREMENT,
            serial_number VARCHAR(100) NOT NULL,
            gateway_id VARCHAR(100),
            device_model VARCHAR(200),
            warranty_end_date DATE,
            warranty_data JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_queried_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_latest TINYINT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # 创建华为设备维保表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_warranty_huawei (
            id INT PRIMARY KEY AUTO_INCREMENT,
            serial_number VARCHAR(100) NOT NULL,
            device_model VARCHAR(200),
            warranty_end_date DATE,
            warranty_data JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_queried_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_latest TINYINT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # 创建联想设备维保表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_warranty_lenovo (
            id INT PRIMARY KEY AUTO_INCREMENT,
            serial_number VARCHAR(100) NOT NULL,
            device_model VARCHAR(200),
            warranty_end_date DATE,
            warranty_data JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_queried_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_latest TINYINT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # 创建索引（使用 try-except 避免多个 worker 同时创建索引冲突）
        # 深信服表索引
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_sangfor_serial ON device_warranty_sangfor(serial_number)')
        except: pass
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_sangfor_latest ON device_warranty_sangfor(is_latest)')
        except: pass
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_sangfor_gateway ON device_warranty_sangfor(gateway_id)')
        except: pass
        
        # 华为表索引
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_huawei_serial ON device_warranty_huawei(serial_number)')
        except: pass
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_huawei_latest ON device_warranty_huawei(is_latest)')
        except: pass
        
        # 联想表索引
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_lenovo_serial ON device_warranty_lenovo(serial_number)')
        except: pass
        try: cursor.execute('CREATE INDEX IF NOT EXISTS idx_lenovo_latest ON device_warranty_lenovo(is_latest)')
        except: pass
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败：{str(e)}")
        raise
