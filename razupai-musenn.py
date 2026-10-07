import serial
import time
import threading

# ==========================================
# 【ラズパイ用】 ポート設定
# ==========================================
PORT_MONO = '/dev/ttyUSB0'  # ラズパイに刺さっている受信機MONOSTICK
PORT_ARD = '/dev/ttyACM0'   # ラズパイに繋がっているArduino
# ==========================================

# ==========================================
# OpenCVとカメラの設定
# ==========================================
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("⚠️ OpenCV (cv2) がインストールされていません。ライントレース機能は無効になります。")

is_auto_mode = False
is_flipped = True
line_color_mode = 0 # 0=Black, 1=White, 2=Red
last_cx = 80 # 線を見失った時の復帰用
threshold_val = 60 # 影フィルターの閾値
brake_toggle = False # 急カーブ時の減速用トグル

# auto_pilot_loop（別スレッド）とメインループが同時にArduinoへ書き込むと
# コマンド文字列が壊れて手動操作が無視されることがあるため、排他制御する
ard_lock = threading.Lock()

def write_ard(data: bytes):
    try:
        if 'ser_ard' in globals() and ser_ard.is_open:
            with ard_lock:
                ser_ard.write(data)
    except Exception:
        pass

# オートパイロット中、直近にコマンドを送った時刻。
# カメラスレッドが詰まった/フレーム取得に失敗し続けた場合の暴走防止ウォッチドッグに使う
last_auto_cmd_time = time.time()

def auto_watchdog():
    global last_auto_cmd_time
    while True:
        time.sleep(0.1)
        if is_auto_mode and (time.time() - last_auto_cmd_time) > 0.3:
            # 0.3秒以上オートパイロットから新しい命令が来ていない＝カメラ処理が詰まっている可能性
            # 直前の命令のまま暴走させないよう、安全のため強制停止する
            write_ard(b":X\r\n")

threading.Thread(target=auto_watchdog, daemon=True).start()

