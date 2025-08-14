# Raspberry Pi Pico W ファームウェア書き込み手順

## 1. 準備

### 1.1 必要なソフトウェア
- [Thonny IDE](https://thonny.org/) または
- [MicroPython](https://micropython.org/)
- USB Type-Cケーブル

### 1.2 Pico W の初期設定

1. **MicroPython ファームウェアのインストール**
   - [MicroPython公式サイト](https://micropython.org/download/rp2-pico-w/)から最新版をダウンロード
   - Pico WのBOOTSELボタンを押しながらUSB接続
   - Pico WがUSBドライブとして認識される
   - ダウンロードした`.uf2`ファイルをドライブにコピー
   - 自動的に再起動される

## 2. ハードウェア接続

### 2.1 GSRセンサー接続
```
GSRセンサー → Pico W
VCC         → 3V3(OUT) (Pin 36)
GND         → GND      (Pin 38) 
SIG         → GP26     (Pin 31, ADC0)
```

### 2.2 接続確認
- GSRセンサーのVCCが3.3Vに接続されているか
- GNDが共通接続されているか  
- 信号線がGP26(ADC0)に接続されているか

## 3. ソフトウェア書き込み

### 3.1 Thonny IDEを使用する場合

1. **Thonny IDEを起動**
2. **Pico Wに接続**
   - 右下の「Configure interpreter」をクリック
   - 「MicroPython (Raspberry Pi Pico)」を選択
   - 適切なCOMポートを選択
3. **ファームウェアのアップロード**
   - `main.py`ファイルを開く
   - 「Run」→「Run current script」でテスト実行
   - 「File」→「Save copy...」→「Raspberry Pi Pico」を選択
   - ファイル名を`main.py`として保存

### 3.2 動作確認

1. **シリアル出力の確認**
   - Thonnyの「Shell」タブで以下のような出力を確認
   ```
   === Pico W GSR Sensor Started ===
   Sending GSR data via serial...
   GSR:45678
   GSR:45821
   GSR:45234
   ```

2. **LED動作確認**
   - Pico W内蔵LEDが1秒間隔で点滅することを確認

## 4. トラブルシューティング

### 4.1 接続できない場合
- USBケーブルの確認（データ転送対応ケーブルか）
- COMポートの確認（デバイスマネージャー）
- Pico Wを一度BOOTSELモードで再接続

### 4.2 GSRデータが出力されない場合
- ハードウェア接続の確認
- GSRセンサーの電源供給確認
- アナログ入力ピンの確認（GP26 = ADC0）

### 4.3 異常な値が出力される場合
- センサーのキャリブレーション
- 電源電圧の確認（3.3V）
- ノイズの影響（配線の見直し）

## 5. カスタマイズ

### 5.1 サンプリング頻度の変更
```python
# main.pyの最下部
time.sleep(0.1)  # 0.1秒 = 10Hz
# ↓変更例: 20Hz
time.sleep(0.05) # 0.05秒 = 20Hz
```

### 5.2 出力フォーマットの変更
```python
# 現在の形式
print(f"GSR:{gsr_raw}")

# タイムスタンプ付きにする場合
import time
timestamp = time.ticks_ms()
print(f"GSR:{gsr_raw},TS:{timestamp}")
```

### 5.3 平滑化フィルタの追加
```python
# 移動平均フィルタの例
buffer_size = 5
gsr_buffer = [0] * buffer_size
buffer_index = 0

def smooth_gsr(raw_value):
    global gsr_buffer, buffer_index
    gsr_buffer[buffer_index] = raw_value
    buffer_index = (buffer_index + 1) % buffer_size
    return sum(gsr_buffer) // buffer_size
```

## 6. 実験用最終チェック

- [ ] Pico WのLEDが正常に点滅している
- [ ] シリアル出力で`GSR:数値`形式のデータが出力されている
- [ ] GSRセンサーに触れると値が変化する
- [ ] 電源投入から自動的にプログラムが開始される
- [ ] 安定した電源供給（USB接続またはバッテリー）