from flask import Flask, send_file, request, jsonify
from PIL import Image, ImageDraw
import random
import io
import os
import base64
import time

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 验证码配置
SHAPE_SIZE = 50
BACKGROUND_IMAGE = 'background.jpg'
MARGIN = 10
THRESHOLD = 0.1  # 重合率阈值
TIMEOUT = 30  # 超时时间（秒）

# 全局存储验证数据
current_captcha = {
    'gap_x': None,
    'gap_y': None,
    'bg_img': None,
    'slider_img': None,
    'start_time': None
}

def generate_captcha():
    """生成验证码组件"""
    # 打开背景图
    orig_img = Image.open(BACKGROUND_IMAGE).convert('RGBA')
    width, height = orig_img.size
    
    # 固定垂直位置（确保滑块和缺口在同一水平线）
    y = (height - SHAPE_SIZE) // 2
    min_x = width // 2  # 右半部分
    max_x = width - SHAPE_SIZE - MARGIN
    gap_x = random.randint(min_x, max_x)
    gap_area = (gap_x, y, gap_x + SHAPE_SIZE, y + SHAPE_SIZE)
    
    # 生成带缺口的背景图
    bg_img = orig_img.copy()
    draw = ImageDraw.Draw(bg_img)
    draw.rectangle(gap_area, fill=(0, 0, 0, 0))
    
    # 生成滑块图（带2px白色边框和阴影效果）
    slider_img = orig_img.crop(gap_area)
    
    # 创建带样式的滑块
    bordered_slider = Image.new('RGBA', (SHAPE_SIZE+4, SHAPE_SIZE+4), (255,255,255,255))
    bordered_slider.paste(slider_img, (2, 2))
    
    # 保存验证数据
    current_captcha.update({
        'gap_x': gap_x,
        'gap_y': y,
        'bg_img': bg_img,
        'slider_img': bordered_slider,
        'start_time': time.time()
    })
    
    return bg_img, bordered_slider

@app.route('/captcha')
def get_captcha():
    """生成验证码并返回图片数据"""
    bg_img, slider_img = generate_captcha()
    
    # 将图片转换为base64
    bg_img_io = io.BytesIO()
    bg_img.save(bg_img_io, 'PNG')
    bg_img_io.seek(0)
    bg_img_base64 = base64.b64encode(bg_img_io.getvalue()).decode('utf-8')
    
    slider_img_io = io.BytesIO()
    slider_img.save(slider_img_io, 'PNG')
    slider_img_io.seek(0)
    slider_img_base64 = base64.b64encode(slider_img_io.getvalue()).decode('utf-8')
    
    return jsonify({
        "background": "data:image/png;base64," + bg_img_base64,
        "slider": "data:image/png;base64," + slider_img_base64,
        "slider_top": current_captcha['gap_y']  # 返回滑块应该放置的垂直位置
    })

