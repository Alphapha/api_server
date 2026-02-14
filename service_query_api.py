import requests
from bs4 import BeautifulSoup
import re
import time
import logging
import random
from functools import wraps
import pickle
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('service_query_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ServiceQueryAPI')

class SangforBBSLogin:
    def __init__(self, username, password, max_retries=3, retry_interval=2, session_file='session.pkl'):
        self.username = username
        self.password = password
        self.session = None
        self.login_url = "https://bbs.sangfor.com.cn/member.php?mod=logging&action=login"
        self.target_url = "https://bbs.sangfor.com.cn/plugin.php?id=service:query"
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.session_file = session_file
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    
    def load_session(self):
        """从文件加载session"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'rb') as f:
                    saved_session = pickle.load(f)
                logger.info(f"从文件 {self.session_file} 加载session成功")
                # 验证session是否有效
                if self._validate_session(saved_session):
                    self.session = saved_session
                    return True
                else:
                    logger.warning("加载的session无效，需要重新登录")
                    return False
            except Exception as e:
                logger.error(f"加载session失败: {str(e)}")
                return False
        else:
            logger.info(f"session文件 {self.session_file} 不存在，需要重新登录")
            return False
    
    def save_session(self):
        """保存session到文件"""
        if self.session:
            try:
                with open(self.session_file, 'wb') as f:
                    pickle.dump(self.session, f)
                logger.info(f"session已保存到文件 {self.session_file}")
                return True
            except Exception as e:
                logger.error(f"保存session失败: {str(e)}")
                return False
        return False
    
    def _validate_session(self, session):
        """验证session是否有效"""
        try:
            # 尝试访问需要登录的页面
            test_url = "https://bbs.sangfor.com.cn/home.php?mod=space"
            response = session.get(test_url, headers=self.headers, timeout=10)
            response.encoding = "utf-8"
            
            # 检查是否包含登录成功的特征
            success_indicators = ["个人中心", "欢迎您", "会员", "用户"]
            for indicator in success_indicators:
                if indicator in response.text:
                    logger.info("session验证成功")
                    return True
            
            # 检查是否需要登录
            if "您必须先登录后才能进行相关操作" in response.text:
                logger.warning("session已过期，需要重新登录")
                return False
            
            logger.warning("session验证不确定，需要重新登录")
            return False
        except Exception as e:
            logger.error(f"验证session时发生错误: {str(e)}")
            return False
    
    def retry_request(func):
        """网络请求重试装饰器"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            retries = 0
            while retries < self.max_retries:
                try:
                    return func(self, *args, **kwargs)
                except requests.RequestException as e:
                    retries += 1
                    if retries >= self.max_retries:
                        logger.error(f"{func.__name__} 失败，已达到最大重试次数: {str(e)}")
                        return None if func.__name__ == 'get_loginhash' else False
                    wait_time = self.retry_interval * (2 ** (retries - 1)) + random.uniform(0, 1)
                    logger.warning(f"{func.__name__} 失败，{wait_time:.2f}秒后重试 ({retries}/{self.max_retries}): {str(e)}")
                    time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"{func.__name__} 发生未知错误: {str(e)}")
                    return None if func.__name__ == 'get_loginhash' else False
            return None if func.__name__ == 'get_loginhash' else False
        return wrapper
    
    @retry_request
    def get_loginhash(self):
        """动态获取loginhash值"""
        logger.info("开始获取loginhash值")
        response = self.session.get(self.login_url, headers=self.headers, timeout=10)
        response.encoding = "utf-8"
        
        # 使用正则表达式提取loginhash
        loginhash_match = re.search(r'loginhash=(\w+)', response.text)
        if loginhash_match:
            loginhash = loginhash_match.group(1)
            logger.info(f"成功获取loginhash: {loginhash}")
            return loginhash
        else:
            # 使用BeautifulSoup作为备用方案
            logger.warning("正则表达式提取loginhash失败，尝试使用BeautifulSoup")
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', id='loginform')
            if form:
                action = form.get('action', '')
                loginhash_match = re.search(r'loginhash=(\w+)', action)
                if loginhash_match:
                    loginhash = loginhash_match.group(1)
                    logger.info(f"通过BeautifulSoup成功获取loginhash: {loginhash}")
                    return loginhash
        logger.error("获取loginhash失败")
        return None
    
    @retry_request
    def login(self):
        """执行登录操作"""
        # 1. 初始化session
        if not self.session:
            self.session = requests.Session()
            logger.info("已初始化新的session对象")
        
        # 2. 先访问首页，获取初始Cookie
        logger.info("访问首页获取初始Cookie")
        home_response = self.session.get("https://bbs.sangfor.com.cn", headers=self.headers, timeout=10)
        home_response.encoding = "utf-8"
        logger.info(f"首页访问状态码: {home_response.status_code}")
        
        # 3. 获取最新的loginhash
        loginhash = self.get_loginhash()
        if not loginhash:
            logger.error("无法获取loginhash，登录失败")
            return False
        
        # 4. 构建完整的登录URL
        full_login_url = f"https://bbs.sangfor.com.cn/member.php?mod=logging&action=login&loginsubmit=yes&loginhash={loginhash}&inajax=1"
        
        # 5. 构建登录数据
        login_data = {
            "referer": "https%3A%2F%2Fbbs.sangfor.com.cn%2F",
            "username": self.username,
            "password": self.password,  # 显示密码以便调试
            "cookietime": "2592000"
        }
        
        # 6. 构建更完整的登录请求头
        login_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"https://bbs.sangfor.com.cn/member.php?mod=logging&action=login&loginhash={loginhash}"
        }
        
        logger.info("开始执行登录操作")
        
        # 7. 发送登录请求
        response = self.session.post(
            url=full_login_url,
            headers=login_headers,
            data=login_data,
            timeout=15
        )
        response.encoding = "utf-8"
        
        # 8. 检查登录结果
        logger.info(f"登录响应状态码: {response.status_code}")
        logger.info(f"登录响应内容: {response.text}")
        
        # 9. 检查Cookie
        cookies = self.session.cookies.get_dict()
        logger.info(f"登录后获取到 {len(cookies)} 个Cookie")
        
        # 10. 验证登录是否成功
        if self.verify_login():
            # 登录成功，保存session
            self.save_session()
            logger.info("登录成功并保存session")
            return True
        else:
            logger.error("登录验证失败")
            return False
    
    def force_login(self):
        """强制重新登录"""
        # 删除旧的session文件
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
                logger.info(f"已删除旧的session文件 {self.session_file}")
            except Exception as e:
                logger.error(f"删除session文件失败: {str(e)}")
        
        # 初始化新的session
        self.session = requests.Session()
        logger.info("已初始化新的session对象")
        
        # 执行登录
        return self.login()
    
    @retry_request
    def verify_login(self):
        """验证登录是否成功"""
        logger.info("开始验证登录状态")
        
        # 1. 访问个人中心页面验证登录状态
        profile_url = "https://bbs.sangfor.com.cn/home.php?mod=space"
        profile_response = self.session.get(profile_url, headers=self.headers, timeout=10)
        profile_response.encoding = "utf-8"
        
        logger.info(f"个人中心页面状态码: {profile_response.status_code}")
        logger.info(f"个人中心页面内容长度: {len(profile_response.text)}")
        
        # 2. 检查个人中心页面的登录状态
        if profile_response.status_code == 200:
            # 检查登录成功的多种可能特征
            success_indicators = [
                "个人中心",
                "欢迎您",
                "登录成功",
                "会员",
                "用户",
                "退出",
                "修改资料"
            ]
            
            # 检查是否包含任何成功标识
            for indicator in success_indicators:
                if indicator in profile_response.text:
                    logger.info(f"登录成功！检测到特征: '{indicator}'")
                    return True
            
            # 检查是否包含登录失败的特征
            if "登录" in profile_response.text and ("密码" in profile_response.text or "账号" in profile_response.text):
                logger.error("登录失败：可能是账号或密码错误")
                return False
            
            # 检查是否被重定向到登录页面
            if "member.php?mod=logging&action=login" in profile_response.url:
                logger.error("登录失败：被重定向到登录页面")
                return False
        
        # 3. 尝试访问服务查询页面验证
        logger.info("尝试访问服务查询页面验证登录状态")
        response = self.session.get(self.target_url, headers=self.headers, timeout=10)
        response.encoding = "utf-8"
        
        logger.info(f"服务查询页面状态码: {response.status_code}")
        logger.info(f"服务查询页面内容长度: {len(response.text)}")
        
        # 检查是否被重定向到登录页面
        if "member.php?mod=logging&action=login" in response.url:
            logger.error("登录失败：被重定向到登录页面")
            return False
        
        # 检查是否包含登录失败的特征
        if "您必须先登录后才能进行相关操作" in response.text:
            logger.error("登录失败：服务查询页面要求登录")
            return False
        
        # 如果页面长度足够大且状态码为200，也视为成功
        if len(response.text) > 50000 and response.status_code == 200:
            logger.info("登录成功！页面加载正常")
            return True
        
        logger.warning("登录状态不确定：请检查响应内容")
        return False
    
    def get_session(self):
        """获取登录后的session对象"""
        logger.info("开始获取登录后的Session对象")
        
        # 1. 优先从文件加载session
        if self.load_session():
            logger.info("成功从文件加载有效的Session对象")
            return self.session
        
        # 2. 如果加载失败或session无效，进行登录
        logger.info("从文件加载session失败，开始登录")
        if self.login():
            logger.info("成功获取登录后的Session对象")
            return self.session
        
        logger.error("获取Session对象失败")
        return None
    
    def query_service(self, serial_number):
        """使用当前session查询服务信息"""
        if not self.session:
            logger.error("会话未初始化，无法查询服务信息")
            return None
        
        try:
            # 1. 访问服务查询页面，获取初始内容
            logger.info("访问服务查询页面获取初始内容")
            query_page_response = self.session.get(self.target_url, headers=self.headers, timeout=15)
            query_page_response.encoding = "utf-8"
            
            if query_page_response.status_code != 200:
                logger.error(f"访问服务查询页面失败，状态码: {query_page_response.status_code}")
                return None
            
            # 保存服务查询页面内容
            with open('service_query_debug.html', 'w', encoding='utf-8') as f:
                f.write(query_page_response.text)
            logger.info("已保存服务查询页面到 service_query_debug.html")
            
            # 2. 动态获取验证码信息
            logger.info("动态获取验证码信息")
            
            # 生成随机数
            random_num = random.random()
            update_random = random.randint(10000, 99999)
            
            # 构建验证码更新URL
            captcha_update_url = f"https://bbs.sangfor.com.cn/misc.php?mod=seccode&action=update&idhash=cSjSGo8w&{random_num}&modid=plugin::service"
            logger.info(f"验证码更新URL: {captcha_update_url}")
            
            # 发送验证码更新请求
            captcha_response = self.session.get(captcha_update_url, headers=self.headers, timeout=10)
            captcha_response.encoding = "utf-8"
            
            logger.info(f"验证码更新响应状态码: {captcha_response.status_code}")
            logger.info(f"验证码更新响应内容: {captcha_response.text}")
            
            # 从响应中提取idhash
            idhash_match = re.search(r'value="([\w]+)"[^.]*name="seccodehash"', captcha_response.text)
            if not idhash_match:
                idhash_match = re.search(r'idhash=([\w]+)', captcha_response.text)
            if idhash_match:
                idhash = idhash_match.group(1)
                logger.info(f"从响应中提取到idhash: {idhash}")
            else:
                logger.warning("未从响应中提取到idhash，使用默认值")
                idhash = "cSjSGo8w"
            
            # 构建验证码图片URL
            captcha_img_url = f"https://bbs.sangfor.com.cn/misc.php?mod=seccode&update={update_random}&idhash={idhash}"
            logger.info(f"验证码图片URL: {captcha_img_url}")
            
            # 3. 获取验证码图片
            logger.info("获取验证码图片")
            captcha_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://bbs.sangfor.com.cn/plugin.php?id=service:query"
            }
            
            # 下载验证码图片
            img_response = self.session.get(captcha_img_url, headers=captcha_headers, timeout=10)
            
            if img_response.status_code == 200:
                # 保存验证码图片
                with open('captcha_debug.jpg', 'wb') as f:
                    f.write(img_response.content)
                logger.info(f"已保存验证码图片到 captcha_debug.jpg，大小: {len(img_response.content)} 字节")
                
                # 使用用户提供的API接口识别验证码
                import base64
                max_retries = 5
                retry_count = 0
                captcha_text = "ABCD"
                
                while retry_count < max_retries:
                    try:
                        # 将验证码图片转换为base64编码
                        img_base64 = base64.b64encode(img_response.content).decode('utf-8')
                        
                        # 构建API请求
                        api_url = "http://char1es.cn:8888/reg"
                        api_headers = {"Content-Type": "text/plain"}
                        
                        logger.info(f"使用API接口识别验证码 (尝试 {retry_count + 1}/{max_retries})")
                        # 发送POST请求到API接口
                        api_response = self.session.post(
                            api_url,
                            headers=api_headers,
                            data=img_base64,
                            timeout=10
                        )
                        
                        # 记录API响应详情
                        logger.info(f"API响应状态码: {api_response.status_code}")
                        logger.info(f"API响应内容: {api_response.text}")
                        logger.info(f"API响应头: {dict(api_response.headers)}")
                        
                        if api_response.status_code == 200:
                            # 获取API返回的验证码
                            try:
                                # 尝试解码响应内容
                                raw_response = api_response.text
                                logger.info(f"原始API响应: {raw_response}")
                                
                                # 清理和处理响应结果
                                captcha_text = raw_response.strip().upper()
                                # 清理返回结果，只保留字母和数字
                                captcha_text = re.sub(r'[^A-Z0-9]', '', captcha_text)
                                
                                logger.info(f"处理后的验证码识别结果: {captcha_text}")
                                
                                # 验证验证码长度
                                if len(captcha_text) == 4:
                                    logger.info("验证码长度正确，使用该验证码")
                                    break
                                else:
                                    logger.warning(f"验证码长度不正确: {captcha_text}")
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        logger.info(f"{retry_count}秒后重试...")
                                        time.sleep(retry_count)  # 递增等待时间
                                    else:
                                        logger.warning("已达到最大重试次数，使用默认验证码")
                            except Exception as decode_e:
                                logger.error(f"解码验证码响应失败: {str(decode_e)}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    logger.info(f"{retry_count}秒后重试...")
                                    time.sleep(retry_count)  # 递增等待时间
                                else:
                                    logger.warning("已达到最大重试次数，解码失败")
                        else:
                            logger.error(f"API请求失败，状态码: {api_response.status_code}")
                            retry_count += 1
                            if retry_count < max_retries:
                                logger.info(f"{retry_count}秒后重试...")
                                time.sleep(retry_count)
                            else:
                                logger.warning("已达到最大重试次数，使用默认验证码")
                    except Exception as api_e:
                        logger.error(f"API识别失败: {str(api_e)}")
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.info(f"{retry_count}秒后重试...")
                            time.sleep(retry_count)
                        else:
                            logger.warning("已达到最大重试次数，使用默认验证码")
            else:
                logger.error(f"获取验证码图片失败，状态码: {img_response.status_code}")
                captcha_text = "ABCD"
            
            logger.info(f"最终使用idhash: {idhash}, 验证码: {captcha_text}")
            
            # 4. 构建查询请求
            logger.info("构建查询请求")
            
            # 构建完整的查询URL
            query_url = f"https://bbs.sangfor.com.cn/plugin.php?id=service:query&op=doquery&type=svrstate&seccodeverify={captcha_text}&seccodehash={idhash}&seccodemodid=plugin::service&svrid={serial_number}"
            logger.info(f"完整查询URL: {query_url}")
            
            # 构建查询请求头
            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6285.209 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://bbs.sangfor.com.cn",
                "Referer": "https://bbs.sangfor.com.cn/plugin.php?id=service:query",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
            
            # 构建查询数据
            query_data = "ajaxdata=json"
            logger.info(f"查询数据: {query_data}")
            
            # 5. 发送查询请求
            logger.info("发送服务查询请求")
            service_response = self.session.post(
                query_url,
                headers=request_headers,
                data=query_data,
                timeout=15,
                allow_redirects=False
            )
            service_response.encoding = "utf-8"
            logger.info(f"查询响应状态码: {service_response.status_code}")
            logger.info(f"查询响应内容: {service_response.text}")
            logger.info(f"查询响应头: {dict(service_response.headers)}")
            
            # 检查响应
            if service_response.status_code == 200:
                logger.info("查询服务信息成功")
                return service_response.text
            else:
                logger.error(f"查询服务信息失败，状态码: {service_response.status_code}")
                return None
        except Exception as e:
            logger.error(f"查询服务信息异常: {str(e)}")
            return None

# 创建Flask应用
app = Flask(__name__)

# 配置Flask以确保中文正确显示
app.config['JSON_AS_ASCII'] = False

# 全局登录客户端实例
login_client = None

@app.route('/sn_query/sangfor', methods=['GET', 'POST'])
def query_service_sangfor():
    """API接口：查询深信服设备维保信息"""
    try:
        # 获取设备序列号
        if request.method == 'GET':
            serial_number = request.args.get('sn')
        else:
            serial_number = request.json.get('sn') if request.is_json else request.form.get('sn')
        
        if not serial_number:
            return jsonify({
                "success": 0,
                "message": "设备序列号不能为空"
            })
        
        logger.info(f"收到深信服查询请求，设备序列号: {serial_number}")
        
        # 确保登录客户端已初始化
        global login_client
        if not login_client:
            # 从环境变量读取登录信息
            username = os.getenv('SANGFOR_USERNAME', '19533323645')  # 默认值作为备用
            password = os.getenv('SANGFOR_PASSWORD', '5f441ef6414873cfeecdee6807079a91')  # 默认值作为备用
            
            # 创建登录客户端实例
            logger.info("创建登录客户端实例")
            login_client = SangforBBSLogin(username, password)
        
        # 确保获取有效的session
        if not login_client.session:
            logger.info("获取session")
            login_client.get_session()
        
        # 执行服务查询，添加失败重试机制
        logger.info("执行服务查询")
        max_retries = 5
        retry_count = 0
        service_result = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"执行服务查询 (尝试 {retry_count + 1}/{max_retries})")
                service_result = login_client.query_service(serial_number)
                
                if service_result:
                    logger.info(f"服务查询成功")
                    # 解析结果
                    import json
                    try:
                        result = json.loads(service_result)
                        # 检查是否是验证码错误
                        if result.get("success") == -2:
                            logger.warning("服务查询失败: 验证码错误，准备重试")
                            retry_count += 1
                            if retry_count < max_retries:
                                wait_time = retry_count
                                logger.info(f"{wait_time}秒后重试...")
                                time.sleep(wait_time)
                            else:
                                logger.error("已达到最大重试次数，服务查询失败")
                                return jsonify({
                                    "success": 0,
                                    "message": "服务查询失败: 验证码错误"
                                })
                        else:
                            # 解析服务查询成功的响应结果
                            if "data" in result and isinstance(result["data"], list):
                                # 处理data数组中的每个元素
                                parsed_data = []
                                for item in result["data"]:
                                    parsed_item = {
                                        "序列号": item.get("rnum", ""),
                                        "网关id": item.get("rid", ""),
                                        "设备型号": item.get("pdName", ""),
                                        "服务商名称": item.get("cti_channame", ""),
                                        "服务电话": item.get("cit_chanphone", ""),
                                        "网络远程支持有效期": item.get("cti_day2_800", ""),
                                        "同等功能软件升级有效期": item.get("cti_day2_up", ""),
                                        "硬件维保有效期": item.get("cit_day2_rb", "")
                                    }
                                    parsed_data.append(parsed_item)
                                
                                parsed_result = {
                                    "success": 1,
                                    "data": parsed_data
                                }
                                # 使用json.dumps确保中文正确显示
                                import json
                                from flask import Response
                                return Response(
                                    json.dumps(parsed_result, ensure_ascii=False),
                                    mimetype='application/json'
                                )
                            else:
                                return jsonify(result)
                    except json.JSONDecodeError as e:
                        logger.error(f"解析JSON失败: {str(e)}")
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = retry_count
                            logger.info(f"{wait_time}秒后重试...")
                            time.sleep(wait_time)
                        else:
                            logger.error("已达到最大重试次数，解析结果失败")
                            return jsonify({
                                "success": 0,
                                "message": "解析结果失败"
                            })
                else:
                    logger.warning("服务查询失败，准备重试")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_count
                        logger.info(f"{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error("已达到最大重试次数，服务查询失败")
                        return jsonify({
                            "success": 0,
                            "message": "服务查询失败"
                        })
            except Exception as e:
                logger.error(f"服务查询异常: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_count
                    logger.info(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error("已达到最大重试次数，服务查询异常")
                    return jsonify({
                        "success": 0,
                        "message": f"服务查询异常: {str(e)}"
                    })
    except Exception as e:
        logger.error(f"API请求异常: {str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常: {str(e)}"
        })

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
    
    def get_captcha(self):
        """获取验证码"""
        try:
            # 首先访问入口页面获取初始cookie
            self.session.get(self.entry_url, headers=self.headers, timeout=10)
            
            # 生成随机时间戳
            timestamp = int(time.time() * 1000)
            captcha_url = f"{self.portal_url}/servlet/captcha?yzm={timestamp}"
            
            # 获取验证码图片
            captcha_headers = self.headers.copy()
            captcha_headers["Referer"] = "https://app.huawei.com/escpportal/pub/wechat.html?Language=CN"
            captcha_headers["X-Requested-With"] = "XMLHttpRequest"
            
            response = self.session.get(captcha_url, headers=captcha_headers, timeout=10)
            
            if response.status_code == 200:
                # 保存验证码图片
                with open('huawei_captcha.jpg', 'wb') as f:
                    f.write(response.content)
                logger.info("已保存华为验证码图片到 huawei_captcha.jpg")
                return response.content
            else:
                logger.error(f"获取华为验证码失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取华为验证码异常: {str(e)}")
            return None
    
    def recognize_captcha(self, captcha_image):
        """使用API识别验证码"""
        try:
            import base64
            max_retries = 5
            retry_count = 0
            captcha_text = ""
            
            while retry_count < max_retries:
                try:
                    # 将验证码图片转换为base64编码
                    img_base64 = base64.b64encode(captcha_image).decode('utf-8')
                    
                    # 构建API请求
                    api_url = "http://char1es.cn:8888/reg"
                    api_headers = {
                        "Content-Type": "text/plain"
                    }
                    
                    logger.info(f"使用API接口识别华为验证码 (尝试 {retry_count + 1}/{max_retries})")
                    # 发送POST请求到API接口
                    api_response = requests.post(
                        api_url,
                        headers=api_headers,
                        data=img_base64,
                        timeout=10
                    )
                    
                    # 记录API响应详情
                    logger.info(f"API响应状态码: {api_response.status_code}")
                    logger.info(f"API响应内容: {api_response.text}")
                    logger.info(f"API响应头: {dict(api_response.headers)}")
                    
                    if api_response.status_code == 200:
                        # 获取API返回的验证码
                        try:
                            # 尝试解码响应内容
                            raw_response = api_response.text
                            logger.info(f"原始API响应: {raw_response}")
                            
                            # 清理和处理响应结果
                            captcha_text = raw_response.strip().upper()
                            # 清理返回结果，只保留字母和数字
                            captcha_text = re.sub(r'[^A-Z0-9]', '', captcha_text)
                            
                            logger.info(f"处理后的华为验证码识别结果: {captcha_text}")
                            
                            # 验证验证码长度
                            if len(captcha_text) > 0:
                                logger.info("华为验证码识别成功")
                                return captcha_text
                            else:
                                logger.warning(f"华为验证码识别结果为空: {captcha_text}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    logger.info(f"{retry_count}秒后重试...")
                                    time.sleep(retry_count)  # 递增等待时间
                                else:
                                    logger.warning("已达到最大重试次数，华为验证码识别失败")
                                    return ""
                        except Exception as decode_e:
                            logger.error(f"解码华为验证码响应失败: {str(decode_e)}")
                            retry_count += 1
                            if retry_count < max_retries:
                                logger.info(f"{retry_count}秒后重试...")
                                time.sleep(retry_count)  # 递增等待时间
                            else:
                                logger.warning("已达到最大重试次数，解码失败")
                                return ""
                    else:
                        logger.error(f"API请求失败，状态码: {api_response.status_code}")
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.info(f"{retry_count}秒后重试...")
                            time.sleep(retry_count)  # 递增等待时间
                        else:
                            logger.warning("已达到最大重试次数，使用默认验证码")
                            return ""
                except Exception as api_e:
                    logger.error(f"API识别失败: {str(api_e)}")
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.info(f"{retry_count}秒后重试...")
                        time.sleep(retry_count)  # 递增等待时间
                    else:
                        logger.warning("已达到最大重试次数，使用默认验证码")
                        return ""
        except Exception as e:
            logger.error(f"识别华为验证码异常: {str(e)}")
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
            response = self.session.post(validate_url, headers=validate_headers, data=data, timeout=10)
            
            if response.status_code == 200 and response.text.strip() == "yes":
                logger.info("华为验证码验证成功")
                return True
            else:
                logger.error(f"华为验证码验证失败，响应: {response.text}")
                return False
        except Exception as e:
            logger.error(f"验证华为验证码异常: {str(e)}")
            return False
    
    def query_warranty(self, serial_number, captcha_code):
        """查询设备维保信息"""
        try:
            # 首先验证验证码
            if not self.validate_captcha(captcha_code):
                logger.error("验证码验证失败，无法查询维保信息")
                return None
            
            # 构建查询URL
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
            response = self.session.get(query_url, headers=query_headers, params=query_params, timeout=15)
            
            if response.status_code == 200:
                logger.info("查询华为设备维保信息成功")
                return response.text
            else:
                logger.error(f"查询华为设备维保信息失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"查询华为设备维保信息异常: {str(e)}")
            return None

@app.route('/sn_query/huawei', methods=['GET', 'POST'])
def query_service_huawei():
    """API接口：查询华为设备维保信息"""
    try:
        # 获取设备序列号
        if request.method == 'GET':
            serial_number = request.args.get('sn')
        else:
            serial_number = request.json.get('sn') if request.is_json else request.form.get('sn')
        
        if not serial_number:
            return jsonify({
                "success": 0,
                "message": "设备序列号不能为空"
            })
        
        logger.info(f"收到华为查询请求，设备序列号: {serial_number}")
        
        # 创建华为查询客户端
        huawei_client = HuaweiWarrantyQuery()
        
        # 执行服务查询，添加失败重试机制
        max_retries = 3
        retry_count = 0
        service_result = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"执行华为服务查询 (尝试 {retry_count + 1}/{max_retries})")
                
                # 获取验证码
                captcha_image = huawei_client.get_captcha()
                if not captcha_image:
                    logger.error("获取华为验证码失败")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_count
                        logger.info(f"{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error("已达到最大重试次数，获取华为验证码失败")
                        return jsonify({
                            "success": 0,
                            "message": "获取华为验证码失败"
                        })
                
                # 自动识别验证码
                captcha_code = huawei_client.recognize_captcha(captcha_image)
                if not captcha_code:
                    logger.error("华为验证码识别失败")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_count
                        logger.info(f"{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error("已达到最大重试次数，华为验证码识别失败")
                        return jsonify({
                            "success": 0,
                            "message": "华为验证码识别失败"
                        })
                
                # 查询维保信息
                service_result = huawei_client.query_warranty(serial_number, captcha_code)
                
                if service_result:
                    logger.info("华为服务查询成功")
                    # 记录原始响应内容
                    logger.info(f"华为服务查询原始响应: {service_result}")
                    # 解析结果
                    import json
                    try:
                        result = json.loads(service_result)
                        # 记录解析后的结果
                        logger.info(f"华为服务查询解析结果: {result}")
                        # 转换数据为人类可读格式
                        parsed_data = []
                        for item in result:
                            parsed_item = {
                                "序列号": item.get("barcode", ""),
                                "设备型号": item.get("snModel", ""),
                                "服务套餐": item.get("servicePackage", ""),
                                "开始日期": item.get("startDate", ""),
                                "结束日期": item.get("endDate", ""),
                                "状态": item.get("vyborgStutas", ""),
                                "国家/地区": item.get("country", ""),
                                "保修区域": item.get("warrantyArea", ""),
                                "描述": item.get("itemDescription", "")
                            }
                            parsed_data.append(parsed_item)
                        
                        # 使用json.dumps确保中文正确显示
                        import json
                        from flask import Response
                        return Response(
                            json.dumps({"success": 1, "data": parsed_data}, ensure_ascii=False),
                            mimetype='application/json'
                        )
                    except json.JSONDecodeError as e:
                        logger.error(f"解析华为查询结果失败: {str(e)}")
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = retry_count
                            logger.info(f"{wait_time}秒后重试...")
                            time.sleep(wait_time)
                        else:
                            logger.error("已达到最大重试次数，解析华为查询结果失败")
                            return jsonify({
                                "success": 0,
                                "message": "解析华为查询结果失败"
                            })
                else:
                    logger.warning("华为服务查询失败，准备重试")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_count
                        logger.info(f"{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error("已达到最大重试次数，华为服务查询失败")
                        return jsonify({
                            "success": 0,
                            "message": "华为服务查询失败"
                        })
            except Exception as e:
                logger.error(f"华为服务查询异常: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_count
                    logger.info(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error("已达到最大重试次数，华为服务查询异常")
                    return jsonify({
                        "success": 0,
                        "message": f"华为服务查询异常: {str(e)}"
                    })
    except Exception as e:
        logger.error(f"API请求异常: {str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常: {str(e)}"
        })

@app.route('/sn_query/lenovo', methods=['GET', 'POST'])
def query_service_lenovo():
    """API接口：查询联想设备维保信息（预占位）"""
    try:
        # 获取设备序列号
        if request.method == 'GET':
            serial_number = request.args.get('sn')
        else:
            serial_number = request.json.get('sn') if request.is_json else request.form.get('sn')
        
        if not serial_number:
            return jsonify({
                "success": 0,
                "message": "设备序列号不能为空"
            })
        
        logger.info(f"收到联想查询请求，设备序列号: {serial_number}")
        
        # 暂时返回空数据
        return jsonify({
            "success": 1,
            "data": {}
        })
    except Exception as e:
        logger.error(f"API请求异常: {str(e)}")
        return jsonify({
            "success": 0,
            "message": f"请求异常: {str(e)}"
        })

@app.route('/reg', methods=['POST'])
def handle_captcha():
    """API接口：验证码识别"""
    try:
        # 获取请求体中的base64编码图片
        img_base64 = request.get_data(as_text=True)
        logger.info(f"收到验证码识别请求，图片大小: {len(img_base64)} 字节")
        
        # 解码base64字符串为图片字节
        import base64
        img_bytes = base64.b64decode(img_base64)
        logger.info(f"解码后图片大小: {len(img_bytes)} 字节")
        
        # 尝试使用ddddocr识别验证码
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr()
            result = ocr.classification(img_bytes)
            # 取前四位
            captcha_text = result[0:4]
            logger.info(f"验证码识别成功: {captcha_text}")
            return captcha_text
        except ImportError:
            logger.warning("ddddocr库未安装，无法进行验证码识别")
            return "ddddocr not available", 500
        except Exception as ocr_error:
            logger.error(f"验证码识别失败: {str(ocr_error)}")
            return "OCR error", 500
    except Exception as e:
        logger.error(f"验证码处理异常: {str(e)}")
        return "Error", 500

if __name__ == "__main__":
    logger.info("===== 启动服务查询API ======")
    
    # 从环境变量读取登录信息
    username = os.getenv('SANGFOR_USERNAME')  # 默认值作为备用
    password = os.getenv('SANGFOR_PASSWORD')  # 默认值作为备用
    
    # 初始化登录客户端
    logger.info("初始化登录客户端")
    login_client = SangforBBSLogin(username, password)
    
    # 预登录，确保session有效
    logger.info("预登录，确保session有效")
    login_client.get_session()
    
    # 启动Flask应用
    logger.info("启动Flask应用，监听端口9876")
    app.run(host='0.0.0.0', port=9876, debug=False)
