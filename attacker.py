# attacker.py
import requests
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageStat, ImageMorph
import pytesseract
from io import BytesIO
import os
from collections import Counter

# 配置Tesseract路径
pytesseract.pytesseract.tesseract_cmd = r'F:\Trae CN\tesseract_ocr\tesseract.exe'

def process_image(img):
    """综合图像处理方法，包含动态阈值和形态学操作"""
    processed_images = []
    gray = img.convert('L')
    
    # 动态阈值计算（根据图像平均亮度调整）
    try:
        stat = ImageStat.Stat(gray)
        threshold = stat.mean[0] * 0.7  
    except:
        threshold = 120  
    
    # 基础二值化
    binary = gray.point(lambda x: 255 if x > threshold else 0)
    processed_images.append(binary)
    
    # 反色处理
    inverted = ImageOps.invert(binary)
    processed_images.append(inverted)
    
    # 高斯去噪后二值化
    denoised = gray.filter(ImageFilter.GaussianBlur(radius=0.8))  # 增大半径以增强去噪效果
    denoised_binary = denoised.point(lambda x: 255 if x > threshold else 0)
    processed_images.append(denoised_binary)
    
    # 形态学膨胀（连接断裂字符）
    morph = ImageMorph.MorphOp(op_name='dilation4')
    dilated, _ = morph.apply(binary)
    # 确保返回的是PIL.Image对象
    if isinstance(dilated, Image.Image):
        processed_images.append(dilated)
    elif isinstance(dilated, (int, float)):
        print(f"形态学操作返回了非图像对象（类型: {type(dilated)}），跳过此结果。")
    else:
        try:
            dilated = Image.fromarray(dilated)
            processed_images.append(dilated)
        except Exception as e:
            print(f"无法将形态学操作结果转换为PIL.Image对象: {e}")
    
    # 增强对比度+锐化
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)  # 增加对比度
    sharp = enhanced.filter(ImageFilter.SHARPEN)
    processed_images.append(sharp)
    
    return processed_images

def recognize_captcha(img):
    """识别验证码核心逻辑（仅添加后处理和加权投票）"""
    # OCR配置组合（覆盖多种可能性）
    configs = [
        # 更新白名单以仅包含数字和运算符
        ('--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789+-×÷', 1),
        ('--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789+-×÷', 1),
        ('--psm 10 --dpi 300 -c tessedit_char_whitelist=0123456789+-×÷', 3),  # 单字符模式权重更高
        ('--psm 13 -c tessedit_char_whitelist=0123456789+-×÷', 1),
        ('--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789+-×÷', 1),
        ('--psm 9 --oem 3 -c tessedit_char_whitelist=0123456789+-×÷', 1),
        ('--psm 11 --oem 3 -c tessedit_char_whitelist=0123456789+-×÷', 1)  # 新增配置
    ]
    
    candidates = []
    # 遍历所有处理后的图像版本
    for proc_img in process_image(img):
        # 尝试每种配置组合
        for config, weight in configs:
            try:
                text = pytesseract.image_to_string(proc_img, config=config).strip()
                # 新增后处理纠错
                text = post_process(text)
                if len(text) > 0:  # 调整条件，允许非5个字符的结果
                    # 加权添加候选（权重越大出现次数越多）
                    candidates.extend([text]*weight)
            except Exception as e:
                print(f"OCR识别出错：{str(e)}")
                continue
    
    # 如果没有候选结果，返回None
    if not candidates:
        return None
    
    # 投票机制选择出现次数最多的结果
    counter = Counter(candidates)
    print(f"候选结果统计：{counter.most_common()}")
    return counter.most_common(1)[0][0]

def post_process(text):
    """后处理纠正相似字符，保留原始大小写"""
    replace_rules = {
    }
    
    # 应用替换规则，保留原始大小写
    for wrong_char, correct_char in replace_rules.items():
        text = text.replace(wrong_char, correct_char)
    
    # 最终白名单过滤，仅保留数字和运算符
    return ''.join([c for c in text if c in '0123456789+-×÷'])

def recognize_and_save(session, debug=False):
    """获取并识别验证码，带有调试功能"""
    try:
        # 获取验证码
        response = session.get('http://localhost:8081/captcha')
        img = Image.open(BytesIO(response.content))
        
        # 识别验证码
        captcha = recognize_captcha(img)
        
        # 调试模式：保存处理过程
        if debug:
            save_dir = 'debug_images'
            os.makedirs(save_dir, exist_ok=True)
            for idx, proc_img in enumerate(process_image(img)):
                # 确保保存的是PIL.Image对象
                if isinstance(proc_img, Image.Image):
                    proc_img.save(os.path.join(save_dir, f'process_{idx}.png'))
                else:
                    print(f"无法保存第 {idx} 个处理后的图像，因为它不是有效的PIL.Image对象。")
            print(f"调试图片已保存至：{save_dir}")
        
        return captcha
    except Exception as e:
        print(f"处理出错：{str(e)}")
        return None

def test_ocr_accuracy(session, num_tests=10):
    """简单准确率测试（需要人工验证）"""
    correct = 0
    for i in range(num_tests):
        # 每次都开启调试模式保存图片
        captcha = recognize_and_save(session, debug=True)
        print(f"第{i+1}次识别结果：{captcha}")
        # 输入真实值验证
        true_value = input("请输入实际验证码内容：").strip()
        if captcha and captcha == true_value:
            correct += 1
    print(f"准确率：{correct}/{num_tests} ({(correct/num_tests)*100:.1f}%)")

if __name__ == '__main__':
    session = requests.Session()
    # 启动准确率测试
    test_ocr_accuracy(session, num_tests=10)