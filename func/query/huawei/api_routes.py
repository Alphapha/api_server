"""
华为查询 API 路由
"""
from flask import Blueprint, request, jsonify, Response
import logging
import json
import time
from .query_handler import HuaweiWarrantyQuery

logger = logging.getLogger('HuaweiAPI')

# 创建 blueprint
blueprint = Blueprint('query_huawei', __name__, url_prefix='/sn_query/huawei')


def register_routes(app):
    """注册路由到 Flask 应用"""
    app.register_blueprint(blueprint)
    logger.info("已注册华为查询路由")


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
            model = item.get("设备型号", "") or item.get("产品型号", "") or item.get("snModel", "")
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
            response["data"]["设备型号"] = data.get("设备型号", "") or data.get("产品型号", "") or data.get("snModel", "")
            
            # 提取最晚维保日期
            end_date = data.get("最晚维保日期", "")
            response["data"]["维保到期"] = end_date
            
            # 详细信息：直接放原始数据
            if "详细维保信息" in data:
                response["data"]["详细信息"] = data["详细维保信息"]
            else:
                response["data"]["详细信息"] = data
    
    return response


@blueprint.route('', methods=['GET', 'POST'])
def query_service_huawei():
    """API 接口：查询华为设备维保信息"""
    try:
        # 获取设备序列号和缓存参数
        if request.method == 'GET':
            serial_number = request.args.get('sn')
            use_cache = request.args.get('cache', '1') != '0'
        else:
            serial_number = request.json.get('sn') if request.is_json else request.form.get('sn')
            use_cache = request.json.get('cache', 1) if request.is_json else 1
            use_cache = use_cache != 0
        
        if not serial_number:
            return jsonify({
                "success": 0,
                "message": "设备序列号不能为空"
            })
        
        serial_number = serial_number.strip()
        logger.info(f"收到华为查询请求，设备序列号：{serial_number} (使用缓存：{use_cache})")
        
        # 创建华为查询客户端
        huawei_client = HuaweiWarrantyQuery()
        
        # 直接使用 query 方法（已内置数据库查询和保存）
        # use_cache=False 时 force_refresh=True
        result = huawei_client.query(serial_number, force_refresh=not use_cache)
        
        if result:
            logger.info("华为查询完成")
            
            # 统一输出格式
            formatted_result = format_response_data(result, 'huawei')
            
            # 使用 json.dumps 确保中文正确显示
            return Response(
                json.dumps(formatted_result, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            return jsonify({
                "success": 0,
                "message": "查询失败"
            })
    except Exception as e:
        logger.error(f"API 请求异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        })
