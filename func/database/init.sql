-- 创建数据库
CREATE DATABASE IF NOT EXISTS device_warranty DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE device_warranty;

-- 创建深信服设备维保表
CREATE TABLE IF NOT EXISTS device_warranty_sangfor (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键 ID',
    serial_number VARCHAR(100) NOT NULL COMMENT '设备序列号',
    gateway_id VARCHAR(100) COMMENT '网关 ID',
    device_model VARCHAR(200) COMMENT '设备型号',
    warranty_end_date DATE COMMENT '最晚结束日期',
    warranty_data JSON COMMENT '完整维保信息 (JSON 格式)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    last_queried_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后查询时间',
    is_latest TINYINT NOT NULL DEFAULT 1 COMMENT '是否最新版本：1-是，0-历史版本',
    
    UNIQUE KEY uk_serial_latest (serial_number, is_latest),
    KEY idx_serial (serial_number),
    KEY idx_gateway_id (gateway_id),
    KEY idx_warranty_end (warranty_end_date),
    KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='深信服设备维保信息表';

-- 创建华为设备维保表
CREATE TABLE IF NOT EXISTS device_warranty_huawei (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键 ID',
    serial_number VARCHAR(100) NOT NULL COMMENT '设备序列号',
    device_model VARCHAR(200) COMMENT '设备型号',
    warranty_end_date DATE COMMENT '最晚结束日期',
    warranty_data JSON COMMENT '完整维保信息 (JSON 格式)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    last_queried_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后查询时间',
    is_latest TINYINT NOT NULL DEFAULT 1 COMMENT '是否最新版本：1-是，0-历史版本',
    
    UNIQUE KEY uk_serial_latest (serial_number, is_latest),
    KEY idx_serial (serial_number),
    KEY idx_warranty_end (warranty_end_date),
    KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='华为设备维保信息表';

-- 创建联想设备维保表
CREATE TABLE IF NOT EXISTS device_warranty_lenovo (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键 ID',
    serial_number VARCHAR(100) NOT NULL COMMENT '设备序列号',
    device_model VARCHAR(200) COMMENT '设备型号',
    warranty_end_date DATE COMMENT '最晚结束日期',
    warranty_data JSON COMMENT '完整维保信息 (JSON 格式)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    last_queried_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后查询时间',
    is_latest TINYINT NOT NULL DEFAULT 1 COMMENT '是否最新版本：1-是，0-历史版本',
    
    UNIQUE KEY uk_serial_latest (serial_number, is_latest),
    KEY idx_serial (serial_number),
    KEY idx_warranty_end (warranty_end_date),
    KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='联想设备维保信息表';
