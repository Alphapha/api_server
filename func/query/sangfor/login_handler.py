"""
深信服登录模块
处理深信服 BBS 的登录和会话管理
"""
import requests
from bs4 import BeautifulSoup
import re
import time
import logging
import random
import pickle
import os
from functools import wraps

logger = logging.getLogger('SangforLogin')


class SangforBBSLogin:
    """深信服 BBS 登录类"""
    
    def __init__(self, username, password, max_retries=3, retry_interval=2, session_file='/tmp/session.pkl'):
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
        """从文件加载 session"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'rb') as f:
                    saved_session = pickle.load(f)
                logger.info(f"从文件 {self.session_file} 加载 session 成功")
                if self._validate_session(saved_session):
                    self.session = saved_session
                    return True
                else:
                    logger.warning("加载的 session 无效，需要重新登录")
                    return False
            except Exception as e:
                logger.error(f"加载 session 失败：{str(e)}")
                return False
        else:
            logger.info(f"session 文件 {self.session_file} 不存在，需要重新登录")
            return False
    
    def save_session(self):
        """保存 session 到文件"""
        if self.session:
            try:
                with open(self.session_file, 'wb') as f:
                    pickle.dump(self.session, f)
                logger.info(f"session 已保存到文件 {self.session_file}")
                return True
            except Exception as e:
                logger.error(f"保存 session 失败：{str(e)}")
                return False
        return False
    
    def _validate_session(self, session):
        """验证 session 是否有效"""
        try:
            test_url = "https://bbs.sangfor.com.cn/home.php?mod=space"
            response = session.get(test_url, headers=self.headers, timeout=10)
            response.encoding = "utf-8"
            
            success_indicators = ["个人中心", "欢迎您", "会员", "用户"]
            for indicator in success_indicators:
                if indicator in response.text:
                    logger.info("session 验证成功")
                    return True
            
            if "您必须先登录后才能进行相关操作" in response.text:
                logger.warning("session 已过期，需要重新登录")
                return False
            
            logger.warning("session 验证不确定，需要重新登录")
            return False
        except Exception as e:
            logger.error(f"验证 session 时发生错误：{str(e)}")
            return False
    
    def is_session_valid_for_query(self):
        """验证当前 session 是否可以用于查询"""
        if not self.session:
            logger.warning("session 不存在")
            return False
        
        try:
            test_url = "https://bbs.sangfor.com.cn/plugin.php?id=service:query"
            response = self.session.get(test_url, headers=self.headers, timeout=10)
            response.encoding = "utf-8"
            
            success_indicators = ["服务查询", "设备序列号", "查询"]
            for indicator in success_indicators:
                if indicator in response.text:
                    logger.info("session 可用于查询")
                    return True
            
            if "您必须先登录后才能进行相关操作" in response.text:
                logger.warning("session 已过期，无法用于查询")
                return False
            
            if "member.php?mod=logging&action=login" in response.url:
                logger.warning("session 已过期，被重定向到登录页面")
                return False
            
            logger.warning("session 状态不确定")
            return False
        except Exception as e:
            logger.error(f"验证查询 session 时发生错误：{str(e)}")
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
                        logger.error(f"{func.__name__} 失败，已达到最大重试次数：{str(e)}")
                        return None if func.__name__ == 'get_loginhash' else False
                    wait_time = self.retry_interval * (2 ** (retries - 1)) + random.uniform(0, 1)
                    logger.warning(f"{func.__name__} 失败，{wait_time:.2f}秒后重试 ({retries}/{self.max_retries}): {str(e)}")
                    time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"{func.__name__} 发生未知错误：{str(e)}")
                    return None if func.__name__ == 'get_loginhash' else False
            return None if func.__name__ == 'get_loginhash' else False
        return wrapper
    
    @retry_request
    def get_loginhash(self):
        """动态获取 loginhash 值"""
        logger.info("开始获取 loginhash 值")
        response = self.session.get(self.login_url, headers=self.headers, timeout=10)
        response.encoding = "utf-8"
        
        loginhash_match = re.search(r'loginhash=(\w+)', response.text)
        if loginhash_match:
            loginhash = loginhash_match.group(1)
            logger.info(f"成功获取 loginhash: {loginhash}")
            return loginhash
        else:
            logger.warning("正则表达式提取 loginhash 失败，尝试使用 BeautifulSoup")
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', id='loginform')
            if form:
                action = form.get('action', '')
                loginhash_match = re.search(r'loginhash=(\w+)', action)
                if loginhash_match:
                    loginhash = loginhash_match.group(1)
                    logger.info(f"通过 BeautifulSoup 成功获取 loginhash: {loginhash}")
                    return loginhash
        logger.error("获取 loginhash 失败")
        return None
    
    @retry_request
    def login(self):
        """执行登录操作"""
        if not self.session:
            self.session = requests.Session()
            logger.info("已初始化新的 session 对象")
        
        logger.info("访问首页获取初始 Cookie")
        home_response = self.session.get("https://bbs.sangfor.com.cn", headers=self.headers, timeout=10)
        home_response.encoding = "utf-8"
        logger.info(f"首页访问状态码：{home_response.status_code}")
        
        loginhash = self.get_loginhash()
        if not loginhash:
            logger.error("无法获取 loginhash，登录失败")
            return False
        
        full_login_url = f"https://bbs.sangfor.com.cn/member.php?mod=logging&action=login&loginsubmit=yes&loginhash={loginhash}&inajax=1"
        
        login_data = {
            "referer": "https%3A%2F%2Fbbs.sangfor.com.cn%2F",
            "username": self.username,
            "password": self.password,
            "cookietime": "2592000"
        }
        
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
        
        response = self.session.post(
            url=full_login_url,
            headers=login_headers,
            data=login_data,
            timeout=15
        )
        response.encoding = "utf-8"
        
        logger.info(f"登录响应状态码：{response.status_code}")
        
        cookies = self.session.cookies.get_dict()
        logger.info(f"登录后获取到 {len(cookies)} 个 Cookie")
        
        if self.verify_login():
            self.save_session()
            logger.info("登录成功并保存 session")
            return True
        else:
            logger.error("登录验证失败")
            return False
    
    def force_login(self):
        """强制重新登录"""
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
                logger.info(f"已删除旧的 session 文件 {self.session_file}")
            except Exception as e:
                logger.error(f"删除 session 文件失败：{str(e)}")
        
        self.session = requests.Session()
        logger.info("已初始化新的 session 对象")
        
        return self.login()
    
    @retry_request
    def verify_login(self):
        """验证登录是否成功"""
        logger.info("开始验证登录状态")
        
        profile_url = "https://bbs.sangfor.com.cn/home.php?mod=space"
        profile_response = self.session.get(profile_url, headers=self.headers, timeout=10)
        profile_response.encoding = "utf-8"
        
        logger.info(f"个人中心页面状态码：{profile_response.status_code}")
        logger.info(f"个人中心页面内容长度：{len(profile_response.text)}")
        
        if profile_response.status_code == 200:
            success_indicators = [
                "个人中心", "欢迎您", "登录成功", "会员", "用户", "退出", "修改资料"
            ]
            
            for indicator in success_indicators:
                if indicator in profile_response.text:
                    logger.info(f"登录成功！检测到特征：'{indicator}'")
                    return True
            
            if "登录" in profile_response.text and ("密码" in profile_response.text or "账号" in profile_response.text):
                logger.error("登录失败：可能是账号或密码错误")
                return False
            
            if "member.php?mod=logging&action=login" in profile_response.url:
                logger.error("登录失败：被重定向到登录页面")
                return False
        
        logger.info("尝试访问服务查询页面验证登录状态")
        response = self.session.get(self.target_url, headers=self.headers, timeout=10)
        response.encoding = "utf-8"
        
        logger.info(f"服务查询页面状态码：{response.status_code}")
        logger.info(f"服务查询页面内容长度：{len(response.text)}")
        
        if "member.php?mod=logging&action=login" in response.url:
            logger.error("登录失败：被重定向到登录页面")
            return False
        
        if "您必须先登录后才能进行相关操作" in response.text:
            logger.error("登录失败：服务查询页面要求登录")
            return False
        
        if len(response.text) > 50000 and response.status_code == 200:
            logger.info("登录成功！页面加载正常")
            return True
        
        logger.warning("登录状态不确定：请检查响应内容")
        return False
    
    def get_session(self):
        """获取登录后的 session 对象"""
        logger.info("开始获取登录后的 Session 对象")
        
        if self.load_session():
            logger.info("成功从文件加载有效的 Session 对象")
            return self.session
        
        logger.info("从文件加载 session 失败，开始登录")
        if self.login():
            logger.info("成功获取登录后的 Session 对象")
            return self.session
        
        logger.error("获取 Session 对象失败")
        return None
