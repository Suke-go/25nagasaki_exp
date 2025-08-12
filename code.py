
import time
import board
import digitalio
import analogio
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

# --- デバイス設定 ---
try:
    kbd = Keyboard(usb_hid.devices)
except Exception as e:
    print(f"Error setting up keyboard: {e}")
    while True: pass

try:
    gsr = analogio.AnalogIn(board.GP26)
except Exception as e:
    print(f"Error setting up GSR sensor: {e}")
    gsr = None

# --- ピン設定 ---
# キー割り当て: レバーは矢印キー、B1はP、B2はF13（録画トグル用）
PIN_MAPPING = {
    board.GP6: Keycode.UP_ARROW,
    board.GP7: Keycode.DOWN_ARROW,
    board.GP8: Keycode.LEFT_ARROW,
    board.GP9: Keycode.D, # NOTE: For some reason RIGHT_ARROW is not working, using D as fallback
    board.GP2: Keycode.P,         # B1
    board.GP3: Keycode.F13,       # B2
}

pins = {}
for pin_name, keycode in PIN_MAPPING.items():
    pin = digitalio.DigitalInOut(pin_name)
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP
    pins[pin_name] = {'obj': pin, 'keycode': keycode, 'state': True}

# B1とB2のピンオブジェクトを個別に取得
b1_pin = pins[board.GP2]['obj']
b2_pin = pins[board.GP3]['obj']

# --- 状態変数 ---
last_b2_press_time = 0
b2_debounce_time = 0.2

long_press_start_time = 0
long_press_duration = 3.0
long_press_triggered = False

last_gsr_print_time = 0

print("Controller ready. Version 2.0")

# --- メインループ ---
while True:
    now = time.monotonic()

    # 1. 通常のボタン処理 (レバーとB1)
    for pin_name, pin_data in pins.items():
        # B2は個別処理なのでスキップ
        if pin_name == board.GP3:
            continue

        current_state = pin_data['obj'].value
        last_state = pin_data['state']

        if current_state is False and last_state is True:
            kbd.press(pin_data['keycode'])
        elif current_state is True and last_state is False:
            kbd.release(pin_data['keycode'])
        
        pin_data['state'] = current_state

    # 2. B2ボタン処理 (録画トグル)
    b2_state = b2_pin.value
    if b2_state is False and pins[board.GP3]['state'] is True:
        # デバウンス処理: 短時間に連続して押されるのを防ぐ
        if (now - last_b2_press_time) > b2_debounce_time:
            print("B2 Pressed: Sending F13 for Record Toggle")
            kbd.press(Keycode.F13)
            kbd.release(Keycode.F13)
            last_b2_press_time = now
    pins[board.GP3]['state'] = b2_state


    # 3. B1+B2 同時長押し処理 (実験終了)
    b1_state = b1_pin.value
    # b2_stateは上で取得済み

    if b1_state is False and b2_state is False:
        if long_press_start_time == 0:
            long_press_start_time = now
        
        if not long_press_triggered and (now - long_press_start_time) > long_press_duration:
            print(f"Long Press Detected: Sending F15 for Session End")
            kbd.press(Keycode.F15)
            kbd.release(Keycode.F15)
            long_press_triggered = True # 一度だけトリガー
    else:
        # どちらかのボタンが離されたらリセット
        long_press_start_time = 0
        long_press_triggered = False

    # 4. GSRセンサー値のシリアル出力
    if gsr and (now - last_gsr_print_time) > 0.1: # 100msごと
        print(f"GSR:{gsr.value}")
        last_gsr_print_time = now

    time.sleep(0.01)
