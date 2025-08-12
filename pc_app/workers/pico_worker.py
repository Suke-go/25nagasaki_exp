
import serial
import keyboard
import time
from PySide6.QtCore import QThread, Signal

class PicoWorker(QThread):
    """
    Picoからのシリアルデータとキーボード入力を監視するワーカー。
    """
    # --- シグナル定義 ---
    # GSRデータ（int）
    new_gsr_data = Signal(int)
    # Arousal/Valenceの変更（float, float）
    av_changed = Signal(float, float)
    # 録画トグル信号
    record_toggled = Signal()
    # 実験終了信号
    session_ended = Signal()
    # モーフ気づきマーカー信号
    morph_marker_received = Signal()
    # エラーメッセージ（str）
    error = Signal(str)

    def __init__(self, serial_port='COM3', baud_rate=9600):
        super().__init__()
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.ser = None
        self._is_running = True
        
        self.arousal = 0.0
        self.valence = 0.0
        self.av_step = 0.5
        self.av_max = 2.5

    def run(self):
        # キーボードフックを設定
        self.setup_keyboard_hooks()

        # シリアルポートの接続試行
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            print(f"シリアルポート {self.serial_port} に接続しました。")
        except serial.SerialException:
            self.error.emit(f"シリアルポート {self.serial_port} が見つかりません。Picoが接続されているか確認してください。")
            # キーボード入力の監視は継続

        while self._is_running:
            if self.ser and self.ser.is_open:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line.startswith("GSR:"):
                        gsr_value = int(line.split(':')[1])
                        self.new_gsr_data.emit(gsr_value)
                except (UnicodeDecodeError, ValueError, IndexError):
                    # 不正なデータを無視
                    pass
            # 0.01秒待機してCPU負荷を軽減
            self.msleep(10)
        
        # 終了時にキーボードフックを解除
        keyboard.unhook_all()
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("Picoワーカーを終了しました。")

    def setup_keyboard_hooks(self):
        # keyboardライブラリでは矢印キーは文字列として指定
        keyboard.on_press_key('up', lambda e: self.update_arousal(self.av_step))
        keyboard.on_press_key('down', lambda e: self.update_arousal(-self.av_step))
        keyboard.on_press_key('left', lambda e: self.update_valence(-self.av_step))
        keyboard.on_press_key('right', lambda e: self.update_valence(self.av_step))

        keyboard.on_press_key('p', lambda e: self.morph_marker_received.emit())
        keyboard.on_press_key('f13', lambda e: self.record_toggled.emit())
        keyboard.on_press_key('f15', lambda e: self.session_ended.emit())

    def update_arousal(self, change):
        self.arousal = max(-self.av_max, min(self.av_max, self.arousal + change))
        self.av_changed.emit(self.arousal, self.valence)

    def update_valence(self, change):
        self.valence = max(-self.av_max, min(self.av_max, self.valence + change))
        self.av_changed.emit(self.arousal, self.valence)

    def stop(self):
        self._is_running = False
