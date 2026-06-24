"""
深信服验证码处理模块
"""
import requests
import logging
import ddddocr

logger = logging.getLogger('SangforCaptcha')


class SangforCaptchaHandler:
    """深信服验证码处理类"""
    
    def __init__(self, session):
        """
        初始化验证码处理器
        
        Args:
            session: requests Session 对象
        """
        self.session = session
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        logger.info("初始化深信服验证码处理器")
    
    def get_captcha(self, query_url):
        """
        获取并识别验证码
        
        Args:
            query_url: 查询页面 URL
            
        Returns:
            tuple: (验证码文本，idhash)
        """
        try:
            import random
            import re
            
            # 1. 生成随机数
            random_num = random.random()
            update_random = random.randint(10000, 99999)
            
            # 2. 构建验证码更新 URL
            captcha_update_url = f"https://bbs.sangfor.com.cn/misc.php?mod=seccode&action=update&idhash=cSjSGo8w&{random_num}&modid=plugin::service"
            logger.info(f"验证码更新 URL: {captcha_update_url}")
            
            # 3. 发送验证码更新请求
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://bbs.sangfor.com.cn/plugin.php?id=service:query"
            }
            
            captcha_response = self.session.get(captcha_update_url, headers=headers, timeout=10)
            captcha_response.encoding = "utf-8"
            
            # 4. 从响应中提取 idhash
            idhash_match = re.search(r'value="([\w]+)"[^.]*name="seccodehash"', captcha_response.text)
            if not idhash_match:
                idhash_match = re.search(r'idhash=([\w]+)', captcha_response.text)
            
            if idhash_match:
                idhash = idhash_match.group(1)
                logger.info(f"从响应中提取到 idhash: {idhash}")
            else:
                logger.warning("未从响应中提取到 idhash，使用默认值")
                idhash = "cSjSGo8w"
            
            # 5. 构建验证码图片 URL
            captcha_img_url = f"https://bbs.sangfor.com.cn/misc.php?mod=seccode&update={update_random}&idhash={idhash}"
            logger.info(f"验证码图片 URL: {captcha_img_url}")
            
            # 6. 获取验证码图片
            img_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://bbs.sangfor.com.cn/plugin.php?id=service:query"
            }
            
            img_response = self.session.get(captcha_img_url, headers=img_headers, timeout=10)
            
            if img_response.status_code == 200:
                # 保存验证码图片到临时目录
                captcha_path = '/tmp/captcha_debug.jpg'
                with open(captcha_path, 'wb') as f:
                    f.write(img_response.content)
                logger.info(f"已保存验证码图片到 {captcha_path}")
                
                # 使用 ddddocr 识别验证码
                result = self.ocr.classification(img_response.content)
                captcha_text = result[:4].upper()
                logger.info(f"验证码识别结果：{captcha_text}")
                
                return captcha_text, idhash
            else:
                logger.error(f"获取验证码图片失败，状态码：{img_response.status_code}")
                return None, idhash
            
        except Exception as e:
            logger.error(f"获取验证码异常：{str(e)}")
            return None, "cSjSGo8w"
