"""
CircuitPython デバッグ用ファームウェア
物理コントローラーの動作確認とトラブルシューティング
"""

import time
import board
import digitalio
import analogio

print("=== DEBUG MODE: CircuitPython Controller ===")
print("Testing hardware connections...")

# --- GSRセンサーテスト ---
try:
    gsr = analogio.AnalogIn(board.GP26)
    print("✓ GSR sensor on GP26: OK")
except Exception as e:
    print(f"✗ GSR sensor error: {e}")
    gsr = None

# --- LEDテスト ---
try:
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    print("✓ LED: OK")
except Exception as e:
    print(f"✗ LED error: {e}")
    led = None

# --- 物理ピンテスト ---
test_pins = [
    (board.GP6, "UP"),
    (board.GP7, "DOWN"), 
    (board.GP8, "LEFT"),
    (board.GP9, "RIGHT"),
    (board.GP2, "B1"),
    (board.GP3, "B2")
]

pins = {}
for pin_board, name in test_pins:
    try:
        pin = digitalio.DigitalInOut(pin_board)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        pins[name] = {
            'obj': pin,
            'last_state': True,
            'pin_name': f"GP{pin_board.id}"
        }
        print(f"✓ Pin {pins[name]['pin_name']} ({name}): OK")
    except Exception as e:
        print(f"✗ Pin {name} error: {e}")

print()
print("=== Hardware Test Results ===")
print("Now monitoring pin states...")
print("Press buttons/move lever to test - watch for state changes")
print("GSR values will also be displayed")
print()

# --- USB HID テスト ---
try:
    import usb_hid
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.keycode import Keycode
    
    kbd = Keyboard(usb_hid.devices)
    print("✓ USB HID Keyboard: OK")
    hid_available = True
except Exception as e:
    print(f"✗ USB HID error: {e}")
    print("This might be the problem!")
    hid_available = False

print("\n" + "="*50)
print("LIVE MONITORING - Press Ctrl+C to stop")
print("="*50)

# --- メインモニタリングループ ---
last_gsr_time = 0
led_state = False
last_led_time = 0
test_key_sent = False

try:
    while True:
        current_time = time.monotonic()
        
        # LED点滅
        if led and current_time - last_led_time > 0.5:
            led_state = not led_state
            led.value = led_state
            last_led_time = current_time
        
        # ピン状態監視
        for name, pin_data in pins.items():
            current_state = pin_data['obj'].value
            last_state = pin_data['last_state']
            
            if current_state != last_state:
                state_str = "PRESSED" if current_state == False else "RELEASED"
                print(f"[{time.monotonic():.2f}] {name} ({pin_data['pin_name']}): {state_str}")
                
                # USB HID テスト
                if hid_available and current_state == False:  # ボタン押下時
                    try:
                        if name == "UP":
                            kbd.press(Keycode.UP_ARROW)
                            kbd.release(Keycode.UP_ARROW)
                            print(f"  → Sent UP_ARROW key")
                        elif name == "DOWN":
                            kbd.press(Keycode.DOWN_ARROW) 
                            kbd.release(Keycode.DOWN_ARROW)
                            print(f"  → Sent DOWN_ARROW key")
                        elif name == "LEFT":
                            kbd.press(Keycode.LEFT_ARROW)
                            kbd.release(Keycode.LEFT_ARROW)
                            print(f"  → Sent LEFT_ARROW key")
                        elif name == "RIGHT":
                            kbd.press(Keycode.RIGHT_ARROW)
                            kbd.release(Keycode.RIGHT_ARROW)
                            print(f"  → Sent RIGHT_ARROW key")
                        elif name == "B1":
                            kbd.press(Keycode.P)
                            kbd.release(Keycode.P)
                            print(f"  → Sent P key")
                        elif name == "B2":
                            kbd.press(Keycode.F13)
                            kbd.release(Keycode.F13)
                            print(f"  → Sent F13 key")
                    except Exception as e:
                        print(f"  ✗ Key send error: {e}")
                
                pin_data['last_state'] = current_state
        
        # GSR値表示
        if gsr and current_time - last_gsr_time > 2.0:  # 2秒間隔
            gsr_value = gsr.value
            print(f"[{current_time:.2f}] GSR: {gsr_value}")
            last_gsr_time = current_time
        
        # 10秒後に自動テストキー送信
        if hid_available and not test_key_sent and current_time > 10:
            try:
                print("\n[AUTO TEST] Sending test key 'A'...")
                kbd.press(Keycode.A)
                kbd.release(Keycode.A)
                print("[AUTO TEST] Test key sent - check if PC receives it")
                test_key_sent = True
            except Exception as e:
                print(f"[AUTO TEST] Failed to send test key: {e}")
        
        time.sleep(0.05)  # 50ms間隔

except KeyboardInterrupt:
    print("\n=== Debug session ended ===")
    if led:
        led.value = False
    print("Check the results above to diagnose the issue.")
    print("\nCommon issues:")
    print("- USB HID not working: Try different USB port or cable")
    print("- Pins not responding: Check wiring connections") 
    print("- Keys not received on PC: Check if Pico appears as HID device")