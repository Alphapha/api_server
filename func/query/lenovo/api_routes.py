"""
联想查询 API 路由
"""
from flask import Blueprint, request, jsonify, Response
import json
import logging

logger = logging.getLogger('QueryLenovoAPI')

# 创建 blueprint
blueprint = Blueprint('query_lenovo', __name__, url_prefix='/sn_query/lenovo')


def register_routes(app):
    """注册路由到 Flask 应用"""
    app.register_blueprint(blueprint)
    logger.info("已注册联想查询路由")


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
            
            # 提取设备型号
            model = item.get("设备型号", "") or item.get("产品型号", "")
            response["data"]["设备型号"] = model
            
            # 提取最晚维保日期
            end_date = item.get("最晚维保日期", "")
            
            response["data"]["维保到期"] = end_date
            
            # 详细信息：直接放原始数据
            if "详细维保信息" in item:
                response["data"]["详细信息"] = item["详细维保信息"]
            else:
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
    查询联想设备序列号
    
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
        logger.info(f"收到联想查询请求：{serial_number} (使用缓存：{use_cache})")
        
        # 执行查询
        from func.query.lenovo.query_handler import LenovoQueryService
        
        service = LenovoQueryService()
        # use_cache=False 时 force_refresh=True
        result = service.query(serial_number, force_refresh=not use_cache)
        
        if result and result.get("success") == 1:
            logger.info("联想服务查询成功")
            
            # 统一输出格式
            formatted_result = format_response_data(result, 'lenovo')
            
            return Response(
                json.dumps(formatted_result, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            logger.warning(f"联想服务查询失败：{result}")
            return jsonify({
                "success": 0,
                "message": result.get("message", "服务查询失败")
            })
    
    except Exception as e:
        logger.error(f"API 请求异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        })
