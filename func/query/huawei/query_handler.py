"""
华为设备维保信息查询模块
完整实现华为官网的验证码获取、识别和查询逻辑
"""
import requests
import logging
import time
import re
import base64
import ddddocr
import json
from func.database import query_one, execute

logger = logging.getLogger('HuaweiQuery')


class HuaweiWarrantyQuery:
    """华为设备维保信息查询类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6285.209 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        self.portal_url = "https://app.huawei.com/escpportal"
        self.entry_url = "https://support.huawei.com/enterprise/ecareWechat?lang=zh"
        self.ocr = ddddocr.DdddOcr(show_ad=False)  # 初始化本地 OCR
        logger.info("初始化华为查询客户端")
    
    def save_to_database(self, serial_number, data):
        """
        保存数据到数据库
        
        Args:
            serial_number: 序列号
            data: 查询结果数据（互联网原始响应）
        """
        try:
            # 从原始数据中提取关键字段
            device_model = ''
            warranty_end_date = None
            
            # data 就是互联网原始响应（可能是 list 或 dict）
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                device_model = item.get('productName', '') or item.get('productModel', '') or item.get('snModel', '')
                
                # 计算最晚结束时间
                end_dates = []
                if item.get('serviceEndDate'):
                    end_dates.append(item['serviceEndDate'])
                if item.get('warrantyEndDate'):
                    end_dates.append(item['warrantyEndDate'])
                if item.get('endDate'):
                    end_dates.append(item['endDate'])
                if end_dates:
                    warranty_end_date = max(end_dates)
            elif isinstance(data, dict):
                device_model = data.get('productName', '') or data.get('productModel', '') or data.get('snModel', '')
                
                # 计算最晚结束时间
                end_dates = []
                if data.get('serviceEndDate'):
                    end_dates.append(data['serviceEndDate'])
                if data.get('warrantyEndDate'):
                    end_dates.append(data['warrantyEndDate'])
                if data.get('endDate'):
                    end_dates.append(data['endDate'])
                if end_dates:
                    warranty_end_date = max(end_dates)
            
            # 检查是否已存在该序列号的记录
            existing = query_one(
                "SELECT id FROM device_warranty_huawei WHERE serial_number = %s AND is_latest = 1",
                (serial_number,)
            )
            
            if existing:
                # 更新现有记录
                execute(
                    """
                    UPDATE device_warranty_huawei 
                    SET device_model = %s, warranty_end_date = %s, warranty_data = %s,
                        last_queried_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        device_model,
                        warranty_end_date,
                        json.dumps(data, ensure_ascii=False),
                        existing['id']
                    )
                )
                logger.info(f"华为数据已更新到数据库，ID: {existing['id']}")
            else:
                # 标记旧数据为历史版本
                execute(
                    """
                    UPDATE device_warranty_huawei 
                    SET is_latest = 0 
                    WHERE serial_number = %s AND is_latest = 1
                    """,
                    (serial_number,)
                )
                
                # 插入新数据
                new_id = execute(
                    """
                    INSERT INTO device_warranty_huawei 
                    (serial_number, device_model, warranty_end_date, warranty_data, 
                     last_queried_at, is_latest)
                    VALUES (%s, %s, %s, %s, NOW(), 1)
                    """,
                    (
                        serial_number,
                        device_model,
                        warranty_end_date,
                        json.dumps(data, ensure_ascii=False)
                    )
                )
                logger.info(f"华为数据已插入到数据库，ID: {new_id}")
            return new_id
        except Exception as e:
            logger.error(f"保存华为数据到数据库失败：{str(e)}")
            return None
    
    def query_from_database(self, serial_number):
        """
        从数据库查询数据
        
        Args:
            serial_number: 序列号
            
        Returns:
            dict: 格式化后的查询结果
        """
        try:
            result = query_one(
                """
                SELECT * FROM device_warranty_huawei 
                WHERE serial_number = %s AND is_latest = 1
                """,
                (serial_number,)
            )
            
            if result:
                # 更新最后查询时间
                execute(
                    "UPDATE device_warranty_huawei SET last_queried_at = NOW() WHERE id = %s",
                    (result['id'],)
                )
                logger.info(f"华为数据库命中：{serial_number}")
                
                # 格式化数据库记录为统一格式
                warranty_data = result.get('warranty_data')
                if isinstance(warranty_data, str):
                    try:
                        warranty_data = json.loads(warranty_data)
                    except:
                        pass
                
                # 从原始数据中提取信息
                raw_data = warranty_data
                device_model = ''
                warranty_end_date = ''
                
                # warranty_data 就是互联网原始响应（可能是 list 或 dict）
                if isinstance(warranty_data, list) and len(warranty_data) > 0:
                    item = warranty_data[0]
                    device_model = item.get('productName', '') or item.get('productModel', '') or item.get('snModel', '')
                    
                    # 计算最晚结束时间
                    end_dates = []
                    if item.get('serviceEndDate'):
                        end_dates.append(item['serviceEndDate'])
                    if item.get('warrantyEndDate'):
                        end_dates.append(item['warrantyEndDate'])
                    if item.get('endDate'):
                        end_dates.append(item['endDate'])
                    if end_dates:
                        warranty_end_date = max(end_dates)
                    
                    # 原始数据就是整个列表
                    raw_data = warranty_data
                elif isinstance(warranty_data, dict):
                    device_model = warranty_data.get('productName', '') or warranty_data.get('productModel', '') or warranty_data.get('snModel', '')
                    
                    # 计算最晚结束时间
                    end_dates = []
                    if warranty_data.get('serviceEndDate'):
                        end_dates.append(warranty_data['serviceEndDate'])
                    if warranty_data.get('warrantyEndDate'):
                        end_dates.append(warranty_data['warrantyEndDate'])
                    if warranty_data.get('endDate'):
                        end_dates.append(warranty_data['endDate'])
                    if end_dates:
                        warranty_end_date = max(end_dates)
                    
                    # 原始数据就是整个 dict
                    raw_data = warranty_data
                else:
                    # 兼容旧格式
                    device_model = result.get('device_model', '')
                    warranty_end_date = result.get('warranty_end_date', '')
                
                # 构建统一的 data 格式
                formatted_data = {
                    "序列号": result.get('serial_number', ''),
                    "设备型号": device_model,
                    "最晚维保日期": warranty_end_date,
                    "详细维保信息": raw_data
                }
                
                return formatted_data
            else:
                logger.info(f"华为数据库未命中：{serial_number}")
                return None
        except Exception as e:
            logger.error(f"从数据库查询华为数据失败：{str(e)}")
            return None
    
    def query(self, serial_number, captcha_code=None, force_refresh=False):
        """
        查询设备维保信息
        
        Args:
            serial_number: 设备序列号
            captcha_code: 验证码（可选，如果不传则自动获取）
            force_refresh: 是否强制刷新
            
        Returns:
            dict: 查询结果
        """
        logger.info(f"开始查询华为设备：{serial_number}")
        
        # 优先查询数据库（除非强制刷新）
        if not force_refresh:
            db_result = self.query_from_database(serial_number)
            if db_result:
                return {
                    'success': 1,
                    'data': [db_result],
                    'source': 'database',
                    'vendor': 'huawei'
                }
        
        try:
            # 如果没有提供验证码，自动获取和识别
            if not captcha_code:
                # 获取验证码
                captcha_image = self.get_captcha()
                if not captcha_image:
                    return {
                        'success': 0,
                        'message': '获取验证码失败'
                    }
                
                # 识别验证码
                captcha_code = self.recognize_captcha(captcha_image)
                if not captcha_code:
                    return {
                        'success': 0,
                        'message': '验证码识别失败'
                    }
            
            # 查询维保信息
            result_text = self.query_warranty(serial_number, captcha_code)
            
            if result_text:
                try:
                    result_data = json.loads(result_text)
                    
                    # 保存到数据库：保存原始数据（不做任何包装，直接保存互联网响应）
                    self.save_to_database(serial_number, result_data)
                    
                    # 从数据库读取格式化后的数据返回
                    db_result = self.query_from_database(serial_number)
                    if db_result:
                        return {
                            'success': 1,
                            'data': [db_result],
                            'source': 'internet',
                            'vendor': 'huawei'
                        }
                    
                    # 如果数据库读取失败，返回错误
                    return {
                        'success': 0,
                        'message': '保存数据后读取失败'
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"解析华为响应失败：{str(e)}")
                    return {
                        'success': 0,
                        'message': f'解析响应失败：{str(e)}'
                    }
            else:
                return {
                    'success': 0,
                    'message': '查询失败'
                }
        except Exception as e:
            logger.error(f"查询华为设备异常：{str(e)}")
            return {
                'success': 0,
                'message': f'查询异常：{str(e)}'
            }
    
    def get_captcha(self):
        """获取验证码"""
        try:
            # 首先访问入口页面获取初始 cookie
            logger.info("访问华为入口页面获取 cookie")
            self.session.get(self.entry_url, headers=self.headers, timeout=10)
            
            # 生成随机时间戳
            timestamp = int(time.time() * 1000)
            captcha_url = f"{self.portal_url}/servlet/captcha?yzm={timestamp}"
            
            # 获取验证码图片
            captcha_headers = self.headers.copy()
            captcha_headers["Referer"] = "https://app.huawei.com/escpportal/pub/wechat.html?Language=CN"
            captcha_headers["X-Requested-With"] = "XMLHttpRequest"
            
            logger.info(f"获取华为验证码：{captcha_url}")
            response = self.session.get(captcha_url, headers=captcha_headers, timeout=10)
            
            if response.status_code == 200:
                # 保存验证码图片到临时目录
                captcha_path = '/tmp/huawei_captcha.jpg'
                with open(captcha_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"已保存华为验证码图片到 {captcha_path}")
                return response.content
            else:
                logger.error(f"获取华为验证码失败，状态码：{response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取华为验证码异常：{str(e)}")
            return None
    
    def recognize_captcha(self, captcha_image):
        """使用本地 ddddocr 识别验证码"""
        try:
            logger.info("使用本地 ddddocr 识别华为验证码")
            
            # 使用 ddddocr 识别验证码
            result = self.ocr.classification(captcha_image)
            
            # 清理和处理响应结果
            captcha_text = result.strip().upper()
            # 清理返回结果，只保留字母和数字
            captcha_text = re.sub(r'[^A-Z0-9]', '', captcha_text)
            
            logger.info(f"华为验证码识别结果：{captcha_text}")
            
            # 验证验证码长度
            if len(captcha_text) > 0:
                logger.info("华为验证码识别成功")
                return captcha_text
            else:
                logger.warning(f"华为验证码识别结果为空：{captcha_text}")
                return ""
        except Exception as e:
            logger.error(f"识别华为验证码异常：{str(e)}")
            return ""
    
    def validate_captcha(self, captcha_code):
        """验证验证码"""
        try:
            validate_url = f"{self.portal_url}/servlet/captchaValidate"
            validate_headers = self.headers.copy()
            validate_headers["Host"] = "app.huawei.com"
            validate_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            validate_headers["X-Requested-With"] = "XMLHttpRequest"
            validate_headers["Referer"] = "https://app.huawei.com/escpportal/pub/wechat.html?Language=CN"
            validate_headers["Sec-Fetch-Site"] = "same-origin"
            validate_headers["Sec-Fetch-Mode"] = "cors"
            validate_headers["Sec-Fetch-Dest"] = "empty"
            validate_headers["Pragma"] = "no-cache"
            validate_headers["Cache-Control"] = "no-cache"
            
            data = f"paramCode={captcha_code}"
            logger.info(f"验证华为验证码：{captcha_code}")
            response = self.session.post(validate_url, headers=validate_headers, data=data, timeout=10)
            
            if response.status_code == 200 and response.text.strip() == "yes":
                logger.info("华为验证码验证成功")
                return True
            else:
                logger.error(f"华为验证码验证失败，响应：{response.text}")
                return False
        except Exception as e:
            logger.error(f"验证华为验证码异常：{str(e)}")
            return False
    
    def query_warranty(self, serial_number, captcha_code):
        """查询设备维保信息"""
        try:
            # 首先验证验证码
            if not self.validate_captcha(captcha_code):
                logger.error("验证码验证失败，无法查询维保信息")
                return None
            
            # 构建查询 URL
            timestamp = int(time.time())
            query_url = f"{self.portal_url}/services/portal/vyborgTask/findHardWareVyborgForWeb"
            query_params = {
                "barcode": serial_number,
                "language": "cn",
                "source": "escp",
                "userIp": "",
                "buType": "1",
                "paramCode": captcha_code,
                "_": timestamp
            }
            
            # 构建请求头
            query_headers = self.headers.copy()
            query_headers["Host"] = "app.huawei.com"
            query_headers["Content-Type"] = "application/json"
            query_headers["X-Requested-With"] = "XMLHttpRequest"
            query_headers["Referer"] = "https://app.huawei.com/escpportal/pub/wechat.html?Language=CN"
            query_headers["Sec-Fetch-Site"] = "same-origin"
            query_headers["Sec-Fetch-Mode"] = "cors"
            query_headers["Sec-Fetch-Dest"] = "empty"
            query_headers["Pragma"] = "no-cache"
            query_headers["Cache-Control"] = "no-cache"
            
            # 发送查询请求
            logger.info(f"查询华为设备维保信息：{serial_number}")
            response = self.session.get(query_url, headers=query_headers, params=query_params, timeout=15)
            
            if response.status_code == 200:
                logger.info("查询华为设备维保信息成功")
                return response.text
            else:
                logger.error(f"查询华为设备维保信息失败，状态码：{response.status_code}")
                return None
        except Exception as e:
            logger.error(f"查询华为设备维保信息异常：{str(e)}")
            return None
    
    def parse_result(self, result_data):
        """
        解析华为查询结果
        
        Args:
            result_data: 原始查询结果
            
        Returns:
            dict: 解析后的结果
        """
        try:
            if not result_data:
                return {'success': 0, 'message': '查询结果为空'}
            
            # 华为返回的数据结构可能是字典或列表
            if isinstance(result_data, list) and len(result_data) > 0:
                data = result_data[0]
            elif isinstance(result_data, dict):
                data = result_data
            else:
                return {'success': 0, 'message': '数据格式异常'}
            
            # 提取关键字段
            parsed_data = {
                '序列号': data.get('barCode', ''),
                '产品型号': data.get('productModel', ''),
                '设备型号': data.get('productName', ''),
                '服务截止日期': data.get('serviceEndDate', ''),
                '维保截止日期': data.get('warrantyEndDate', ''),
                '服务状态': data.get('serviceStatus', ''),
                '维保状态': data.get('warrantyStatus', ''),
                '原始数据': data
            }
            
            return {
                'success': 1,
                'data': [parsed_data]
            }
        except Exception as e:
            logger.error(f"解析华为结果失败：{str(e)}")
            return {'success': 0, 'message': f'解析失败：{str(e)}'}
