
import cv2
import time
import os
from PySide6.QtCore import QThread, Signal

class CameraWorker(QThread):
    """
    指定されたカメラデバイスから映像を録画し、ファイルに保存するワーカー。
    """
    finished = Signal()
    error = Signal(str)

    def __init__(self, camera_index, save_path):
        super().__init__()
        self.camera_index = camera_index
        self.save_path = save_path
        self._is_running = True

    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error.emit(f"カメラ {self.camera_index} を開けませんでした。")
            return

        # カメラ設定（表情解析に適した解像度）
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 20)  # 表情解析に必要な滑らかさを保持
        
        # ビデオのコーデックとフォーマットを定義（Windows互換性向上）
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 互換性の高いコーデック
        fps = 20  # 表情解析に適したフレームレート
        width = 1280  # HD解像度で表情の詳細をキャプチャ
        height = 720

        # 保存先ディレクトリの確認
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

        writer = cv2.VideoWriter(self.save_path, fourcc, fps, (width, height))

        while self._is_running:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            # フレームレート制御（表情解析に適したタイミング）
            self.msleep(50)  # 約20FPSに相当
        
        print(f"カメラ {self.camera_index} の録画を終了し、ファイルを保存しました: {self.save_path}")
        cap.release()
        writer.release()
        self.finished.emit()

    def stop(self):
        self._is_running = False
        self.wait()  # スレッドの終了を待機
