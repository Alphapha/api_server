"""
深信服查询 API 路由
"""
from flask import Blueprint, request, jsonify, Response
import json
import logging
import os
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger('QuerySangforAPI')

# 创建 blueprint
blueprint = Blueprint('query_sangfor', __name__, url_prefix='/sn_query/sangfor')

# 全局登录客户端实例
login_client = None


def register_routes(app):
    """注册路由到 Flask 应用"""
    app.register_blueprint(blueprint)
    logger.info("已注册深信服查询路由")


def get_login_client():
    """获取或创建登录客户端"""
    global login_client
    
    if not login_client:
        from func.query.sangfor.login_handler import SangforBBSLogin
        
        # 从环境变量读取账号密码（必须配置）
        username = os.getenv('SANGFOR_USERNAME')
        password = os.getenv('SANGFOR_PASSWORD')
        
        if not username or not password:
            raise ValueError("请在 .env 文件中配置 SANGFOR_USERNAME 和 SANGFOR_PASSWORD")
        
        logger.info("创建登录客户端实例")
        login_client = SangforBBSLogin(username, password)
    
    return login_client


def format_response_data(result, vendor):
    """
    统一响应数据格式
    
    Args:
        result: 原始查询结果
        vendor: 厂商名称 (sangfor, huawei, lenovo)
    
    Returns:
        统一格式的数据
    """
    # 默认返回结构
    response = {
        "success": result.get("success", 0),
        "data": {
            "序列号": "",
            "设备型号": "",
            "维保到期": "",
            "详细信息": {}
        }
    }
    
    # 如果有 data 字段，提取关键信息
    if "data" in result:
        data = result["data"]
        
        if isinstance(data, list) and len(data) > 0:
            # 取第一条记录
            item = data[0]
            
            # 提取序列号
            response["data"]["序列号"] = item.get("序列号", "")
            
            # 提取设备型号（可能有多个字段）
            model = item.get("设备型号", "") or item.get("产品型号", "") or item.get("机器型号", "")
            response["data"]["设备型号"] = model
            
            # 提取最晚维保日期
            end_date = item.get("最晚维保日期", "")
            response["data"]["维保到期"] = end_date
            
            # 详细信息：直接放原始数据（排除已经提取的字段）
            if "详细维保信息" in item:
                response["data"]["详细信息"] = item["详细维保信息"]
            else:
                # 如果没有详细维保信息字段，说明 item 本身就是原始数据
                response["data"]["详细信息"] = item
            
        elif isinstance(data, dict):
            # 如果是字典，直接提取
            response["data"]["序列号"] = data.get("序列号", "")
            response["data"]["设备型号"] = data.get("设备型号", "") or data.get("产品型号", "")
            
            # 提取最晚维保日期
            end_date = data.get("最晚维保日期", "")
            response["data"]["维保到期"] = end_date
            
            # 详细信息：直接放原始数据
            if "详细维保信息" in data:
                response["data"]["详细信息"] = data["详细维保信息"]
            else:
                response["data"]["详细信息"] = data
    
    return response


@blueprint.route('', methods=['GET'])
def query_serial():
    """
    查询深信服设备序列号
    
    Query Parameters:
        sn: 设备序列号
        cache: 是否使用缓存（可选，默认为 1）
               1 - 优先查询数据库，数据库无记录时查询互联网
               0 - 直接从互联网获取最新数据
            
    Returns:
        JSON 响应
    """
    try:
        serial_number = request.args.get('sn')
        use_cache = request.args.get('cache', '1') != '0'
        
        if not serial_number:
            return jsonify({
                'success': 0,
                'message': '缺少参数：sn'
            }), 400
        
        serial_number = serial_number.strip()
        logger.info(f"收到深信服查询请求：{serial_number} (使用缓存：{use_cache})")
        
        # 获取登录客户端
        client = get_login_client()
        
        # 确保获取有效的 session
        if not client.session:
            logger.info("获取 session")
            client.get_session()
        
        # 执行查询，添加失败重试机制
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                from func.query.sangfor.query_handler import SangforQueryService
                
                service = SangforQueryService(client.session)
                # use_cache=False 时 force_refresh=True
                result = service.query(serial_number, max_retries=1, force_refresh=not use_cache)
                
                if result:
                    # 检查是否是验证码错误
                    if result.get("success") == -2:
                        logger.warning("服务查询失败：验证码错误，准备重试")
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = retry_count
                            logger.info(f"{wait_time}秒后重试...")
                            time.sleep(wait_time)
                        else:
                            logger.error("已达到最大重试次数，服务查询失败")
                            return jsonify({
                                "success": 0,
                                "message": "服务查询失败：验证码错误"
                            })
                    
                    # 检查是否是 session 失效（301/302 重定向）
                    elif result.get("message") == "session 已失效":
                        logger.warning("服务查询失败：session 已失效，准备重新登录")
                        login_success = client.force_login()
                        if login_success:
                            logger.info("重新登录成功，准备重试查询")
                            # 重置重试计数器，允许重新开始查询
                            retry_count = 0
                            wait_time = 1
                            logger.info(f"{wait_time}秒后重试...")
                            time.sleep(wait_time)
                            # 使用新的 session 创建新的查询服务对象
                            service = SangforQueryService(client.session)
                        else:
                            logger.error("重新登录失败")
                            return jsonify({
                                "success": 0,
                                "message": "服务查询失败：重新登录失败，请检查账号密码"
                            })
                    
                    # 查询成功
                    elif result.get("success") == 1:
                        logger.info("服务查询成功")
                        
                        # 统一输出格式
                        formatted_result = format_response_data(result, 'sangfor')
                        
                        return Response(
                            json.dumps(formatted_result, ensure_ascii=False),
                            mimetype='application/json'
                        )
                    
                    # 其他错误
                    else:
                        logger.warning(f"服务查询返回错误：{result}")
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = retry_count
                            logger.info(f"{wait_time}秒后重试...")
                            time.sleep(wait_time)
                        else:
                            return jsonify({
                                "success": 0,
                                "message": result.get("message", "服务查询失败")
                            })
                else:
                    logger.error("服务查询返回空结果")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_count
                        logger.info(f"{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        return jsonify({
                            "success": 0,
                            "message": "服务查询失败：返回空结果"
                        })
            
            except Exception as e:
                logger.error(f"查询过程中发生异常：{str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_count
                    logger.info(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    return jsonify({
                        "success": 0,
                        "message": f"查询异常：{str(e)}"
                    })
        
        return jsonify({
            "success": 0,
            "message": "查询失败：达到最大重试次数"
        })
    
    except Exception as e:
        logger.error(f"API 请求异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        })
