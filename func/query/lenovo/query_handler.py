"""
联想设备序列号查询模块
"""
import requests
import logging
import json
import re
from bs4 import BeautifulSoup
from func.database import query_one, execute

logger = logging.getLogger('QueryLenovo')


class LenovoQueryService:
    """联想查询服务类"""
    
    def __init__(self, session=None):
        """
        初始化查询服务
        
        Args:
            session: requests Session 对象（可选）
        """
        self.session = session or requests.Session()
        self.entry_url = "https://datacentersupport.lenovo.com/cn/zc"
        self.api_url = "https://datacentersupport.lenovo.com/cn/zc/api/v4/mse/v2/getproducts"
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6285.209 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Origin": "https://datacentersupport.lenovo.com",
            "Referer": "https://datacentersupport.lenovo.com/cn/zc",
            "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="125", "Google Chrome";v="125"',
            "Sec-Ch-Ua-Mobile": "%s0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        logger.info("初始化联想查询服务")
    
    def save_to_database(self, serial_number, data):
        """
        保存数据到数据库
        
        Args:
            serial_number: 序列号
            data: 查询结果数据（互联网原始响应，包含 product_info 和 warranty_info）
        """
        try:
            # 从原始数据中提取关键字段
            device_model = ''
            warranty_end_date = None
            
            # data 就是互联网原始响应（包含 product_info 和 warranty_info）
            if isinstance(data, dict):
                product_info = data.get('product_info', [])
                warranty_info = data.get('warranty_info', {})
                
                # 从 product_info 提取设备型号
                if isinstance(product_info, list) and len(product_info) > 0:
                    product = product_info[0]
                    device_model = product.get('Name', '')
                
                # 从 warranty_info 提取最晚结束时间
                if isinstance(warranty_info, dict):
                    latest_end = None
                    
                    # 检查 BaseWarranties
                    for w in warranty_info.get('BaseWarranties', []):
                        end_date = w.get('End', '')
                        if end_date and end_date != 'N/A':
                            if latest_end is None or end_date > latest_end:
                                latest_end = end_date
                    
                    # 检查 UpmaWarranties
                    for w in warranty_info.get('UpmaWarranties', []):
                        end_date = w.get('End', '')
                        if end_date and end_date != 'N/A':
                            if latest_end is None or end_date > latest_end:
                                latest_end = end_date
                    
                    # 检查 AodWarranties
                    for w in warranty_info.get('AodWarranties', []):
                        end_date = w.get('EndDate', '')
                        if end_date and end_date != 'N/A':
                            if latest_end is None or end_date > latest_end:
                                latest_end = end_date
                    
                    warranty_end_date = latest_end
            
            # 标记旧数据为历史版本
            execute(
                """
                UPDATE device_warranty_lenovo 
                SET is_latest = 0 
                WHERE serial_number = %s AND is_latest = 1
                """,
                (serial_number,)
            )
            
            # 检查是否已存在该序列号的记录
            existing = query_one(
                "SELECT id FROM device_warranty_lenovo WHERE serial_number = %s AND is_latest = 1",
                (serial_number,)
            )
            
            if existing:
                # 更新现有记录
                execute(
                    """
                    UPDATE device_warranty_lenovo 
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
                logger.info(f"联想数据已更新到数据库，ID: {existing['id']}")
            else:
                # 插入新数据
                new_id = execute(
                    """
                    INSERT INTO device_warranty_lenovo 
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
                logger.info(f"联想数据已插入到数据库，ID: {new_id}")
            return new_id
        except Exception as e:
            logger.error(f"保存联想数据到数据库失败：{str(e)}")
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
                SELECT * FROM device_warranty_lenovo 
                WHERE serial_number = %s AND is_latest = 1
                """,
                (serial_number,)
            )
            
            if result:
                # 更新最后查询时间
                execute(
                    "UPDATE device_warranty_lenovo SET last_queried_at = NOW() WHERE id = %s",
                    (result['id'],)
                )
                logger.info(f"联想数据库命中：{serial_number}")
                
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
                
                # warranty_data 就是互联网原始响应（包含 product_info 和 warranty_info）
                if isinstance(warranty_data, dict) and 'product_info' in warranty_data and 'warranty_info' in warranty_data:
                    product_info = warranty_data.get('product_info', [])
                    warranty_info = warranty_data.get('warranty_info', {})
                    
                    # 提取设备型号
                    if isinstance(product_info, list) and len(product_info) > 0:
                        device_model = product_info[0].get('Name', '')
                    
                    # 提取最晚结束时间
                    latest_end = None
                    for w in warranty_info.get('BaseWarranties', []):
                        end_date = w.get('End', '')
                        if end_date and end_date != 'N/A':
                            if latest_end is None or end_date > latest_end:
                                latest_end = end_date
                    
                    for w in warranty_info.get('UpmaWarranties', []):
                        end_date = w.get('End', '')
                        if end_date and end_date != 'N/A':
                            if latest_end is None or end_date > latest_end:
                                latest_end = end_date
                    
                    for w in warranty_info.get('AodWarranties', []):
                        end_date = w.get('EndDate', '')
                        if end_date and end_date != 'N/A':
                            if latest_end is None or end_date > latest_end:
                                latest_end = end_date
                    
                    warranty_end_date = latest_end or ''
                    
                    # 原始数据就是 warranty_data 本身
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
                logger.info(f"联想数据库未命中：{serial_number}")
                return None
        except Exception as e:
            logger.error(f"从数据库查询联想数据失败：{str(e)}")
            return None
    
    def get_csrf_token(self):
        """获取 CSRF Token"""
        try:
            response = self.session.get(self.entry_url, headers=self.base_headers, timeout=10)
            if response.status_code == 200:
                # 从 Cookie 中获取 CSRF token
                csrf_token = self.session.cookies.get('X-Csrf-Token', '')
                if not csrf_token:
                    # 尝试从页面中提取
                    match = re.search(r'X-Csrf-Token[=:]\s*["\']([a-zA-Z0-9+/=]+)["\']', response.text)
                    if match:
                        csrf_token = match.group(1)
                
                logger.info(f"获取到 CSRF Token: {csrf_token[:20]}..." if csrf_token else "未获取到 CSRF Token")
                return csrf_token
            else:
                logger.error(f"获取 CSRF Token 失败，状态码：{response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取 CSRF Token 异常：{str(e)}")
            return None
    
    def get_product_info(self, serial_number):
        """获取产品信息"""
        try:
            # 准备请求数据
            payload = {"productId": serial_number}
            
            # 获取 CSRF Token
            csrf_token = self.get_csrf_token()
            
            # 设置请求头
            headers = self.base_headers.copy()
            if csrf_token:
                headers["X-Csrf-Token"] = csrf_token
                headers["X-Requested-With"] = "XMLHttpRequest"
            
            # 发送 POST 请求
            response = self.session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"获取产品信息成功：{result}")
                return result
            else:
                logger.error(f"获取产品信息失败，状态码：{response.status_code}, 响应：{response.text}")
                return None
        except Exception as e:
            logger.error(f"获取产品信息异常：{str(e)}")
            return None
    
    def get_warranty_details(self, product_url):
        """获取维保详情（从产品页面提取）"""
        try:
            logger.info(f"访问产品页面：{product_url}")
            response = self.session.get(product_url, headers=self.base_headers, timeout=15)
            if response.status_code == 200:
                # 保存页面用于调试
                with open('/tmp/lenovo_product_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.info("已保存产品页面到 /tmp/lenovo_product_page.html")
                
                # 优先尝试提取 ds_warranties 对象（包含完整时间信息）
                # 注意：实际格式是 "var ds_warranties = window.ds_warranties || {...}"
                ds_match = re.search(r'var\s+ds_warranties\s*=\s*window\.ds_warranties\s*\|\|\s*({.*?});', response.text, re.DOTALL)
                if ds_match:
                    warranty_data = json.loads(ds_match.group(1))
                    logger.info(f"获取到 ds_warranties 数据")
                    return warranty_data
                
                # 如果没有 ds_warranties，尝试从 lmd 对象中提取保修信息
                # 注意：实际格式是 "var lmd = window.lmd || {...}"
                lmd_match = re.search(r'var\s+lmd\s*=\s*window\.lmd\s*\|\|\s*({.*?});', response.text, re.DOTALL)
                if lmd_match:
                    lmd_data = json.loads(lmd_match.group(1))
                    logger.info(f"获取到 lmd 数据（无时间信息）")
                    
                    # 提取保修信息（lmd 对象直接包含 warrantyInsights 字段）
                    warranty_insights = lmd_data.get("warrantyInsights", "")
                    
                    if warranty_insights:
                        logger.info(f"从 lmd 中获取到保修信息：{warranty_insights}")
                        # 解析保修信息，格式如："服务 1|NA, 服务 2|NA"
                        warranty_list = []
                        for item in warranty_insights.split(','):
                            parts = item.split('|')
                            if len(parts) >= 1:
                                warranty_list.append({
                                    "服务名称": parts[0].strip(),
                                    "状态": parts[1].strip() if len(parts) > 1 else "Unknown"
                                })
                        
                        return {"warrantyInsights": warranty_list}
                    else:
                        logger.warning("lmd 对象中没有 warrantyInsights 字段")
                
                logger.warning("未找到任何保修数据")
                return None
            else:
                logger.error(f"获取产品详情页失败，状态码：{response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取维保详情异常：{str(e)}")
            return None
    
    def query(self, serial_number, force_refresh=False):
        """
        查询设备序列号
        
        Args:
            serial_number: 设备序列号
            force_refresh: 是否强制刷新
            
        Returns:
            dict: 查询结果
        """
        logger.info(f"开始查询联想设备：{serial_number}")
        
        # 优先查询数据库（除非强制刷新）
        if not force_refresh:
            db_result = self.query_from_database(serial_number)
            if db_result:
                return {
                    'success': 1,
                    'data': [db_result],
                    'source': 'database',
                    'vendor': 'lenovo'
                }
        
        try:
            # 第一步：获取产品信息
            product_info = self.get_product_info(serial_number)
            
            if not product_info or len(product_info) == 0:
                logger.warning(f"未找到产品信息：{serial_number}")
                return {
                    "success": 0,
                    "message": "未找到产品信息，请检查序列号是否正确"
                }
            
            # 解析产品信息
            product = product_info[0]
            product_id = product.get("Id", "")
            product_name = product.get("Name", "")
            serial = product.get("Serial", "")
            machine_type = product.get("MachineType", "")
            
            logger.info(f"产品信息：{product_name}, 序列号：{serial}")
            
            # 第二步：获取维保信息
            # 构建产品详情 URL
            if product_id:
                # 从 ID 构建 URL: SERVERS/THINKSYSTEM/SR650V2/7Z73/7Z73CTO1WW/J901ELMC
                # -> /cn/zc/products/servers/thinksystem/sr650v2/7z73/7z73cto1ww/j901elmc
                url_path = product_id.lower().replace('/', '/')
                product_url = f"{self.entry_url}/products/{url_path}"
                
                warranty_info = self.get_warranty_details(product_url)
                
                if warranty_info:
                    # 解析维保信息
                    warranty_details = []
                    earliest_start = None
                    latest_end = None
                    
                    # 检查是否包含 warrantyInsights（从 lmd 对象提取）
                    if "warrantyInsights" in warranty_info:
                        # 注意：lmd 对象中的 warrantyInsights 没有时间信息，只有服务名称和状态
                        # 这里我们返回原始数据，但标记为无时间信息
                        for w in warranty_info["warrantyInsights"]:
                            warranty_item = {
                                "保修名称": w.get("服务名称", ""),
                                "开始日期": "N/A",
                                "结束日期": "N/A",
                                "状态": w.get("状态", "")
                            }
                            warranty_details.append(warranty_item)
                    else:
                        # 提取 BaseWarranties (基础保修)
                        base_warranties = warranty_info.get("BaseWarranties", [])
                        for w in base_warranties:
                            start_date = w.get("Start", "")
                            end_date = w.get("End", "")
                            
                            # 更新最早开始时间和最晚结束时间
                            if start_date and start_date != "N/A":
                                if earliest_start is None or start_date < earliest_start:
                                    earliest_start = start_date
                            if end_date and end_date != "N/A":
                                if latest_end is None or end_date > latest_end:
                                    latest_end = end_date
                            
                            warranty_item = {
                                "保修名称": w.get("Name", ""),
                                "开始日期": start_date,
                                "结束日期": end_date,
                                "状态": "Active" if w.get("Status") == 1 else "Expired",
                                "保修类型": w.get("WarrentyType", ""),
                                "描述": w.get("Description", ""),
                                "国家": w.get("CountryName", ""),
                                "渠道": w.get("Channel", ""),
                                "来源": w.get("Origin", ""),
                                "POP 日期": w.get("POPDate", ""),
                                "分类": w.get("Category", ""),
                                "交付类型": w.get("DeliveryType", ""),
                                "持续时间": w.get("Duration", 0),
                                "是否 Premier": w.get("IsPremier", False),
                                "类型": w.get("Type", ""),
                                "排序权重": w.get("SortWeight", 0)
                            }
                            warranty_details.append(warranty_item)
                        
                        # 提取 UpmaWarranties (升级保修)
                        upma_warranties = warranty_info.get("UpmaWarranties", [])
                        for w in upma_warranties:
                            start_date = w.get("Start", "")
                            end_date = w.get("End", "")
                            
                            if start_date and start_date != "N/A":
                                if earliest_start is None or start_date < earliest_start:
                                    earliest_start = start_date
                            if end_date and end_date != "N/A":
                                if latest_end is None or end_date > latest_end:
                                    latest_end = end_date
                            
                            warranty_item = {
                                "保修名称": w.get("Name", ""),
                                "开始日期": start_date,
                                "结束日期": end_date,
                                "状态": "Active" if w.get("Status") == 1 else "Expired",
                                "保修类型": w.get("WarrentyType", ""),
                                "描述": w.get("Description", ""),
                                "国家": w.get("CountryName", ""),
                                "渠道": w.get("Channel", ""),
                                "来源": w.get("Origin", ""),
                                "POP 日期": w.get("POPDate", ""),
                                "分类": w.get("Category", ""),
                                "交付类型": w.get("DeliveryType", ""),
                                "持续时间": w.get("Duration", 0),
                                "是否 Premier": w.get("IsPremier", False),
                                "类型": w.get("Type", ""),
                                "排序权重": w.get("SortWeight", 0)
                            }
                            warranty_details.append(warranty_item)
                        
                        # 提取 AodWarranties (其他保修)
                        aod_warranties = warranty_info.get("AodWarranties", [])
                        for w in aod_warranties:
                            start_date = w.get("Start", "")
                            end_date = w.get("EndDate", "")
                            
                            if start_date and start_date != "N/A":
                                if earliest_start is None or start_date < earliest_start:
                                    earliest_start = start_date
                            if end_date and end_date != "N/A":
                                if latest_end is None or end_date > latest_end:
                                    latest_end = end_date
                            
                            warranty_item = {
                                "保修名称": w.get("Name", ""),
                                "开始日期": start_date,
                                "结束日期": end_date,
                                "状态": w.get("StatusV2", "Expired"),
                                "保修类型": w.get("WarrentyType", ""),
                                "描述": w.get("Description", ""),
                                "国家": w.get("CountryName", ""),
                                "渠道": w.get("Channel", ""),
                                "来源": w.get("Origin", ""),
                                "POP 日期": w.get("POPDate", ""),
                                "分类": w.get("Category", ""),
                                "交付类型": w.get("DeliveryType", ""),
                                "持续时间": w.get("Duration", 0),
                                "是否 Premier": w.get("IsPremier", False),
                                "类型": w.get("Type", ""),
                                "排序权重": w.get("SortWeight", 0)
                            }
                            warranty_details.append(warranty_item)
                    
                    # 构建返回结果
                    result_data = {
                        "序列号": serial,
                        "设备型号": product_name,
                        "机器型号": machine_type,
                        "产品名称": product.get("Brand", ""),
                        "最早开始时间": earliest_start or "N/A",
                        "最晚结束时间": latest_end or "N/A",
                        "维保详细信息": warranty_details
                    }
                    
                    logger.info(f"联想服务查询成功，获取到 {len(warranty_details)} 条保修信息")
                    
                    # 保存到数据库：保存原始数据（不做任何包装，直接保存完整的互联网响应）
                    # 互联网响应包含 product_info 和 warranty_info
                    raw_data = {
                        "product_info": product_info,
                        "warranty_info": warranty_info
                    }
                    self.save_to_database(serial, raw_data)
                    
                    # 从数据库读取格式化后的数据返回
                    db_result = self.query_from_database(serial)
                    if db_result:
                        return {
                            "success": 1,
                            "data": [db_result],
                            "source": "internet",
                            "vendor": "lenovo"
                        }
                    
                    # 如果数据库读取失败，返回错误
                    return {
                        "success": 0,
                        "message": "保存数据后读取失败"
                    }
                else:
                    # 没有维保信息，返回基本信息
                    logger.warning("未获取到维保信息")
                    return {
                        "success": 1,
                        "data": [{
                            "序列号": serial,
                            "设备型号": product_name,
                            "机器型号": machine_type,
                            "提示": "未查询到详细维保信息"
                        }]
                    }
            else:
                logger.warning(f"产品 ID 为空")
                return {
                    "success": 0,
                    "message": "产品 ID 为空"
                }
            
        except Exception as e:
            logger.error(f"查询异常：{str(e)}")
            return {
                "success": 0,
                "message": f"查询异常：{str(e)}"
            }
