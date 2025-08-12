
# 情動経験に関する心理生理学実験 計測ソフトウェア

このリポジトリは、特定の情動刺激（自己顔のモーフなど）が人のArousal（覚醒度）およびValence（感情価）に与える影響を計測するためのソフトウェア群です。

Raspberry Pi Picoを搭載した自作コントローラーと、PC上で動作するPySide6製のGUIアプリケーションで構成されています。

## システム構成

### ハードウェア
*   **コントローラー**: Raspberry Pi Pico
    *   入力: 4方向レバー, ボタン x2
    *   センサー: GSR (皮膚電気活動) センサー

### ソフトウェア
*   **Pico側**: `code.py` (CircuitPython)
    *   コントローラーの入力をUSBキーボード信号としてPCに送信します。
    *   GSRセンサーの値をリアルタイムでPCにシリアル通信で送信します。
*   **PC側**: `pc_app/main.py` (Python + PySide6)
    *   実験の進行を管理するマスターコントロールGUI。
    *   刺激（動画など）を呈示します。
    *   コントローラーからの入力に基づき、Arousal/Valenceの値を2D空間にリアルタイムでプロットします。
    *   GSRの値を別ウィンドウでリアルタイムにプロットします。
    *   カメラ2台の映像、GSRデータ、イベントマーカー（ボタン操作、タイムスタンプ等）をPCに保存します。

## セットアップ

### 1. コントローラー (Pico)
1.  お使いのRaspberry Pi Picoに[CircuitPython](https://circuitpython.org/board/raspberry_pi_pico/)をインストールします。
2.  `code.py`をPicoのドライブ（`CIRCUITPY`）にコピーします。

### 2. PCアプリケーション
1.  このリポジトリをクローンします。
    ```bash
    git clone https://github.com/Suke-go/25nagasaki_exp.git
    cd 25nagasaki_exp
    ```
2.  必要なPythonライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```

## 使い方

1.  コントローラーをPCにUSBで接続します。
2.  以下のコマンドでPCアプリケーションを起動します。
    ```bash
    python pc_app/main.py
    ```
3.  GUIの指示に従って実験を開始します。

### コントローラー操作

| 操作したいこと | ボタン操作 |
| :--- | :--- |
| **Arousal/Valence評価** | **レバー**を上下左右に倒す |
| **録画を開始/停止する** | **B2** を1回短く押す |
| **「モーフに気づいた」と記録** | **B1** を1回短く押す |
| **実験を正常に終了する** | **B1 と B2 を一緒に3秒間押し続ける** |
| **緊急停止** | **実験者**がキーボードの **`Esc` キー**を押す |

## データ構造

取得されたデータは、要件定義書に基づき `pc_app/data/{YYYYMMDD-HHMMSS}_{PID}/` 以下に保存されます。
