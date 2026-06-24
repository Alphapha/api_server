"""
华为验证码处理模块
"""
import requests
import logging
import ddddocr
import re

logger = logging.getLogger('HuaweiCaptcha')


class HuaweiCaptchaHandler:
    """华为验证码处理类"""
    
    def __init__(self, session):
        """
        初始化验证码处理器
        
        Args:
            session: requests Session 对象
        """
        self.session = session
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        # 华为查询页面
        self.query_page_url = "https://support.huawei.com/enterprise/zh/serialNumberQuery"
        logger.info("初始化华为验证码处理器")
    
    def get_captcha(self):
        """
        获取并识别验证码
        
        Returns:
            str: 识别的验证码文本
        """
        try:
            # 1. 先访问查询页面
            logger.info("访问华为查询页面")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive"
            }
            
            response = self.session.get(self.query_page_url, headers=headers, timeout=10)
            response.encoding = "utf-8"
            
            if response.status_code != 200:
                logger.error(f"访问查询页面失败，状态码：{response.status_code}")
                return None
            
            # 2. 从页面中提取验证码图片 URL
            # 通常验证码图片 URL 在 HTML 中
            logger.info("从页面中提取验证码图片 URL")
            
            # 尝试多种可能的验证码图片 URL 模式
            captcha_patterns = [
                r'captcha/image\?[^"\']+',
                r'verifyCode\.image\?[^"\']+',
                r'src=["\'][^"\']*captcha[^"\']*\.jpg["\']',
                r'src=["\'][^"\']*verifyCode[^"\']*\.jpg["\']'
            ]
            
            captcha_img_url = None
            for pattern in captcha_patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    captcha_img_url = match.group(0)
                    logger.info(f"找到验证码图片 URL: {captcha_img_url}")
                    break
            
            # 如果没找到，使用默认 URL
            if not captcha_img_url:
                logger.warning("未找到验证码图片 URL，使用默认地址")
                captcha_img_url = "https://support.huawei.com/enterprise/zh/captcha/image"
            
            # 3. 获取验证码图片
            logger.info("获取验证码图片")
            img_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": self.query_page_url
            }
            
            img_response = self.session.get(captcha_img_url, headers=img_headers, timeout=10)
            
            # 检查返回的是否是图片
            content_type = img_response.headers.get('Content-Type', '')
            logger.info(f"验证码响应 Content-Type: {content_type}")
            
            if img_response.status_code != 200 or ('image' not in content_type and len(img_response.content) < 100):
                logger.error(f"获取验证码失败，状态码：{img_response.status_code}, Content-Type: {content_type}")
                return None
            
            # 4. 保存验证码图片到临时目录（用于调试）
            captcha_path = '/tmp/huawei_captcha.jpg'
            with open(captcha_path, 'wb') as f:
                f.write(img_response.content)
            logger.info(f"已保存验证码图片到 {captcha_path}")
            
            # 5. 使用 ddddocr 识别验证码
            logger.info("使用 ddddocr 识别验证码")
            result = self.ocr.classification(img_response.content)
            
            # 取前 4 位并转大写
            captcha_text = result[:4].upper()
            logger.info(f"验证码识别结果：{captcha_text}")
            
            return captcha_text
            
        except Exception as e:
            logger.error(f"获取验证码异常：{str(e)}")
            return None
