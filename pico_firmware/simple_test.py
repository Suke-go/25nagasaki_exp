"""
シンプルなテスト用ファームウェア
物理コントローラーの基本動作確認
"""

import time
import board
import digitalio
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

print("=== Simple Controller Test ===")

# HIDキーボードの初期化
try:
    kbd = Keyboard(usb_hid.devices)
    print("✓ HID Keyboard ready")
except Exception as e:
    print(f"✗ HID Error: {e}")
    kbd = None

# LED初期化
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

# テストピンの初期化（GP6のみ）
try:
    test_pin = digitalio.DigitalInOut(board.GP6)
    test_pin.direction = digitalio.Direction.INPUT
    test_pin.pull = digitalio.Pull.UP
    print("✓ GP6 pin ready")
    pin_ready = True
except Exception as e:
    print(f"✗ Pin Error: {e}")
    pin_ready = False

print("\nTest instructions:")
print("1. LED should blink every second")
print("2. Connect a button between GP6 and GND")
print("3. Press the button - should send UP_ARROW key")
print("4. Watch serial output for button presses")
print("\nStarting test loop...")

last_state = True
led_state = False
last_led_time = 0

try:
    while True:
        current_time = time.monotonic()
        
        # LED点滅
        if current_time - last_led_time > 1:
            led_state = not led_state
            led.value = led_state
            last_led_time = current_time
            print(f"[{current_time:.1f}] LED: {'ON' if led_state else 'OFF'}")
        
        # ボタンテスト
        if pin_ready:
            current_state = test_pin.value
            if current_state != last_state:
                if current_state == False:  # ボタン押下
                    print(f"[{current_time:.1f}] BUTTON PRESSED!")
                    if kbd:
                        kbd.press(Keycode.UP_ARROW)
                        kbd.release(Keycode.UP_ARROW)
                        print("  → UP_ARROW key sent")
                else:  # ボタン離し
                    print(f"[{current_time:.1f}] BUTTON RELEASED")
                
                last_state = current_state
        
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("\n=== Test stopped ===")
    led.value = False