import sys
import os
import cv2
import time
import json
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QStackedWidget, QPushButton, QGroupBox, QCheckBox, QMessageBox, QComboBox)
from PySide6.QtCore import Qt, QPointF, QThread, Signal, QTimer
from PySide6.QtGui import QBrush, QPen, QColor, QPainter, QPixmap, QImage
import pyqtgraph as pg

# --- ワーカーのインポート ---
from workers.camera_worker import CameraWorker
from workers.pico_worker import PicoWorker

# --- 定数 ---
AROUSAL_VALENCE_MAX = 2.5
AV_PLOT_SIZE = 400

# --- 2D評価空間プロット用ウィジェット (変更なし) ---
class AVPlot(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.scene.setSceneRect(-AV_PLOT_SIZE/2, -AV_PLOT_SIZE/2, AV_PLOT_SIZE, AV_PLOT_SIZE)
        self.scene.addLine(-AV_PLOT_SIZE/2, 0, AV_PLOT_SIZE/2, 0, QPen(Qt.white))
        self.scene.addLine(0, -AV_PLOT_SIZE/2, 0, AV_PLOT_SIZE/2, QPen(Qt.white))
        self.dot = QGraphicsEllipseItem(0, 0, 20, 20)
        self.dot.setBrush(QBrush(Qt.red))
        self.scene.addItem(self.dot)
        self.update_dot_position(0, 0)

    def update_dot_position(self, arousal, valence):
        x = (valence / AROUSAL_VALENCE_MAX) * (AV_PLOT_SIZE / 2)
        y = (-arousal / AROUSAL_VALENCE_MAX) * (AV_PLOT_SIZE / 2)
        self.dot.setPos(x - 10, y - 10)

# --- GSRプロット用ウィジェット ---
class GSRWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # GSRグラフ
        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setLabel('left', 'GSR Value')
        self.graphWidget.setLabel('bottom', 'Time')
        self.x = list(range(300))
        self.y = [0] * 300
        self.graphWidget.setBackground('k')
        self.pen = pg.mkPen(color=(0, 255, 0))
        self.data_line = self.graphWidget.plot(self.x, self.y, pen=self.pen)
        
        # 現在の値表示
        self.current_value_label = QLabel("GSR: 0")
        self.current_value_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        layout.addWidget(QLabel("GSR リアルタイム表示"))
        layout.addWidget(self.current_value_label)
        layout.addWidget(self.graphWidget)

    def update_plot(self, new_value):
        self.x = self.x[1:] + [self.x[-1] + 1]
        self.y = self.y[1:] + [new_value]
        self.data_line.setData(self.x, self.y)
        self.current_value_label.setText(f"GSR: {new_value}")

# --- コントロールパネル用ウィジェット ---
class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 現在の状態表示
        self.status_label = QLabel("状態: 待機中")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: blue;")
        
        # Arousal/Valence値表示
        self.av_values_label = QLabel("Arousal: 0.0, Valence: 0.0")
        self.av_values_label.setStyleSheet("font-size: 12px;")
        
        # 録画状況表示
        self.recording_label = QLabel("録画: 停止中")
        self.recording_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        
        # キー操作説明
        key_help = QLabel("""
キー操作:
• ↑/↓: Arousal調整
• ←/→: Valence調整  
• P: モーフ気づきマーカー
• F13: 録画開始/停止
• F15: セッション終了
        """)
        key_help.setStyleSheet("font-size: 10px; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        
        layout.addWidget(QLabel("コントロールパネル"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.av_values_label)
        layout.addWidget(self.recording_label)
        layout.addWidget(key_help)
        layout.addStretch()

    def update_status(self, status):
        self.status_label.setText(f"状態: {status}")
    
    def update_av_values(self, arousal, valence):
        self.av_values_label.setText(f"Arousal: {arousal:.1f}, Valence: {valence:.1f}")
    
    def update_recording_status(self, is_recording):
        if is_recording:
            self.recording_label.setText("録画: 実行中")
            self.recording_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        else:
            self.recording_label.setText("録画: 停止中")
            self.recording_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")

# --- マスターコントロール用メインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("実験コントローラー - GSR & A/V モニタリング")
        self.setGeometry(100, 100, 1200, 800)
        self.camera_checkboxes = []
        self.active_camera_workers = []
        self.is_recording = False
        self.session_dir = ""
        self.current_recording_dir = ""
        self.recording_session_count = 0
        self.events_file = None
        self.gsr_file = None
        self.preview_camera = None
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)

        # --- UI要素 ---
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- 画面の定義 ---
        # 0: セットアップ画面
        self.setup_screen = QWidget()
        setup_layout = QVBoxLayout()
        self.setup_screen.setLayout(setup_layout)

        self.camera_group = QGroupBox("1. 接続カメラの選択")
        self.camera_layout = QVBoxLayout()
        self.camera_group.setLayout(self.camera_layout)
        detect_button = QPushButton("カメラを検出")
        detect_button.clicked.connect(self.detect_cameras)
        self.camera_layout.addWidget(detect_button)

        start_button = QPushButton("2. 実験開始")
        start_button.clicked.connect(self.start_experiment)

        setup_layout.addWidget(self.camera_group)
        setup_layout.addWidget(start_button)

        # 1: 実験画面 (統合された表示)
        self.experiment_screen = QWidget()
        exp_layout = QHBoxLayout()
        
        # 左側: 動画とA/V表示
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        # カメラ選択とプレビュー
        camera_preview_layout = QHBoxLayout()
        camera_preview_layout.addWidget(QLabel("プレビューカメラ:"))
        self.preview_camera_combo = QComboBox()
        self.preview_camera_combo.currentTextChanged.connect(self.change_preview_camera)
        camera_preview_layout.addWidget(self.preview_camera_combo)
        camera_preview_layout.addStretch()
        
        self.video_label = QLabel("動画表示エリア")
        self.video_label.setStyleSheet("background-color: black; color: white; font-size: 16px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumHeight(400)
        self.video_label.setScaledContents(True)
        
        self.av_plot = AVPlot()
        
        left_layout.addLayout(camera_preview_layout)
        left_layout.addWidget(self.video_label, 2)
        left_layout.addWidget(self.av_plot, 1)
        left_widget.setLayout(left_layout)
        
        # 右側: GSRとコントロールパネル
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        self.gsr_widget = GSRWidget()
        self.control_panel = ControlPanel()
        right_layout.addWidget(self.gsr_widget, 2)
        right_layout.addWidget(self.control_panel, 1)
        right_widget.setLayout(right_layout)
        
        exp_layout.addWidget(left_widget, 2)
        exp_layout.addWidget(right_widget, 1)
        self.experiment_screen.setLayout(exp_layout)

        self.stacked_widget.addWidget(self.setup_screen)
        self.stacked_widget.addWidget(self.experiment_screen)

        # --- ワーカーのセットアップ ---
        self.pico_worker = PicoWorker(serial_port='COM13') # find_com_ports.pyで確認したポート番号
        self.pico_worker.new_gsr_data.connect(self.handle_new_gsr)
        self.pico_worker.av_changed.connect(self.handle_av_change)
        self.pico_worker.record_toggled.connect(self.handle_record_toggle)
        self.pico_worker.morph_marker_received.connect(self.log_morph_marker)
        self.pico_worker.session_ended.connect(self.end_session)
        self.pico_worker.error.connect(self.show_error)
        self.pico_worker.start()
        
        # 初期状態設定
        self.control_panel.update_status("カメラ選択待ち")

    def get_camera_info(self, index):
        """カメラの詳細情報を取得"""
        try:
            # PowerShellコマンドでカメラデバイスの情報を取得
            cmd = f'Get-WmiObject -Class Win32_PnPEntity | Where-Object {{$_.Name -like "*camera*" -or $_.Name -like "*webcam*" -or $_.Name -like "*USB Video*"}} | Format-Table -Property Name, DeviceID -AutoSize'
            result = subprocess.run(['powershell', '-Command', cmd], 
                                  capture_output=True, text=True, timeout=5)
            
            camera_info = f"カメラ {index}"
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                # デバイス情報をパース（簡易版）
                for line in lines:
                    if 'USB' in line and 'camera' in line.lower():
                        parts = line.split()
                        if len(parts) > 0:
                            camera_info = f"カメラ {index} - {parts[0]}"
                            break
            
            # 解像度情報を取得
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                camera_info += f" ({width}x{height})"
                cap.release()
            
            return camera_info
        except Exception as e:
            print(f"カメラ情報取得エラー {index}: {e}")
            return f"カメラ {index}"

    def detect_cameras(self):
        # 既存のチェックボックスをクリア
        for checkbox in self.camera_checkboxes:
            self.camera_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.camera_checkboxes = []

        # 利用可能なカメラを検索（より安全に）
        available_cameras = []
        camera_info_dict = {}
        
        for i in range(10): # 0から9まで試す（USBハブ使用のため範囲拡大）
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # DirectShowを使用してエラー軽減
                if cap.isOpened():
                    # 実際にフレームが取得できるかテスト
                    ret, frame = cap.read()
                    if ret:
                        available_cameras.append(i)
                        camera_info_dict[i] = self.get_camera_info(i)
                        print(f"検出: {camera_info_dict[i]}")
                    else:
                        print(f"カメラ {i}: 開けるがフレーム取得不可")
                cap.release()
            except Exception as e:
                print(f"カメラ {i}: エラー - {e}")
        
        print(f"検出されたカメラ: {available_cameras}")
        
        if not available_cameras:
            self.show_error("利用可能なカメラが見つかりませんでした。\nUSBハブの接続やカメラの電源を確認してください。")
            return

        # チェックボックスを作成
        for index in available_cameras:
            camera_info = camera_info_dict.get(index, f"カメラ {index}")
            checkbox = QCheckBox(camera_info)
            checkbox.setToolTip(f"デバイス ID: {index}")  # ツールチップでデバイスIDを表示
            self.camera_layout.addWidget(checkbox)
            self.camera_checkboxes.append(checkbox)

    def start_experiment(self):
        # チェックボックスからカメラインデックスを抽出
        self.selected_cameras = []
        for cb in self.camera_checkboxes:
            if cb.isChecked():
                # ツールチップからデバイスIDを取得
                tooltip = cb.toolTip()
                if tooltip and "デバイス ID:" in tooltip:
                    camera_index = tooltip.split("デバイス ID: ")[1]
                    self.selected_cameras.append(camera_index)
                else:
                    # フォールバック: テキストからカメラ番号を抽出
                    text = cb.text()
                    if "カメラ" in text:
                        try:
                            parts = text.split()
                            camera_index = parts[1] if len(parts) > 1 else text.split("カメラ")[1].split()[0]
                            self.selected_cameras.append(camera_index)
                        except:
                            pass
        
        if not self.selected_cameras:
            self.show_error("録画するカメラを1台以上選択してください。")
            return
        
        # セッションディレクトリを作成
        self.session_dir = f"data/{datetime.now().strftime('%Y%m%d-%H%M%S')}_PID001"
        os.makedirs(self.session_dir, exist_ok=True)
        self.recording_session_count = 0
        
        # プレビュー用カメラ選択肢を更新
        self.preview_camera_combo.clear()
        self.preview_camera_combo.addItem("プレビューなし")
        for cam_index in self.selected_cameras:
            self.preview_camera_combo.addItem(f"カメラ {cam_index}")
        
        print(f"実験開始。選択されたカメラ: {self.selected_cameras}")
        print(f"セッションディレクトリ: {self.session_dir}")
        self.control_panel.update_status("実験中 - 録画待機")
        self.stacked_widget.setCurrentIndex(1)

    # --- スロット関数 (ワーカーからの信号を処理) ---
    def handle_new_gsr(self, gsr_value):
        self.gsr_widget.update_plot(gsr_value)
        if self.is_recording and self.gsr_file:
            self.gsr_file.write(f"{time.perf_counter_ns()},{gsr_value}\n")

    def handle_av_change(self, arousal, valence):
        self.av_plot.update_dot_position(arousal, valence)
        self.control_panel.update_av_values(arousal, valence)
        self.log_event('av_change', {'arousal': arousal, 'valence': valence})

    def handle_record_toggle(self):
        self.is_recording = not self.is_recording
        self.control_panel.update_recording_status(self.is_recording)
        
        if self.is_recording:
            print("録画開始...")
            self.control_panel.update_status("録画中")
            
            # 録画セッション番号を増加し、サブディレクトリを作成
            self.recording_session_count += 1
            self.current_recording_dir = os.path.join(self.session_dir, f"session_{self.recording_session_count:02d}")
            os.makedirs(os.path.join(self.current_recording_dir, 'video'), exist_ok=True)
            
            print(f"録画セッション {self.recording_session_count}: {self.current_recording_dir}")
            
            # ログファイルを開く
            self.events_file = open(os.path.join(self.current_recording_dir, 'events.jsonl'), 'a')
            self.gsr_file = open(os.path.join(self.current_recording_dir, 'serial.csv'), 'a')
            self.gsr_file.write("pc_ns,gsr_value\n")

            self.log_event('record_start', {'session_number': self.recording_session_count})

            # 選択されたカメラの録画を開始
            for cam_index in self.selected_cameras:
                save_path = os.path.join(self.current_recording_dir, f"video/camera_{cam_index}.mp4")
                worker = CameraWorker(int(cam_index), save_path)
                worker.error.connect(self.show_error)
                self.active_camera_workers.append(worker)
                worker.start()
        else:
            print(f"録画停止...セッション {self.recording_session_count} 完了")
            self.control_panel.update_status("実験中 - 録画待機")
            self.log_event('record_stop', {'session_number': self.recording_session_count})
            # カメラワーカーを停止
            for worker in self.active_camera_workers:
                worker.stop()
            self.active_camera_workers = []
            # ファイルを閉じる
            if self.events_file: self.events_file.close()
            if self.gsr_file: self.gsr_file.close()

    def log_morph_marker(self):
        self.log_event('morph_awareness_marker', {})

    def end_session(self):
        print("セッション終了信号を受信しました。")
        if self.is_recording:
            self.handle_record_toggle() # 録画を停止
        self.close() # アプリケーションを終了

    def log_event(self, event_type, data):
        if not self.is_recording or not self.events_file:
            return
        event_data = {
            'pc_ns': time.perf_counter_ns(),
            'type': event_type,
            'data': data
        }
        self.events_file.write(json.dumps(event_data) + '\n')

    def change_preview_camera(self, camera_text):
        # 既存のプレビューカメラを停止
        if self.preview_camera:
            self.preview_camera.release()
            self.preview_camera = None
        self.preview_timer.stop()
        
        if camera_text == "プレビューなし":
            self.video_label.setText("動画表示エリア")
            self.video_label.setStyleSheet("background-color: black; color: white; font-size: 16px;")
            return
        
        # 新しいカメラを開始
        try:
            camera_index = int(camera_text.split(' ')[1])
            self.preview_camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if self.preview_camera.isOpened():
                self.preview_timer.start(33)  # 約30FPS
                self.video_label.setStyleSheet("")
            else:
                self.show_error(f"カメラ {camera_index} を開けませんでした。")
        except Exception as e:
            self.show_error(f"プレビュー開始エラー: {str(e)}")
    
    def update_preview(self):
        if not self.preview_camera or not self.preview_camera.isOpened():
            return
        
        ret, frame = self.preview_camera.read()
        if ret:
            # フレームをリサイズ（表示用に適切なサイズに調整）
            height, width, channel = frame.shape
            target_width = 640
            target_height = int(height * target_width / width)
            frame = cv2.resize(frame, (target_width, target_height))
            
            # BGR → RGB変換
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # QImageに変換
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # QLabelに設定
            self.video_label.setPixmap(pixmap)

    def show_error(self, message):
        QMessageBox.critical(self, "エラー", message)

    def closeEvent(self, event):
        print("アプリケーションを終了します。")
        self.pico_worker.stop()
        for worker in self.active_camera_workers:
            worker.stop()
        
        # プレビューカメラも停止
        if self.preview_camera:
            self.preview_camera.release()
        self.preview_timer.stop()
        
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())