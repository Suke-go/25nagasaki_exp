"""
実験記録システム - GSRとコントローラー操作の記録に特化（シンプル版）

GSRプロット問題を修正したバージョン
"""

import sys
import os
import time
import csv
from datetime import datetime
from collections import deque
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import pyqtgraph as pg
import numpy as np

# --- ワーカーのインポート ---
from pc_app.workers.pico_worker import PicoWorker

class ExperimentRecorder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("実験記録システム - GSR & コントローラー")
        self.setGeometry(100, 100, 1000, 700)
        
        # 実験状態
        self.is_recording = False
        self.experiment_id = ""
        self.session_dir = ""
        self.gsr_file = None
        self.operations_file = None
        
        # データ記録用
        self.start_time = None
        self.current_arousal = 0.0
        self.current_valence = 0.0
        
        # カメラウィンドウ
        self.camera_window = None
        
        # グラフ用データ（dequeを使用して効率的な循環バッファ）
        self.max_points = 300
        self.gsr_times = deque(maxlen=self.max_points)
        self.gsr_values = deque(maxlen=self.max_points)
        self.graph_start_time = time.time()
        
        self.setup_ui()
        self.setup_worker()
        
        # グラフ更新用タイマー
        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_graph)
        self.graph_timer.start(100)  # 100ms間隔で更新
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 左側: コントロールパネル
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右側: GSRグラフとデータ表示
        right_panel = self.create_data_panel()
        main_layout.addWidget(right_panel, 2)
        
    def create_control_panel(self):
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 実験ID入力
        id_group = QGroupBox("実験設定")
        id_layout = QVBoxLayout()
        id_group.setLayout(id_layout)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("実験ID を入力 (例: EXP001)")
        self.id_input.textChanged.connect(self.on_id_changed)
        
        self.setup_button = QPushButton("実験セットアップ")
        self.setup_button.clicked.connect(self.setup_experiment)
        self.setup_button.setEnabled(False)
        
        id_layout.addWidget(QLabel("実験ID:"))
        id_layout.addWidget(self.id_input)
        id_layout.addWidget(self.setup_button)
        
        # 記録制御
        record_group = QGroupBox("記録制御")
        record_layout = QVBoxLayout()
        record_group.setLayout(record_layout)
        
        # カメラウィンドウ開くボタン
        self.camera_window_button = QPushButton("カメラウィンドウを開く")
        self.camera_window_button.clicked.connect(self.open_camera_window)
        self.camera_window_button.setStyleSheet("QPushButton { font-size: 12px; padding: 8px; background-color: #4CAF50; color: white; }")
        
        self.record_button = QPushButton("記録開始")
        self.record_button.clicked.connect(self.toggle_recording)
        self.record_button.setEnabled(False)
        self.record_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        
        self.status_label = QLabel("状態: セットアップ待ち")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: blue;")
        
        record_layout.addWidget(self.camera_window_button)
        record_layout.addWidget(self.record_button)
        record_layout.addWidget(self.status_label)
        
        # 現在値表示
        values_group = QGroupBox("現在値")
        values_layout = QVBoxLayout()
        values_group.setLayout(values_layout)
        
        self.gsr_value_label = QLabel("GSR: ---")
        self.arousal_label = QLabel("Arousal: 0.0")
        self.valence_label = QLabel("Valence: 0.0")
        
        for label in [self.gsr_value_label, self.arousal_label, self.valence_label]:
            label.setFont(QFont("Arial", 12))
            values_layout.addWidget(label)
        
        # キー操作説明
        help_group = QGroupBox("キー操作")
        help_layout = QVBoxLayout()
        help_group.setLayout(help_layout)
        
        help_text = QLabel("""
物理コントローラー:
• ↑/↓: Arousal調整
• ←/→: Valence調整
• B1(P): イベントマーカー
• B2(F13): 記録開始/停止

キーボード:
• F13: 記録開始/停止
• F15: 実験終了
        """)
        help_text.setStyleSheet("font-size: 10px;")
        help_layout.addWidget(help_text)
        
        layout.addWidget(id_group)
        layout.addWidget(record_group)
        layout.addWidget(values_group)
        layout.addWidget(help_group)
        layout.addStretch()
        
        return panel
    
    def create_data_panel(self):
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # GSRグラフ（シンプル設定）
        self.gsr_graph = pg.PlotWidget()
        self.gsr_graph.setLabel('left', 'GSR Value')
        self.gsr_graph.setLabel('bottom', 'Time (seconds)')
        self.gsr_graph.setTitle('GSR リアルタイム表示')
        self.gsr_graph.showGrid(x=True, y=True, alpha=0.3)
        self.gsr_graph.setBackground('w')
        
        # プロット線を初期化
        self.gsr_curve = self.gsr_graph.plot(
            pen=pg.mkPen(color='blue', width=2),
            name='GSR'
        )
        
        # ログ表示
        log_group = QGroupBox("操作ログ")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(150)
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        layout.addWidget(self.gsr_graph, 3)
        layout.addWidget(log_group, 1)
        
        return panel
    
    def setup_worker(self):
        self.pico_worker = PicoWorker(serial_port='COM13')
        self.pico_worker.new_gsr_data.connect(self.handle_gsr_data)
        self.pico_worker.av_changed.connect(self.handle_av_change)
        self.pico_worker.record_toggled.connect(self.toggle_recording)
        self.pico_worker.morph_marker_received.connect(self.handle_marker)
        self.pico_worker.session_ended.connect(self.end_experiment)
        self.pico_worker.error.connect(self.show_error)
        self.pico_worker.start()
        
    def on_id_changed(self):
        text = self.id_input.text().strip()
        self.setup_button.setEnabled(len(text) > 0)
    
    def setup_experiment(self):
        self.experiment_id = self.id_input.text().strip()
        if not self.experiment_id:
            self.show_error("実験IDを入力してください")
            return
            
        # ディレクトリ作成
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.session_dir = f"experiment_data/{timestamp}_{self.experiment_id}"
        
        try:
            os.makedirs(self.session_dir, exist_ok=True)
            self.log_message(f"実験ディレクトリ作成: {self.session_dir}")
            self.status_label.setText("状態: 記録準備完了")
            self.record_button.setEnabled(True)
            self.setup_button.setEnabled(False)
            self.id_input.setEnabled(False)
        except Exception as e:
            self.show_error(f"ディレクトリ作成エラー: {e}")
    
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        if not self.session_dir:
            self.show_error("先に実験セットアップを行ってください")
            return
            
        try:
            # セッション番号を管理（複数回の録画に対応）
            if not hasattr(self, 'current_session_count'):
                self.current_session_count = 0
            self.current_session_count += 1
            
            # セッション用サブディレクトリを作成
            session_subdir = os.path.join(self.session_dir, f"session_{self.current_session_count:02d}")
            os.makedirs(session_subdir, exist_ok=True)
            
            # ファイルを開く
            gsr_file_path = os.path.join(session_subdir, 'gsr_data.csv')
            ops_file_path = os.path.join(session_subdir, 'operations.csv')
            
            self.gsr_file = open(gsr_file_path, 'w', newline='', encoding='utf-8')
            self.gsr_writer = csv.writer(self.gsr_file)
            self.gsr_writer.writerow(['timestamp', 'elapsed_seconds', 'gsr_value'])
            
            self.operations_file = open(ops_file_path, 'w', newline='', encoding='utf-8')
            self.ops_writer = csv.writer(self.operations_file)
            self.ops_writer.writerow(['timestamp', 'elapsed_seconds', 'operation_type', 'arousal', 'valence', 'details'])
            
            # カメラ録画も開始（カメラウィンドウが開かれている場合）
            if self.camera_window and hasattr(self.camera_window, 'start_recording'):
                camera_started = self.camera_window.start_recording(self.session_dir, self.current_session_count)
                if camera_started:
                    self.log_message("カメラ録画も開始しました")
            
            # 記録開始
            self.is_recording = True
            self.start_time = time.time()
            
            # UI更新
            self.record_button.setText("記録停止")
            self.record_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; background-color: #ff4444; color: white; }")
            self.status_label.setText(f"状態: 記録中 (セッション {self.current_session_count})")
            self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: green;")
            
            # ログ
            self.log_message(f"記録開始 (セッション {self.current_session_count})")
            self.log_operation("record_start", f"記録開始 セッション{self.current_session_count}")
            
        except Exception as e:
            self.show_error(f"記録開始エラー: {e}")
    
    def stop_recording(self):
        if not self.is_recording:
            return
            
        try:
            # 記録停止
            self.log_operation("record_stop", f"記録停止 セッション{self.current_session_count}")
            
            # カメラ録画も停止
            if self.camera_window and hasattr(self.camera_window, 'stop_recording'):
                self.camera_window.stop_recording()
                self.log_message("カメラ録画も停止しました")
            
            # ファイルを閉じる
            if self.gsr_file:
                self.gsr_file.close()
                self.gsr_file = None
            if self.operations_file:
                self.operations_file.close()
                self.operations_file = None
            
            self.is_recording = False
            
            # UI更新
            self.record_button.setText("記録開始")
            self.record_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
            self.status_label.setText("状態: 記録停止")
            self.status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: blue;")
            
            # ログ
            self.log_message(f"記録停止 (セッション {self.current_session_count})")
            
        except Exception as e:
            self.show_error(f"記録停止エラー: {e}")
    
    def handle_gsr_data(self, gsr_value):
        # UI更新
        self.gsr_value_label.setText(f"GSR: {gsr_value}")
        
        # グラフ用データに追加
        current_time = time.time() - self.graph_start_time
        self.gsr_times.append(current_time)
        self.gsr_values.append(gsr_value)
        
        # CSV記録（記録中のみ）
        if self.is_recording and self.gsr_file and self.start_time:
            try:
                timestamp = datetime.now().isoformat()
                elapsed = time.time() - self.start_time
                self.gsr_writer.writerow([timestamp, f"{elapsed:.3f}", gsr_value])
                self.gsr_file.flush()
            except Exception as e:
                print(f"CSV記録エラー: {e}")
    
    def update_graph(self):
        """グラフを定期的に更新"""
        if len(self.gsr_times) > 1 and len(self.gsr_values) > 1:
            try:
                # numpy配列に変換してプロット
                times = np.array(self.gsr_times)
                values = np.array(self.gsr_values)
                self.gsr_curve.setData(times, values)
            except Exception as e:
                print(f"グラフ更新エラー: {e}")
    
    def handle_av_change(self, arousal, valence):
        # 現在値更新
        self.current_arousal = arousal
        self.current_valence = valence
        
        # UI更新
        self.arousal_label.setText(f"Arousal: {arousal:.1f}")
        self.valence_label.setText(f"Valence: {valence:.1f}")
        
        # ログ記録
        details = f"A={arousal:.1f}, V={valence:.1f}"
        self.log_message(f"コントローラー: {details}")
        self.log_operation("controller_input", details)
    
    def handle_marker(self):
        self.log_message("イベントマーカー記録")
        self.log_operation("event_marker", "Pキー押下")
    
    def log_operation(self, operation_type, details):
        if not self.is_recording or not self.operations_file:
            return
        
        timestamp = datetime.now().isoformat()
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        self.ops_writer.writerow([
            timestamp, 
            f"{elapsed:.3f}", 
            operation_type, 
            f"{self.current_arousal:.1f}", 
            f"{self.current_valence:.1f}", 
            details
        ])
        self.operations_file.flush()
    
    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_display.append(log_entry)
        
        # スクロールを最下部に
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def end_experiment(self):
        self.log_message("実験終了信号受信")
        if self.is_recording:
            self.stop_recording()
        
        reply = QMessageBox.question(
            self, '実験終了', 
            '実験を終了しますか？', 
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.close()
    
    def open_camera_window(self):
        """カメラウィンドウを開く"""
        if self.camera_window is None:
            from camera_window import CameraWindow  # 後で作成するクラス
            self.camera_window = CameraWindow()
            self.camera_window.closed.connect(self.on_camera_window_closed)
        
        self.camera_window.show()
        self.camera_window.raise_()
        self.camera_window.activateWindow()
    
    def on_camera_window_closed(self):
        """カメラウィンドウが閉じられた時の処理"""
        self.camera_window = None
    
    def show_error(self, message):
        QMessageBox.critical(self, "エラー", message)
        self.log_message(f"エラー: {message}")
    
    def closeEvent(self, event):
        if self.is_recording:
            reply = QMessageBox.question(
                self, '終了確認', 
                '記録中です。終了しますか？', 
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            self.stop_recording()
        
        # カメラウィンドウも閉じる
        if self.camera_window:
            self.camera_window.close()
        
        self.pico_worker.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    recorder = ExperimentRecorder()
    recorder.show()
    sys.exit(app.exec())