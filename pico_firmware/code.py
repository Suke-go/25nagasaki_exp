"""
CircuitPython 実験用コントローラーファームウェア (修正版)
Raspberry Pi Pico W + GSRセンサー + 物理ボタン

問題修正:
- pin.id 属性エラーの修正
- より安全なピン初期化
- エラーハンドリング強化
"""

import time
import board
import digitalio
import analogio
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

print("=== CircuitPython Controller v3.1 (Fixed) ===")
print("Initializing hardware...")

# --- デバイス設定 ---
try:
    kbd = Keyboard(usb_hid.devices)
    print("✓ Keyboard HID initialized")
except Exception as e:
    print(f"✗ Error setting up keyboard: {e}")
    kbd = None

try:
    gsr = analogio.AnalogIn(board.GP26)
    print("✓ GSR sensor initialized on GP26")
except Exception as e:
    print(f"✗ Error setting up GSR sensor: {e}")
    gsr = None

# --- 内蔵LED設定 ---
try:
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    print("✓ LED initialized")
except Exception as e:
    print(f"✗ LED error: {e}")
    led = None

# --- ピン設定 (修正版) ---
# ピン名とキーコードの対応表
PIN_CONFIG = [
    (board.GP6, Keycode.UP_ARROW, "UP", "GP6"),
    (board.GP7, Keycode.DOWN_ARROW, "DOWN", "GP7"),
    (board.GP8, Keycode.LEFT_ARROW, "LEFT", "GP8"), 
    (board.GP9, Keycode.RIGHT_ARROW, "RIGHT", "GP9"),
    (board.GP2, Keycode.P, "B1", "GP2"),
    (board.GP3, Keycode.F13, "B2", "GP3")
]

pins = {}
for pin_obj, keycode, name, pin_name in PIN_CONFIG:
    try:
        pin = digitalio.DigitalInOut(pin_obj)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        pins[name] = {
            'obj': pin,
            'keycode': keycode,
            'state': True,  # プルアップ初期状態
            'pin_name': pin_name,
            'board_pin': pin_obj
        }
        print(f"✓ Pin {pin_name} ({name}) initialized")
    except Exception as e:
        print(f"✗ Error initializing {pin_name} ({name}): {e}")

# 特殊ボタンの参照
b1_available = 'B1' in pins
b2_available = 'B2' in pins

if b1_available and b2_available:
    print("✓ Special buttons (B1, B2) ready for long press detection")

# --- 状態変数 ---
last_b2_press_time = 0
b2_debounce_time = 0.3

long_press_start_time = 0
long_press_duration = 3.0
long_press_triggered = False

last_gsr_print_time = 0
gsr_output_interval = 0.1

led_blink_time = 0
led_state = False

print("✓ Controller ready for experiment")
print()
print("Available controls:")
for name, pin_data in pins.items():
    print(f"  {pin_data['pin_name']} ({name}): {pin_data['keycode']}")
print()
print("Special functions:")
if b1_available and b2_available:
    print("  B1+B2 hold 3s: Session end (F15)")
print()

# --- メインループ ---
print("Starting main loop...")
try:
    while True:
        current_time = time.monotonic()

        # 1. ステータスLED点滅
        if led and current_time - led_blink_time > 1.0:
            led_state = not led_state
            led.value = led_state
            led_blink_time = current_time

        # 2. 通常キー処理（B2以外）
        for name, pin_data in pins.items():
            if name == 'B2':  # B2は特別処理
                continue
                
            try:
                current_state = pin_data['obj'].value
                last_state = pin_data['state']

                if current_state != last_state:
                    if current_state is False and kbd:  # ボタン押下
                        kbd.press(pin_data['keycode'])
                        print(f"[{current_time:.2f}] {name} PRESSED -> {pin_data['keycode']}")
                    elif current_state is True and kbd:  # ボタン離し
                        kbd.release(pin_data['keycode'])
                        print(f"[{current_time:.2f}] {name} RELEASED")
                    
                    pin_data['state'] = current_state
            except Exception as e:
                print(f"Error processing {name}: {e}")

        # 3. B2ボタン処理（デバウンス付き）
        if b2_available and kbd:
            try:
                b2_state = pins['B2']['obj'].value
                if (b2_state is False and 
                    pins['B2']['state'] is True and
                    (current_time - last_b2_press_time) > b2_debounce_time):
                    
                    kbd.press(Keycode.F13)
                    kbd.release(Keycode.F13)
                    print(f"[{current_time:.2f}] B2 PRESSED -> F13 (Recording Toggle)")
                    last_b2_press_time = current_time
                
                pins['B2']['state'] = b2_state
            except Exception as e:
                print(f"Error processing B2: {e}")

        # 4. B1+B2長押し処理
        if b1_available and b2_available and kbd:
            try:
                b1_state = pins['B1']['obj'].value
                b2_state = pins['B2']['obj'].value

                if b1_state is False and b2_state is False:
                    if long_press_start_time == 0:
                        long_press_start_time = current_time
                        print(f"[{current_time:.2f}] Long press started...")
                    
                    if (not long_press_triggered and 
                        (current_time - long_press_start_time) > long_press_duration):
                        
                        kbd.press(Keycode.F15)
                        kbd.release(Keycode.F15)
                        print(f"[{current_time:.2f}] LONG PRESS -> F15 (Session End)")
                        long_press_triggered = True
                else:
                    if long_press_start_time != 0:
                        print(f"[{current_time:.2f}] Long press cancelled")
                    long_press_start_time = 0
                    long_press_triggered = False
            except Exception as e:
                print(f"Error processing long press: {e}")

        # 5. GSRセンサー出力
        if gsr and (current_time - last_gsr_print_time) >= gsr_output_interval:
            try:
                gsr_value = gsr.value
                print(f"GSR:{gsr_value}")
                last_gsr_print_time = current_time
            except Exception as e:
                print(f"Error reading GSR: {e}")

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n=== Controller stopped by user ===")
except Exception as e:
    print(f"\n=== FATAL ERROR: {e} ===")
    # エラー時の高速点滅
    if led:
        for _ in range(20):
            led.value = not led.value
            time.sleep(0.1)
finally:
    # クリーンアップ
    if led:
        led.value = False
    if kbd:
        # 全てのキーをリリース
        for name, pin_data in pins.items():
            try:
                kbd.release(pin_data['keycode'])
            except:
                pass
    print("Controller shutdown complete.")