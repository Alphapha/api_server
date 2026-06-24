"""
API Server - 设备维保查询服务
基于 Flask 的多厂商设备维保信息查询 API
"""
import os
import sys
import logging

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('API-Server')

# 创建 Flask 应用
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支持中文

# 导入并注册各厂商查询路由
from func.query.sangfor.api_routes import register_routes as register_sangfor_routes
from func.query.huawei.api_routes import register_routes as register_huawei_routes
from func.query.lenovo.api_routes import register_routes as register_lenovo_routes
from func.database import init_db

# 初始化数据库
init_db()

# 注册路由
register_sangfor_routes(app)
register_huawei_routes(app)
register_lenovo_routes(app)


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "message": "API Server is running"
    })


@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """获取支持的厂商列表"""
    return jsonify({
        "vendors": [
            {
                "name": "sangfor",
                "display_name": "深信服",
                "endpoint": "/api/query/sangfor"
            },
            {
                "name": "huawei",
                "display_name": "华为",
                "endpoint": "/api/query/huawei"
            },
            {
                "name": "lenovo",
                "display_name": "联想",
                "endpoint": "/api/query/lenovo"
            }
        ]
    })


# 初始化日志
logger.info("API Server 初始化完成")
logger.info(f"已注册路由: /api/query/sangfor, /api/query/huawei, /api/query/lenovo")


if __name__ == '__main__':
    logger.info("===== 启动 API Server =====")
    app.run(host='0.0.0.0', port=9876, debug=False)
