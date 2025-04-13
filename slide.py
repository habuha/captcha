from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFilter
import random
import io
import time
import math
import os
import numpy as np
from datetime import datetime

app = Flask(__name__)

# 存储验证信息的字典
verification_data = {}

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
        self.max_speed = 1500          # 最大速度（像素/秒）
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

# 创建验证码生成器和轨迹分析器实例
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
                const response = await fetch('/get_captcha');
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
                bgImage.style.backgroundImage = `url('/bg_image/${verifyId}')`;
                
                const gapImage = document.getElementById('gapImage');
                gapImage.src = `/gap_image/${verifyId}`;
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
                const response = await fetch('/verify', {
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

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/get_captcha')
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

@app.route('/bg_image/<verify_id>')
def get_bg_image(verify_id):
    """获取背景图片"""
    if verify_id in verification_data:
        bg_byte_io = io.BytesIO()
        verification_data[verify_id]['bg_image'].save(bg_byte_io, format='PNG')
        bg_byte_io.seek(0)
        return send_file(bg_byte_io, mimetype='image/png')
    return 'Invalid verify_id', 400

@app.route('/gap_image/<verify_id>')
def get_gap_image(verify_id):
    """获取缺口图片"""
    if verify_id in verification_data:
        gap_byte_io = io.BytesIO()
        verification_data[verify_id]['gap_image'].save(gap_byte_io, format='PNG')
        gap_byte_io.seek(0)
        return send_file(gap_byte_io, mimetype='image/png')
    return 'Invalid verify_id', 400

@app.route('/verify', methods=['POST'])
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
    if abs(x - verify_data['gap_x']) <= 10:
        # 验证成功后删除验证数据
        del verification_data[verify_id]
        return jsonify({'success': True, 'message': '验证成功'})
    
    return jsonify({'success': False, 'message': '验证失败，请重试'})

if __name__ == '__main__':
    # 确保背景图片目录存在
    os.makedirs('static', exist_ok=True)
    app.run(debug=True)
