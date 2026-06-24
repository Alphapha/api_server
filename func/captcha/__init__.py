"""
本地验证码识别模块
使用 ddddocr 进行验证码识别
"""
import logging
import ddddocr

logger = logging.getLogger('CaptchaOCR')


class CaptchaRecognizer:
    """验证码识别器"""
    
    _instance = None
    _ocr = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化 OCR 识别器"""
        if self._ocr is None:
            logger.info("初始化 ddddocr 识别器")
            self._ocr = ddddocr.DdddOcr(show_ad=False)
    
    def recognize(self, img_bytes):
        """
        识别验证码
        
        Args:
            img_bytes: 验证码图片字节
            
        Returns:
            str: 验证码文本（4 位）
        """
        try:
            logger.info(f"开始识别验证码，图片大小：{len(img_bytes)} 字节")
            
            # 使用 ddddocr 识别
            result = self._ocr.classification(img_bytes)
            
            # 取前 4 位
            captcha_text = result[0:4].upper()
            
            logger.info(f"验证码识别结果：{captcha_text}")
            return captcha_text
            
        except Exception as e:
            logger.error(f"验证码识别失败：{str(e)}")
            return "ABCD"


def recognize_captcha(img_bytes):
    """
    便捷函数：识别验证码
    
    Args:
        img_bytes: 验证码图片字节
        
    Returns:
        str: 验证码文本（4 位）
    """
    recognizer = CaptchaRecognizer()
    return recognizer.recognize(img_bytes)
