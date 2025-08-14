"""
CircuitPython 実験用コントローラーファームウェア
Raspberry Pi Pico W + GSRセンサー + 物理ボタン

機能:
- GSRセンサー値の取得とシリアル出力 (GP26)
- レバー操作による矢印キー入力 (GP6-9)
- ボタンによる特殊キー入力 (GP2: P, GP3: F13)
- B1+B2長押しでセッション終了 (F15)
- エラーハンドリング強化
"""

import time
import board
import digitalio
import analogio
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

print("=== CircuitPython Controller v3.0 ===")
print("Initializing hardware...")

# --- デバイス設定 ---
try:
    kbd = Keyboard(usb_hid.devices)
    print("✓ Keyboard HID initialized")
except Exception as e:
    print(f"✗ Error setting up keyboard: {e}")
    while True: 
        time.sleep(1)

try:
    gsr = analogio.AnalogIn(board.GP26)
    print("✓ GSR sensor initialized on GP26")
except Exception as e:
    print(f"✗ Error setting up GSR sensor: {e}")
    gsr = None

# --- 内蔵LED設定（ステータス表示用）---
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

# --- ピン設定 ---
# 物理コントローラーのピンマッピング
PIN_MAPPING = {
    # レバー（方向キー）
    board.GP6: Keycode.UP_ARROW,     # ↑: Arousal増加
    board.GP7: Keycode.DOWN_ARROW,   # ↓: Arousal減少
    board.GP8: Keycode.LEFT_ARROW,   # ←: Valence減少
    board.GP9: Keycode.RIGHT_ARROW,  # →: Valence増加
    
    # ボタン
    board.GP2: Keycode.P,            # B1: モーフ気づきマーカー
    board.GP3: Keycode.F13,          # B2: 録画トグル（デバウンス処理有り）
}

# ピンオブジェクトの初期化
pins = {}
for pin_name, keycode in PIN_MAPPING.items():
    try:
        pin = digitalio.DigitalInOut(pin_name)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP  # プルアップ抵抗有効
        pins[pin_name] = {
            'obj': pin, 
            'keycode': keycode, 
            'state': True,  # 初期状態（プルアップなのでTrue）
            'name': f"GP{pin_name.id}"
        }
        print(f"✓ Pin {pin_name} initialized")
    except Exception as e:
        print(f"✗ Error initializing pin {pin_name}: {e}")

# 特殊ボタンのピンオブジェクト取得
try:
    b1_pin = pins[board.GP2]['obj']  # モーフマーカーボタン
    b2_pin = pins[board.GP3]['obj']  # 録画トグルボタン
    print("✓ Special buttons initialized")
except KeyError:
    print("✗ Special buttons not available")
    b1_pin = b2_pin = None

# --- 状態変数 ---
# デバウンス処理用
last_b2_press_time = 0
b2_debounce_time = 0.3  # 300ms

# 長押し検出用（実験終了）
long_press_start_time = 0
long_press_duration = 3.0  # 3秒
long_press_triggered = False

# GSR出力制御用
last_gsr_print_time = 0
gsr_output_interval = 0.1  # 100ms間隔（10Hz）

# ステータスLED用
led_blink_time = 0
led_state = False

print("✓ Controller ready for experiment")
print("Controls:")
print("  Lever: ↑↓←→ for Arousal/Valence")
print("  B1(P): Morph awareness marker")
print("  B2(F13): Recording toggle")
print("  B1+B2 hold 3s: Session end (F15)")
print()

# --- メインループ ---
try:
    while True:
        current_time = time.monotonic()

        # 1. ステータスLED点滅（動作確認用）
        if current_time - led_blink_time > 1.0:  # 1秒間隔
            led_state = not led_state
            led.value = led_state
            led_blink_time = current_time

        # 2. 通常のキー処理（レバーとB1）
        for pin_name, pin_data in pins.items():
            # B2は特別処理なのでスキップ
            if pin_name == board.GP3:
                continue

            current_state = pin_data['obj'].value
            last_state = pin_data['state']

            # 状態変化を検出
            if current_state != last_state:
                if current_state is False:  # ボタン押下
                    try:
                        kbd.press(pin_data['keycode'])
                        print(f"Key pressed: {pin_data['name']} -> {pin_data['keycode']}")
                    except Exception as e:
                        print(f"Error pressing key: {e}")
                else:  # ボタン離し
                    try:
                        kbd.release(pin_data['keycode'])
                        print(f"Key released: {pin_data['name']}")
                    except Exception as e:
                        print(f"Error releasing key: {e}")
                
                pin_data['state'] = current_state

        # 3. B2ボタン処理（録画トグル、デバウンス有り）
        if b2_pin:
            b2_state = b2_pin.value
            if (b2_state is False and 
                pins[board.GP3]['state'] is True and 
                (current_time - last_b2_press_time) > b2_debounce_time):
                
                try:
                    print("B2 pressed: Recording toggle (F13)")
                    kbd.press(Keycode.F13)
                    kbd.release(Keycode.F13)
                    last_b2_press_time = current_time
                except Exception as e:
                    print(f"Error sending F13: {e}")
            
            pins[board.GP3]['state'] = b2_state

        # 4. B1+B2同時長押し処理（実験終了）
        if b1_pin and b2_pin:
            b1_state = b1_pin.value
            b2_state = b2_pin.value

            if b1_state is False and b2_state is False:
                # 両方のボタンが押されている
                if long_press_start_time == 0:
                    long_press_start_time = current_time
                    print("Long press started...")
                
                # 3秒経過したかチェック
                if (not long_press_triggered and 
                    (current_time - long_press_start_time) > long_press_duration):
                    
                    try:
                        print("LONG PRESS DETECTED: Session end (F15)")
                        kbd.press(Keycode.F15)
                        kbd.release(Keycode.F15)
                        long_press_triggered = True
                    except Exception as e:
                        print(f"Error sending F15: {e}")
            else:
                # どちらかのボタンが離されたらリセット
                if long_press_start_time != 0:
                    print("Long press cancelled")
                long_press_start_time = 0
                long_press_triggered = False

        # 5. GSRセンサー値のシリアル出力
        if gsr and (current_time - last_gsr_print_time) >= gsr_output_interval:
            try:
                gsr_value = gsr.value
                print(f"GSR:{gsr_value}")
                last_gsr_print_time = current_time
            except Exception as e:
                print(f"Error reading GSR: {e}")

        # CPU負荷軽減
        time.sleep(0.01)  # 10ms

except KeyboardInterrupt:
    print("\n=== Controller stopped by user ===")
except Exception as e:
    print(f"\n=== FATAL ERROR: {e} ===")
    # エラー時は高速点滅
    for _ in range(50):
        led.value = not led.value
        time.sleep(0.1)
finally:
    # クリーンアップ
    led.value = False
    print("Controller shutdown complete.")