@app.route('/')
def index():
    """前端页面"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>滑块验证码</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: #f5f5f5;
            }}
            .captcha-container {{
                width: 474px;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            #bg-image {{
                border: 1px solid #ddd;
                display: block;
                margin: 0 auto 15px;
            }}
            .slider-track {{
                width: 100%;
                height: {SHAPE_SIZE+4}px;
                position: relative;
                margin-top: 15px;
            }}
            #slider {{
                width: {SHAPE_SIZE+4}px;
                height: {SHAPE_SIZE+4}px;
                position: absolute;
                left: {MARGIN}px;
                cursor: grab;
                box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                border: 2px solid white;
                border-radius: 2px;
                z-index: 10;
            }}
            #slider.dragging {{
                cursor: grabbing;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }}
            .track-container {{
                width: 100%;
                height: 30px;
                position: relative;
                margin-top: 15px;
            }}
            .track {{
                width: 100%;
                height: 6px;
                background-color: #ccc;
                border-radius: 3px;
                position: relative;
            }}
            .thumb {{
                width: {SHAPE_SIZE+4}px;
                height: 30px;
                position: absolute;
                top: -12px;
                left: {MARGIN}px;
                cursor: grab;
                background-color: #4a6fa5;
                border-radius: 3px;
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10;
            }}
            .thumb.dragging {{
                cursor: grabbing;
                background-color: #6b8cae;
            }}
            .instructions {{
                text-align: center;
                color: #666;
                margin-bottom: 15px;
            }}
            #message {{
                text-align: center;
                margin-top: 15px;
                font-size: 18px;
                font-weight: bold;
            }}
            .success {{
                color: green;
            }}
            .error {{
                color: red;
            }}
        </style>
    </head>
    <body>
        <div class="captcha-container">
            <div class="instructions">请拖动下方滑钮到图片空缺处</div>
            <img id="bg-image" src="" width="474" height="266">
            <div class="slider-track">
                <img id="slider" src="">
            </div>
            <div class="track-container">
                <div class="track">
                    <div class="thumb"></div>
                </div>
            </div>
            <div id="message"></div>
        </div>

        <script>
            let isDragging = false;
            let startX = 0;
            let thumbStartX = {MARGIN};
            let sliderX = {MARGIN};

            function refreshCaptcha() {{
                // 获取验证码图片
                fetch('/captcha')
                    .then(response => response.json())
                    .then(data => {{
                        document.getElementById('bg-image').src = data.background;
                        document.getElementById('slider').src = data.slider;
                        // 设置滑块垂直位置与缺口对齐
                        document.getElementById('slider').style.top = data.slider_top + 'px';
                        document.getElementById('message').textContent = '';
                        document.getElementById('message').className = '';
                        document.getElementById('slider').style.left = '{MARGIN}px';
                        document.querySelector('.thumb').style.left = '{MARGIN}px';
                        sliderX = {MARGIN};
                    }});
            }}

            // 初始化
            refreshCaptcha();

            function verifyCaptcha() {{
                fetch('/verify', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ position: sliderX }})
                }})
                .then(response => response.json())
                .then(data => {{
                    const messageElement = document.getElementById('message');
                    if (data.success) {{
                        messageElement.textContent = '验证成功！';
                        messageElement.className = 'success';
                        // 验证成功后自动刷新
                        setTimeout(refreshCaptcha, 1000);
                    }} else {{
                        messageElement.textContent = '验证失败，请重试';
                        messageElement.className = 'error';
                        setTimeout(refreshCaptcha, 1500);
                    }}
                }});
            }}

            document.querySelector('.thumb').addEventListener('mousedown', (e) => {{
                isDragging = true;
                startX = e.clientX;
                thumbStartX = parseInt(document.querySelector('.thumb').style.left) || {MARGIN};
                document.querySelector('.thumb').classList.add('dragging');
                document.getElementById('slider').classList.add('dragging');
                e.preventDefault(); // 防止文本选中
            }});

            document.addEventListener('mousemove', (e) => {{
                if (isDragging) {{
                    const deltaX = e.clientX - startX;
                    const newLeft = thumbStartX + deltaX;
                    
                    // 限制移动范围
                    const trackWidth = document.querySelector('.track').offsetWidth;
                    const maxLeft = trackWidth - {SHAPE_SIZE+4};
                    
                    sliderX = Math.max({MARGIN}, Math.min(newLeft, maxLeft));
                    
                    document.getElementById('slider').style.left = sliderX + 'px';
                    document.querySelector('.thumb').style.left = sliderX + 'px';
                }}
            }});

            document.addEventListener('mouseup', () => {{
                if (isDragging) {{
                    isDragging = false;
                    document.querySelector('.thumb').classList.remove('dragging');
                    document.getElementById('slider').classList.remove('dragging');
                    verifyCaptcha();
                }}
            }});
        </script>
    </body>
    </html>
    '''

@app.route('/verify', methods=['POST'])
def verify():
    """验证滑动位置"""
    data = request.json
    slider_left = int(data.get('position', 0))  # 滑块左边界
    gap_left = current_captcha['gap_x']  # 缺口左边界
    
    # 计算滑块和缺口的坐标范围
    slider_right = slider_left + SHAPE_SIZE  # 滑块右边界
    gap_right = gap_left + SHAPE_SIZE  # 缺口右边界
    
    # 计算重合区域
    overlap_start = max(gap_left, slider_left)  # 重合区左边界
    overlap_end = min(gap_right, slider_right)  # 重合区右边界
    overlap_width = max(0, overlap_end - overlap_start)
    overlap_ratio = overlap_width / SHAPE_SIZE
    
    success = overlap_ratio >= THRESHOLD
    
    # 调试信息
    print(f"滑块位置: {slider_left}-{slider_right}, 缺口位置: {gap_left}-{gap_right}")
    print(f"重合宽度: {overlap_width}, 重合率: {overlap_ratio:.2f}, 验证结果: {success}")
    
    return jsonify({
        'success': success,
        'overlap_ratio': round(overlap_ratio, 2),
        'slider_position': slider_left,
        'gap_position': gap_left
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)