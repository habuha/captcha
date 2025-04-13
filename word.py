from flask import Flask, request, session, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageTransform
import random
import string
import io
import time
import base64

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # 生产环境需要更安全的密钥

# 验证码配置
IMG_WIDTH = 400
IMG_HEIGHT = 200
NOISE_POINTS = 500  # 增加噪点数量
FONT_SIZE = 27  # 字体大小
HANDLE_SIZE = 33  # 点击区域大小
TIMEOUT = 30  # 超时时间（秒）

# 1000个常用汉字列表
HANZI_LIST = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社事者平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严"

def generate_hanzi_list():
    """随机生成4个汉字"""
    return random.sample(HANZI_LIST, 4)

def generate_captcha_image(hanzi_list):
    """生成验证码图片"""
    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 添加噪点
    for _ in range(NOISE_POINTS):
        draw.point([random.randint(0, IMG_WIDTH), random.randint(0, IMG_HEIGHT)],
                   fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

    # 随机打乱汉字的顺序
    shuffled_hanzi_list = hanzi_list.copy()
    random.shuffle(shuffled_hanzi_list)

    # 绘制汉字并扭曲
    positions = []
    for i, hanzi in enumerate(shuffled_hanzi_list):
        x = random.randint(50 + i * 80, 100 + i * 80)
        y = random.randint(50, IMG_HEIGHT - 50)
        positions.append((x, y))

        # 创建一个新的图像用于绘制单个汉字
        char_img = Image.new('RGB', (FONT_SIZE, FONT_SIZE), color=(255, 255, 255))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((0, 0), hanzi, fill=(0, 0, 0), font=ImageFont.truetype("FZSTK.TTF", FONT_SIZE))

        # 扭曲汉字
        distortion = random.uniform(-0.1, 0.1)
        matrix = (1, distortion, 0, distortion, 1, 0)
        char_img = char_img.transform((FONT_SIZE, FONT_SIZE), Image.AFFINE, matrix, Image.BICUBIC)

        # 将扭曲后的汉字粘贴到主图像上
        img.paste(char_img, (x, y))

    # 在汉字之上添加干扰线
    # 增加干扰线长度和粗度
    for _ in range(7):  # 增加干扰线数量
        # 干扰线可以跨越整个图片
        start_x = random.randint(0, IMG_WIDTH)
        start_y = random.randint(0, IMG_HEIGHT)
        end_x = random.randint(0, IMG_WIDTH)
        end_y = random.randint(0, IMG_HEIGHT)
        # 线宽增加到3-5像素
        draw.line((start_x, start_y, end_x, end_y), 
                 fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
                 width=random.randint(2, 3))

    # 添加干扰线集中在图片中央
    center_x = IMG_WIDTH // 2
    center_y = IMG_HEIGHT // 2
    for _ in range(10):
        start_x = random.randint(center_x - 50, center_x + 50)
        start_y = random.randint(center_y - 50, center_y + 50)
        end_x = random.randint(center_x - 50, center_x + 50)
        end_y = random.randint(center_y - 50, center_y + 50)
        draw.line((start_x, start_y, end_x, end_y), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

    return img, shuffled_hanzi_list, positions

@app.route('/captcha')
def get_captcha():
    """生成验证码并返回提示信息"""
    hanzi_list = generate_hanzi_list()
    img, shuffled_hanzi_list, positions = generate_captcha_image(hanzi_list)

    # 存储验证码信息
    session['captcha'] = {
        'hanzi_list': hanzi_list,
        'shuffled_hanzi_list': shuffled_hanzi_list,
        'positions': positions,
        'start_time': time.time()
    }

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    # 返回图片和提示信息
    return jsonify({
        "image": "data:image/png;base64," + base64.b64encode(img_io.getvalue()).decode('utf-8'),
        "prompt": " ".join(hanzi_list)
    })

@app.route('/verify', methods=['POST'])
def verify():
    """验证用户点击顺序"""
    user_clicks = request.json.get('clicks', [])
    mouse_trace = request.json.get('mouse_trace', [])
    operation_time = request.json.get('operation_time', 0)

    captcha_info = session.get('captcha', {})
    hanzi_list = captcha_info.get('hanzi_list', [])
    start_time = captcha_info.get('start_time', 0)

    # 检查超时
    if time.time() - start_time > TIMEOUT:
        session.pop('captcha', None)
        return jsonify({"status": "timeout", "message": "验证超时"})

    # 简单的鼠标轨迹和操作速度验证
    if len(mouse_trace) < 3 or operation_time < 1:
        session.pop('captcha', None)
        return jsonify({"status": "failure", "message": "验证失败，可能是机器操作"})

    # 检查点击顺序
    if user_clicks == hanzi_list:
        session.pop('captcha', None)
        return jsonify({"status": "success", "message": "验证成功"})
    else:
        session.pop('captcha', None)
        return jsonify({"status": "failure", "message": "验证失败"})

@app.route('/check_click', methods=['POST'])
def check_click():
    """处理点击事件"""
    click_data = request.json
    x = click_data.get('x')
    y = click_data.get('y')
    captcha_info = session.get('captcha', {})
    shuffled_hanzi_list = captcha_info.get('shuffled_hanzi_list', [])
    positions = captcha_info.get('positions', [])

    # 检查点击位置是否在某个汉字区域内
    for i, pos in enumerate(positions):
        # 判断点击位置是否在汉字的区域内
        if abs(x - pos[0]) <= FONT_SIZE and abs(y - pos[1]) <= FONT_SIZE:
            return jsonify({
                "status": "success",
                "hanzi": shuffled_hanzi_list[i],
                "center_x": pos[0],  # 汉字的中心 X 坐标
                "center_y": pos[1]   # 汉字的中心 Y 坐标
            })

    return jsonify({"status": "failure"})

@app.route('/')
def index():
    """前端页面"""
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
        // 获取验证码图片和提示信息
        fetch('/captcha')
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

                // 清除所有遮罩层
                const container = document.getElementById('captcha-container');
                const overlays = container.querySelectorAll('.overlay');
                overlays.forEach(overlay => overlay.remove());
                
                // 重置计时器
                startTimer();
            });
    }

    // 初始化
    refreshCaptcha();
    startTimer();

    function verifyCaptcha() {
        const operationTime = (Date.now() - startTime) / 1000;
        fetch('/verify', {
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

        fetch('/check_click', {
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

                // 创建遮罩层
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082)
