
import sys
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QStackedWidget)
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QBrush, QPen, QColor, QPainter
import pyqtgraph as pg
# --- 定数 ---
AROUSAL_VALENCE_MAX = 2.5
AV_PLOT_SIZE = 400

# --- 2D評価空間プロット用ウィジェット ---
class AVPlot(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)

        # プロットの範囲設定
        self.scene.setSceneRect(-AV_PLOT_SIZE/2, -AV_PLOT_SIZE/2, AV_PLOT_SIZE, AV_PLOT_SIZE)

        # 軸の描画
        self.scene.addLine(-AV_PLOT_SIZE/2, 0, AV_PLOT_SIZE/2, 0, QPen(Qt.white))
        self.scene.addLine(0, -AV_PLOT_SIZE/2, 0, AV_PLOT_SIZE/2, QPen(Qt.white))
        
        # ラベル
        self.scene.addText("Arousal").setDefaultTextColor(Qt.white)
        self.scene.addText("Valence").setPos(-50, -AV_PLOT_SIZE/2)

        # 現在位置を示す点
        self.dot = QGraphicsEllipseItem(0, 0, 20, 20)
        self.dot.setBrush(QBrush(Qt.red))
        self.scene.addItem(self.dot)

        self.arousal = 0.0
        self.valence = 0.0
        self.update_dot_position()

    def update_dot_position(self):
        # 座標の計算 (Arousal: Y軸, Valence: X軸)
        # Y軸は上が正なので、Arousalの符号を反転させる
        x = (self.valence / AROUSAL_VALENCE_MAX) * (AV_PLOT_SIZE / 2)
        y = (-self.arousal / AROUSAL_VALENCE_MAX) * (AV_PLOT_SIZE / 2)
        self.dot.setPos(x - 10, y - 10) # 点の中心に合わせる

    def update_values(self, arousal, valence):
        self.arousal = max(-AROUSAL_VALENCE_MAX, min(AROUSAL_VALENCE_MAX, arousal))
        self.valence = max(-AROUSAL_VALENCE_MAX, min(AROUSAL_VALENCE_MAX, valence))
        self.update_dot_position()
        print(f"UI Updated: Arousal={self.arousal}, Valence={self.valence}")


# --- GSRプロット用ウィンドウ ---
class GSRWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GSR Real-time Plot")
        self.graphWidget = pg.PlotWidget()
        self.setCentralWidget(self.graphWidget)

        self.x = list(range(100))  # 100個のデータを表示
        self.y = [0] * 100 # 初期値は0
        
        self.graphWidget.setBackground('k')
        self.pen = pg.mkPen(color=(0, 255, 0))
        self.data_line =  self.graphWidget.plot(self.x, self.y, pen=self.pen)

    def update_plot(self, new_value):
        self.x = self.x[1:] + [self.x[-1] + 1]
        self.y = self.y[1:] + [new_value]
        self.data_line.setData(self.x, self.y)


# --- マスターコントロール用メインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self, gsr_window):
        super().__init__()
        self.setWindowTitle("Master Controller")
        self.setGeometry(100, 100, 800, 600)
        
        self.gsr_window = gsr_window

        # --- UI要素 ---
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- 画面の定義 ---
        # 0: 待機画面
        self.welcome_screen = QWidget()
        welcome_layout = QVBoxLayout()
        welcome_layout.addWidget(QLabel("実験待機中..."))
        self.welcome_screen.setLayout(welcome_layout)

        # 1: 実験画面 (鑑賞画面)
        self.experiment_screen = QWidget()
        exp_layout = QHBoxLayout()
        
        # 左側に動画表示エリア（プレースホルダー）
        video_area = QLabel("動画表示エリア")
        video_area.setStyleSheet("background-color: black; color: white;")
        video_area.setAlignment(Qt.AlignCenter)
        
        # 右側にArousal/Valenceプロット
        self.av_plot = AVPlot()

        exp_layout.addWidget(video_area, 2) # 2/3の幅
        exp_layout.addWidget(self.av_plot, 1) # 1/3の幅
        self.experiment_screen.setLayout(exp_layout)

        # StackedWidgetに画面を追加
        self.stacked_widget.addWidget(self.welcome_screen)
        self.stacked_widget.addWidget(self.experiment_screen)

        # --- ダミーデータでUIをテスト ---
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.dummy_update)
        self.test_timer.start(1000) # 1秒ごとに更新
        self.dummy_arousal = 0
        self.dummy_valence = 0
        self.dummy_gsr = 60000

        # 初期画面を設定
        self.go_to_experiment_screen() # テストのため直接実験画面へ

    def go_to_experiment_screen(self):
        self.stacked_widget.setCurrentIndex(1)

    def dummy_update(self):
        # ダミーのArousal/Valence値を更新
        self.dummy_arousal += 0.1
        self.dummy_valence -= 0.15
        if self.dummy_arousal > AROUSAL_VALENCE_MAX: self.dummy_arousal = -AROUSAL_VALENCE_MAX
        if self.dummy_valence < -AROUSAL_VALENCE_MAX: self.dummy_valence = AROUSAL_VALENCE_MAX
        self.av_plot.update_values(self.dummy_arousal, self.dummy_valence)

        # ダミーのGSR値を更新
        self.dummy_gsr += (500 - time.time() % 1000)
        if self.dummy_gsr > 65535: self.dummy_gsr = 50000
        if self.dummy_gsr < 50000: self.dummy_gsr = 65535
        self.gsr_window.update_plot(self.dummy_gsr)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # ウィンドウを作成して表示
    gsr_win = GSRWindow()
    main_win = MainWindow(gsr_win)
    
    gsr_win.show()
    main_win.show()
    
    sys.exit(app.exec())
