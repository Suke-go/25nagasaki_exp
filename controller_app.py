import serial
import json
import time
from pynput.keyboard import Controller, Key

# --- 設定 ---
PORT = 'COM4'
BAUDRATE = 115200
TIMEOUT = 1
# ----------------

# --- キー割り当て ---
# Picoのピン名とキーボードのキーを対応させる
# Pico側のコードでは PULL_UP のため、押したときが 0, 離したときが 1
KEY_MAP = {
    'U': 'w',
    'D': 's',
    'L': 'a',
    'R': 'd',
    'B1': 'p', # \ は問題があったため p に変更
    'B2': Key.enter,
}
# ---------------------

keyboard = Controller()
# 全てのキーの最後の状態を保持（1: released, 0: pressed）
last_state = {key: 1 for key in KEY_MAP}

ser = None
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    print(f"ポート {PORT} を開きました。Picoのリセットを待っています...")
    time.sleep(2)
    print("コントローラー入力をキーボード操作に変換します... (Ctrl+Cで終了)")

    while True:
        line = ser.readline()
        if not line:
            continue # データがなければループの先頭へ

        try:
            line_str = line.decode('utf-8').strip()
            # 受信した生データを表示（デバッグ用）
            print(f"受信データ: {line_str}", end='\r')
            data = json.loads(line_str)

            for pin_name, key_to_press in KEY_MAP.items():
                # KEY_MAPにないピン名は無視
                if pin_name not in last_state:
                    continue

                current_val = data.get(pin_name, 1) # データがなければ離している状態(1)とみなす
                last_val = last_state[pin_name]

                if current_val == 0 and last_val == 1:
                    # 押された瞬間
                    keyboard.press(key_to_press)
                elif current_val == 1 and last_val == 0:
                    # 離された瞬間
                    keyboard.release(key_to_press)

                last_state[pin_name] = current_val

        except (json.JSONDecodeError, UnicodeDecodeError):
            # パースエラーは無視して次のデータを待つ
            continue

except serial.SerialException as e:
    print(f"エラー: ポート {PORT} を開けませんでした。: {e}")
except KeyboardInterrupt:
    print("\nプログラムを終了します。")
finally:
    if ser and ser.is_open:
        ser.close()
        print(f"ポート {PORT} を閉じました。")
