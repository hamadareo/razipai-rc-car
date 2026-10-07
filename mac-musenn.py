import sys
import serial
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import time
import json
import glob

# ==========================================
# 【Mac用】 ポート設定
# ==========================================
# 接続されているTWELITEを自動検索
ports = glob.glob('/dev/cu.usbserial-*')
if ports:
    MAC_PORT = ports[0]
    print(f"🔍 TWELITEを自動検出しました: {MAC_PORT}")
else:
    MAC_PORT = '/dev/cu.usbserial-MW9ZUNWB'
    print(f"⚠️ 自動検出できませんでした。デフォルトのポートを使用します: {MAC_PORT}")
# ==========================================

latest_lqi = 0
last_lqi_time = 0
serial_buffer = ""

try:
    ser = serial.Serial(MAC_PORT, 115200, timeout=0)
    ser.write(':X\r\n'.encode('utf-8'))
except Exception as e:
    print(f"エラー: MONOSTICKが開けません: {e}")
    sys.exit(1)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>クラッドバスター Webコントローラー - PRO</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Orbitron:wght@500;700;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --neon-green: #00ff00;
            --neon-green-dim: rgba(0, 255, 0, 0.2);
            --dark-bg: #0d0d12;
            --panel-bg: #1a1a24;
            --text-main: #ffffff;
            --text-dim: #8892b0;
        }
        
        * { box-sizing: border-box; }
        
        body { 
            background-color: var(--dark-bg); 
            color: var(--text-main); 
            font-family: 'Inter', sans-serif; 
            margin: 0; 
            padding: 20px; 
            user-select: none;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }

        h1 { 
            font-family: 'Orbitron', sans-serif;
            color: var(--neon-green); 
            text-shadow: 0 0 10px var(--neon-green-dim);
            margin-top: 10px;
            text-align: center;
        }

        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            width: 100%;
            max-width: 800px;
            margin-top: 20px;
        }

        @media (max-width: 600px) {
            .dashboard {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--panel-bg);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid #333;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .panel h2 {
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            color: var(--text-dim);
            margin: 0 0 20px 0;
            text-transform: uppercase;
            letter-spacing: 2px;
            width: 100%;
            text-align: left;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }

        /* D-Pad */
        .dpad-container {
            display: grid;
            grid-template-columns: 60px 60px 60px;
            grid-template-rows: 60px 60px 60px;
            gap: 10px;
            justify-content: center;
            align-items: center;
        }
        
        .auto-btn {
            margin-top: 20px;
            width: 100%;
            padding: 15px;
            background: #2a2a35;
            color: var(--text-dim);
            border: 2px solid #333;
            border-radius: 12px;
            font-family: 'Orbitron', sans-serif;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
        }
        .auto-btn.active {
            background: rgba(255, 0, 255, 0.2);
            color: #ff00ff;
            border-color: #ff00ff;
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2);
        }

        .key { 
            width: 100%; 
            height: 100%; 
            background: #2a2a35; 
            border-radius: 12px; 
            font-size: 24px; 
            font-family: 'Orbitron', sans-serif;
            font-weight: bold; 
            display: flex;
            justify-content: center;
            align-items: center;
            transition: 0.1s; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
            cursor: pointer;
            border: 2px solid transparent;
        }
        
        .key.active { 
            background: var(--neon-green-dim); 
            color: var(--neon-green); 
            border-color: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green-dim); 
            transform: scale(0.95); 
        }

        #keyW { grid-column: 2; grid-row: 1; }
        #keyA { grid-column: 1; grid-row: 2; }
        #keyS { grid-column: 2; grid-row: 2; }
        #keyD { grid-column: 3; grid-row: 2; }

        /* Signal Meter */
        .gauge {
            width: 150px;
            height: 75px;
            position: relative;
            overflow: hidden;
            margin: 10px 0;
        }
        .gauge-bg {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: #333;
            position: absolute;
            top: 0;
            left: 0;
        }
        .gauge-fill {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: var(--neon-green);
            position: absolute;
            top: 0;
            left: 0;
            clip-path: polygon(0 50%, 100% 50%, 100% 100%, 0 100%);
            transform: rotate(-90deg);
            transition: transform 0.3s ease-out;
            transform-origin: 50% 50%;
        }
        .gauge-cover {
            width: 120px;
            height: 120px;
            background: var(--panel-bg);
            border-radius: 50%;
            position: absolute;
            top: 15px;
            left: 15px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            padding-top: 25px;
        }
        .lqi-value {
            font-family: 'Orbitron', sans-serif;
            font-size: 32px;
            font-weight: bold;
        }
        
        .status-badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 10px;
            background: #ff3b3b33;
            color: #ff3b3b;
            border: 1px solid #ff3b3b;
            transition: 0.3s;
        }
        .status-badge.connected {
            background: var(--neon-green-dim);
            color: var(--neon-green);
            border-color: var(--neon-green);
        }

        /* Logs */
        .log-container {
            width: 100%;
            height: 120px;
            background: #000;
            border-radius: 8px;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
            color: var(--text-dim);
            overflow-y: auto;
            text-align: left;
            border: 1px solid #333;
        }
        .log-entry { margin-bottom: 4px; }
        .log-entry.cmd { color: var(--neon-green); }

        .fullscreen-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            background: none;
            border: 1px solid var(--text-dim);
            color: var(--text-dim);
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            transition: 0.2s;
        }
        .fullscreen-btn:hover {
            color: #fff;
            border-color: #fff;
        }

        .instruction {
            color: var(--text-dim);
            font-size: 14px;
            margin-bottom: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <button class="fullscreen-btn" onclick="toggleFullScreen()">⛶ Fullscreen</button>
    
    <h1>RAD-PI PRO CONTROLLER</h1>
    <div class="instruction">キーボードの <b>W A S D</b> または画面のボタンで操作してください</div>
    
    <div class="dashboard">
        <!-- D-Pad Panel -->
        <div class="panel">
            <h2>Controls</h2>
            <div class="dpad-container">
                <div class="key" id="keyW" onmousedown="press('w')" onmouseup="release('w')" ontouchstart="press('w')" ontouchend="release('w')">W</div>
                <div class="key" id="keyA" onmousedown="press('a')" onmouseup="release('a')" ontouchstart="press('a')" ontouchend="release('a')">A</div>
                <div class="key" id="keyS" onmousedown="press('s')" onmouseup="release('s')" ontouchstart="press('s')" ontouchend="release('s')">S</div>
                <div class="key" id="keyD" onmousedown="press('d')" onmouseup="release('d')" ontouchstart="press('d')" ontouchend="release('d')">D</div>
            </div>
            <button id="btnAuto" class="auto-btn" onclick="toggleAuto()">🤖 AUTOPILOT: OFF</button>
            <button id="btnFlip" class="auto-btn active" onclick="toggleFlip()" style="margin-top: 10px;">🔄 CAMERA FLIP (180°): ON</button>
            <button id="btnColor" class="auto-btn" onclick="toggleColor()" style="margin-top: 10px;">⚫ 追跡カラー: ブラック (黒線を追跡)</button>
            
            <div style="margin-top: 20px; background: #2a2a35; padding: 10px; border-radius: 8px;">
                <label style="color: var(--text-dim); font-family: 'Orbitron'; font-size: 14px;">🎚️ 影フィルター (閾値): <span id="threshVal">60</span></label>
                <div style="font-size: 11px; color: #888; margin-bottom: 5px;">※数値を下げると影を無視します（線も消える場合は上げる）</div>
                <input type="range" id="threshSlider" min="10" max="150" value="60" oninput="updateThresh(this.value)" onchange="sendThresh(this.value)" style="width: 100%;">
            </div>
        </div>

        <!-- Telemetry Panel -->
        <div class="panel">
            <h2>Telemetry</h2>
            <div class="gauge">
                <div class="gauge-bg"></div>
                <div class="gauge-fill" id="gaugeFill"></div>
                <div class="gauge-cover">
                    <span class="lqi-value" id="lqiVal">0</span>
                </div>
            </div>
            <div style="font-size:12px; color:var(--text-dim);">SIGNAL STRENGTH (LQI)</div>
            
            <div class="status-badge" id="connStatus">DISCONNECTED</div>
        </div>
        
        <!-- Log Panel -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>System Logs</h2>
            <div class="log-container" id="logContainer">
                <div class="log-entry">System initialized. Ready for commands.</div>
            </div>
        </div>
    </div>

    <script>
        const keys = { w: false, a: false, s: false, d: false };
        let lastCmd = 'X';
        let lastCmdTime = Date.now();
        let isAutoMode = false;
        let isFlipped = true;

        function log(msg, type='info') {
            const container = document.getElementById('logContainer');
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
            entry.innerText = `[${time}] ${msg}`;
            container.appendChild(entry);
            container.scrollTop = container.scrollHeight;
            if(container.children.length > 20) container.removeChild(container.firstChild);
        }
        
        function toggleFlip() {
            isFlipped = !isFlipped;
            const btn = document.getElementById('btnFlip');
            if (isFlipped) {
                btn.classList.add('active');
                btn.innerText = '🔄 CAMERA FLIP (180°): ON';
                fetch('/cmd?c=FLIP1');
                log('Camera Flipped', 'info');
            } else {
                btn.classList.remove('active');
                btn.innerText = '🔄 CAMERA FLIP (180°): OFF';
                fetch('/cmd?c=FLIP0');
                log('Camera Flipped (Normal)', 'info');
            }
        }
        
        function toggleAuto() {
            isAutoMode = !isAutoMode;
            const btn = document.getElementById('btnAuto');
            if (isAutoMode) {
                btn.classList.add('active');
                btn.innerText = '🤖 AUTOPILOT: ON';
                fetch('/cmd?c=AUTO1');
                log('AutoPilot Enabled', 'success');
            } else {
                btn.classList.remove('active');
                btn.innerText = '🤖 AUTOPILOT: OFF';
                fetch('/cmd?c=AUTO0');
                log('AutoPilot Disabled', 'warning');
            }
        }
        
        function updateThresh(val) {
            document.getElementById('threshVal').innerText = val;
        }
        
        function sendThresh(val) {
            fetch('/cmd?c=THR' + val);
            log('Threshold changed to ' + val, 'info');
        }
        
        let lineMode = 0; // 0=Black, 1=White, 2=Red
        function toggleColor() {
            lineMode = (lineMode + 1) % 3;
            const btn = document.getElementById('btnColor');
            if (lineMode === 0) {
                btn.innerText = '⚫ 追跡カラー: ブラック (黒線を追跡)';
                fetch('/cmd?c=COL0');
                log('Tracking color set to Black', 'info');
            } else if (lineMode === 1) {
                btn.innerText = '⚪ 追跡カラー: ホワイト (白線を追跡)';
                fetch('/cmd?c=COL1');
                log('Tracking color set to White', 'info');
            } else if (lineMode === 2) {
                btn.innerText = '🔴 追跡カラー: レッド (赤線を追跡)';
                fetch('/cmd?c=COL2');
                log('Tracking color set to Red', 'info');
            }
        }

        function updateCmd() {
            let cmd = 'X';
            if (keys.w && keys.a) cmd = 'Q';
            else if (keys.w && keys.d) cmd = 'E';
            else if (keys.s && keys.a) cmd = 'Z';
            else if (keys.s && keys.d) cmd = 'C';
            else if (keys.w) cmd = 'W';
            else if (keys.s) cmd = 'S';
            else if (keys.a) cmd = 'A';
            else if (keys.d) cmd = 'D';

            // Manual override: if a key is pressed while in auto mode, disable auto mode!
            if (cmd !== 'X' && isAutoMode) {
                isAutoMode = false;
                const btn = document.getElementById('btnAuto');
                btn.classList.remove('active');
                btn.innerText = '🤖 AUTOPILOT: OFF';
                fetch('/cmd?c=AUTO0');
                log('Manual Override! Autopilot Disabled', 'cmd');
            }

            if (cmd !== lastCmd) {
                lastCmd = cmd;
                lastCmdTime = Date.now();
                
                // Only send manual commands if we are not in auto mode
                if (!isAutoMode) {
                    fetch(`/cmd?c=${cmd}`);
                    if(cmd !== 'X') log(`Transmitting: ${cmd}`, 'cmd');
                    else log(`Stop (X)`);
                }
            }
        }

        // Keyboard events
        window.addEventListener('keydown', (e) => {
            const key = e.key.toLowerCase();
            if (keys.hasOwnProperty(key) && !keys[key]) {
                keys[key] = true;
                const el = document.getElementById('key' + key.toUpperCase());
                if (el) el.classList.add('active');
                updateCmd();
            }
        });

        window.addEventListener('keyup', (e) => {
            const key = e.key.toLowerCase();
            if (keys.hasOwnProperty(key)) {
                keys[key] = false;
                const el = document.getElementById('key' + key.toUpperCase());
                if (el) el.classList.remove('active');
                updateCmd();
            }
        });
        
        // Touch/Mouse events
        function press(key) {
            if(!keys[key]) {
                keys[key] = true;
                const el = document.getElementById('key' + key.toUpperCase());
                if (el) el.classList.add('active');
                updateCmd();
            }
        }
        function release(key) {
            if(keys[key]) {
                keys[key] = false;
                const el = document.getElementById('key' + key.toUpperCase());
                if (el) el.classList.remove('active');
                updateCmd();
            }
        }
        // Prevent default touch behaviors
        document.addEventListener('contextmenu', event => event.preventDefault());

        // 安全対策: 指/カーソルがボタンの外に外れて離された場合や、
        // タブ/ウィンドウがフォーカスを失った場合に、押しっぱなし状態が残らないよう強制的に全キーを解除する
        function releaseAllKeys() {
            let changed = false;
            for (const k in keys) {
                if (keys[k]) {
                    keys[k] = false;
                    changed = true;
                    const el = document.getElementById('key' + k.toUpperCase());
                    if (el) el.classList.remove('active');
                }
            }
            if (changed) updateCmd();
        }
        window.addEventListener('mouseup', releaseAllKeys);
        window.addEventListener('touchend', releaseAllKeys);
        window.addEventListener('touchcancel', releaseAllKeys);
        window.addEventListener('blur', releaseAllKeys);
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) releaseAllKeys();
        });

        // Fullscreen toggle
        function toggleFullScreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {});
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
            }
        }

        // Telemetry Polling
        setInterval(() => {
            fetch('/status_data')
            .then(r => r.json())
            .then(data => {
                // Update Gauge (0-255 map to 0-180deg)
                const percent = Math.min(100, Math.max(0, data.lqi / 2.55));
                const degree = -90 + (percent * 1.8); 
                document.getElementById('gaugeFill').style.transform = `rotate(${degree}deg)`;
                
                // Update LQI Value (0-100)
                document.getElementById('lqiVal').innerText = Math.round(percent);
                
                // Update Status
                const badge = document.getElementById('connStatus');
                if (data.connected) {
                    if(!badge.classList.contains('connected')) {
                        badge.classList.add('connected');
                        badge.innerText = 'CONNECTED';
                        log('Telemetry link established', 'cmd');
                    }
                } else {
                    if(badge.classList.contains('connected')) {
                        badge.classList.remove('connected');
                        badge.innerText = 'DISCONNECTED';
                        log('Telemetry link lost', 'info');
                    }
                }
            }).catch(e => {});
        }, 500);

        // Heartbeat
        setInterval(() => {
            // 走行中（W/A/S/D）は無線衝突を防ぐためハートビートを送らない
            if (lastCmd === 'X' && (Date.now() - lastCmdTime > 1000)) {
                fetch('/cmd?c=H');
                // Don't log heartbeat to avoid spam
            }
        }, 1000);

    </script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    
    def do_GET(self):
        if self.path == '/':
            body = HTML_PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith('/cmd'):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'c' in params:
                cmd = params['c'][0].upper()
                if cmd in ['W','A','S','D','Q','E','Z','C','X','H', 'AUTO1', 'AUTO0', 'FLIP1', 'FLIP0', 'COL1', 'COL0', 'COL2'] or cmd.startswith('THR'):
                    try:
                        ser.write(f":{cmd}\r\n".encode('utf-8'))
                        if cmd != 'H':
                            print(f"📡 送信: {cmd}")
                    except:
                        pass
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(b'ok')
        elif self.path == '/status_data':
            global latest_lqi, last_lqi_time, serial_buffer
            try:
                chunk = ser.read(1024).decode('utf-8', errors='ignore')
                if chunk:
                    print(f"[RAW受信] {repr(chunk)}") # 生データを全て表示
                    serial_buffer += chunk
                    
                    import re
                    matches = re.findall(r':LQI=(\d+)', serial_buffer)
                    if matches:
                        latest_lqi = int(matches[-1])
                        last_lqi_time = time.time()
                        print(f"✅ 電波強度更新: {latest_lqi}")
                        serial_buffer = "" # 処理したらバッファをクリア
            except:
                pass
                
            is_active = (time.time() - last_lqi_time) < 3.0
            data = {
                'lqi': latest_lqi if is_active else 0,
                'connected': is_active
            }
            body = json.dumps(data).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            
    def log_message(self, format, *args):
        pass

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print("=========================================")
    print(f" 🌐 クラッドバスター PRO Webコントローラー起動！")
    print("=========================================")
    print(f"ブラウザ（SafariやChrome）を開いて、以下のアドレスにアクセスしてください！")
    print(f" 👉 http://localhost:{port}")
    print("=========================================")
    print("終了する場合はターミナルで Ctrl+C を押してください\\n")
    
    webbrowser.open(f'http://localhost:{port}')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.write(':X\r\n'.encode('utf-8'))
            ser.close()
        except:
            pass
        httpd.server_close()

if __name__ == '__main__':
    run()