# ラジパイ (razipai-rc-car)

市販の大型ラジコンカー（タミヤ クラッドバスター）に **Raspberry Pi** と **Arduino** を載せて、PC やスマホのブラウザから操縦できるようにしたプロジェクトです。
無線には **TWELITE（MONOSTICK）** を使っています。カメラを使った **ライントレース（自動運転）** にも対応しています。

## しくみ

```
[ブラウザ]  ──HTTP──▶  [Mac: mac-musenn.py]
                            │ TWELITE MONOSTICK（無線 2.4GHz）
                            ▼
                     [Raspberry Pi: razupai-musenn.py]  ◀── カメラ（ライントレース用）
                            │ USB シリアル（9600bps）
                            ▼
                     [Arduino: rc-control-ArduinoIDE.ino]
                            │ PWM
                            ▼
                     [ESC（モーター） / ステアリングサーボ]
```

| ファイル | 動かす場所 | 役割 |
| --- | --- | --- |
| `mac-musenn.py` | Mac | Web コントローラーを配信し、操作を TWELITE で車に送る |
| `ラジパイ起動.command` | Mac | `mac-musenn.py` をダブルクリックで起動する |
| `razupai-musenn.py` | Raspberry Pi | 無線で受けた命令を確認して Arduino に転送する。ライントレースもここで処理する |
| `rc-control-ArduinoIDE/rc-control-ArduinoIDE.ino` | Arduino | 命令に合わせて ESC とサーボを動かす |
| `debug_receiver.py` | Raspberry Pi | MONOSTICK が受け取った生データを表示するデバッグ用ツール |

## 主な機能

- **ブラウザから操縦**: `W` `A` `S` `D` キー、または画面のボタンで操作します。2 つのキーを同時に押すと斜めに進みます。スマホからも操作できます
- **電波強度の表示**: TWELITE の LQI（電波の強さ）をメーターで表示します
- **ライントレース（AUTOPILOT）**: カメラで床の線を見つけて、自動で追いかけます
  - 追いかける線の色: 黒・白・赤
  - 影フィルター（しきい値）をブラウザから調整できます
  - カメラ映像の 180° 反転に対応しています
  - 急カーブでは減速します。線を見失ったら止まります
- **ノイズ対策**: TWELITE のヘッダー付きのデータから命令だけを取り出し、決められたコマンドだけを Arduino に送ります
- **安全対策**
  - 起動時と終了時に停止コマンドを送ります
  - ブラウザでキーを離したとき、ウィンドウから離れたときは停止します
  - ライントレース中にカメラ処理が 0.3 秒以上止まったら、強制的に停止します
  - 手動でキーを押すと、ライントレースは自動で OFF になります

## 必要なもの

### ハードウェア

- RC カー（ESC とステアリングサーボを使うタイプ。作者はタミヤ クラッドバスターを使用）
- Raspberry Pi ＋ カメラモジュール（作者はカメラモジュール 3 を使用）
- Arduino（UNO など）
- TWELITE MONOSTICK × 2（Mac 側と Raspberry Pi 側に 1 本ずつ）

### 配線（Arduino）

| ピン | 接続先 |
| --- | --- |
| D9 | ステアリングサーボ |
| D10 | ESC |

### ソフトウェア

- **Mac**: Python 3、`pyserial`
- **Raspberry Pi**: Python 3、`pyserial`、OpenCV、NumPy、Picamera2（カメラモジュール 3 を使う場合）
- **Arduino**: Arduino IDE（標準の `Servo` ライブラリを使用）

```bash
# Mac
pip3 install pyserial
```

```bash
# Raspberry Pi
sudo apt install python3-serial python3-opencv python3-numpy python3-picamera2
```

## 使い方

1. **Arduino**: `rc-control-ArduinoIDE/rc-control-ArduinoIDE.ino` を Arduino IDE で書き込みます
2. **Raspberry Pi**: Arduino と MONOSTICK を USB でつないで、次を実行します

   ```bash
   python3 razupai-musenn.py
   ```

   ポートは `/dev/ttyUSB0`（MONOSTICK）と `/dev/ttyACM0`（Arduino）を想定しています。違う場合はファイルの先頭で変更してください。
3. **Mac**: MONOSTICK をつないで、`ラジパイ起動.command` をダブルクリックします（または `python3 mac-musenn.py`）
   MONOSTICK は `/dev/cu.usbserial-*` から自動で探します。
4. ブラウザで `http://localhost:8080` が開くので、そこから操縦します。
   スマホから操作するときは、Mac と同じネットワークにつないで `http://<MacのIPアドレス>:8080` を開いてください。

### TWELITE の設定

Raspberry Pi 側の MONOSTICK は、**ヘッダー付き透過モード**（`;U;...` 形式）での受信を想定しています。普通の透過モード（`:W` などがそのまま届く形式）でも動くようにしてあります。

## 通信のコマンド

命令は `:` から始まり、`\r\n` で終わる文字列として送ります（例: `:W\r\n`）。

| コマンド | 意味 |
| --- | --- |
| `Q` / `W` / `E` | 前進（左 / まっすぐ / 右） |
| `A` / `X` / `D` | 停止（ハンドル左 / 中央 / 右） |
| `Z` / `S` / `C` | 後退（左 / まっすぐ / 右） |
| `Y` / `U` | ゆっくり前進（左 / 右）※ライントレースの急カーブ用 |
| `AUTO1` / `AUTO0` | ライントレース ON / OFF |
| `FLIP1` / `FLIP0` | カメラ映像の 180° 反転 ON / OFF |
| `COL0` / `COL1` / `COL2` | 追いかける線の色（黒 / 白 / 赤） |
| `THR<数値>` | 影フィルターのしきい値（例: `THR60`） |
| `H` | ハートビート（Raspberry Pi が電波強度 `:LQI=<値>` を返す） |

ESC とサーボの値（`ESC_FORWARD`、`STEER_LEFT` など）は作者の車体に合わせてあります。使う車体に合わせて `.ino` の先頭で調整してください。

## 注意事項

- Web コントローラー（ポート 8080）には**パスワードがありません**。同じネットワークにいる人なら誰でも操縦できてしまうので、信頼できるネットワークで使ってください
- 手動で操縦しているときに無線が途切れると、直前の命令のまま動き続けることがあります。必ず目の届く範囲で、すぐ電源を切れる状態で走らせてください
- 大型の RC カーは重くて力も強いので、周りの人や物に十分注意してください

## ライセンス

[MIT License](LICENSE)
