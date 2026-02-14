# 设备序列号查询API服务器

## 1. 概述

本项目实现了一个基于Flask的RESTful API服务，用于查询设备的维保信息。目前支持深信服(Sangfor)和华为(Huawei)设备的序列号查询，并预留了联想(Lenovo)的查询接口。

## 2. 功能特性

- **多厂商支持**：深信服、华为设备的维保信息查询
- **自动验证码处理**：自动获取和识别验证码
- **会话管理**：持久化登录会话，减少登录频率
- **错误重试机制**：网络错误和验证码错误时自动重试
- **统一接口**：所有厂商使用相同的API接口格式
- **安全配置**：使用环境变量管理敏感信息

## 3. 实现原理

### 3.1 核心架构

- **会话管理层**：负责深信服BBS论坛的登录和会话维护
- **服务查询层**：负责发送设备序列号和验证码进行维保信息查询
- **API接口层**：提供RESTful接口，处理HTTP请求和响应
- **多厂商适配层**：支持多厂商设备查询的扩展架构

### 3.2 服务查询流程

1. **获取有效会话**：从文件加载或重新登录获取
2. **访问服务查询页面**：获取初始页面内容
3. **动态获取验证码**：调用验证码更新接口获取idhash，下载验证码图片，使用外部OCR API识别验证码
4. **发送查询请求**：携带设备序列号和验证码发送POST请求
5. **解析响应结果**：将原始响应转换为人类可读格式

## 4. 使用方法

### 4.1 安装依赖

```bash
# 使用虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖包
pip install Flask requests beautifulsoup4 python-dotenv
```

### 4.2 配置环境变量

1. **复制配置模板**：
   ```bash
   cp .env.example .env
   ```

2. **编辑 .env 文件**，填写实际的账号信息：
   ```env
   # 深信服(Sangfor) BBS账号配置
   SANGFOR_USERNAME=your_username
   SANGFOR_PASSWORD=your_password_md5

   # 华为(Huawei)账号配置
   HUAWEI_USERNAME=your_username
   HUAWEI_PASSWORD=your_password
   ```

### 4.3 启动服务

```bash
python service_query_api.py
```

服务默认运行在 `http://0.0.0.0:9876`

### 4.4 API接口调用

#### 4.4.1 深信服设备查询

**GET请求**：
```bash
curl "http://localhost:9876/sn_query/sangfor?sn=设备序列号"
```

**POST请求**：
```bash
curl -X POST -H "Content-Type: application/json" -d '{"sn": "设备序列号"}' "http://localhost:9876/sn_query/sangfor"
```

#### 4.4.2 华为设备查询

**GET请求**：
```bash
curl "http://localhost:9876/sn_query/huawei?sn=设备序列号"
```

**POST请求**：
```bash
curl -X POST -H "Content-Type: application/json" -d '{"sn": "设备序列号"}' "http://localhost:9876/sn_query/huawei"
```

#### 4.4.3 验证码识别接口

**POST请求**：
```bash
curl -X POST http://localhost:9876/reg -d "base64编码的图片数据"
```

**参数说明**：
- 请求体：base64编码的图片数据（纯文本格式）
- 响应：识别出的验证码文本（前四位）

**返回示例**：
```
ABCD
```

**错误返回**：
- `ddddocr not available`：ddddocr库未安装
- `OCR error`：验证码识别失败
- `Error`：其他处理错误

## 5. 示例代码

### 5.1 Python示例

```python
import requests

# 查询深信服设备
response = requests.get("http://localhost:9876/sn_query/sangfor?sn=61902B45")
print(response.json())

# 查询华为设备
response = requests.get("http://localhost:9876/sn_query/huawei?sn=1023A7333670")
print(response.json())
```

### 5.2 响应示例

#### 深信服设备响应

```json
{
  "success": 1,
  "data": [
    {
      "序列号": "WAZCCG0292",
      "网关id": "61902B45",
      "设备型号": "AC-1000-B1300",
      "服务商名称": "上海联合电子科技有限公司",
      "服务电话": "021-60959881",
      "网络远程支持有效期": "2025-08-10",
      "同等功能软件升级有效期": "2025-08-10",
      "硬件维保有效期": "2025-08-10"
    }
  ]
}
```

#### 华为设备响应

```json
{
  "success": 1,
  "data": [
    {
      "序列号": "1023A7333670",
      "设备型号": "S5731S-H24T4XC-A",
      "服务套餐": "15天更换保修",
      "开始日期": "2024/02/08",
      "结束日期": "2025/02/07",
      "状态": "Terminated",
      "国家/地区": "China",
      "保修区域": "中国",
      "描述": "S5731S-H24T4XC 组合配置(24个10/100/1000BASE-T以太网端口,4个万兆SFP+,单子卡槽位,含1个交流电源)"
    }
  ]
}
```

## 6. 常见问题

### 6.1 验证码识别失败

**问题**：API返回验证码错误
**解决方案**：检查网络连接，确保能够访问外部OCR API，增加重试次数

### 6.2 会话过期

**问题**：登录状态失效
**解决方案**：检查账号密码是否正确，清除旧会话文件 `session.pkl` 后重新启动服务

### 6.3 网络错误

**问题**：网络连接问题导致查询失败
**解决方案**：检查网络连接，增加超时时间，确保能够访问厂商网站

## 7. 变更记录

- **2026-02-14**：初始化项目，实现深信服和华为设备查询功能
- **2026-02-14**：添加文档和配置文件，完善项目结构
- **2026-02-14**：添加验证码识别接口 `/reg`，支持base64编码图片的验证码识别

## 8. 注意事项

1. **安全配置**：请勿将 `.env` 文件提交到版本控制系统
2. **账号密码**：深信服BBS账号密码需要使用MD5加密
3. **依赖项**：确保安装了所有必要的依赖包
4. **网络权限**：确保服务器能够访问外部OCR API和厂商网站

## 9. 扩展指南

### 9.1 添加新厂商支持

1. **创建查询类**：实现类似 `HuaweiWarrantyQuery` 的查询类
2. **添加路由**：在 `service_query_api.py` 中添加新的路由函数
3. **更新文档**：在 README.md 和相关文档中添加新厂商的使用说明

### 9.2 优化建议

- **缓存机制**：为频繁查询的序列号添加缓存
- **并发处理**：考虑使用异步处理提高并发能力
- **监控系统**：添加API调用监控和告警
- **测试覆盖**：增加单元测试和集成测试