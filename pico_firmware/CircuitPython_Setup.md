# CircuitPython 実験用コントローラー設定ガイド

## 1. CircuitPython環境構築

### 1.1 CircuitPython ファームウェアのインストール

1. **CircuitPython ファームウェアのダウンロード**
   - [CircuitPython公式サイト](https://circuitpython.org/board/raspberry_pi_pico_w/)
   - Raspberry Pi Pico W用の最新安定版をダウンロード（`.uf2`ファイル）

2. **ファームウェアの書き込み**
   - Pico WのBOOTSELボタンを押しながらUSB接続
   - `RPI-RP2`ドライブとして認識される
   - ダウンロードした`.uf2`ファイルをドライブにドラッグ&ドロップ
   - 自動的に再起動され、`CIRCUITPY`ドライブとして認識される

### 1.2 必要ライブラリのインストール

1. **Adafruit CircuitPython Bundleのダウンロード**
   - [Bundle Downloads](https://circuitpython.org/libraries)
   - 使用するCircuitPythonバージョンに対応するBundleをダウンロード

2. **HIDライブラリのコピー**
   ```
   Bundle/lib/adafruit_hid/ → CIRCUITPY/lib/adafruit_hid/
   ```
   - `CIRCUITPY`ドライブの`lib`フォルダに`adafruit_hid`フォルダ全体をコピー

## 2. ハードウェア接続

### 2.1 物理コントローラーのピン配線

```
機能                    → Pico W Pin
=================================
GSRセンサー VCC         → 3V3(OUT) (Pin 36)
GSRセンサー GND         → GND      (Pin 38)
GSRセンサー SIG         → GP26     (Pin 31)

レバー UP              → GP6      (Pin 9)
レバー DOWN            → GP7      (Pin 10)
レバー LEFT            → GP8      (Pin 11)
レバー RIGHT           → GP9      (Pin 12)

ボタンB1 (Pキー)       → GP2      (Pin 4)
ボタンB2 (F13キー)     → GP3      (Pin 5)

全てのスイッチのGND    → GND      (適当なGNDピン)
```

### 2.2 回路図
```
[レバー/ボタン] ──┐
                  │
                  ├── GPxx (Pico W)
                  │
                 GND
```

- 各スイッチは片側がGPIOピン、もう片側がGNDに接続
- Pico W内蔵のプルアップ抵抗を使用
- 押下時はGPIOピンがLOWになる

## 3. ソフトウェア設定

### 3.1 ファームウェアのデプロイ

1. **既存のcode.pyをバックアップ**
   ```bash
   # 現在のcode.pyを保存
   cp C:\Users\kosuk\controller\code.py C:\Users\kosuk\controller\code_backup.py
   ```

2. **新しいcode.pyをCIRCUITPYドライブにコピー**
   ```bash
   # 実験用ファームウェアをコピー
   cp C:\Users\kosuk\controller\pico_firmware\code.py [CIRCUITPY]/code.py
   ```

### 3.2 動作確認

1. **シリアルコンソールの確認**
   - Tera Term、PuTTY、またはThonny IDEのシリアルモニタを使用
   - COMポート接続（ボーレート115200）
   - 起動時に以下のメッセージが表示される:
   ```
   === CircuitPython Controller v3.0 ===
   Initializing hardware...
   ✓ Keyboard HID initialized
   ✓ GSR sensor initialized on GP26
   ✓ Pin board.GP6 initialized
   ...
   ✓ Controller ready for experiment
   ```

2. **LED動作確認**
   - Pico W内蔵LEDが1秒間隔で点滅

3. **キー入力テスト**
   - 各レバー/ボタンを操作してPCでキー入力が認識されることを確認
   - シリアルコンソールにキー操作ログが表示される

4. **GSRデータ確認**
   - シリアルコンソールに`GSR:数値`形式でデータが出力される
   - センサーに触れると値が変化することを確認

## 4. キーマッピング

| 物理コントローラー | キー出力 | 機能 |
|-------------------|---------|------|
| レバー ↑          | ↑      | Arousal増加 |
| レバー ↓          | ↓      | Arousal減少 |
| レバー ←          | ←      | Valence減少 |
| レバー →          | →      | Valence増加 |
| ボタンB1          | P       | モーフ気づきマーカー |
| ボタンB2          | F13     | 録画開始/停止 |
| B1+B2長押し(3秒)  | F15     | セッション終了 |

## 5. トラブルシューティング

### 5.1 キー入力が認識されない

**症状**: ボタンを押してもPCでキー入力が認識されない

**対処法**:
1. USB HIIDデバイスとして認識されているか確認
   - デバイスマネージャー → ヒューマンインターフェースデバイス
   - "CircuitPython HID"デバイスが表示されるか
2. シリアルコンソールでキー押下ログが出力されているか確認
3. 別のUSBポートで試す

### 5.2 GSRデータが出力されない

**症状**: シリアルコンソールに`GSR:数値`が表示されない

**対処法**:
1. ハードウェア接続確認
   - VCC → 3V3, GND → GND, SIG → GP26
2. GSRセンサーの電源確認（3.3V供給）
3. アナログ入力の確認
   ```python
   import analogio, board
   gsr = analogio.AnalogIn(board.GP26)
   print(gsr.value)  # 手動でテスト
   ```

### 5.3 右矢印キーが動作しない

**症状**: レバーの右操作が認識されない（既存の問題）

**対処法**:
1. 新しいファームウェア（code.py v3.0）では修正済み
2. それでも動作しない場合は配線確認
3. 代替として別のピンに変更:
   ```python
   board.GP10: Keycode.RIGHT_ARROW,  # GP9の代わりにGP10を使用
   ```

### 5.4 長押し機能が正常に動作しない

**症状**: B1+B2を3秒長押ししてもF15が送信されない

**対処法**:
1. シリアルコンソールで"Long press started..."メッセージを確認
2. 両方のボタンを確実に同時押し
3. 3秒間ボタンを離さない
4. デバウンス時間の調整（必要に応じて）

## 6. カスタマイズ

### 6.1 キーマッピングの変更
```python
# code.py内のPIN_MAPPINGを編集
PIN_MAPPING = {
    board.GP6: Keycode.UP_ARROW,
    # 他のキーを変更...
}
```

### 6.2 GSRサンプリング頻度の変更
```python
gsr_output_interval = 0.05  # 50ms間隔（20Hz）
```

### 6.3 デバウンス時間の調整
```python
b2_debounce_time = 0.5  # 500ms（より長い間隔）
```

## 7. 実験前最終チェックリスト

- [ ] Pico WがCIRCUITPYドライブとして認識される
- [ ] 内蔵LEDが1秒間隔で点滅している
- [ ] シリアルコンソールに起動メッセージが表示される
- [ ] 全てのレバー操作でキー入力が認識される
- [ ] B1ボタンでPキーが入力される
- [ ] B2ボタンでF13キーが入力される（デバウンス機能付き）
- [ ] B1+B2長押しでF15キーが入力される
- [ ] GSRセンサーからデータが出力される（GSR:数値）
- [ ] センサーに触れると値が変化する
- [ ] PCの実験ソフトウェアがキー入力を正しく受信する