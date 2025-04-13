from flask import Flask, request, session, send_file
from PIL import Image, ImageDraw, ImageFont
import random
import io
from datetime import datetime, timedelta
import time
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 验证码配置（放大尺寸）
CAPTCHA_LENGTH = 5
IMG_WIDTH = 300  # 宽度增加50%
IMG_HEIGHT = 100  # 高度增加66%
NOISE_POINTS = 100  # 噪点数量增加
FONT_SIZE = 20  # 字体放大
LINE_NUM = 3  # 干扰线数量增加

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

    # 创建渐变背景图像
    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 添加渐变背景
    for y in range(IMG_HEIGHT):
        r = 240 + int(15 * y/IMG_HEIGHT)
        g = 245 + int(10 * y/IMG_HEIGHT)
        b = 255 - int(15 * y/IMG_HEIGHT)
        draw.line([(0, y), (IMG_WIDTH, y)], fill=(r, g, b))

    try:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)
    except:
        font = ImageFont.load_default()
        char_spacing = FONT_SIZE * 0.8
    else:
        bbox = draw.textbbox((0,0), expression, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        char_spacing = FONT_SIZE * 0.5

    x = (IMG_WIDTH - text_width) // 2 if font else (IMG_WIDTH - len(expression)*char_spacing) // 2
    y = (IMG_HEIGHT - text_height) // 2 if font else (IMG_HEIGHT - FONT_SIZE) // 2

    # 绘制带阴影的文字
    for i, char in enumerate(expression):
        if font:
            char_width = draw.textlength(char, font=font)
        else:
            char_width = char_spacing
        
        # 文字阴影（减小偏移量和透明度）
        shadow_offset = 1  # 从2减小到1
        draw.text((x + shadow_offset + random.randint(-2,2),  # 减小随机偏移范围
                  y + shadow_offset + random.randint(-1,1)),
                  char, fill=(180,180,180),  # 调亮阴影颜色
                  font=font)
        
        # 主文字
        draw.text((x + random.randint(-3,3), 
                  y + random.randint(-2,2)),
                  char,
                  fill=(random.randint(0,100), random.randint(0,100), random.randint(0,100)),
                  font=font)
        x += char_width + random.randint(8,12)

    # 添加曲线干扰线
    for _ in range(LINE_NUM):
        # 让干扰线起点更集中在中心区域
        center_x = IMG_WIDTH // 2
        center_y = IMG_HEIGHT // 2
        start_x = random.randint(center_x - 50, center_x + 50)
        start_y = random.randint(center_y - 30, center_y + 30)
        
        # 减小弯曲程度和随机偏移范围
        for _ in range(3):  # 三段曲线
            # 限制终点在中心区域附近
            end_x = start_x + random.randint(-40, 40)
            end_y = start_y + random.randint(-20, 20)
            # 控制点更靠近直线中点，减小弯曲程度
            control_x = (start_x + end_x) // 2 + random.randint(-10, 10)
            control_y = (start_y + end_y) // 2 + random.randint(-5, 5)
            
            # 确保线条不会超出图像边界
            end_x = max(0, min(end_x, IMG_WIDTH))
            end_y = max(0, min(end_y, IMG_HEIGHT))
            
            draw.line([(start_x, start_y), (control_x, control_y), (end_x, end_y)],
                     fill=(random.randint(100,200), random.randint(100,200), random.randint(100,200)),
                     width=3, joint="curve")
            start_x, start_y = end_x, end_y

    # 添加动态噪点
    for _ in range(NOISE_POINTS):
        size = random.choice([1,1,1,2])  # 90%小点，10%稍大点
        x0 = random.randint(0, IMG_WIDTH - 1)
        y0 = random.randint(0, IMG_HEIGHT - 1)
        x1 = x0 + size
        y1 = y0 + size
        # 确保坐标不超出图像边界
        if x1 >= IMG_WIDTH:
            x1 = IMG_WIDTH - 1
        if y1 >= IMG_HEIGHT:
            y1 = IMG_HEIGHT - 1
        draw.ellipse([x0, y0, x1, y1], 
                    fill=(random.randint(0,255), random.randint(0,255), random.randint(0,255)))

    return img, result

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>验证码示例</title>
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
            <img src="/captcha" alt="验证码" onclick="refreshCaptcha()" 
                 style="cursor: pointer; width: 300px; height: 100px;">
            <form action="/verify" method="POST" onsubmit="return verifyCaptcha(event)">
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
                    img.src = '/captcha?' + Date.now();
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

                const response = await fetch('/verify', {
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

# 添加IP频率限制相关变量
ip_request_count = defaultdict(int)
ip_first_request_time = {}
REQUEST_LIMIT = 8  # 10秒内最多8次请求
TIME_WINDOW = 10  # 10秒时间窗口
CAPTCHA_TIMEOUT = 30  # 验证码30秒过期

@app.route('/captcha')
def get_captcha():
    # IP频率限制检查
    client_ip = request.remote_addr
    current_time = time.time()
    
    if client_ip in ip_first_request_time:
        if current_time - ip_first_request_time[client_ip] > TIME_WINDOW:
            # 超过时间窗口，重置计数器
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

@app.route('/verify', methods=['POST'])
def verify():
    # 检查验证码是否过期
    if 'captcha_time' not in session or time.time() - session['captcha_time'] > CAPTCHA_TIMEOUT:
        return "验证码已过期，请刷新后重试", 403

    user_input = request.form.get('captcha', '').lower()
    server_captcha = session.get('captcha', '').lower()

    if user_input == server_captcha:
        session.pop('captcha', None)
        session.pop('captcha_time', None)
        return "验证成功！"
    return "验证失败！"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
