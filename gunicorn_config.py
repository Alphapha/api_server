# Gunicorn 配置文件
import os

# 项目根目录
base_dir = os.path.dirname(os.path.abspath(__file__))

# 服务配置
bind = "0.0.0.0:9876"  # 监听所有网络接口
workers = 4  # 工作进程数
worker_class = "sync"
timeout = 300  # 超时时间（秒）- 增加到5分钟，支持深信服登录+查询
keepalive = 5  # 连接保持时间

# 日志配置
log_dir = os.path.join(base_dir, 'logs')
os.makedirs(log_dir, exist_ok=True)
accesslog = os.path.join(log_dir, 'access.log')  # 访问日志
errorlog = os.path.join(log_dir, 'error.log')  # 错误日志
loglevel = "info"  # 日志级别

# 进程配置
pidfile = os.path.join(log_dir, 'server.pid')  # PID 文件
daemon = True  # 是否后台运行（True=后台，False=前台）
