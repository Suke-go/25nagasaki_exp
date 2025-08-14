"""
Raspberry Pi Pico W ファームウェア
実験用GSRセンサーデータ収集

機能:
- GSRセンサー値の読み取り (ADC0)
- シリアル出力でPCに送信
- 内蔵LED点滅でステータス表示
"""

import machine
import time
import sys

# ADCピンの設定 (GP26 = ADC0)
adc = machine.ADC(26)

# 内蔵LED設定 (動作状況表示用)
led = machine.Pin("LED", machine.Pin.OUT)

# シリアル通信の初期化
print("=== Pico W GSR Sensor Started ===")
print("Sending GSR data via serial...")

# メインループ
led_state = False
sample_count = 0

try:
    while True:
        # GSR値の読み取り (16bit ADC: 0-65535)
        gsr_raw = adc.read_u16()
        
        # GSRデータをシリアル出力 (PCが解析可能な形式)
        print(f"GSR:{gsr_raw}")
        
        # LED点滅 (動作確認用)
        led_state = not led_state
        led.value(led_state)
        
        # サンプリング頻度: 10Hz (100ms間隔)
        time.sleep(0.1)
        
        # デバッグ用カウンター (1分ごと)
        sample_count += 1
        if sample_count % 600 == 0:  # 60秒 × 10Hz = 600サンプル
            print(f"DEBUG:Running for {sample_count//600} minutes")
        
except KeyboardInterrupt:
    print("=== Pico W GSR Sensor Stopped ===")
    led.value(False)
    sys.exit(0)
except Exception as e:
    print(f"ERROR:{str(e)}")
    # エラー時は高速点滅
    for i in range(20):
        led.toggle()
        time.sleep(0.1)
    led.value(False)