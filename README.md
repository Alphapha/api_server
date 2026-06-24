# API Server - 设备维保查询服务

基于 Flask 的多厂商设备维保信息查询 API 服务，采用模块化架构设计。

## 项目结构

```
api_server/
├── main.py                     # 主程序入口
├── gunicorn_config.py          # Gunicorn 配置
├── manage.sh                   # 服务管理脚本
├── requirements.txt            # Python 依赖
├── .env                        # 环境变量配置（敏感信息，勿提交）
├── .gitignore                  # Git 忽略文件配置
├── README.md                   # 本文档
├── data/                       # 数据目录（自动生成，存放数据库等文件）
│   └── device_warranty.db      # SQLite 数据库文件
├── logs/                       # 日志目录（自动生成）
│   ├── app.log                 # 应用日志（业务逻辑、数据库、查询请求）
│   ├── access.log              # 访问日志（HTTP 请求记录）
│   ├── error.log               # 错误日志（系统错误和警告）
│   └── server.pid              # 服务进程文件
└── func/                       # 功能模块目录
    ├── database/              # 数据库模块
    │   ├── __init__.py        # 模块初始化
    │   └── db_pool.py         # 数据库连接管理
    ├── captcha/               # 验证码识别模块
    │   ├── sangfor/          # 深信服验证码
    │   │   └── captcha_handler.py
    │   ├── huawei/           # 华为验证码
    │   │   └── captcha_handler.py
    │   └── lenovo/           # 联想验证码
    │       └── captcha_handler.py
    └── query/                 # 查询模块
        ├── sangfor/          # 深信服查询
        │   ├── api_routes.py      # API 路由
        │   ├── login_handler.py   # 登录处理
        │   └── query_handler.py   # 查询处理
        ├── huawei/           # 华为查询
        │   ├── api_routes.py      # API 路由
        │   └── query_handler.py   # 查询处理
        └── lenovo/           # 联想查询
            ├── api_routes.py      # API 路由
            └── query_handler.py   # 查询处理
```

## 快速开始

### 1. 环境要求

- Python 3.9+
- Conda 环境：`api-server`

### 2. 安装依赖

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate api-server
pip install -r requirements.txt
```

### 3. 配置环境变量（必须）

创建 `.env` 文件（根目录）：

```bash
# 深信服账号配置
SANGFOR_USERNAME=your_username
SANGFOR_PASSWORD=your_password

# 数据库配置
DB_PATH=/home/cc/api_server/data/device_warranty.db

# 服务配置（可选）
FLASK_ENV=production
PORT=9876
```

**注意：** 
- `.env` 文件包含敏感信息，已被 `.gitignore` 忽略，请勿提交到版本控制系统
- `DB_PATH` 可根据需要修改，数据库文件将存放在 `data/` 目录下

### 4. 启动服务

#### 方式一：Gunicorn（推荐，生产环境）

**使用管理脚本（推荐）：**

项目提供了便捷的管理脚本 `manage.sh`：

```bash
# 启动服务（后台运行）
./manage.sh start

# 查看服务状态
./manage.sh status

# 停止服务
./manage.sh stop

# 重启服务
./manage.sh restart

# 查看日志
./manage.sh logs app      # 查看应用日志
./manage.sh logs error    # 查看错误日志
./manage.sh logs access   # 查看访问日志

# 查看帮助
./manage.sh help
```

**手动启动（后台运行）：**
```bash
# 直接启动（后台运行）
gunicorn -c gunicorn_config.py main:app

# 查看进程状态
ps aux | grep gunicorn

# 查看 PID
cat logs/server.pid
```

**前台运行（调试用）：**
```bash
# 临时在前台运行
gunicorn -c gunicorn_config.py main:app --daemon=False

# 或修改 gunicorn_config.py 中的 daemon = False
```

**停止服务：**
```bash
# 使用 PID 文件停止
if [ -f logs/server.pid ]; then
    kill $(cat logs/server.pid)
fi

# 或直接停止
pkill -f gunicorn
```

**重启服务：**
```bash
# 先停止
pkill -f gunicorn

# 再启动
gunicorn -c gunicorn_config.py main:app
```

#### 方式二：直接运行（开发环境）

```bash
python main.py
```

**注意：** 直接运行会占用终端，适合开发调试，生产环境建议使用 Gunicorn 后台运行。

### 5. 访问地址

- 本地访问：`http://localhost:9876`
- 主机名访问：`http://api-server:9876`
- IP 访问：`http://10.2.2.5:9876`

