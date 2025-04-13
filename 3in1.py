import base64 
from flask import Flask, Blueprint, render_template, request, jsonify, send_file, session
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import io
import time
import math
import os
import numpy as np
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # 生产环境需要更安全的密钥

# 配置
REQUEST_LIMIT = 8  # 10秒内最多8次请求
TIME_WINDOW = 10  # 10秒时间窗口
CAPTCHA_TIMEOUT = 30  # 验证码30秒过期
TIMEOUT = 30  # 超时时间（秒）

# IP频率限制相关变量
ip_request_count = defaultdict(int)
ip_first_request_time = {}

# 数学验证码配置
CAPTCHA_LENGTH = 5
IMG_WIDTH = 300  # 宽度增加50%
IMG_HEIGHT = 100  # 高度增加66%
NOISE_POINTS = 100  # 噪点数量增加
FONT_SIZE = 20  # 字体放大
LINE_NUM = 3  # 干扰线数量增加

# 汉字验证码配置
HANZI_IMG_WIDTH = 400
HANZI_IMG_HEIGHT = 200
HANZI_NOISE_POINTS = 500  # 增加噪点数量
HANZI_FONT_SIZE = 27  # 字体大小
HANDLE_SIZE = 33  # 点击区域大小
HANZI_LIST = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社事者平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严"

