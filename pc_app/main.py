import sys
import os
import cv2
import time
import json
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QStackedWidget, QPushButton, QGroupBox, QCheckBox, QMessageBox)
from PySide6.QtCore import Qt, QPointF, QThread, Signal
from PySide6.QtGui import QBrush, QPen, QColor, QPainter
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
        self.events_file = None
        self.gsr_file = None

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
        video_area = QLabel("動画表示エリア")
        video_area.setStyleSheet("background-color: black; color: white; font-size: 16px;")
        video_area.setAlignment(Qt.AlignCenter)
        video_area.setMinimumHeight(400)
        self.av_plot = AVPlot()
        left_layout.addWidget(video_area, 2)
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
        self.pico_worker = PicoWorker(serial_port='COM3') # ご自身のポートに合わせて変更してください
        self.pico_worker.new_gsr_data.connect(self.handle_new_gsr)
        self.pico_worker.av_changed.connect(self.handle_av_change)
        self.pico_worker.record_toggled.connect(self.handle_record_toggle)
        self.pico_worker.morph_marker_received.connect(self.log_morph_marker)
        self.pico_worker.session_ended.connect(self.end_session)
        self.pico_worker.error.connect(self.show_error)
        self.pico_worker.start()
        
        # 初期状態設定
        self.control_panel.update_status("カメラ選択待ち")

    def detect_cameras(self):
        # 既存のチェックボックスをクリア
        for checkbox in self.camera_checkboxes:
            self.camera_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.camera_checkboxes = []

        # 利用可能なカメラを検索
        available_cameras = []
        for i in range(5): # 0から4まで試す
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        
        if not available_cameras:
            self.show_error("利用可能なカメラが見つかりませんでした。")
            return

        # チェックボックスを作成
        for index in available_cameras:
            checkbox = QCheckBox(f"カメラ {index}")
            self.camera_layout.addWidget(checkbox)
            self.camera_checkboxes.append(checkbox)

    def start_experiment(self):
        self.selected_cameras = [cb.text().split(' ')[1] for cb in self.camera_checkboxes if cb.isChecked()]
        if not self.selected_cameras:
            self.show_error("録画するカメラを1台以上選択してください。")
            return
        print(f"実験開始。選択されたカメラ: {self.selected_cameras}")
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
            # 保存ディレクトリ作成
            self.session_dir = f"data/{datetime.now().strftime('%Y%m%d-%H%M%S')}_PID001" # PIDは後で入力できるようにする
            os.makedirs(os.path.join(self.session_dir, 'video'), exist_ok=True)
            
            # ログファイルを開く
            self.events_file = open(os.path.join(self.session_dir, 'events.jsonl'), 'a')
            self.gsr_file = open(os.path.join(self.session_dir, 'serial.csv'), 'a')
            self.gsr_file.write("pc_ns,gsr_value\n")

            self.log_event('record_start', {})

            # 選択されたカメラの録画を開始
            for cam_index in self.selected_cameras:
                save_path = os.path.join(self.session_dir, f"video/camera_{cam_index}.mp4")
                worker = CameraWorker(int(cam_index), save_path)
                worker.error.connect(self.show_error)
                self.active_camera_workers.append(worker)
                worker.start()
        else:
            print("録画停止...")
            self.control_panel.update_status("待機中")
            self.log_event('record_stop', {})
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

    def show_error(self, message):
        QMessageBox.critical(self, "エラー", message)

    def closeEvent(self, event):
        print("アプリケーションを終了します。")
        self.pico_worker.stop()
        for worker in self.active_camera_workers:
            worker.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())