"""
OTA 固件更新 API 路由
提供 OTA 热更新相关的接口：创建任务、查询状态、进度更新、确认成功等
"""
from flask import Blueprint, request, jsonify, Response
import json
import logging

from .ota_handler import OTAManager

logger = logging.getLogger('OTAAPI')

# 创建 blueprint
blueprint = Blueprint('ota_management', __name__, url_prefix='/api/ota')

# 全局 OTA 管理器实例
ota_manager = None


def get_ota_manager() -> OTAManager:
    """
    获取或创建 OTA 管理器单例

    Returns:
        OTAManager 实例
    """
    global ota_manager
    if not ota_manager:
        ota_manager = OTAManager()
        logger.info("创建 OTA 管理器实例")
    return ota_manager


def register_routes(app):
    """
    注册路由到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    app.register_blueprint(blueprint)
    logger.info("已注册 OTA 固件更新路由")


@blueprint.route('/update', methods=['POST'])
def create_ota_update():
    """
    创建 OTA 热更新任务
    设备通过此接口触发固件更新，服务端记录任务并返回任务信息

    Request Body (JSON):
        device_id: 设备唯一标识 (必填)
        firmware_url: 固件 HTTPS 下载地址 (必填)

    Returns:
        JSON 响应，包含任务创建结果
    """
    try:
        # 获取请求参数
        if request.is_json:
            data = request.get_json()
            device_id = data.get('device_id', '')
            firmware_url = data.get('firmware_url', '')
        else:
            device_id = request.form.get('device_id', '')
            firmware_url = request.form.get('firmware_url', '')

        # 参数校验
        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id（设备唯一标识）"
            }), 400

        if not firmware_url:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：firmware_url（固件下载地址）"
            }), 400

        device_id = device_id.strip()
        firmware_url = firmware_url.strip()

        logger.info(
            f"收到 OTA 更新请求: device={device_id}, url={firmware_url}"
        )

        # 创建 OTA 更新任务
        manager = get_ota_manager()
        result = manager.create_update_task(device_id, firmware_url)

        if result.get("success"):
            logger.info(f"OTA 更新任务创建成功: device={device_id}")
            return Response(
                json.dumps({
                    "success": 1,
                    "message": result["message"],
                    "data": result["data"]
                }, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            logger.warning(f"OTA 更新任务创建失败: {result['message']}")
            return jsonify({
                "success": 0,
                "message": result["message"]
            }), 400

    except Exception as e:
        logger.error(f"创建 OTA 更新任务异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/status', methods=['GET'])
def get_ota_status():
    """
    查询 OTA 更新状态和进度

    Query Parameters:
        device_id: 设备唯一标识 (必填)

    Returns:
        JSON 响应，包含当前更新状态、进度、分区信息等
    """
    try:
        device_id = request.args.get('device_id', '')

        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id（设备唯一标识）"
            }), 400

        device_id = device_id.strip()
        logger.info(f"查询 OTA 状态: device={device_id}")

        manager = get_ota_manager()
        result = manager.get_status(device_id)

        return Response(
            json.dumps({
                "success": 1 if result.get("success") else 0,
                "message": result["message"],
                "data": result.get("data", {})
            }, ensure_ascii=False),
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"查询 OTA 状态异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/progress', methods=['POST'])
def update_ota_progress():
    """
    设备上报 OTA 更新进度
    设备在下载、校验、安装过程中调用此接口上报进度

    Request Body (JSON):
        device_id: 设备唯一标识 (必填)
        status: 当前状态 (pending/downloading/verifying/installing/success/failed/rollback)
        progress: 进度百分比 0-100 (可选)
        downloaded_bytes: 已下载字节数 (可选)
        total_bytes: 总字节数 (可选)
        current_partition: 当前运行分区 (可选，如 factory, ota_0, ota_1)
        target_partition: 目标更新分区 (可选)
        error_message: 错误信息 (可选，失败时填写)

    Returns:
        JSON 响应
    """
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        device_id = data.get('device_id', '').strip()
        status = data.get('status', '').strip()
        progress = int(data.get('progress', 0) or 0)
        downloaded_bytes = int(data.get('downloaded_bytes', 0) or 0)
        total_bytes = int(data.get('total_bytes', 0) or 0)
        current_partition = data.get('current_partition', '').strip()
        target_partition = data.get('target_partition', '').strip()
        error_message = data.get('error_message', '').strip()

        # 参数校验
        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id"
            }), 400

        if not status:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：status（当前状态）"
            }), 400

        valid_statuses = [
            "pending", "downloading", "verifying", "installing",
            "success", "failed", "rollback"
        ]
        if status not in valid_statuses:
            return jsonify({
                "success": 0,
                "message": f"无效的状态值，可选值：{', '.join(valid_statuses)}"
            }), 400

        logger.info(
            f"OTA 进度上报: device={device_id}, status={status}, "
            f"progress={progress}%"
        )

        manager = get_ota_manager()
        result = manager.update_progress(
            device_id=device_id,
            status=status,
            progress=progress,
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            current_partition=current_partition,
            target_partition=target_partition,
            error_message=error_message
        )

        if result.get("success"):
            return Response(
                json.dumps({
                    "success": 1,
                    "message": result["message"],
                    "data": result["data"]
                }, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            return jsonify({
                "success": 0,
                "message": result["message"]
            }), 404

    except Exception as e:
        logger.error(f"OTA 进度上报异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/confirm', methods=['POST'])
def confirm_ota_success():
    """
    确认 OTA 更新成功
    新固件正常运行后，设备调用此接口确认成功，取消回滚保护

    Request Body (JSON):
        device_id: 设备唯一标识 (必填)

    Returns:
        JSON 响应
    """
    try:
        if request.is_json:
            data = request.get_json()
            device_id = data.get('device_id', '')
        else:
            device_id = request.form.get('device_id', '')

        device_id = device_id.strip()

        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id"
            }), 400

        logger.info(f"确认 OTA 成功: device={device_id}")

        manager = get_ota_manager()
        result = manager.confirm_update_success(device_id)

        if result.get("success"):
            return Response(
                json.dumps({
                    "success": 1,
                    "message": result["message"],
                    "data": result["data"]
                }, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            return jsonify({
                "success": 0,
                "message": result["message"]
            }), 404

    except Exception as e:
        logger.error(f"确认 OTA 成功异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/rollback', methods=['POST'])
def mark_ota_rollback():
    """
    标记 OTA 回滚
    如果新固件启动失败，设备自动回滚后调用此接口上报

    Request Body (JSON):
        device_id: 设备唯一标识 (必填)
        reason: 回滚原因 (可选)

    Returns:
        JSON 响应
    """
    try:
        if request.is_json:
            data = request.get_json()
            device_id = data.get('device_id', '')
            reason = data.get('reason', '')
        else:
            device_id = request.form.get('device_id', '')
            reason = request.form.get('reason', '')

        device_id = device_id.strip()
        reason = reason.strip()

        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id"
            }), 400

        logger.warning(f"标记 OTA 回滚: device={device_id}, reason={reason}")

        manager = get_ota_manager()
        result = manager.mark_rollback(device_id, reason)

        if result.get("success"):
            return Response(
                json.dumps({
                    "success": 1,
                    "message": result["message"],
                    "data": result["data"]
                }, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            return jsonify({
                "success": 0,
                "message": result["message"]
            }), 404

    except Exception as e:
        logger.error(f"标记 OTA 回滚异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/tasks', methods=['GET'])
def list_ota_tasks():
    """
    列出所有 OTA 更新任务（管理接口）

    Query Parameters:
        无

    Returns:
        JSON 响应，包含所有 OTA 任务列表
    """
    try:
        logger.info("查询所有 OTA 任务列表")

        manager = get_ota_manager()
        result = manager.list_all_tasks()

        return Response(
            json.dumps({
                "success": 1,
                "message": result["message"],
                "data": result["data"]
            }, ensure_ascii=False),
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"查询 OTA 任务列表异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/validate', methods=['POST'])
def validate_firmware():
    """
    验证固件 URL 是否合法（预检接口）

    Request Body (JSON):
        firmware_url: 固件下载 URL (必填)

    Returns:
        JSON 响应，包含验证结果
    """
    try:
        if request.is_json:
            data = request.get_json()
            firmware_url = data.get('firmware_url', '')
        else:
            firmware_url = request.form.get('firmware_url', '')

        firmware_url = firmware_url.strip()

        if not firmware_url:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：firmware_url"
            }), 400

        logger.info(f"验证固件 URL: {firmware_url}")

        manager = get_ota_manager()
        result = manager.validate_firmware_url(firmware_url)

        if result.get("success"):
            return Response(
                json.dumps({
                    "success": 1,
                    "message": result["message"],
                    "data": {
                        "firmware_url": firmware_url,
                        "valid": True
                    }
                }, ensure_ascii=False),
                mimetype='application/json'
            )
        else:
            return jsonify({
                "success": 0,
                "message": result["message"],
                "data": {
                    "firmware_url": firmware_url,
                    "valid": False
                }
            }), 400

    except Exception as e:
        logger.error(f"验证固件 URL 异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500
