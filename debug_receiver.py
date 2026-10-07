import serial
import time

PORT_MONO = '/dev/ttyUSB0'

print("=========================================")
print(" 🔍 MONOSTICK デバッグ（生データ受信）ツール起動")
print(" Macから操作して、ここに何か表示されるか確認してください。")
print("=========================================")

try:
    ser_mono = serial.Serial(PORT_MONO, 115200, timeout=1)
    ser_mono.reset_input_buffer()
    
    while True:
        if ser_mono.in_waiting > 0:
            raw_bytes = ser_mono.read(ser_mono.in_waiting)
            print(f"受信した生データ: {raw_bytes}")
            
except serial.SerialException as e:
    print(f"\n❌ エラー: ポートが開けません。({e})")
except KeyboardInterrupt:
    print("\n終了します。")
finally:
    if 'ser_mono' in locals() and ser_mono.is_open:
        ser_mono.close()