## API 接口

### 健康检查

```bash
curl http://localhost:9876/health
```

**响应：**
```json
{
  "status": "ok",
  "message": "API Server is running"
}
```

### 深信服序列号查询

```bash
# 使用数据库缓存（默认）
curl "http://localhost:9876/sn_query/sangfor?sn=61902B45"

# 强制从互联网获取最新数据
curl "http://localhost:9876/sn_query/sangfor?sn=61902B45&cache=0"
```

**响应示例：**
```json
{
  "success": 1,
  "data": [
    {
      "序列号": "WAZCCG0292",
      "网关 id": "61902B45",
      "设备型号": "AC-1000-B1300",
      "服务商名称": "上海合联电子科技有限公司",
      "服务电话": "021-60959881",
      "网络远程支持有效期": "2025-08-10",
      "同等功能软件升级有效期": "2025-08-10",
      "硬件维保有效期": "2025-08-10",
      "warranty_data": "{...}"  // 完整原始数据
    }
  ],
  "source": "database",  // 或 "internet"
  "vendor": "sangfor"
}
```

### 华为序列号查询

```bash
# 使用数据库缓存（默认）
curl "http://localhost:9876/sn_query/huawei?sn=1023A7333670"

# 强制从互联网获取最新数据
curl "http://localhost:9876/sn_query/huawei?sn=1023A7333670&cache=0"
```

**响应示例：**
```json
{
  "success": 1,
  "data": [
    {
      "序列号": "1023A7333670",
      "设备型号": "S5731S-H24T4XC-A",
      "服务套餐": "15 天更换保修",
      "开始日期": "2024/02/08",
      "结束日期": "2025/02/07",
      "状态": "",
      "国家/地区": "",
      "保修区域": "",
      "描述": "S5731S-H24T4XC 组合配置 (24 个 10/100/1000BASE-T 以太网端口，4 个万兆 SFP+,单子卡槽位，含 1 个交流电源)",
      "warranty_data": "{...}"  // 完整原始数据
    }
  ],
  "source": "database",  // 或 "internet"
  "vendor": "huawei"
}
```

**功能特点：**
- ✅ 完整的验证码获取、识别和验证流程
- ✅ 使用本地 `ddddocr` 进行验证码识别
- ✅ 支持失败自动重试机制（最多 3 次）
- ✅ 临时文件存储到 `/tmp` 目录

### 联想序列号查询

```bash
# 使用数据库缓存（默认）
curl "http://localhost:9876/sn_query/lenovo?sn=J901ELMC"

# 强制从互联网获取最新数据
curl "http://localhost:9876/sn_query/lenovo?sn=J901ELMC&cache=0"
```

**响应示例：**
```json
{
  "success": 1,
  "data": [
    {
      "序列号": "J901ELMC",
      "设备型号": "SR650 V2",
      "机器型号": "7Z01CTO1WW",
      "产品名称": "ThinkSystem",
      "最早开始时间": "2024-04-22",
      "最晚结束时间": "2029-04-22",
      "维保详细信息": [
        {
          "保修名称": "ThinkSystem 3 年上门服务",
          "开始日期": "2024-04-22",
          "结束日期": "2027-04-22",
          "状态": "Active"
        },
        // ... 更多保修信息
      ],
      "warranty_data": "{...}"  // 完整原始数据
    }
  ],
  "source": "database",  // 或 "internet"
  "vendor": "lenovo"
}
```

### 查询参数说明

所有查询接口支持以下参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sn` | string | 必填 | 设备序列号 |
| `cache` | integer | `1` | 是否使用数据库缓存：<br>`1` - 优先查询数据库<br>`0` - 直接从互联网获取 |

**响应字段说明：**

- `source`: 数据来源
  - `database` - 从数据库缓存返回
  - `internet` - 从互联网实时获取
  - `None` - 查询失败或无数据
- `vendor`: 厂商标识（`sangfor`, `huawei`, `lenovo`）
- `data`: 查询结果数组
  - 每个设备包含基础字段和 `warranty_data`（完整原始 JSON 数据）

## 配置说明

### Gunicorn 配置

编辑 `gunicorn_config.py`：

```python
bind = "0.0.0.0:9876"    # 监听地址
workers = 4              # 工作进程数
timeout = 120            # 超时时间（秒）
```

### 临时文件

所有临时文件存储在 `/tmp` 目录：

- `/tmp/captcha_debug.jpg` - 深信服验证码图片
- `/tmp/huawei_captcha.jpg` - 华为验证码图片
- `/tmp/session.pkl` - 深信服登录 session 缓存

### 日志文件

所有日志文件存储在 `logs/` 目录：

- `logs/app.log` - 应用日志（业务逻辑、数据库操作、查询请求等）
- `logs/access.log` - 访问日志（所有 HTTP 请求记录）
- `logs/error.log` - 错误日志（系统错误和警告）
- `logs/server.pid` - 服务进程文件

**查看日志：**
```bash
# 查看应用日志（业务日志）
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 查看访问日志（HTTP 请求）
tail -f logs/access.log

