"""
カメラウィンドウ - カメラ選択、プレビュー、録画機能
main.pyから分離された独立ウィンドウ
"""

import sys
import os
import cv2
import time
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGroupBox, QCheckBox, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QImage

# カメラワーカーのインポート
from pc_app.workers.camera_worker import CameraWorker

class CameraWindow(QMainWindow):
    # シグナル定義
    closed = Signal()  # ウィンドウが閉じられた時
    recording_started = Signal()  # 録画開始時
    recording_stopped = Signal()  # 録画停止時
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("カメラコントローラー - プレビュー & 録画")
        self.setGeometry(200, 200, 900, 700)
        
        # 状態管理
        self.camera_checkboxes = []
        self.active_camera_workers = []
        self.selected_cameras = []
        self.is_recording = False
        self.session_dir = ""
        self.recording_session_count = 0
        
        # プレビュー用
        self.preview_camera = None
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)
        
        self.setup_ui()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # カメラ選択エリア
        camera_group = QGroupBox("1. カメラ選択")
        camera_layout = QVBoxLayout()
        camera_group.setLayout(camera_layout)
        
        detect_button = QPushButton("カメラを検出")
        detect_button.clicked.connect(self.detect_cameras)
        detect_button.setStyleSheet("QPushButton { font-size: 12px; padding: 8px; background-color: #2196F3; color: white; }")
        
        self.camera_layout = QVBoxLayout()
        
        camera_layout.addWidget(detect_button)
        camera_layout.addLayout(self.camera_layout)
        
        # 選択確定ボタン
        self.setup_cameras_button = QPushButton("2. 選択したカメラをセットアップ")
        self.setup_cameras_button.clicked.connect(self.setup_cameras)
        self.setup_cameras_button.setEnabled(False)
        
        # プレビューエリア  
        preview_group = QGroupBox("3. カメラプレビュー")
        preview_layout = QVBoxLayout()
        preview_group.setLayout(preview_layout)
        
        # プレビューカメラ選択
        preview_select_layout = QHBoxLayout()
        preview_select_layout.addWidget(QLabel("プレビューカメラ:"))
        self.preview_camera_combo = QComboBox()
        self.preview_camera_combo.currentTextChanged.connect(self.change_preview_camera)
        preview_select_layout.addWidget(self.preview_camera_combo)
        preview_select_layout.addStretch()
        
        # 映像表示エリア
        self.video_label = QLabel("カメラを選択してください")
        self.video_label.setStyleSheet("background-color: black; color: white; font-size: 16px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumHeight(400)
        self.video_label.setScaledContents(True)
        
        preview_layout.addLayout(preview_select_layout)
        preview_layout.addWidget(self.video_label)
        
        # 録画制御エリア
        record_group = QGroupBox("4. 録画制御")
        record_layout = QVBoxLayout()
        record_group.setLayout(record_layout)
        
        self.record_status_label = QLabel("状態: カメラ未設定")
        self.record_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: blue;")
        
        note_label = QLabel("※ 録画開始/停止はメインウィンドウから制御されます")
        note_label.setStyleSheet("font-size: 10px; color: gray;")
        
        record_layout.addWidget(self.record_status_label)
        record_layout.addWidget(note_label)
        
        # レイアウト組み立て
        main_layout.addWidget(camera_group)
        main_layout.addWidget(self.setup_cameras_button)
        main_layout.addWidget(preview_group)
        main_layout.addWidget(record_group)
    
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

        # 利用可能なカメラを検索
        available_cameras = []
        camera_info_dict = {}
        
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
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
            checkbox.setToolTip(f"デバイス ID: {index}")
            self.camera_layout.addWidget(checkbox)
            self.camera_checkboxes.append(checkbox)
        
        self.setup_cameras_button.setEnabled(True)
    
    def setup_cameras(self):
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
                    # フォールバック
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
        
        # プレビュー用カメラ選択肢を更新
        self.preview_camera_combo.clear()
        self.preview_camera_combo.addItem("プレビューなし")
        for cam_index in self.selected_cameras:
            self.preview_camera_combo.addItem(f"カメラ {cam_index}")
        
        self.record_status_label.setText("状態: カメラ設定完了 - 録画待機")
        self.record_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: green;")
        
        print(f"カメラ設定完了。選択されたカメラ: {self.selected_cameras}")
    
    def change_preview_camera(self, camera_text):
        # 既存のプレビューカメラを停止
        if self.preview_camera:
            self.preview_camera.release()
            self.preview_camera = None
        self.preview_timer.stop()
        
        if camera_text == "プレビューなし":
            self.video_label.setText("プレビューオフ")
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
            # フレームをリサイズ
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
    
    def start_recording(self, session_dir, session_count):
        """メインウィンドウから呼び出される録画開始"""
        if not self.selected_cameras:
            self.show_error("カメラが設定されていません。")
            return False
        
        try:
            self.session_dir = session_dir
            self.recording_session_count = session_count
            current_recording_dir = os.path.join(session_dir, f"session_{session_count:02d}")
            os.makedirs(os.path.join(current_recording_dir, 'video'), exist_ok=True)
            
            print(f"カメラ録画開始 - セッション {session_count}: {current_recording_dir}")
            
            # 選択されたカメラの録画を開始
            for cam_index in self.selected_cameras:
                save_path = os.path.join(current_recording_dir, f"video/camera_{cam_index}.mp4")
                worker = CameraWorker(int(cam_index), save_path)
                worker.error.connect(self.show_error)
                self.active_camera_workers.append(worker)
                worker.start()
            
            self.is_recording = True
            self.record_status_label.setText(f"状態: 録画中 (セッション {session_count})")
            self.record_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: red;")
            
            self.recording_started.emit()
            return True
        except Exception as e:
            self.show_error(f"録画開始エラー: {e}")
            return False
    
    def stop_recording(self):
        """メインウィンドウから呼び出される録画停止"""
        if not self.is_recording:
            return
        
        try:
            print(f"カメラ録画停止 - セッション {self.recording_session_count} 完了")
            
            # カメラワーカーを停止
            for worker in self.active_camera_workers:
                worker.stop()
            self.active_camera_workers = []
            
            self.is_recording = False
            self.record_status_label.setText("状態: カメラ設定完了 - 録画待機")
            self.record_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: green;")
            
            self.recording_stopped.emit()
        except Exception as e:
            self.show_error(f"録画停止エラー: {e}")
    
    def show_error(self, message):
        QMessageBox.critical(self, "カメラエラー", message)
    
    def closeEvent(self, event):
        # プレビューカメラを停止
        if self.preview_camera:
            self.preview_camera.release()
        self.preview_timer.stop()
        
        # 録画中の場合は停止
        if self.is_recording:
            self.stop_recording()
        
        self.closed.emit()
        super().closeEvent(event)