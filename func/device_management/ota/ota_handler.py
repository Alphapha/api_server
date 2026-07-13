"""
OTA 固件更新管理 Handler
提供 OTA 更新状态跟踪、固件 URL 验证等功能
"""
import os
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger('OTAHandler')


class OTAStatus:
    """OTA 更新状态枚举"""
    PENDING = "pending"          # 等待开始
    DOWNLOADING = "downloading"  # 下载中
    VERIFYING = "verifying"      # 校验中
    INSTALLING = "installing"    # 安装中
    SUCCESS = "success"          # 成功
    FAILED = "failed"            # 失败
    ROLLBACK = "rollback"        # 回滚中


class OTAManager:
    """OTA 固件更新管理器"""

    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化 OTA 管理器

        Args:
            storage_path: OTA 状态存储路径，默认为 data/ota_status
        """
        if storage_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )))
            storage_path = os.path.join(base_dir, 'data', 'ota_status')

        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

        # 内存中的状态缓存：device_id -> 状态字典
        self._status_cache: Dict[str, Dict[str, Any]] = {}
        logger.info("OTA 管理器初始化完成")

    def validate_firmware_url(self, url: str) -> Dict[str, Any]:
        """
        验证固件 URL 是否合法

        Args:
            url: 固件下载 URL

        Returns:
            验证结果字典，包含 success、message 字段
        """
        if not url:
            return {
                "success": False,
                "message": "固件 URL 不能为空"
            }

        # 检查是否为 HTTPS
        if not url.startswith("https://"):
            return {
                "success": False,
                "message": "固件 URL 必须以 https:// 开头，确保传输安全"
            }

        # 检查 URL 格式有效性（简单检查）
        if len(url) < 15 or " " in url:
            return {
                "success": False,
                "message": "固件 URL 格式无效"
            }

        # 检查文件扩展名（可选，但推荐）
        valid_extensions = ('.bin', '.img', '.firmware')
        if not any(url.lower().endswith(ext) for ext in valid_extensions):
            logger.warning(f"固件 URL 扩展名不常见: {url}")

        return {
            "success": True,
            "message": "固件 URL 验证通过"
        }

    def create_update_task(self, device_id: str, firmware_url: str) -> Dict[str, Any]:
        """
        创建 OTA 更新任务

        Args:
            device_id: 设备唯一标识
            firmware_url: 固件下载 URL

        Returns:
            任务信息字典
        """
        # 先验证 URL
        validation = self.validate_firmware_url(firmware_url)
        if not validation["success"]:
            return validation

        # 生成任务 ID
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # 构建任务状态
        task_status = {
            "task_id": task_id,
            "device_id": device_id,
            "firmware_url": firmware_url,
            "status": OTAStatus.PENDING,
            "progress": 0,
            "current_partition": "",
            "target_partition": "",
            "error_message": "",
            "created_at": now,
            "updated_at": now,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "rollback_protection": True
        }

        # 保存到缓存
        self._status_cache[device_id] = task_status
        self._save_status_to_disk(device_id, task_status)

        logger.info(f"创建 OTA 更新任务: device={device_id}, task={task_id}, url={firmware_url}")

        return {
            "success": True,
            "message": "OTA 更新任务创建成功",
            "data": task_status
        }

    def update_progress(self, device_id: str, status: str, progress: int = 0,
                        downloaded_bytes: int = 0, total_bytes: int = 0,
                        current_partition: str = "", target_partition: str = "",
                        error_message: str = "") -> Dict[str, Any]:
        """
        更新 OTA 任务进度

        Args:
            device_id: 设备 ID
            status: 新状态（OTAStatus 枚举值）
            progress: 进度百分比 (0-100)
            downloaded_bytes: 已下载字节数
            total_bytes: 总字节数
            current_partition: 当前运行分区
            target_partition: 目标更新分区
            error_message: 错误信息（如果有）

        Returns:
            更新结果
        """
        if device_id not in self._status_cache:
            # 尝试从磁盘加载
            self._load_status_from_disk(device_id)

        if device_id not in self._status_cache:
            return {
                "success": False,
                "message": f"未找到设备 {device_id} 的 OTA 任务，请先创建任务"
            }

        task = self._status_cache[device_id]
        task["status"] = status
        task["progress"] = min(max(progress, 0), 100)
        task["downloaded_bytes"] = downloaded_bytes
        task["total_bytes"] = total_bytes
        task["current_partition"] = current_partition
        task["target_partition"] = target_partition
        task["error_message"] = error_message
        task["updated_at"] = datetime.now().isoformat()

        self._save_status_to_disk(device_id, task)

        logger.info(
            f"OTA 进度更新: device={device_id}, status={status}, "
            f"progress={progress}%, downloaded={downloaded_bytes}/{total_bytes}"
        )

        return {
            "success": True,
            "message": "进度更新成功",
            "data": task
        }

    def get_status(self, device_id: str) -> Dict[str, Any]:
        """
        获取设备的 OTA 更新状态

        Args:
            device_id: 设备 ID

        Returns:
            状态信息字典
        """
        if device_id not in self._status_cache:
            self._load_status_from_disk(device_id)

        if device_id not in self._status_cache:
            return {
                "success": False,
                "message": f"设备 {device_id} 暂无 OTA 任务记录",
                "data": {
                    "device_id": device_id,
                    "status": "none",
                    "progress": 0,
                    "current_partition": "",
                    "last_updated": None
                }
            }

        return {
            "success": True,
            "message": "获取状态成功",
            "data": self._status_cache[device_id]
        }

    def list_all_tasks(self) -> Dict[str, Any]:
        """
        列出所有 OTA 任务

        Returns:
            所有任务列表
        """
        # 从磁盘加载所有状态
        self._load_all_status_from_disk()

        tasks = list(self._status_cache.values())
        # 按创建时间倒序排列
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "success": True,
            "message": f"共找到 {len(tasks)} 个 OTA 任务",
            "data": {
                "total": len(tasks),
                "tasks": tasks
            }
        }

    def confirm_update_success(self, device_id: str) -> Dict[str, Any]:
        """
        确认固件更新成功（新固件正常运行，取消回滚）

        Args:
            device_id: 设备 ID

        Returns:
            确认结果
        """
        if device_id not in self._status_cache:
            self._load_status_from_disk(device_id)

        if device_id not in self._status_cache:
            return {
                "success": False,
                "message": f"设备 {device_id} 无进行中的 OTA 任务"
            }

        task = self._status_cache[device_id]
        task["status"] = OTAStatus.SUCCESS
        task["progress"] = 100
        task["updated_at"] = datetime.now().isoformat()
        self._save_status_to_disk(device_id, task)

        logger.info(f"OTA 更新成功确认: device={device_id}, task={task['task_id']}")

        return {
            "success": True,
            "message": "固件更新确认成功，回滚保护已解除",
            "data": task
        }

    def mark_rollback(self, device_id: str, reason: str = "") -> Dict[str, Any]:
        """
        标记设备发生回滚

        Args:
            device_id: 设备 ID
            reason: 回滚原因

        Returns:
            回滚标记结果
        """
        if device_id not in self._status_cache:
            self._load_status_from_disk(device_id)

        if device_id not in self._status_cache:
            return {
                "success": False,
                "message": f"设备 {device_id} 无 OTA 任务记录"
            }

        task = self._status_cache[device_id]
        task["status"] = OTAStatus.ROLLBACK
        task["error_message"] = reason or "新固件启动失败，自动回滚"
        task["updated_at"] = datetime.now().isoformat()
        self._save_status_to_disk(device_id, task)

        logger.warning(
            f"OTA 回滚标记: device={device_id}, task={task['task_id']}, "
            f"reason={task['error_message']}"
        )

        return {
            "success": True,
            "message": "已标记回滚状态",
            "data": task
        }

    def _save_status_to_disk(self, device_id: str, status: Dict[str, Any]) -> None:
        """
        将状态保存到磁盘文件

        Args:
            device_id: 设备 ID
            status: 状态字典
        """
        import json
        try:
            safe_device_id = device_id.replace('/', '_').replace('\\', '_')
            file_path = os.path.join(self.storage_path, f"{safe_device_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 OTA 状态到磁盘失败: {str(e)}")

    def _load_status_from_disk(self, device_id: str) -> None:
        """
        从磁盘加载设备状态

        Args:
            device_id: 设备 ID
        """
        import json
        try:
            safe_device_id = device_id.replace('/', '_').replace('\\', '_')
            file_path = os.path.join(self.storage_path, f"{safe_device_id}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._status_cache[device_id] = json.load(f)
        except Exception as e:
            logger.error(f"从磁盘加载 OTA 状态失败: {str(e)}")

    def _load_all_status_from_disk(self) -> None:
        """从磁盘加载所有设备状态"""
        import json
        try:
            if not os.path.exists(self.storage_path):
                return

            for filename in os.listdir(self.storage_path):
                if filename.endswith('.json'):
                    device_id = filename[:-5]  # 去掉 .json 后缀
                    if device_id not in self._status_cache:
                        file_path = os.path.join(self.storage_path, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                self._status_cache[device_id] = json.load(f)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"批量加载 OTA 状态失败: {str(e)}")