# 滑块验证码配置
class CaptchaGenerator:
    def __init__(self):
        self.bg_width = 300  # 背景图片宽度
        self.bg_height = 150  # 背景图片高度
        self.gap_width = 40   # 缺口宽度
        self.gap_height = 40  # 缺口高度
        self.bg_dir = 'static'  # 背景图片目录
        self.expire_time = 30  # 验证码有效期（秒）

    def _get_random_bg_image(self):
        """随机获取一张背景图片"""
        bg_files = [f for f in os.listdir(self.bg_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        bg_file = random.choice(bg_files)
        bg_path = os.path.join(self.bg_dir, bg_file)
        return Image.open(bg_path).convert('RGBA')

    def _create_gap_area(self, bg_image):
        """创建真实缺口和陷阱缺口"""
        # 生成真实缺口位置
        gap_x = random.randint(100, self.bg_width - self.gap_width - 50)
        gap_y = random.randint(10, self.bg_height - self.gap_height - 10)

        # 生成陷阱缺口位置（确保与真实缺口有足够距离且不在同一高度）
        while True:
            trap_x = random.randint(50, self.bg_width - self.gap_width - 50)
            trap_y = random.randint(10, self.bg_height - self.gap_height - 10)
            
            # 确保陷阱缺口与真实缺口的距离足够远（至少80像素）且不在同一高度（至少30像素）
            distance = math.sqrt((trap_x - gap_x)**2 + (trap_y - gap_y)**2)
            height_diff = abs(trap_y - gap_y)
            
            if distance >= 80 and height_diff >= 30:
                break

        # 创建真实缺口图片
        gap_image = bg_image.crop((gap_x, gap_y, gap_x + self.gap_width, gap_y + self.gap_height))
        
        # 在背景图上绘制半透明遮罩（包括真实缺口和陷阱缺口）
        mask = Image.new('RGBA', bg_image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(mask)
        
        # 绘制真实缺口遮罩
        draw.rectangle([(gap_x, gap_y), (gap_x + self.gap_width, gap_y + self.gap_height)], 
                      fill=(255, 255, 255, 128))
        
        # 绘制陷阱缺口遮罩（稍微透明一些）
        draw.rectangle([(trap_x, trap_y), (trap_x + self.gap_width, trap_y + self.gap_height)], 
                      fill=(255, 255, 255, 100))
        
        # 将遮罩应用到背景图
        bg_image = Image.alpha_composite(bg_image, mask)
        
        return bg_image, gap_image, gap_x, gap_y, trap_x, trap_y

    def generate(self):
        """生成验证码"""
        # 获取并调整背景图片大小
        bg_image = self._get_random_bg_image()
        bg_image = bg_image.resize((self.bg_width, self.bg_height))
        
        # 创建缺口
        bg_image, gap_image, gap_x, gap_y, trap_x, trap_y = self._create_gap_area(bg_image)
        
        return {
            'bg_image': bg_image,
            'gap_image': gap_image,
            'gap_x': gap_x,
            'gap_y': gap_y,
            'trap_x': trap_x,
            'trap_y': trap_y,
            'gap_width': self.gap_width,
            'gap_height': self.gap_height,
            'expire_time': self.expire_time
        }

class TrackAnalyzer:
    def __init__(self):
        self.min_track_length = 10     # 最小轨迹点数
        self.max_speed = 2000          # 最大速度（像素/秒）
        self.max_deviation = 50        # 最大垂直偏移
        self.min_y_changes = 3         # 最小Y轴变化次数
        self.min_y_change = 1          # 最小Y轴变化幅度（像素）
        self.max_slide_time = 5000     # 最大滑动时间（毫秒）
        self.min_slide_time = 100      # 最小滑动时间（毫秒）

    def analyze_tracks(self, tracks):
        """分析鼠标轨迹是否合理"""
        if len(tracks) < self.min_track_length:
            return False, "轨迹过短"

        # 计算总滑动时间
        total_time = tracks[-1]['timestamp'] - tracks[0]['timestamp']
        if total_time > self.max_slide_time:
            return False, "滑动时间过长"
        if total_time < self.min_slide_time:
            return False, "滑动时间过短"

        # 记录Y轴方向的变化次数
        y_changes = 0
        last_y = tracks[0]['y']
        
        # 检查速度和Y轴变化
        for i in range(1, len(tracks)):
            prev = tracks[i-1]
            curr = tracks[i]
            
            # 计算两点间的时间和距离
            dt = (curr['timestamp'] - prev['timestamp']) / 1000  # 转换为秒
            if dt == 0:
                return False, "移动速度异常"
                
            dx = curr['x'] - prev['x']
            dy = curr['y'] - prev['y']
            
            # 计算速度
            speed = math.sqrt(dx*dx + dy*dy) / dt
            if speed > self.max_speed:
                return False, "移动速度过快"
            
            # 检查垂直方向的偏移
            if abs(dy) > self.max_deviation:
                return False, "垂直移动幅度过大"
            
            # 检测Y轴的变化
            if abs(curr['y'] - last_y) >= self.min_y_change:
                y_changes += 1
                last_y = curr['y']

        # 如果Y轴变化次数太少，判定为机器操作
        if y_changes < self.min_y_changes:
            return False, "移动轨迹过于平直"

        return True, "轨迹正常"

# 蓝图定义
math_captcha_bp = Blueprint('math_captcha', __name__, url_prefix='/math')
word_captcha_bp = Blueprint('word_captcha', __name__, url_prefix='/word')
slide_captcha_bp = Blueprint('slide_captcha', __name__, url_prefix='/slide')

# 数学验证码部分
def generate_math_expression():
    operators = ['+', '-', '×', '÷']
    op = random.choice(operators)

    if op == '+':
        a = random.randint(0, 99)
        b = random.randint(0, 99)
        result = a + b
    elif op == '-':
        a = random.randint(50, 99)
        b = random.randint(0, a-10)
        result = a - b
    elif op == '×':
        a = random.randint(0, 99)
        b = random.randint(0, 10)
        result = a * b
    elif op == '÷':
        b = random.randint(1, 10)
        a = b * random.randint(0, 50)
        result = a // b

    expression = f"{a} {op} {b}"
    return expression, str(result)

def generate_captcha():
    expression, result = generate_math_expression()

    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 添加渐变背景
    for y in range(IMG_HEIGHT):
        r = 240 + int(15 * y / IMG_HEIGHT)
        g = 245 + int(10 * y / IMG_HEIGHT)
        b = 255 - int(15 * y / IMG_HEIGHT)
        draw.line([(0, y), (IMG_WIDTH, y)], fill=(r, g, b))

    try:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)
    except:
        font = ImageFont.load_default()
        char_spacing = FONT_SIZE * 0.8
    else:
        bbox = draw.textbbox((0, 0), expression, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        char_spacing = FONT_SIZE * 0.5

    x = (IMG_WIDTH - text_width) // 2 if font else (IMG_WIDTH - len(expression) * char_spacing) // 2
    y = (IMG_HEIGHT - text_height) // 2 if font else (IMG_HEIGHT - FONT_SIZE) // 2

    for i, char in enumerate(expression):
        if font:
            char_width = draw.textlength(char, font=font)
        else:
            char_width = char_spacing
        
        draw.text((x + random.randint(-3, 3), y + random.randint(-2, 2)),
                  char,
                  fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)),
                  font=font)
        x += char_width + random.randint(8, 12)

    for _ in range(LINE_NUM):
        center_x = IMG_WIDTH // 2
        center_y = IMG_HEIGHT // 2
        start_x = random.randint(center_x - 50, center_x + 50)
        start_y = random.randint(center_y - 30, center_y + 30)
        
        for _ in range(3):
            end_x = start_x + random.randint(-40, 40)
            end_y = start_y + random.randint(-20, 20)
            control_x = (start_x + end_x) // 2 + random.randint(-10, 10)
            control_y = (start_y + end_y) // 2 + random.randint(-5, 5)
            
            end_x = max(0, min(end_x, IMG_WIDTH))
            end_y = max(0, min(end_y, IMG_HEIGHT))
            
            draw.line([(start_x, start_y), (control_x, control_y), (end_x, end_y)],
                     fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)),
                     width=3, joint="curve")
            start_x, start_y = end_x, end_y

    for _ in range(NOISE_POINTS):
        size = random.choice([1, 1, 1, 2])
        x0 = random.randint(0, IMG_WIDTH - 1)
        y0 = random.randint(0, IMG_HEIGHT - 1)
        x1 = x0 + size
        y1 = y0 + size
        if x1 >= IMG_WIDTH:
            x1 = IMG_WIDTH - 1
        if y1 >= IMG_HEIGHT:
            y1 = IMG_HEIGHT - 1
        draw.ellipse([x0, y0, x1, y1], 
                    fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

    return img, result

@math_captcha_bp.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>数学验证码</title>
        <style>
            body {
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                font-family: 'Arial', sans-serif;
            }
            .container {
                background: rgba(255,255,255,0.9);
                padding: 30px 50px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                text-align: center;
            }
            h1 {
                color: #2c3e50;
                margin-bottom: 25px;
            }
            img {
                border: 2px solid #ddd;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
            img:hover {
                transform: scale(1.02);
            }
            form {
                margin-top: 25px;
            }
            input[type="text"] {
                padding: 12px 20px;
                font-size: 16px;
                border: 2px solid #3498db;
                border-radius: 25px;
                width: 200px;
                margin-right: 10px;
                transition: all 0.3s ease;
            }
            input[type="text"]:focus {
                outline: none;
                border-color: #2980b9;
                box-shadow: 0 0 8px rgba(52,152,219,0.3);
            }
            button {
                padding: 12px 25px;
                font-size: 16px;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            button:hover {
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            .timer {
                margin-top: 15px;
                font-size: 14px;
                color: #666;
            }
            .expired {
                color: red;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>数学验证码</h1>
            <img src="/math/captcha" alt="验证码" onclick="refreshCaptcha()" 
                 style="cursor: pointer; width: 300px; height: 100px;">
            <form action="/math/verify" method="POST" onsubmit="return verifyCaptcha(event)">
                <input type="text" name="captcha" placeholder="输入计算结果" autocomplete="off">
                <button type="submit">验证答案</button>
            </form>
            <div class="timer" id="timer">验证码有效时间: 30秒</div>
        </div>

        <script>
            let countdown = 30;
            let timerInterval;
            
            function startTimer() {
                clearInterval(timerInterval);
                countdown = 30;
                updateTimerDisplay();
                
                timerInterval = setInterval(() => {
                    countdown--;
                    updateTimerDisplay();
                    
                    if (countdown <= 0) {
                        clearInterval(timerInterval);
                        document.getElementById('timer').textContent = '验证码已过期，正在自动刷新...';
                        document.getElementById('timer').className = 'timer expired';
                        refreshCaptcha();  // 添加自动刷新功能
                    }
                }, 1000);
            }
            
            function updateTimerDisplay() {
                const timerElement = document.getElementById('timer');
                timerElement.textContent = `验证码有效时间: ${countdown}秒`;
                timerElement.className = 'timer';
            }

            function refreshCaptcha() {
                const img = document.querySelector('img');
                img.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    img.src = '/math/captcha?' + Date.now();
                    img.style.transform = 'scale(1)';
                    startTimer(); // 刷新验证码时重置计时器
                }, 300);
            }

            // 初始化计时器
            window.onload = startTimer;

            async function verifyCaptcha(event) {
                event.preventDefault();
                const form = event.target;
                const input = form.querySelector('input');
                
                if (!input.value.trim()) {
                    alert('请输入计算结果');
                    return;
                }

                const response = await fetch('/math/verify', {
                    method: 'POST',
                    body: new FormData(form)
                });
                
                const result = await response.text();
                alert(result);
                refreshCaptcha();
                form.reset();
                input.focus();
            }
        </script>
    </body>
    </html>
    """

@math_captcha_bp.route('/captcha')
def get_captcha():
    client_ip = request.remote_addr
    current_time = time.time()
    
    if client_ip in ip_first_request_time:
        if current_time - ip_first_request_time[client_ip] > TIME_WINDOW:
            ip_request_count[client_ip] = 0
            ip_first_request_time[client_ip] = current_time
        elif ip_request_count[client_ip] >= REQUEST_LIMIT:
            return "请求过于频繁，请稍后再试", 429
    else:
        ip_first_request_time[client_ip] = current_time
    
    ip_request_count[client_ip] += 1

    img, captcha_text = generate_captcha()
    session['captcha'] = captcha_text
    session['captcha_time'] = time.time()  # 记录验证码生成时间

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

@math_captcha_bp.route('/verify', methods=['POST'])
def verify():
    if 'captcha_time' not in session or time.time() - session['captcha_time'] > CAPTCHA_TIMEOUT:
        return "验证码已过期，请刷新后重试", 403

    user_input = request.form.get('captcha', '').lower()
    server_captcha = session.get('captcha', '').lower()

    if user_input == server_captcha:
        session.pop('captcha', None)
        session.pop('captcha_time', None)
        return "验证成功！"
    return "验证失败！"

# 汉字验证码部分
def generate_hanzi_list():
    return random.sample(HANZI_LIST, 4)

def generate_captcha_image(hanzi_list):
    img = Image.new('RGB', (HANZI_IMG_WIDTH, HANZI_IMG_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    for _ in range(HANZI_NOISE_POINTS):
        draw.point([random.randint(0, HANZI_IMG_WIDTH), random.randint(0, HANZI_IMG_HEIGHT)],
                   fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

    shuffled_hanzi_list = hanzi_list.copy()
    random.shuffle(shuffled_hanzi_list)

    positions = []
    for i, hanzi in enumerate(shuffled_hanzi_list):
        x = random.randint(50 + i * 80, 100 + i * 80)
        y = random.randint(50, HANZI_IMG_HEIGHT - 50)
        positions.append((x, y))

        char_img = Image.new('RGB', (HANZI_FONT_SIZE, HANZI_FONT_SIZE), color=(255, 255, 255))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((0, 0), hanzi, fill=(0, 0, 0), font=ImageFont.truetype("FZSTK.TTF", HANZI_FONT_SIZE))

        distortion = random.uniform(-0.1, 0.1)
        matrix = (1, distortion, 0, distortion, 1, 0)
        char_img = char_img.transform((HANZI_FONT_SIZE, HANZI_FONT_SIZE), Image.AFFINE, matrix, Image.BICUBIC)

        img.paste(char_img, (x, y))

    for _ in range(7):
        start_x = random.randint(0, HANZI_IMG_WIDTH)
        start_y = random.randint(0, HANZI_IMG_HEIGHT)
        end_x = random.randint(0, HANZI_IMG_WIDTH)
        end_y = random.randint(0, HANZI_IMG_HEIGHT)
        draw.line((start_x, start_y, end_x, end_y), 
                 fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
                 width=random.randint(2, 3))

    center_x = HANZI_IMG_WIDTH // 2
    center_y = HANZI_IMG_HEIGHT // 2
    for _ in range(10):
        start_x = random.randint(center_x - 50, center_x + 50)
        start_y = random.randint(center_y - 50, center_y + 50)
        end_x = random.randint(center_x - 50, center_x + 50)
        end_y = random.randint(center_y - 50, center_y + 50)
        draw.line((start_x, start_y, end_x, end_y), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

    return img, shuffled_hanzi_list, positions

@word_captcha_bp.route('/')
def index():
    return """
    <style>
    :root {
        --primary-color: #4a6fa5;
        --secondary-color: #6b8cae;
        --background-color: #f5f7fa;
        --text-color: #333;
        --success-color: #4caf50;
        --failure-color: #f44336;
    }

    body {
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        margin: 0;
        font-family: 'Arial', sans-serif;
        transition: background 0.5s ease;
    }

    .container {
        background-color: white;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        padding: 30px;
        width: 500px;
        text-align: center;
    }

    h1 {
        color: var(--primary-color);
        margin-bottom: 30px;
    }

    #captcha-container {
        position: relative;
        display: inline-block;
        margin-bottom: 20px;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
    }

    #captcha {
        cursor: pointer;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        width: 100%;
        border-radius: 10px;
    }

    #captcha:hover {
        transform: scale(1.02);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
    }

    #prompt {
        font-size: 20px;
        color: var(--text-color);
        margin-top: 20px;
        min-height: 30px;
    }

    .overlay {
        position: absolute;
        width: 40px;
        height: 40px;
        background-color: rgba(0, 0, 0, 0.5);
        border-radius: 50%;
        pointer-events: none;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    .overlay span {
        color: white;
        font-size: 20px;
        font-weight: bold;
    }

    .success-message {
        color: var(--success-color);
        font-weight: bold;
        font-size: 18px;
        margin-top: 20px;
        animation: fadeIn 0.5s;
    }

    .failure-message {
        color: var(--failure-color);
        font-weight: bold;
        font-size: 18px;
        margin-top: 20px;
        animation: fadeIn 0.5s;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    </style>
    <div class="container">
        <h1>点选验证码示例</h1>
        <div id="captcha-container">
            <img id="captcha" src="" alt="验证码">
        </div>
        <p id="prompt"></p>
        <div id="message"></div>
        <div class="timer" id="timer">验证码有效时间: 30秒</div>
    </div>
    <script>
    let clicks = [];
    let promptText = '';
    let mouseTrace = [];
    let startTime = 0;
    let countdown = 30;
    let timerInterval;

    function startTimer() {
        clearInterval(timerInterval);
        countdown = 30;
        updateTimerDisplay();
        
        timerInterval = setInterval(() => {
            countdown--;
            updateTimerDisplay();
            
            if (countdown <= 0) {
                clearInterval(timerInterval);
                document.getElementById('timer').textContent = '验证码已过期，正在自动刷新...';
                document.getElementById('timer').className = 'timer expired';
                refreshCaptcha();
            }
        }, 1000);
    }

    function updateTimerDisplay() {
        const timerElement = document.getElementById('timer');
        timerElement.textContent = `验证码有效时间: ${countdown}秒`;
        timerElement.className = 'timer';
    }

    function refreshCaptcha() {
        fetch('/word/captcha')
            .then(response => response.json())
            .then(data => {
                const img = document.getElementById('captcha');
                img.src = data.image;
                clicks = [];
                mouseTrace = [];
                startTime = Date.now();
                promptText = data.prompt;
                document.getElementById('prompt').textContent = promptText;
                document.getElementById('message').textContent = '';

                const container = document.getElementById('captcha-container');
                const overlays = container.querySelectorAll('.overlay');
                overlays.forEach(overlay => overlay.remove());
                
                startTimer();
            });
    }

    refreshCaptcha();
    startTimer();

    function verifyCaptcha() {
        const operationTime = (Date.now() - startTime) / 1000;
        fetch('/word/verify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ clicks: clicks, mouse_trace: mouseTrace, operation_time: operationTime })
        })
        .then(response => response.json())
        .then(data => {
            const messageElement = document.getElementById('message');
            messageElement.textContent = data.message;

            if (data.status === 'success') {
                messageElement.className = 'success-message';
            } else if (data.status === 'failure') {
                messageElement.className = 'failure-message';
            } else if (data.status === 'timeout') {
                messageElement.className = 'failure-message';
            }

            setTimeout(() => {
                refreshCaptcha();
            }, 1500);
        });
    }

    document.getElementById('captcha').addEventListener('mousemove', (e) => {
        const rect = e.target.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        mouseTrace.push([x, y]);
    });

    document.getElementById('captcha').addEventListener('click', (e) => {
        const rect = e.target.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        fetch('/word/check_click', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ x: x, y: y })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                clicks.push(data.hanzi);

                const overlay = document.createElement('div');
                overlay.className = 'overlay';
                overlay.style.left = `${x - 20}px`;
                overlay.style.top = `${y - 20}px`;

                const number = document.createElement('span');
                number.textContent = clicks.length;
                overlay.appendChild(number);

                document.getElementById('captcha').parentElement.appendChild(overlay);

                if (clicks.length === 4) {
                    verifyCaptcha();
                }
            }
        });
    });
    </script>
    """

@word_captcha_bp.route('/captcha')
def get_captcha():
    hanzi_list = generate_hanzi_list()
    img, shuffled_hanzi_list, positions = generate_captcha_image(hanzi_list)

    session['captcha'] = {
        'hanzi_list': hanzi_list,
        'shuffled_hanzi_list': shuffled_hanzi_list,
        'positions': positions,
        'start_time': time.time()
    }

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return jsonify({
        "image": "data:image/png;base64," + base64.b64encode(img_io.getvalue()).decode('utf-8'),
        "prompt": " ".join(hanzi_list)
    })

@word_captcha_bp.route('/verify', methods=['POST'])
def verify():
    user_clicks = request.json.get('clicks', [])
    mouse_trace = request.json.get('mouse_trace', [])
    operation_time = request.json.get('operation_time', 0)

    captcha_info = session.get('captcha', {})
    hanzi_list = captcha_info.get('hanzi_list', [])
    start_time = captcha_info.get('start_time', 0)

    if time.time() - start_time > TIMEOUT:
        session.pop('captcha', None)
        return jsonify({"status": "timeout", "message": "验证超时"})

    if len(mouse_trace) < 3 or operation_time < 1:
        session.pop('captcha', None)
        return jsonify({"status": "failure", "message": "验证失败，可能是机器操作"})

    if user_clicks == hanzi_list:
        session.pop('captcha', None)
        return jsonify({"status": "success", "message": "验证成功"})
    else:
        session.pop('captcha', None)
        return jsonify({"status": "failure", "message": "验证失败"})

@word_captcha_bp.route('/check_click', methods=['POST'])
def check_click():
    click_data = request.json
    x = click_data.get('x')
    y = click_data.get('y')
    captcha_info = session.get('captcha', {})
    shuffled_hanzi_list = captcha_info.get('shuffled_hanzi_list', [])
    positions = captcha_info.get('positions', [])

    for i, pos in enumerate(positions):
        if abs(x - pos[0]) <= HANZI_FONT_SIZE and abs(y - pos[1]) <= HANZI_FONT_SIZE:
            return jsonify({
                "status": "success",
                "hanzi": shuffled_hanzi_list[i],
                "center_x": pos[0],
                "center_y": pos[1]
            })

    return jsonify({"status": "failure"})

# 滑块验证码部分
verification_data = {}
captcha_generator = CaptchaGenerator()
track_analyzer = TrackAnalyzer()

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>滑块验证码</title>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background-color: #f5f5f5;
            font-family: Arial, sans-serif;
        }

        .captcha-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            width: 300px;
        }

        .image-container {
            position: relative;
            width: 100%;
            height: 150px;
            overflow: hidden;
            margin-bottom: 10px;
        }

        .bg-image {
            width: 100%;
            height: 100%;
            background-size: cover;
            background-position: center;
        }

        .gap-image, .trap-image {
            position: absolute;
            pointer-events: none;
            z-index: 2;
            left: 0;
        }

        .trap-image {
            opacity: 0.7;
        }

        .slider-container {
            position: relative;
            width: 100%;
            height: 40px;
            background-color: #f0f0f0;
            border-radius: 20px;
            overflow: visible;
            box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.1);
        }

        .slider {
            position: absolute;
            width: 44px;
            height: 44px;
            top: -2px;
            left: -2px;
            background: linear-gradient(145deg, #ffffff, #e6e6e6);
            border-radius: 50%;
            cursor: pointer;
            user-select: none;
            box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.1),
                       -2px -2px 6px rgba(255, 255, 255, 0.8),
                       inset 2px 2px 4px rgba(255, 255, 255, 0.8),
                       inset -2px -2px 4px rgba(0, 0, 0, 0.05);
            border: 2px solid #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: box-shadow 0.2s ease;
            z-index: 10;
        }

        .slider::before {
            content: '';
            width: 20px;
            height: 20px;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%234CAF50"><path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z"/></svg>') no-repeat center;
            background-size: contain;
        }

        .slider:hover {
            box-shadow: 3px 3px 8px rgba(0, 0, 0, 0.15),
                       -3px -3px 8px rgba(255, 255, 255, 0.9),
                       inset 2px 2px 4px rgba(255, 255, 255, 0.8),
                       inset -2px -2px 4px rgba(0, 0, 0, 0.05);
        }

        .slider:active {
            cursor: grabbing;
            box-shadow: 1px 1px 4px rgba(0, 0, 0, 0.1),
                       -1px -1px 4px rgba(255, 255, 255, 0.7),
                       inset 3px 3px 6px rgba(0, 0, 0, 0.05),
                       inset -3px -3px 6px rgba(255, 255, 255, 0.7);
        }

        .slider.dragging {
            cursor: grabbing;
            background: linear-gradient(145deg, #e6e6e6, #ffffff);
        }

        .message {
            margin-top: 10px;
            text-align: center;
            height: 20px;
            color: #666;
            font-size: 14px;
        }

        .timer {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.5);
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            z-index: 3;
        }

        .timer.warning {
            background: rgba(255, 77, 79, 0.7);
        }

        .refresh-button {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.8);
            border: none;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 3;
        }

        .refresh-button:hover {
            background: rgba(255, 255, 255, 0.9);
        }

        .refresh-icon {
            width: 20px;
            height: 20px;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%234CAF50"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>');
            background-size: contain;
        }
    </style>
</head>
<body>
    <div class="captcha-container">
        <div class="image-container">
            <div id="bgImage" class="bg-image"></div>
            <img id="gapImage" class="gap-image" alt="缺口">
            <div id="trapImage" class="trap-image"></div>
            <div id="timer" class="timer">30s</div>
            <button class="refresh-button" onclick="getCaptcha()">
                <div class="refresh-icon"></div>
            </button>
        </div>
        <div class="slider-container">
            <div id="slider" class="slider"></div>
        </div>
        <div id="message" class="message">请拖动滑块完成验证</div>
    </div>

    <script>
        let isDragging = false;
        let startX = 0;
        let currentX = 0;
        let verifyId = '';
        let mouseTracks = [];
        let countdownTimer = null;
        let expireTime = 30;

        function updateTimer(remainingTime) {
            const timer = document.getElementById('timer');
            if (remainingTime <= 0) {
                timer.textContent = '0s';
                clearInterval(countdownTimer);
                getCaptcha();
                return;
            }
            timer.textContent = `${remainingTime}s`;
            
            if (remainingTime <= 5) {
                timer.classList.add('warning');
            } else {
                timer.classList.remove('warning');
            }
        }

        function startCountdown(duration) {
            if (countdownTimer) {
                clearInterval(countdownTimer);
            }
            
            updateTimer(duration);
            
            const endTime = Date.now() + duration * 1000;
            
            countdownTimer = setInterval(() => {
                const remainingTime = Math.ceil((endTime - Date.now()) / 1000);
                updateTimer(remainingTime);
            }, 1000);
        }

        async function getCaptcha() {
            try {
                const response = await fetch('/slide/get_captcha');
                const data = await response.json();
                
                if (!data.verify_id || !data.expire_time || 
                    !data.gap_x || !data.gap_y || 
                    !data.trap_x || !data.trap_y || 
                    !data.gap_width || !data.gap_height) {
                    throw new Error('验证码数据不完整');
                }

                verifyId = data.verify_id;
                expireTime = parseInt(data.expire_time);
                
                const bgImage = document.getElementById('bgImage');
                bgImage.style.backgroundImage = `url('/slide/bg_image/${verifyId}')`;
                
                const gapImage = document.getElementById('gapImage');
                gapImage.src = `/slide/gap_image/${verifyId}`;
                gapImage.style.width = `${data.gap_width}px`;
                gapImage.style.height = `${data.gap_height}px`;
                gapImage.style.top = `${data.gap_y}px`;
                gapImage.style.transform = 'translateX(0)';
                
                const trapImage = document.getElementById('trapImage');
                trapImage.style.width = `${data.gap_width}px`;
                trapImage.style.height = `${data.gap_height}px`;
                trapImage.style.top = `${data.trap_y}px`;
                trapImage.style.transform = 'translateX(0)';
                
                const slider = document.getElementById('slider');
                slider.style.left = '-2px';
                
                document.getElementById('message').textContent = '请拖动滑块完成验证';
                document.getElementById('message').style.color = '#666';
                
                mouseTracks = [];
                
                startCountdown(expireTime);
            } catch (error) {
                console.error('获取验证码失败:', error);
                document.getElementById('message').textContent = '加载验证码失败，请刷新重试';
                document.getElementById('message').style.color = '#ff4d4f';
            }
        }

        const slider = document.getElementById('slider');
        const gapImage = document.getElementById('gapImage');
        const sliderContainer = document.querySelector('.slider-container');

        function handleDragStart(e) {
            isDragging = true;
            const rect = slider.getBoundingClientRect();
            startX = (e.type === 'mousedown' ? e.clientX : e.touches[0].clientX) - rect.left;
            mouseTracks = [];
            document.getElementById('message').textContent = '';
            
            slider.classList.add('dragging');
            
            slider.style.transition = 'none';
            gapImage.style.transition = 'none';
            
            e.preventDefault();
        }

        function handleDragMove(e) {
            if (!isDragging) return;
            
            e.preventDefault();
            
            const clientX = e.type === 'mousemove' ? e.clientX : e.touches[0].clientX;
            const containerRect = sliderContainer.getBoundingClientRect();
            const maxX = containerRect.width - slider.offsetWidth;
            
            let newX = clientX - startX - containerRect.left;
            newX = Math.max(-2, Math.min(newX, maxX + 2));
            
            slider.style.left = `${newX}px`;
            
            const trapImage = document.getElementById('trapImage');
            const translateX = newX + 2;
            
            gapImage.style.transform = `translateX(${translateX}px)`;
            trapImage.style.transform = `translateX(${translateX}px)`;
            
            currentX = translateX;
            
            mouseTracks.push({
                x: clientX,
                y: e.type === 'mousemove' ? e.clientY : e.touches[0].clientY,
                timestamp: Date.now()
            });
        }

        function handleDragEnd() {
            if (!isDragging) return;
            isDragging = false;
            
            slider.classList.remove('dragging');
            
            slider.style.transition = 'left 0.3s';
            const gapImage = document.getElementById('gapImage');
            const trapImage = document.getElementById('trapImage');
            gapImage.style.transition = 'transform 0.3s';
            trapImage.style.transition = 'transform 0.3s';
            
            verifyPosition();
        }

        async function verifyPosition() {
            try {
                const response = await fetch('/slide/verify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        verify_id: verifyId,
                        x: currentX,
                        mouse_tracks: mouseTracks
                    })
                });
                
                const result = await response.json();
                const message = document.getElementById('message');
                message.textContent = result.message;
                message.style.color = result.success ? '#52c41a' : '#ff4d4f';
                
                if (result.success) {
                    setTimeout(() => {
                        getCaptcha();
                    }, 1000);
                } else {
                    const slider = document.getElementById('slider');
                    const gapImage = document.getElementById('gapImage');
                    const trapImage = document.getElementById('trapImage');
                    
                    slider.style.left = '-2px';
                    gapImage.style.transform = 'translateX(0)';
                    trapImage.style.transform = 'translateX(0)';
                }
            } catch (error) {
                console.error('验证请求失败:', error);
                document.getElementById('message').textContent = '网络错误，请重试';
                document.getElementById('message').style.color = '#ff4d4f';
            }
        }

        slider.addEventListener('mousedown', handleDragStart);
        document.addEventListener('mousemove', handleDragMove);
        document.addEventListener('mouseup', handleDragEnd);

        slider.addEventListener('touchstart', handleDragStart, { passive: false });
        document.addEventListener('touchmove', handleDragMove, { passive: false });
        document.addEventListener('touchend', handleDragEnd);

        document.addEventListener('selectstart', (e) => {
            if (isDragging) {
                e.preventDefault();
            }
        });

        document.addEventListener('DOMContentLoaded', getCaptcha);
    </script>
</body>
</html>
'''

@slide_captcha_bp.route('/')
def index():
    return HTML_TEMPLATE

@slide_captcha_bp.route('/get_captcha')
def get_captcha():
    """获取新的验证码"""
    # 生成验证码
    captcha_data = captcha_generator.generate()
    
    # 生成验证ID
    verify_id = str(random.randint(100000, 999999))
    
    # 存储验证信息
    verification_data[verify_id] = {
        'bg_image': captcha_data['bg_image'],
        'gap_image': captcha_data['gap_image'],
        'gap_x': captcha_data['gap_x'],
        'gap_y': captcha_data['gap_y'],
        'trap_x': captcha_data['trap_x'],
        'trap_y': captcha_data['trap_y'],
        'start_time': time.time(),
        'expire_time': captcha_data['expire_time']
    }
    
    return jsonify({
        'verify_id': verify_id,
        'gap_x': captcha_data['gap_x'],
        'gap_y': captcha_data['gap_y'],
        'trap_x': captcha_data['trap_x'],
        'trap_y': captcha_data['trap_y'],
        'gap_width': captcha_data['gap_width'],
        'gap_height': captcha_data['gap_height'],
        'expire_time': captcha_data['expire_time']
    })

@slide_captcha_bp.route('/bg_image/<verify_id>')
def get_bg_image(verify_id):
    """获取背景图片"""
    if verify_id in verification_data:
        bg_byte_io = io.BytesIO()
        verification_data[verify_id]['bg_image'].save(bg_byte_io, format='PNG')
        bg_byte_io.seek(0)
        return send_file(bg_byte_io, mimetype='image/png')
    return 'Invalid verify_id', 400

@slide_captcha_bp.route('/gap_image/<verify_id>')
def get_gap_image(verify_id):
    """获取缺口图片"""
    if verify_id in verification_data:
        gap_byte_io = io.BytesIO()
        verification_data[verify_id]['gap_image'].save(gap_byte_io, format='PNG')
        gap_byte_io.seek(0)
        return send_file(gap_byte_io, mimetype='image/png')
    return 'Invalid verify_id', 400

@slide_captcha_bp.route('/verify', methods=['POST'])
def verify():
    """验证滑块位置"""
    data = request.json
    verify_id = data.get('verify_id')
    x = data.get('x')
    tracks = data.get('mouse_tracks', [])
    
    if not verify_id or verify_id not in verification_data:
        return jsonify({'success': False, 'message': '验证失败，请重试'})
    
    verify_data = verification_data[verify_id]
    
    # 检查是否过期
    elapsed_time = time.time() - verify_data['start_time']
    if elapsed_time > verify_data['expire_time']:
        del verification_data[verify_id]
        return jsonify({'success': False, 'message': '验证码已过期'})
    
    # 分析轨迹
    is_valid_track, _ = track_analyzer.analyze_tracks(tracks)
    if not is_valid_track:
        return jsonify({
            'success': False, 
            'message': '出现异常行为'
        })
    
    # 检查是否点击了陷阱缺口
    trap_distance = abs(x - verify_data['trap_x'])
    if trap_distance <= 10:
        return jsonify({'success': False, 'message': '验证失败，请重试'})
    
    # 验证位置（允许10像素的误差）
    if abs(x - verify_data['gap_x']) <= 5:
        # 验证成功后删除验证数据
        del verification_data[verify_id]
        return jsonify({'success': True, 'message': '验证成功'})
    
    return jsonify({'success': False, 'message': '验证失败，请重试'})

# 注册蓝图
app.register_blueprint(math_captcha_bp)
app.register_blueprint(word_captcha_bp)
app.register_blueprint(slide_captcha_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)