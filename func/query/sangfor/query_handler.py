"""
深信服设备序列号查询模块
"""
import logging
import time
import json
from func.captcha.sangfor.captcha_handler import SangforCaptchaHandler
from func.database import query_one, execute

logger = logging.getLogger('QuerySangfor')


class SangforQueryService:
    """深信服查询服务类"""
    
    def __init__(self, session, username=None, password=None):
        """
        初始化查询服务
        
        Args:
            session: requests Session 对象
            username: 用户名（可选）
            password: 密码（可选）
        """
        self.session = session
        self.username = username
        self.password = password
        self.query_url = "https://bbs.sangfor.com.cn/plugin.php%sid=service:query"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        self.captcha_handler = SangforCaptchaHandler(session)
        logger.info("初始化深信服查询服务")
    
    def save_to_database(self, query_value, data):
        """
        保存数据到数据库
        
        Args:
            query_value: 用户查询的值（可能是序列号或网关ID）
            data: 查询结果数据（互联网原始响应的 data 字段，是一个数组）
        """
        try:
            # 从原始数据中提取关键字段
            device_model = ''
            gateway_id = ''
            actual_serial = ''  # API返回的实际序列号
            warranty_end_date = None
            
            # data 是互联网原始响应的 data 字段（数组）
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                actual_serial = item.get("序列号", "") or item.get("rnum", "")
                gateway_id = item.get("网关 id", "") or item.get("rid", "")
                device_model = item.get("设备型号", "") or item.get("pdName", "")
                
                # 计算最晚结束时间
                end_dates = []
                if item.get("网络远程支持有效期") or item.get("cti_day2_800"):
                    end_dates.append(item.get("网络远程支持有效期", "") or item["cti_day2_800"])
                if item.get("同等功能软件升级有效期") or item.get("cti_day2_up"):
                    end_dates.append(item.get("同等功能软件升级有效期", "") or item["cti_day2_up"])
                if item.get("硬件维保有效期") or item.get("cit_day_rb"):
                    end_dates.append(item.get("硬件维保有效期", "") or item["cit_day_rb"])
                if end_dates:
                    warranty_end_date = max(end_dates)
            
            # 使用API返回的实际序列号，如果为空则使用用户查询的值
            final_serial = actual_serial if actual_serial else query_value
            
            # 检查是否已存在该序列号或网关ID的记录
            existing = query_one(
                "SELECT id FROM device_warranty_sangfor WHERE (serial_number = %s OR gateway_id = %s) AND is_latest = 1",
                (final_serial, gateway_id)
            )
            
            if existing:
                # 更新现有记录
                execute(
                    """
                    UPDATE device_warranty_sangfor 
                    SET serial_number = %s, gateway_id = %s, device_model = %s, warranty_end_date = %s, warranty_data = %s,
                        last_queried_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        final_serial,
                        gateway_id,
                        device_model,
                        warranty_end_date,
                        json.dumps(data, ensure_ascii=False),
                        existing['id']
                    )
                )
                logger.info(f"深信服数据已更新到数据库，ID: {existing['id']}")
            else:
                # 标记旧数据为历史版本（同时检查序列号和网关ID）
                execute(
                    """
                    UPDATE device_warranty_sangfor 
                    SET is_latest = 0 
                    WHERE (serial_number = %s OR gateway_id = %s) AND is_latest = 1
                    """,
                    (final_serial, gateway_id)
                )
                
                # 插入新数据
                new_id = execute(
                    """
                    INSERT INTO device_warranty_sangfor 
                    (serial_number, gateway_id, device_model, warranty_end_date, warranty_data, 
                     last_queried_at, is_latest)
                    VALUES (%s, %s, %s, %s, %s, NOW(), 1)
                    """,
                    (
                        final_serial,
                        gateway_id,
                        device_model,
                        warranty_end_date,
                        json.dumps(data, ensure_ascii=False)
                    )
                )
                logger.info(f"深信服数据已插入到数据库，ID: {new_id}")
            return new_id
        except Exception as e:
            logger.error(f"保存深信服数据到数据库失败：{str(e)}")
            return None
    
    def query_from_database(self, query_value):
        """
        从数据库查询数据（支持序列号和网关ID两种方式）
        
        Args:
            query_value: 序列号或网关ID
            
        Returns:
            dict: 格式化后的查询结果
        """
        try:
            # 先尝试通过 serial_number 查询
            result = query_one(
                """
                SELECT * FROM device_warranty_sangfor 
                WHERE serial_number = %s AND is_latest = 1
                """,
                (query_value,)
            )
            
            # 如果没找到，尝试通过 gateway_id 查询
            if not result:
                result = query_one(
                    """
                    SELECT * FROM device_warranty_sangfor 
                    WHERE gateway_id = %s AND is_latest = 1
                    """,
                    (query_value,)
                )
            
            if result:
                # 更新最后查询时间
                execute(
                    "UPDATE device_warranty_sangfor SET last_queried_at = NOW() WHERE id = %s",
                    (result['id'],)
                )
                logger.info(f"深信服数据库命中：{query_value}")
                
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
                gateway_id = ''
                warranty_end_date = ''
                
                # warranty_data 就是互联网原始响应（包含 success 和 data）
                if isinstance(warranty_data, dict) and warranty_data.get("success") == 1 and warranty_data.get("data"):
                    data_list = warranty_data["data"]
                    if isinstance(data_list, list) and len(data_list) > 0:
                        item = data_list[0]
                        gateway_id = item.get("网关 id", "") or item.get("rid", "")
                        device_model = item.get("设备型号", "") or item.get("pdName", "")
                        
                        # 计算最晚结束时间
                        end_dates = []
                        if item.get("网络远程支持有效期") or item.get("cti_day2_800"):
                            end_dates.append(item.get("网络远程支持有效期", "") or item["cti_day2_800"])
                        if item.get("同等功能软件升级有效期") or item.get("cti_day2_up"):
                            end_dates.append(item.get("同等功能软件升级有效期", "") or item["cti_day2_up"])
                        if item.get("硬件维保有效期") or item.get("cit_day_rb"):
                            end_dates.append(item.get("硬件维保有效期", "") or item["cit_day_rb"])
                        if end_dates:
                            warranty_end_date = max(end_dates)
                        
                        # 原始数据只保存 data 字段的内容（数组）
                        raw_data = data_list
                else:
                    # 兼容旧格式
                    device_model = result.get('device_model', '')
                    gateway_id = result.get('gateway_id', '')
                    warranty_end_date = result.get('warranty_end_date', '')
                
                # 使用从原始数据中提取的序列号，如果为空则使用数据库中的序列号
                final_serial = result.get('serial_number', '')
                if 'item' in dir() and item:
                    api_serial = item.get("序列号", "") or item.get("rnum", "")
                    if api_serial:
                        final_serial = api_serial
                
                # 构建统一的 data 格式
                formatted_data = {
                    "序列号": final_serial,
                    "设备型号": device_model,
                    "最晚维保日期": warranty_end_date,
                    "详细维保信息": raw_data
                }
                
                return formatted_data
            else:
                logger.info(f"深信服数据库未命中：{query_value}")
                return None
        except Exception as e:
            logger.error(f"从数据库查询深信服数据失败：{str(e)}")
            return None
    
    def query(self, serial_number, max_retries=5, force_refresh=False):
        """
        查询设备序列号
        
        Args:
            serial_number: 设备序列号
            max_retries: 最大重试次数
            force_refresh: 是否强制刷新
            
        Returns:
            dict: 查询结果
        """
        logger.info(f"开始查询深信服设备：{serial_number}")
        
        # 优先查询数据库（除非强制刷新）
        if not force_refresh:
            db_result = self.query_from_database(serial_number)
            if db_result:
                return {
                    'success': 1,
                    'data': [db_result],
                    'source': 'database',
                    'vendor': 'sangfor'
                }
        
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 1. 访问服务查询页面，获取初始内容
                logger.info(f"访问服务查询页面 (尝试 {retry_count + 1}/{max_retries})")
                query_page_response = self.session.get(self.query_url, headers=self.headers, timeout=15)
                query_page_response.encoding = "utf-8"
                
                if query_page_response.status_code != 200:
                    logger.error(f"访问服务查询页面失败，状态码：{query_page_response.status_code}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(retry_count)
                    continue
                
                # 2. 获取验证码
                logger.info("获取验证码")
                captcha_text, idhash = self.captcha_handler.get_captcha(self.query_url)
                
                if not captcha_text:
                    logger.warning("获取验证码失败")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(retry_count)
                    continue
                
                # 3. 构建查询请求
                logger.info("构建查询请求")
                query_url = (
                    f"https://bbs.sangfor.com.cn/plugin.php?id=service:query"
                    f"&op=doquery&type=svrstate&seccodeverify={captcha_text}"
                    f"&seccodehash={idhash}&seccodemodid=plugin::service&svrid={serial_number}"
                )
                
                request_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6285.209 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://bbs.sangfor.com.cn",
                    "Referer": "https://bbs.sangfor.com.cn/plugin.php%sid=service:query",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                    "Pragma": "no-cache",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
                
                query_data = "ajaxdata=json"
                
                # 4. 发送查询请求
                logger.info("发送服务查询请求")
                service_response = self.session.post(
                    query_url,
                    headers=request_headers,
                    data=query_data,
                    timeout=15,
                    allow_redirects=False
                )
                service_response.encoding = "utf-8"
                
                logger.info(f"查询响应状态码：{service_response.status_code}")
                
                # 5. 检查响应
                if service_response.status_code != 200:
                    logger.error(f"查询服务信息失败，状态码：{service_response.status_code}")
                    
                    # 如果是 301 或 302 重定向，可能是 session 失效
                    if service_response.status_code in [301, 302]:
                        logger.warning("收到重定向响应，可能是 session 已失效")
                        return {
                            'success': 0,
                            'message': 'session 已失效',
                            'source': 'api',
                            'vendor': 'sangfor'
                        }
                    
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(retry_count)
                    continue
                
                # 6. 解析结果
                result = self.parse_result(service_response.text)
                
                # 7. 检查是否需要重试
                if result.get("success") == -2:
                    logger.warning("服务查询失败：验证码错误，准备重试")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(retry_count)
                    continue
                
                # 8. 保存到数据库：保存原始数据（不做任何包装，只保存 data 字段内容）
                if result.get("success") == 1 and result.get("data"):
                    # 只保存 data 字段的内容（数组）
                    self.save_to_database(serial_number, result["data"])
                
                # 从数据库读取格式化后的数据返回
                db_result = self.query_from_database(serial_number)
                if db_result:
                    return {
                        'success': 1,
                        'data': [db_result],
                        'source': 'internet',
                        'vendor': 'sangfor'
                    }
                
                # 如果数据库读取失败，返回原始结果
                return result
                
            except Exception as e:
                logger.error(f"查询服务信息异常：{str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(retry_count)
                else:
                    return {
                        "success": 0,
                        "message": f"查询异常：{str(e)}"
                    }
        
        return {
            "success": 0,
            "message": "查询失败：已达到最大重试次数"
        }
    
    def parse_result(self, response_text):
        """
        解析查询结果
        
        Args:
            response_text: 响应文本
            
        Returns:
            dict: 解析后的结果
        """
        logger.info("解析查询结果")
        
        try:
            result = json.loads(response_text)
            
            # 检查是否是验证码错误
            if result.get("success") == -2:
                return {"success": -2, "message": "验证码错误"}
            
            # 检查是否是 session 失效
            if "您必须先登录后才能进行相关操作" in response_text:
                return {"success": 0, "message": "session 已失效"}
            
            # 解析服务查询成功的响应结果
            if "data" in result and isinstance(result["data"], list):
                # 处理 data 数组中的每个元素
                parsed_data = []
                for item in result["data"]:
                    parsed_item = {
                        "序列号": item.get("rnum", ""),
                        "网关 id": item.get("rid", ""),
                        "设备型号": item.get("pdName", ""),
                        "服务商名称": item.get("cti_channame", ""),
                        "服务电话": item.get("cit_chanphone", ""),
                        "网络远程支持有效期": item.get("cti_day2_800", ""),
                        "同等功能软件升级有效期": item.get("cti_day2_up", ""),
                        "硬件维保有效期": item.get("cit_day_rb", "")
                    }
                    parsed_data.append(parsed_item)
                
                return {
                    "success": 1,
                    "data": parsed_data
                }
            else:
                return result
                
        except json.JSONDecodeError as e:
            logger.error(f"解析 JSON 失败：{str(e)}")
            return {
                "success": 0,
                "message": f"解析 JSON 失败：{str(e)}"
            }
