"""
SPIFFS 数据备份与恢复 API 路由
提供 SPIFFS 分区（会话、cron、记忆等数据）的备份和恢复接口
"""
from flask import Blueprint, request, jsonify, Response, send_file, stream_with_context
import os
import json
import logging
import hashlib

from .spiffs_handler import SPIFFSBackupManager

logger = logging.getLogger('SPIFFSAPI')

# 创建 blueprint
blueprint = Blueprint('spiffs_management', __name__, url_prefix='/api/spiffs')

# 全局备份管理器实例
backup_manager = None

# 默认分块大小（1MB）
DEFAULT_CHUNK_SIZE = 1024 * 1024


def get_backup_manager() -> SPIFFSBackupManager:
    """
    获取或创建 SPIFFS 备份管理器单例

    Returns:
        SPIFFSBackupManager 实例
    """
    global backup_manager
    if not backup_manager:
        backup_manager = SPIFFSBackupManager()
        logger.info("创建 SPIFFS 备份管理器实例")
    return backup_manager


def register_routes(app):
    """
    注册路由到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    app.register_blueprint(blueprint)
    logger.info("已注册 SPIFFS 备份恢复路由")


@blueprint.route('/backup', methods=['POST'])
def create_backup_task():
    """
    创建 SPIFFS 备份任务（准备接收数据）
    如果是小文件，可以直接上传完整数据；大文件建议使用分块上传

    Request Body (multipart/form-data 或 JSON):
        device_id: 设备唯一标识 (必填)
        file_size: 备份文件总大小（字节，可选，分块上传时建议提供）
        file_hash: 备份文件 SHA256 哈希（可选，用于完整性校验）
        description: 备份描述信息（可选）
        file: 完整备份文件（可选，如果直接上传完整文件）

    Returns:
        JSON 响应，包含备份任务信息或上传结果
    """
    try:
        device_id = ""
        file_size = 0
        file_hash = ""
        description = ""
        file_data = None

        # 处理 multipart/form-data
        if request.content_type and 'multipart/form-data' in request.content_type:
            device_id = request.form.get('device_id', '').strip()
            file_size = int(request.form.get('file_size', 0) or 0)
            file_hash = request.form.get('file_hash', '').strip()
            description = request.form.get('description', '').strip()

            # 检查是否直接上传了文件
            if 'file' in request.files:
                uploaded_file = request.files['file']
                file_data = uploaded_file.read()
                if file_size == 0:
                    file_size = len(file_data)
                # 如果没传哈希，计算一个
                if not file_hash:
                    file_hash = hashlib.sha256(file_data).hexdigest()

        # 处理 JSON
        elif request.is_json:
            data = request.get_json()
            device_id = data.get('device_id', '').strip()
            file_size = int(data.get('file_size', 0) or 0)
            file_hash = data.get('file_hash', '').strip()
            description = data.get('description', '').strip()

        # 处理 form-urlencoded
        else:
            device_id = request.form.get('device_id', '').strip()
            file_size = int(request.form.get('file_size', 0) or 0)
            file_hash = request.form.get('file_hash', '').strip()
            description = request.form.get('description', '').strip()

        # 参数校验
        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id（设备唯一标识）"
            }), 400

        manager = get_backup_manager()

        # 如果有直接上传的文件数据，走直接上传流程
        if file_data is not None and len(file_data) > 0:
            logger.info(
                f"直接上传 SPIFFS 备份: device={device_id}, "
                f"size={len(file_data)} bytes"
            )

            result = manager.upload_backup_direct(
                device_id=device_id,
                backup_data=file_data,
                file_hash=file_hash,
                description=description
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
                }), 500

        # 否则，创建分块上传任务
        logger.info(
            f"创建 SPIFFS 备份任务: device={device_id}, "
            f"expected_size={file_size} bytes"
        )

        result = manager.create_backup(
            device_id=device_id,
            file_size=file_size,
            file_hash=file_hash,
            description=description
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
            }), 400

    except Exception as e:
        logger.error(f"创建备份任务异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/backup/chunk', methods=['POST'])
def upload_backup_chunk():
    """
    分块上传备份数据

    Request Body (multipart/form-data):
        device_id: 设备唯一标识 (必填)
        backup_id: 备份任务 ID (必填)
        chunk_index: 当前分块索引，从 0 开始 (必填)
        total_chunks: 总分块数 (必填)
        chunk: 分块文件数据 (必填)

    Returns:
        JSON 响应
    """
    try:
        if not (request.content_type and 'multipart/form-data' in request.content_type):
            return jsonify({
                "success": 0,
                "message": "此接口必须使用 multipart/form-data 格式上传"
            }), 400

        device_id = request.form.get('device_id', '').strip()
        backup_id = request.form.get('backup_id', '').strip()
        chunk_index_str = request.form.get('chunk_index', '').strip()
        total_chunks_str = request.form.get('total_chunks', '').strip()

        # 参数校验
        if not device_id:
            return jsonify({"success": 0, "message": "缺少必填参数：device_id"}), 400
        if not backup_id:
            return jsonify({"success": 0, "message": "缺少必填参数：backup_id"}), 400
        if not chunk_index_str:
            return jsonify({"success": 0, "message": "缺少必填参数：chunk_index"}), 400
        if not total_chunks_str:
            return jsonify({"success": 0, "message": "缺少必填参数：total_chunks"}), 400

        try:
            chunk_index = int(chunk_index_str)
            total_chunks = int(total_chunks_str)
        except ValueError:
            return jsonify({
                "success": 0,
                "message": "chunk_index 和 total_chunks 必须是整数"
            }), 400

        if chunk_index < 0 or chunk_index >= total_chunks:
            return jsonify({
                "success": 0,
                "message": "chunk_index 必须在 0 到 total_chunks-1 之间"
            }), 400

        # 读取分块数据
        if 'chunk' not in request.files:
            return jsonify({"success": 0, "message": "缺少分块文件：chunk"}), 400

        chunk_file = request.files['chunk']
        chunk_data = chunk_file.read()

        if len(chunk_data) == 0:
            return jsonify({
                "success": 0,
                "message": "分块数据不能为空"
            }), 400

        logger.info(
            f"上传备份分块: device={device_id}, backup={backup_id}, "
            f"chunk={chunk_index}/{total_chunks}, size={len(chunk_data)}"
        )

        manager = get_backup_manager()
        result = manager.upload_backup_chunk(
            device_id=device_id,
            backup_id=backup_id,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_data=chunk_data
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
            }), 400 if "未找到" in result["message"] else 500

    except Exception as e:
        logger.error(f"上传备份分块异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/backup/complete', methods=['POST'])
def complete_backup_upload():
    """
    完成备份上传（合并分块，验证完整性）

    Request Body (JSON 或 form):
        device_id: 设备唯一标识 (必填)
        backup_id: 备份任务 ID (必填)

    Returns:
        JSON 响应，包含最终备份结果
    """
    try:
        if request.is_json:
            data = request.get_json()
            device_id = data.get('device_id', '').strip()
            backup_id = data.get('backup_id', '').strip()
        else:
            device_id = request.form.get('device_id', '').strip()
            backup_id = request.form.get('backup_id', '').strip()

        if not device_id:
            return jsonify({"success": 0, "message": "缺少必填参数：device_id"}), 400
        if not backup_id:
            return jsonify({"success": 0, "message": "缺少必填参数：backup_id"}), 400

        logger.info(f"完成备份上传: device={device_id}, backup={backup_id}")

        manager = get_backup_manager()
        result = manager.complete_backup(device_id, backup_id)

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
            }), 400

    except Exception as e:
        logger.error(f"完成备份上传异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/restore', methods=['GET'])
def restore_backup():
    """
    恢复 SPIFFS 备份（下载备份文件）

    Query Parameters:
        device_id: 设备唯一标识 (必填)
        backup_id: 备份 ID（可选，不指定则使用最新备份）

    Returns:
        二进制备份文件流
    """
    try:
        device_id = request.args.get('device_id', '').strip()
        backup_id = request.args.get('backup_id', '').strip()

        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id"
            }), 400

        logger.info(f"恢复备份请求: device={device_id}, backup={backup_id or '(latest)'}")

        manager = get_backup_manager()
        result = manager.get_backup_file_path(device_id, backup_id)

        if not result.get("success"):
            return jsonify({
                "success": 0,
                "message": result["message"]
            }), 404

        backup_data = result["data"]
        file_path = backup_data["file_path"]
        file_name = f"{device_id}_{backup_data['backup_id']}.bin"

        logger.info(
            f"提供备份文件下载: device={device_id}, "
            f"backup={backup_data['backup_id']}, size={backup_data['file_size']}"
        )

        return send_file(
            file_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=file_name,
            conditional=True
        )

    except Exception as e:
        logger.error(f"恢复备份异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/restore/info', methods=['GET'])
def get_restore_info():
    """
    获取恢复用的备份文件信息（不下载，只获取元数据）

    Query Parameters:
        device_id: 设备唯一标识 (必填)
        backup_id: 备份 ID（可选，不指定则使用最新备份）

    Returns:
        JSON 响应，包含备份文件的大小、哈希、创建时间等信息
    """
    try:
        device_id = request.args.get('device_id', '').strip()
        backup_id = request.args.get('backup_id', '').strip()

        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id"
            }), 400

        logger.info(f"查询备份恢复信息: device={device_id}, backup={backup_id or '(latest)'}")

        manager = get_backup_manager()
        result = manager.get_backup_file_path(device_id, backup_id)

        if not result.get("success"):
            return jsonify({
                "success": 0,
                "message": result["message"]
            }), 404

        backup_data = result["data"]

        return Response(
            json.dumps({
                "success": 1,
                "message": "获取备份信息成功，设备可通过 /api/spiffs/restore 下载文件",
                "data": {
                    "backup_id": backup_data["backup_id"],
                    "device_id": backup_data["device_id"],
                    "file_size": backup_data["file_size"],
                    "file_hash": backup_data["file_hash"],
                    "created_at": backup_data["created_at"],
                    "restore_url": f"/api/spiffs/restore?device_id={device_id}&backup_id={backup_data['backup_id']}",
                    "chunk_size": DEFAULT_CHUNK_SIZE
                }
            }, ensure_ascii=False),
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"获取恢复信息异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/backups', methods=['GET'])
def list_device_backups():
    """
    列出设备的所有备份文件

    Query Parameters:
        device_id: 设备唯一标识 (必填)

    Returns:
        JSON 响应，包含备份列表
    """
    try:
        device_id = request.args.get('device_id', '').strip()

        if not device_id:
            return jsonify({
                "success": 0,
                "message": "缺少必填参数：device_id"
            }), 400

        logger.info(f"列出设备备份: device={device_id}")

        manager = get_backup_manager()
        result = manager.list_backups(device_id)

        return Response(
            json.dumps({
                "success": 1,
                "message": result["message"],
                "data": result["data"]
            }, ensure_ascii=False),
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"列出备份异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/backup/info', methods=['GET'])
def get_backup_detail():
    """
    获取指定备份的详细信息

    Query Parameters:
        device_id: 设备唯一标识 (必填)
        backup_id: 备份 ID (必填)

    Returns:
        JSON 响应，包含备份详细信息
    """
    try:
        device_id = request.args.get('device_id', '').strip()
        backup_id = request.args.get('backup_id', '').strip()

        if not device_id:
            return jsonify({"success": 0, "message": "缺少必填参数：device_id"}), 400
        if not backup_id:
            return jsonify({"success": 0, "message": "缺少必填参数：backup_id"}), 400

        logger.info(f"获取备份详情: device={device_id}, backup={backup_id}")

        manager = get_backup_manager()
        result = manager.get_backup_info(device_id, backup_id)

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
        logger.error(f"获取备份详情异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500


@blueprint.route('/backup', methods=['DELETE'])
def delete_backup():
    """
    删除指定备份

    Request Body (JSON 或 form):
        device_id: 设备唯一标识 (必填)
        backup_id: 备份 ID (必填)

    Returns:
        JSON 响应
    """
    try:
        if request.is_json:
            data = request.get_json()
            device_id = data.get('device_id', '').strip()
            backup_id = data.get('backup_id', '').strip()
        else:
            device_id = request.form.get('device_id', '').strip()
            backup_id = request.form.get('backup_id', '').strip()

        if not device_id:
            return jsonify({"success": 0, "message": "缺少必填参数：device_id"}), 400
        if not backup_id:
            return jsonify({"success": 0, "message": "缺少必填参数：backup_id"}), 400

        logger.warning(f"删除备份: device={device_id}, backup={backup_id}")

        manager = get_backup_manager()
        result = manager.delete_backup(device_id, backup_id)

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
        logger.error(f"删除备份异常：{str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常：{str(e)}"
        }), 500