# 查看最近的日志
tail -50 logs/app.log
```

### 数据库

默认使用 SQLite 数据库，文件位于 `data/device_warranty.db`（路径可在 `.env` 中配置）。

**数据库特性：**
- ✅ 自动创建表结构（启动时）
- ✅ 每个厂商独立表（`device_warranty_sangfor`, `device_warranty_huawei`, `device_warranty_lenovo`）
- ✅ 版本管理（`is_latest` 字段）
- ✅ 审计字段（创建时间、更新时间、最后查询时间）
- ✅ 索引优化（序列号、网关 ID、时间等）
- ✅ 配置灵活（通过 `.env` 文件的 `DB_PATH` 参数修改路径）

**查看数据库数据：**
```bash
# 查看深信服数据
sqlite3 data/device_warranty.db "SELECT serial_number, device_model, warranty_end_date FROM device_warranty_sangfor;"

# 查看华为数据
sqlite3 data/device_warranty.db "SELECT serial_number, device_model, warranty_end_date FROM device_warranty_huawei;"

# 查看联想数据
sqlite3 data/device_warranty.db "SELECT serial_number, device_model, warranty_end_date FROM device_warranty_lenovo;"
```

**切换到 MySQL（可选）：**

如果需要更高的并发和可靠性，可以切换到 MySQL：

1. 安装依赖：
```bash
pip install pymysql dbutils
```

2. 修改数据库配置（`.env`）：
```bash
DB_TYPE=mysql
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=device_warranty
```

3. 创建数据库：
```sql
CREATE DATABASE device_warranty CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

4. 修改 `func/database/db_pool.py` 使用 MySQL 连接池（参考历史版本）

## 模块化架构

### 目录规范

- `func/captcha/{vendor}/` - 各厂商验证码识别模块
- `func/query/{vendor}/` - 各厂商查询模块

### 模块结构

每个厂商模块包含：

1. **api_routes.py** - Flask Blueprint 路由定义（统一命名）
2. **query_handler.py** - 查询业务逻辑
3. **login_handler.py** - 登录和会话管理（如需要）
4. **captcha_handler.py** - 验证码获取和识别（在 `func/captcha/{vendor}/` 下）

### 添加新厂商

1. 在 `func/captcha/` 下创建厂商目录
2. 在 `func/query/` 下创建厂商目录
3. 实现 `captcha_handler.py` 和 `query_handler.py`
4. 创建 `api_routes.py` 并定义路由（使用 `blueprint` 和 `register_routes` 模式）
5. 在 `main.py` 中注册路由
6. 在 `func/database/db_pool.py` 中创建对应的数据库表

### 数据库表结构

每个厂商对应一个表，表结构一致：

```sql
CREATE TABLE device_warranty_{vendor} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_number VARCHAR(100) NOT NULL,      -- 设备序列号
    gateway_id VARCHAR(100),                   -- 网关 ID（仅深信服需要）
    device_model VARCHAR(200),                 -- 设备型号
    warranty_end_date DATE,                    -- 最晚结束日期
    warranty_data JSON,                        -- 完整维保信息（JSON 格式）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_queried_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_latest INTEGER DEFAULT 1                -- 是否最新版本：1-是，0-历史版本
);
```

**索引：**
- `serial_number` - 序列号索引
- `is_latest` - 版本索引
- `gateway_id` - 网关 ID 索引（仅深信服）
- `warranty_end_date` - 到期时间索引

### 代码规范

所有模块遵循统一命名规范：

```python
# api_routes.py 标准结构
from flask import Blueprint

blueprint = Blueprint('query_xxx', __name__, url_prefix='/sn_query/xxx')

def register_routes(app):
    app.register_blueprint(blueprint)
    logger.info("已注册 xxx 查询路由")

@blueprint.route('', methods=['GET'])
def query():
    ...
```

## 生产环境部署

### 1. 防火墙配置

```bash
# 开放 9876 端口
sudo ufw allow 9876/tcp

# 或限制特定 IP 访问
sudo ufw allow from YOUR_IP to any port 9876
```