def auto_pilot_loop():
    global is_auto_mode, is_flipped, line_color_mode, last_cx, threshold_val, brake_toggle, last_auto_cmd_time
    if not HAS_CV2:
        return
        
    # --- カメラモジュール3 (libcamera) 完全対応のカメラ検索 ---
    cap = None
    picam2 = None
    
    # 候補1: ラズパイ公式の Picamera2 ライブラリを使用（カメラモジュール3の最適解）
    try:
        print("🔍 ラズパイ公式の Picamera2 を使ってカメラを起動中...")
        from picamera2 import Picamera2
        picam2 = Picamera2()
        # 視野角(FOV)を最大化するため、センサー全体を使う広角解像度（640x480）を指定
        config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
        picam2.configure(config)
        picam2.start()
        print("✅ Picamera2 でカメラの起動に成功しました！")
    except Exception as e:
        print(f"⚠️ Picamera2での起動に失敗しました。他の方法を探します... ({e})")
        picam2 = None
        
        # 候補2: 従来の OpenCV (V4L2)
        candidates = [0, 2, 4, -1, 1, 3]
        for candidate in candidates:
            temp_cap = cv2.VideoCapture(candidate)
            name = f"ポート {candidate}"
                
            if temp_cap.isOpened():
                ret, frame = temp_cap.read()
                if ret and frame is not None:
                    print(f"✅ {name} で画像の取得に成功しました！")
                    cap = temp_cap
                    # 広角を維持するため大きめの解像度を指定
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    break
                else:
                    temp_cap.release()
    
    if not picam2 and (not cap or not cap.isOpened()):
        print("❌ どの方法でもカメラ映像が取得できませんでした。")
        return
        
    print("📷 カメラ初期化完了。ライントレース準備OK！")
        
    while True:
        if picam2:
            try:
                frame_rgb = picam2.capture_array()
                # OpenCVはBGR形式なので変換
                frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                ret = True
            except:
                ret = False
        else:
            ret, frame = cap.read()
            
        if not ret:
            # カメラ映像が取れない間、直前の命令のまま暴走させないよう安全停止する
            if is_auto_mode:
                write_ard(b":X\r\n")
                last_auto_cmd_time = time.time()
            time.sleep(0.1)
            continue
            
        # カメラから取得した広角画像を、処理を軽くするために160x120に縮小する
        frame = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_LINEAR)
            
        # 画面反転がONの場合は上下左右反転（180度回転）
        if is_flipped:
            frame = cv2.flip(frame, -1)
            
        # 視野を最大限に広げてカーブを先読みするため、画面全体を使う
        h, w = frame.shape[:2]
        crop_img = frame[0:h, 0:w]
        debug_img = crop_img.copy()

        if is_auto_mode:
            if line_color_mode == 0 or line_color_mode == 1:
                gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
                blur = cv2.GaussianBlur(gray, (5, 5), 0)
                if line_color_mode == 0:
                    # 黒線を追跡（閾値以下を抽出）
                    _, thresh = cv2.threshold(blur, threshold_val, 255, cv2.THRESH_BINARY_INV)
                else:
                    # 白線を追跡（閾値以上を抽出）
                    _, thresh = cv2.threshold(blur, threshold_val, 255, cv2.THRESH_BINARY)
            elif line_color_mode == 2:
                blur_bgr = cv2.GaussianBlur(crop_img, (5, 5), 0)
                # 赤線を追跡（HSV色空間で赤色を抽出）
                hsv = cv2.cvtColor(blur_bgr, cv2.COLOR_BGR2HSV)
                # Webからの閾値を、抽出する色の「彩度(S)」と「明度(V)」の下限として利用する
                # （数値を上げると、より鮮やかな赤だけを拾うようになる）
                lower_red1 = np.array([0, threshold_val, threshold_val])
                upper_red1 = np.array([10, 255, 255])
                lower_red2 = np.array([160, threshold_val, threshold_val])
                upper_red2 = np.array([180, 255, 255])
                
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                thresh = cv2.bitwise_or(mask1, mask2)
                
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # --- HUD (ヘッドアップディスプレイ) の描画 ---
            roi_h = crop_img.shape[0]
            # 1. 認識有効エリアの境界線 (これより下に触れていないと無視)
            cv2.line(debug_img, (0, roi_h - 40), (w, roi_h - 40), (255, 0, 255), 1)
            # 2. 直進(STRAIGHT)と判定する「あそび」の境界線
            cv2.line(debug_img, (65, 0), (65, roi_h), (255, 255, 0), 1)
            cv2.line(debug_img, (95, 0), (95, roi_h), (255, 255, 0), 1)
            
            # 【究極のノイズ対策：足元から繋がっている線だけを抽出】
            valid_contours = []
            
            for c in contours:
                area = cv2.contourArea(c)
                if 30 < area < 10000:
                    x, y, w_box, h_box = cv2.boundingRect(c)
                    
                    # 1. 画面の一番下（手前）から繋がっている線か？
                    touches_bottom = (y + h_box) >= (roi_h - 15)
                    
                    if touches_bottom:
                        # 【見失い防止】足元から繋がっている場合は、カーブで形が歪んでいても無条件で「線」と信用する
                        valid_contours.append(c)
                    else:
                        # 2. カーブを少し通り過ぎて、線が足元から離れて浮いてしまった場合
                        is_horizontal = w_box > (h_box * 1.5)
                        extent = area / (w_box * h_box)
                        is_curve = extent < 0.6
                        
                        if is_horizontal or is_curve:
                            # 遠くにある椅子の脚や影を誤認識しないよう、浮いている図形には厳格な細長さフィルターをかける
                            perimeter = cv2.arcLength(c, True)
                            if area > 0:
                                complexity = (perimeter * perimeter) / area
                                if complexity > 18:
                                    valid_contours.append(c)
            
            cmd = 'X'
            if len(valid_contours) > 0:
                # 複数候補がある場合は、前回の線の位置（last_cx）に一番近いものを「追跡中の線」とみなす
                def get_cx(cnt):
                    M = cv2.moments(cnt)
                    return int(M['m10'] / M['m00']) if M['m00'] > 0 else float('inf')
                    
                c = min(valid_contours, key=lambda cnt: abs(get_cx(cnt) - last_cx))
                
                M = cv2.moments(c)
                if M['m00'] > 0:
                    cx_mass = int(M['m10'] / M['m00'])
                    cy_mass = int(M['m01'] / M['m00'])
                    
                    # 線の「一番奥（上）」の座標を取得
                    extTop = tuple(c[c[:, :, 1].argmin()][0])
                    top_x = extTop[0]
                    top_y = extTop[1]
                    
                    # 【改善: スーパー先読みステアリング（Pure Pursuit）】
                    # モーターのパワー不足でブレーキ（QとAの交互送信）だと車が止まってしまうため、常にアクセル全開（Q/E）で走る。
                    # その代わり、スピードが出た状態でも曲がりきれるように、一番奥の点（80%）を強く重視して「超早め」にハンドルを切る！
                    cx = int((cx_mass * 0.2) + (top_x * 0.8))
                    last_cx = cx
                    
                    # プレビュー描画（黄色=重心、紫=奥の点、赤=実際の目標）
                    cv2.drawContours(debug_img, [c], -1, (0, 255, 0), 2)
                    cv2.circle(debug_img, (cx_mass, cy_mass), 4, (0, 255, 255), -1)
                    cv2.circle(debug_img, (top_x, top_y), 4, (255, 0, 255), -1)
                    cv2.circle(debug_img, (cx, cy_mass), 6, (0, 0, 255), -1)
                    
                    # 画面幅160、中心は80。
                    # cxが画面端に近いほど「線を見失いそうな急カーブ」＝減速コマンド(Y/U)を使う
                    if cx < 35:
                        cmd = 'Y' # 見失いそうな急カーブ：減速して左折
                        cv2.putText(debug_img, "SHARP LEFT (SLOW)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                    elif cx < 65:
                        cmd = 'Q' # 通常の左
                        cv2.putText(debug_img, "LEFT", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    elif cx > 125:
                        cmd = 'U' # 見失いそうな急カーブ：減速して右折
                        cv2.putText(debug_img, "SHARP RIGHT (SLOW)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                    elif cx > 95:
                        cmd = 'E' # 通常の右
                        cv2.putText(debug_img, "RIGHT", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    else:
                        cmd = 'W' # 直進
                        cv2.putText(debug_img, "STRAIGHT", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                # 線を見失った場合は、暴走を防ぐために完全に停止する
                cmd = 'X'
                cv2.putText(debug_img, "LOST LINE (STOP)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            write_ard(f":{cmd}\r\n".encode('utf-8'))
            last_auto_cmd_time = time.time()
        else:
            # 自動運転がOFFの時はSTANDBY表示
            cv2.putText(debug_img, "STANDBY (MANUAL)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
        # 画面左下に現在の閾値を表示
        cv2.putText(debug_img, f"THR: {threshold_val}", (5, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 画面表示が小さすぎないように、プレビュー用にだけ画像を大きく拡大する（幅4倍、高さ4倍）
        display_img = cv2.resize(debug_img, (640, 240), interpolation=cv2.INTER_LINEAR)
            
        # ラズパイの画面に映像を常に表示
        cv2.imshow("Line Trace Preview", display_img)
        cv2.waitKey(1) # 画面を更新するために必須
                
        time.sleep(0.05) # 20fps程度で処理

if HAS_CV2:
    threading.Thread(target=auto_pilot_loop, daemon=True).start()

# ==========================================
# メイン処理
# ==========================================
print("=========================================")
print(" 📡 クラッドバスター 【中継・ライントレース対応】起動！")
print("=========================================")

try:
    ser_mono = serial.Serial(PORT_MONO, 115200, timeout=1)
    ser_ard = serial.Serial(PORT_ARD, 9600, timeout=1)
    
    ser_mono.reset_input_buffer()
    ser_ard.reset_input_buffer()
    
    print(" 準備完了！Macからの電波を待っています...\n")
    
    buffer = ""
    # 受け付けるコマンドのリスト
    valid_cmds = ['W', 'A', 'S', 'D', 'Q', 'E', 'Z', 'C', 'X']

    while True:
        if ser_mono.in_waiting > 0:
            # MONOSTICKからまとめてデータを読み込む
            chunk = ser_mono.read(ser_mono.in_waiting).decode('utf-8', errors='ignore')
            buffer += chunk
            
            # 改行（\n）が来るまでデータを溜めて、1行のパッケージとして処理する
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                # パターン1: TWELITEの詳細モード「;U;」で届いた場合
                if line.startswith(';U;'):
                    parts = line.split(';')
                    # パッケージが正しい長さかチェック
                    if len(parts) >= 8:
                        lqi = parts[3]     # TWELITEヘッダ付き透過モード ;U;%t;%i;0x%A;... の %i (LQI) はparts[3]
                        payload = parts[7].strip() # 7番目に入っているMacからのデータを抽出
                        
                        if payload == ":AUTO1":
                            print("🤖 ライントレースモード ON")
                            is_auto_mode = True
                            continue
                        elif payload == ":AUTO0":
                            print("🤖 ライントレースモード OFF")
                            is_auto_mode = False
                            # カメラスレッドの次周期を待たず、その場で即座に安全停止する
                            write_ard(b":X\r\n")
                            continue
                        elif payload == ":FLIP1":
                            print("🔄 カメラ映像を反転しました")
                            is_flipped = True
                            continue
                        elif payload == ":FLIP0":
                            print("🔄 カメラ映像の反転を解除しました")
                            is_flipped = False
                            continue
                        elif payload == ":COL0":
                            print("⚫ 追跡カラーをブラック（黒線）に変更しました")
                            line_color_mode = 0
                            continue
                        elif payload == ":COL1":
                            print("⚪ 追跡カラーをホワイト（白線）に変更しました")
                            line_color_mode = 1
                            continue
                        elif payload == ":COL2":
                            print("🔴 追跡カラーをレッド（赤線）に変更しました")
                            line_color_mode = 2
                            continue
                        elif payload.startswith(":THR"):
                            try:
                                threshold_val = int(payload[4:])
                                print(f"🎚️ 影フィルターの閾値を {threshold_val} に変更しました")
                            except ValueError:
                                pass
                            continue
                        elif payload == ":H":
                            # 操作中（W/A/S/D送信中）の無線衝突を防ぐため、ハートビート時のみ電波強度を返信
                            # ※メインループ（手動コマンドの受信）を止めないよう、待機・送信は別スレッドで行う
                            def reply_lqi(value):
                                try:
                                    time.sleep(0.15) # Mac側の受信準備が確実に整うまで長めに待つ
                                    ser_mono.write(f":LQI={value}\r\n".encode('utf-8'))
                                    time.sleep(0.05) # 念のため2回送る
                                    ser_mono.write(f":LQI={value}\r\n".encode('utf-8'))
                                except Exception:
                                    pass
                            threading.Thread(target=reply_lqi, args=(lqi,), daemon=True).start()
                        else:
                            # ペイロードが有効なコマンドかチェック（完全一致）
                            if payload in [f":{c}" for c in valid_cmds]:
                                if not is_auto_mode:
                                    print(f"受信 & 転送: {payload[1:]} (電波強度: {lqi})")
                                    # Arduinoへ純度100%の命令だけを転送
                                    write_ard(f"{payload}\r\n".encode('utf-8'))
                                
                # パターン2: トランスペアレントモード（そのままの文字）で届いた場合の保険
                elif line.startswith(':'):
                    payload = line.strip()
                    if payload == ":AUTO1":
                        print("🤖 ライントレースモード ON")
                        is_auto_mode = True
                    elif payload == ":AUTO0":
                        print("🤖 ライントレースモード OFF")
                        is_auto_mode = False
                        # カメラスレッドの次周期を待たず、その場で即座に安全停止する
                        write_ard(b":X\r\n")
                    elif payload == ":FLIP1":
                        print("🔄 カメラ映像を反転しました")
                        is_flipped = True
                    elif payload == ":FLIP0":
                        print("🔄 カメラ映像の反転を解除しました")
                        is_flipped = False
                    elif payload == ":COL0":
                        print("⚫ 追跡カラーをブラック（黒線）に変更しました")
                        line_color_mode = 0
                    elif payload == ":COL1":
                        print("⚪ 追跡カラーをホワイト（白線）に変更しました")
                        line_color_mode = 1
                    elif payload == ":COL2":
                        print("🔴 追跡カラーをレッド（赤線）に変更しました")
                        line_color_mode = 2
                    elif payload.startswith(":THR"):
                        try:
                            threshold_val = int(payload[4:])
                            print(f"🎚️ 影フィルターの閾値を {threshold_val} に変更しました")
                        except ValueError:
                            pass
                    elif payload == ":H":
                        try:
                            time.sleep(0.05)
                            ser_mono.write(b":LQI=100\r\n")
                        except:
                            pass
                    else:
                        if payload in [f":{c}" for c in valid_cmds]:
                            if not is_auto_mode:
                                print(f"受信 & 転送: {payload[1:]}")
                                write_ard(f"{payload}\r\n".encode('utf-8'))

except serial.SerialException as e:
    print(f"\n❌ エラー: ポートが開けません。配線を確認してください。({e})")
except KeyboardInterrupt:
    print("\nシステムを安全に終了します。")
finally:
    is_auto_mode = False
    if 'ser_mono' in globals() and ser_mono.is_open:
        ser_mono.close()
    if 'ser_ard' in globals() and ser_ard.is_open:
        ser_ard.close()