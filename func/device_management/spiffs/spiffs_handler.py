"""
SPIFFS 数据备份与恢复 Handler
提供 SPIFFS 分区（会话、cron、记忆等数据）的备份存储、检索、管理功能
"""
import os
import logging
import time
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, Any

logger = logging.getLogger('SPIFFSHandler')


class BackupStatus:
    """备份状态枚举"""
    COMPLETED = "completed"    # 备份完成
    PARTIAL = "partial"        # 部分备份（分块上传中）
    RESTORING = "restoring"    # 恢复中
    DELETED = "deleted"        # 已删除


class SPIFFSBackupManager:
    """SPIFFS 备份管理器"""

    def __init__(self, backup_dir: Optional[str] = None):
        """
        初始化 SPIFFS 备份管理器

        Args:
            backup_dir: 备份文件存储目录，默认为 data/backups
        """
        if backup_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )))
            backup_dir = os.path.join(base_dir, 'data', 'backups')

        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

        # 元数据存储路径
        self.metadata_path = os.path.join(self.backup_dir, 'metadata.json')
        self._metadata = self._load_metadata()

        logger.info(f"SPIFFS 备份管理器初始化完成，存储目录: {self.backup_dir}")

    def _load_metadata(self) -> Dict[str, Any]:
        """
        从磁盘加载元数据

        Returns:
            元数据字典
        """
        try:
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载备份元数据失败: {str(e)}")

        # 默认结构
        return {
            "backups": {},  # device_id -> List[backup_info]
            "version": "1.0"
        }

    def _save_metadata(self) -> None:
        """保存元数据到磁盘"""
        try:
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存备份元数据失败: {str(e)}")

    def _get_device_backup_dir(self, device_id: str) -> str:
        """
        获取设备的备份存储目录

        Args:
            device_id: 设备 ID

        Returns:
            设备备份目录路径
        """
        safe_device_id = device_id.replace('/', '_').replace('\\', '_')
        device_dir = os.path.join(self.backup_dir, safe_device_id)
        os.makedirs(device_dir, exist_ok=True)
        return device_dir

    def create_backup(self, device_id: str, file_size: int = 0,
                      file_hash: str = "", description: str = "") -> Dict[str, Any]:
        """
        创建备份任务（准备接收备份数据）

        Args:
            device_id: 设备唯一标识
            file_size: 备份文件总大小（字节）
            file_hash: 备份文件的 SHA256 哈希（可选，用于完整性校验）
            description: 备份描述信息（可选）

        Returns:
            备份任务信息字典
        """
        if not device_id:
            return {
                "success": False,
                "message": "设备 ID 不能为空"
            }

        backup_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        timestamp = int(time.time())

        # 构建备份信息
        backup_info = {
            "backup_id": backup_id,
            "device_id": device_id,
            "status": BackupStatus.PARTIAL,
            "file_size": file_size,
            "received_size": 0,
            "file_hash": file_hash,
            "calculated_hash": "",
            "description": description,
            "created_at": now,
            "updated_at": now,
            "timestamp": timestamp,
            "chunks_received": [],
            "total_chunks": 0
        }

        # 创建设备备份目录和备份文件目录
        device_dir = self._get_device_backup_dir(device_id)
        backup_data_dir = os.path.join(device_dir, backup_id)
        os.makedirs(backup_data_dir, exist_ok=True)

        # 保存备份元数据
        if device_id not in self._metadata["backups"]:
            self._metadata["backups"][device_id] = []

        self._metadata["backups"][device_id].append(backup_info)
        self._save_metadata()

        logger.info(
            f"创建 SPIFFS 备份任务: device={device_id}, "
            f"backup={backup_id}, size={file_size} bytes"
        )

        return {
            "success": True,
            "message": "备份任务创建成功，可以开始上传数据",
            "data": backup_info
        }

    def upload_backup_chunk(self, device_id: str, backup_id: str,
                            chunk_index: int, total_chunks: int,
                            chunk_data: bytes) -> Dict[str, Any]:
        """
        分块上传备份数据

        Args:
            device_id: 设备 ID
            backup_id: 备份任务 ID
            chunk_index: 当前块索引（从 0 开始）
            total_chunks: 总块数
            chunk_data: 块数据（二进制）

        Returns:
            上传结果
        """
        # 查找备份任务
        backup_info = self._find_backup(device_id, backup_id)
        if not backup_info:
            return {
                "success": False,
                "message": f"未找到备份任务: device={device_id}, backup={backup_id}"
            }

        # 存储块文件
        device_dir = self._get_device_backup_dir(device_id)
        backup_data_dir = os.path.join(device_dir, backup_id)
        chunk_file = os.path.join(backup_data_dir, f"chunk_{chunk_index:06d}")

        try:
            with open(chunk_file, 'wb') as f:
                f.write(chunk_data)

            chunk_size = len(chunk_data)
            backup_info["total_chunks"] = total_chunks

            if chunk_index not in backup_info["chunks_received"]:
                backup_info["chunks_received"].append(chunk_index)
                backup_info["received_size"] += chunk_size

            backup_info["updated_at"] = datetime.now().isoformat()
            self._save_metadata()

            logger.info(
                f"备份分块上传成功: device={device_id}, backup={backup_id}, "
                f"chunk={chunk_index}/{total_chunks}, size={chunk_size}"
            )

            # 检查是否所有块都已上传完成
            all_received = (
                len(backup_info["chunks_received"]) >= total_chunks and
                total_chunks > 0
            )

            return {
                "success": True,
                "message": f"分块 {chunk_index} 上传成功",
                "data": {
                    "backup_id": backup_id,
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "received_chunks": len(backup_info["chunks_received"]),
                    "received_size": backup_info["received_size"],
                    "all_received": all_received
                }
            }

        except Exception as e:
            logger.error(f"保存备份分块失败: {str(e)}")
            return {
                "success": False,
                "message": f"保存分块失败: {str(e)}"
            }

    def complete_backup(self, device_id: str, backup_id: str) -> Dict[str, Any]:
        """
        完成备份，合并所有分块并验证完整性

        Args:
            device_id: 设备 ID
            backup_id: 备份任务 ID

        Returns:
            完成结果
        """
        backup_info = self._find_backup(device_id, backup_id)
        if not backup_info:
            return {
                "success": False,
                "message": f"未找到备份任务: device={device_id}, backup={backup_id}"
            }

        device_dir = self._get_device_backup_dir(device_id)
        backup_data_dir = os.path.join(device_dir, backup_id)

        # 合并所有分块
        total_chunks = backup_info.get("total_chunks", 0)
        if total_chunks == 0:
            return {
                "success": False,
                "message": "分块数量为 0，无法完成备份"
            }

        # 检查是否所有分块都已接收
        if len(backup_info["chunks_received"]) < total_chunks:
            missing = total_chunks - len(backup_info["chunks_received"])
            return {
                "success": False,
                "message": f"还有 {missing} 个分块未上传，请先上传所有分块"
            }

        try:
            # 最终备份文件路径
            final_file = os.path.join(device_dir, f"{backup_id}.bin")
            sha256_hash = hashlib.sha256()

            with open(final_file, 'wb') as out_f:
                for i in range(total_chunks):
                    chunk_file = os.path.join(backup_data_dir, f"chunk_{i:06d}")
                    if not os.path.exists(chunk_file):
                        return {
                            "success": False,
                            "message": f"缺少分块文件: chunk_{i:06d}"
                        }

                    with open(chunk_file, 'rb') as in_f:
                        chunk_data = in_f.read()
                        out_f.write(chunk_data)
                        sha256_hash.update(chunk_data)

            # 计算最终文件哈希
            calculated_hash = sha256_hash.hexdigest()
            backup_info["calculated_hash"] = calculated_hash

            # 验证哈希（如果提供了）
            expected_hash = backup_info.get("file_hash", "")
            hash_valid = True
            if expected_hash and expected_hash != calculated_hash:
                logger.warning(
                    f"备份哈希校验不一致: expected={expected_hash}, "
                    f"actual={calculated_hash}"
                )
                hash_valid = False

            # 更新文件大小
            final_file_size = os.path.getsize(final_file)
            backup_info["file_size"] = final_file_size
            backup_info["received_size"] = final_file_size

            # 更新状态
            backup_info["status"] = BackupStatus.COMPLETED
            backup_info["updated_at"] = datetime.now().isoformat()
            backup_info["final_file"] = final_file
            backup_info["hash_valid"] = hash_valid

            self._save_metadata()

            # 清理分块文件（可选，节省空间）
            self._cleanup_chunks(backup_data_dir, total_chunks)

            logger.info(
                f"SPIFFS 备份完成: device={device_id}, backup={backup_id}, "
                f"size={final_file_size}, hash_valid={hash_valid}"
            )

            return {
                "success": True,
                "message": "备份完成，文件已合并" + ("" if hash_valid else "（注意：哈希校验不一致）"),
                "data": {
                    "backup_id": backup_id,
                    "file_size": final_file_size,
                    "expected_hash": expected_hash,
                    "calculated_hash": calculated_hash,
                    "hash_valid": hash_valid,
                    "final_file": final_file
                }
            }

        except Exception as e:
            logger.error(f"完成备份失败: {str(e)}")
            return {
                "success": False,
                "message": f"合并分块失败: {str(e)}"
            }

    def upload_backup_direct(self, device_id: str, backup_data: bytes,
                             file_hash: str = "", description: str = "") -> Dict[str, Any]:
        """
        直接上传完整备份文件（无需分块）

        Args:
            device_id: 设备 ID
            backup_data: 备份文件二进制数据
            file_hash: 文件哈希（可选）
            description: 备份描述（可选）

        Returns:
            上传结果
        """
        if not device_id:
            return {
                "success": False,
                "message": "设备 ID 不能为空"
            }

        if not backup_data or len(backup_data) == 0:
            return {
                "success": False,
                "message": "备份数据不能为空"
            }

        backup_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        timestamp = int(time.time())
        file_size = len(backup_data)

        # 计算哈希
        calculated_hash = hashlib.sha256(backup_data).hexdigest()
        hash_valid = True
        if file_hash and file_hash != calculated_hash:
            logger.warning(f"直接上传哈希不一致: expected={file_hash}, actual={calculated_hash}")
            hash_valid = False

        try:
            device_dir = self._get_device_backup_dir(device_id)
            final_file = os.path.join(device_dir, f"{backup_id}.bin")

            with open(final_file, 'wb') as f:
                f.write(backup_data)

            # 构建备份信息
            backup_info = {
                "backup_id": backup_id,
                "device_id": device_id,
                "status": BackupStatus.COMPLETED,
                "file_size": file_size,
                "received_size": file_size,
                "file_hash": file_hash,
                "calculated_hash": calculated_hash,
                "hash_valid": hash_valid,
                "description": description,
                "created_at": now,
                "updated_at": now,
                "timestamp": timestamp,
                "chunks_received": [],
                "total_chunks": 1,
                "final_file": final_file
            }

            if device_id not in self._metadata["backups"]:
                self._metadata["backups"][device_id] = []

            self._metadata["backups"][device_id].append(backup_info)
            self._save_metadata()

            logger.info(
                f"SPIFFS 直接备份完成: device={device_id}, backup={backup_id}, "
                f"size={file_size}, hash_valid={hash_valid}"
            )

            return {
                "success": True,
                "message": "备份上传成功",
                "data": backup_info
            }

        except Exception as e:
            logger.error(f"直接备份失败: {str(e)}")
            return {
                "success": False,
                "message": f"保存备份文件失败: {str(e)}"
            }

    def list_backups(self, device_id: str) -> Dict[str, Any]:
        """
        列出设备的所有备份

        Args:
            device_id: 设备 ID

        Returns:
            备份列表
        """
        # 从磁盘重新加载元数据，确保数据一致性
        self._metadata = self._load_metadata()
        backups = self._metadata["backups"].get(device_id, [])

        # 按时间倒序排列
        backups_sorted = sorted(
            backups,
            key=lambda x: x.get("timestamp", 0),
            reverse=True
        )

        # 过滤掉已删除的备份
        active_backups = [
            b for b in backups_sorted
            if b.get("status") != BackupStatus.DELETED
        ]

        return {
            "success": True,
            "message": f"设备 {device_id} 共有 {len(active_backups)} 个备份",
            "data": {
                "device_id": device_id,
                "total": len(active_backups),
                "backups": active_backups
            }
        }

    def get_backup_info(self, device_id: str, backup_id: str) -> Dict[str, Any]:
        """
        获取指定备份的详细信息

        Args:
            device_id: 设备 ID
            backup_id: 备份 ID

        Returns:
            备份详细信息
        """
        backup_info = self._find_backup(device_id, backup_id)
        if not backup_info:
            return {
                "success": False,
                "message": f"未找到备份: backup_id={backup_id}"
            }

        return {
            "success": True,
            "message": "获取备份信息成功",
            "data": backup_info
        }

    def get_backup_file_path(self, device_id: str, backup_id: str) -> Dict[str, Any]:
        """
        获取备份文件的路径（用于恢复下载）

        Args:
            device_id: 设备 ID
            backup_id: 备份 ID（可为空，表示获取最新备份）

        Returns:
            文件路径信息
        """
        # 如果没有指定 backup_id，获取最新的已完成备份
        if not backup_id:
            latest = self._get_latest_completed_backup(device_id)
            if latest:
                backup_info = latest
                backup_id = latest["backup_id"]
            else:
                return {
                    "success": False,
                    "message": f"设备 {device_id} 没有可用的备份文件"
                }
        else:
            backup_info = self._find_backup(device_id, backup_id)
            if not backup_info:
                return {
                    "success": False,
                    "message": f"未找到备份: backup_id={backup_id}"
                }

        if backup_info.get("status") != BackupStatus.COMPLETED:
            return {
                "success": False,
                "message": f"备份状态为 {backup_info.get('status')}，无法用于恢复"
            }

        final_file = backup_info.get("final_file", "")
        if not final_file or not os.path.exists(final_file):
            return {
                "success": False,
                "message": "备份文件不存在或已损坏"
            }

        return {
            "success": True,
            "message": "获取备份文件成功",
            "data": {
                "backup_id": backup_id,
                "device_id": device_id,
                "file_path": final_file,
                "file_size": backup_info.get("file_size", 0),
                "file_hash": backup_info.get("calculated_hash", ""),
                "created_at": backup_info.get("created_at", "")
            }
        }

    def delete_backup(self, device_id: str, backup_id: str) -> Dict[str, Any]:
        """
        删除指定备份

        Args:
            device_id: 设备 ID
            backup_id: 备份 ID

        Returns:
            删除结果
        """
        backup_info = self._find_backup(device_id, backup_id)
        if not backup_info:
            return {
                "success": False,
                "message": f"未找到备份: backup_id={backup_id}"
            }

        try:
            # 删除备份文件
            final_file = backup_info.get("final_file", "")
            if final_file and os.path.exists(final_file):
                os.remove(final_file)

            # 删除分块目录
            device_dir = self._get_device_backup_dir(device_id)
            backup_data_dir = os.path.join(device_dir, backup_id)
            if os.path.exists(backup_data_dir):
                import shutil
                shutil.rmtree(backup_data_dir, ignore_errors=True)

            # 更新状态
            backup_info["status"] = BackupStatus.DELETED
            backup_info["updated_at"] = datetime.now().isoformat()
            self._save_metadata()

            logger.info(f"删除备份: device={device_id}, backup={backup_id}")

            return {
                "success": True,
                "message": "备份删除成功",
                "data": {
                    "backup_id": backup_id
                }
            }

        except Exception as e:
            logger.error(f"删除备份失败: {str(e)}")
            return {
                "success": False,
                "message": f"删除失败: {str(e)}"
            }

    def _find_backup(self, device_id: str, backup_id: str) -> Optional[Dict[str, Any]]:
        """
        查找指定的备份信息
        先从内存缓存查找，未找到则从磁盘重新加载元数据后再查找

        Args:
            device_id: 设备 ID
            backup_id: 备份 ID

        Returns:
            备份信息字典，未找到返回 None
        """
        backups = self._metadata["backups"].get(device_id, [])
        for backup in backups:
            if backup.get("backup_id") == backup_id:
                return backup

        # 内存中未找到，从磁盘重新加载元数据后再查找
        logger.info(f"内存中未找到备份，从磁盘重新加载元数据: device={device_id}")
        self._metadata = self._load_metadata()
        backups = self._metadata["backups"].get(device_id, [])
        for backup in backups:
            if backup.get("backup_id") == backup_id:
                return backup

        return None

    def _get_latest_completed_backup(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取设备最新的已完成备份
        先从内存缓存查找，未找到则从磁盘重新加载元数据后再查找

        Args:
            device_id: 设备 ID

        Returns:
            最新备份信息，没有则返回 None
        """
        backups = self._metadata["backups"].get(device_id, [])
        completed = [
            b for b in backups
            if b.get("status") == BackupStatus.COMPLETED
        ]
        if completed:
            return max(
                completed,
                key=lambda x: x.get("timestamp", 0)
            )

        # 内存中未找到已完成备份，从磁盘重新加载元数据后再查找
        logger.info(f"内存中未找到已完成备份，从磁盘重新加载元数据: device={device_id}")
        self._metadata = self._load_metadata()
        backups = self._metadata["backups"].get(device_id, [])
        completed = [
            b for b in backups
            if b.get("status") == BackupStatus.COMPLETED
        ]
        if not completed:
            return None

        return max(
            completed,
            key=lambda x: x.get("timestamp", 0)
        )

    @staticmethod
    def _cleanup_chunks(backup_data_dir: str, total_chunks: int) -> None:
        """
        清理分块文件

        Args:
            backup_data_dir: 备份数据目录
            total_chunks: 总分块数
        """
        try:
            for i in range(total_chunks):
                chunk_file = os.path.join(backup_data_dir, f"chunk_{i:06d}")
                if os.path.exists(chunk_file):
                    os.remove(chunk_file)
        except Exception as e:
            logger.warning(f"清理分块文件出错（不影响主流程）: {str(e)}")