### 2. 使用 Nginx 反向代理（推荐）

配置 Nginx：

```nginx
server {
    listen 80;
    server_name your_domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:9876;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 3. 配置 HTTPS

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

### 4. Systemd 服务（可选）

**创建 systemd 服务文件：**

创建 `/etc/systemd/system/api-server.service`：

```ini
[Unit]
Description=API Server
After=network.target

[Service]
Type=notify
User=your_user
WorkingDirectory=/home/cc/api_server
Environment="PATH=/home/cc/anaconda3/envs/api-server/bin"
ExecStart=/home/cc/anaconda3/envs/api-server/bin/gunicorn -c gunicorn_config.py main:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动服务：**

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start api-server

# 设置开机自启
sudo systemctl enable api-server

# 查看状态
sudo systemctl status api-server

# 查看日志
sudo journalctl -u api-server -f

# 重启服务
sudo systemctl restart api-server

# 停止服务
sudo systemctl stop api-server
```

**注意：** 使用 systemd 时，Gunicorn 配置中的 `daemon = True` 应改为 `daemon = False`，因为 systemd 会管理进程。

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable api-server
sudo systemctl start api-server
```

## 故障排查

### 服务管理

#### 普通后台运行

```bash
# 启动服务（后台运行）
gunicorn -c gunicorn_config.py main:app

# 查看进程状态
ps aux | grep gunicorn

# 查看 PID
cat logs/server.pid

# 查看端口占用
lsof -i:9876

# 停止服务
kill $(cat logs/server.pid)

# 或强制停止
pkill -f gunicorn

# 重启服务
pkill -f gunicorn && sleep 2 && gunicorn -c gunicorn_config.py main:app
```

#### 使用 Systemd 管理

```bash
# 查看状态
sudo systemctl status api-server

# 查看日志
sudo journalctl -u api-server -f

# 重启服务
sudo systemctl restart api-server

# 停止服务
sudo systemctl stop api-server

# 启动服务
sudo systemctl start api-server
```

### 查看日志

```bash
# 查看应用日志（业务逻辑）
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 查看访问日志（HTTP 请求）
tail -f logs/access.log

# 查看最近的日志
tail -50 logs/app.log

# 查看 Systemd 日志（如果使用 systemd）
sudo journalctl -u api-server -n 50
```

### 常见问题

#### 1. 服务无法启动

```bash
# 检查端口是否被占用
lsof -i:9876

# 检查日志
tail -50 logs/error.log

# 检查 Python 环境
source /home/cc/anaconda3/etc/profile.d/conda.sh
conda activate api-server
python --version
```

#### 2. 数据库错误

```bash
# 检查数据库文件是否存在
ls -lh data/device_warranty.db

# 检查数据库表
sqlite3 data/device_warranty.db ".tables"

# 查看数据库日志
grep -i "database" logs/app.log
```

#### 3. 查询失败

```bash
# 检查日志中的错误信息
tail -100 logs/app.log | grep -i "error"

# 检查临时文件
ls -lh /tmp/*.jpg /tmp/*.pkl

# 清除缓存重新测试
rm /tmp/session.pkl /tmp/*.jpg
```

### 清除缓存

```bash
# 删除 session 缓存（强制重新登录）
rm /tmp/session.pkl

# 删除验证码图片
rm /tmp/*.jpg

# 清理旧日志（可选）
rm logs/*.log.*
```

## 技术栈

- **Web 框架**: Flask
- **WSGI 服务器**: Gunicorn
- **HTTP 客户端**: Requests
- **HTML 解析**: BeautifulSoup4
- **验证码识别**: ddddocr
- **数据库**: SQLite（默认）/ MySQL（可选）

## 注意事项

1. **首次运行**会自动登录深信服并缓存 session 到 `/tmp/session.pkl`
2. **验证码识别**使用本地 ddddocr，无需外部 API
3. **临时文件**定期清理 `/tmp` 目录
4. **生产环境**建议使用 Nginx + HTTPS
5. **session 过期**会自动重新登录，无需手动干预
6. **数据库缓存**默认启用，可通过 `cache=0` 参数强制从互联网获取
7. **数据持久化**所有查询数据自动保存到数据库，支持版本管理
8. **数据目录**数据库文件存放在 `data/` 目录，路径可在 `.env` 中配置
9. **配置灵活**通过修改 `.env` 的 `DB_PATH` 可轻松切换数据库位置

## License

Private - 仅供内部使用
