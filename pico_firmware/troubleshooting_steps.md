# 物理コントローラー トラブルシューティング

## 現在の症状
- GSRデータは正常に出力されている（Thonnyで確認済み）
- 物理コントローラーのキー入力が認識されない

## 診断手順

### 1. デバッグファームウェアによる詳細診断

1. **デバッグコードの書き込み**
   ```
   debug_code.py → CIRCUITPY/code.py にコピー
   ```

2. **Thonnyシリアルモニターで確認**
   - 起動時のハードウェア初期化メッセージ
   - ピン接続状況の確認
   - USB HID初期化の成功/失敗

3. **物理操作テスト**
   - レバー/ボタンを操作
   - シリアルモニターで状態変化を確認
   - キー送信ログの確認

### 2. よくある問題と対処法

#### 問題1: USB HIDデバイスとして認識されない

**症状**: 
```
✗ USB HID error: No HID devices available
```

**対処法**:
1. **USBケーブルの確認**
   - データ転送対応ケーブルを使用（充電専用ではダメ）
   - ケーブルを交換して再テスト

2. **USBポートの変更**
   - 別のUSBポートに接続
   - USB 2.0ポートを優先的に使用

3. **デバイスマネージャー確認**
   - Windows デバイスマネージャーを開く
   - 「ヒューマンインターフェースデバイス」を確認
   - "CircuitPython HID"または類似デバイスがあるか

4. **boot.py の確認/作成**
   ```python
   # CIRCUITPY/boot.py
   import usb_hid
   
   # HIDデバイスを有効化
   usb_hid.enable(
       (usb_hid.Device.KEYBOARD,)
   )
   ```

#### 問題2: ピンの接続問題

**症状**:
```
✓ Pin GP6 (UP): OK
# でも実際にボタンを押しても反応がない
```

**対処法**:
1. **配線の確認**
   - スイッチの片側がGPIOピン、もう片側がGNDに接続されているか
   - はんだ付けの確認（接触不良）
   - ブレッドボード使用時はしっかり差し込まれているか

2. **プルアップ抵抗の確認**
   - 内蔵プルアップが有効になっているか
   - 外部プルアップ抵抗（10kΩ）の追加を試す

3. **テスター/マルチメーターでの確認**
   - スイッチOFF時: GPIOピン - 3.3V
   - スイッチON時: GPIOピン - 0V（GND）

#### 問題3: CircuitPython設定問題

**症状**: エラーメッセージが出てHID初期化に失敗

**対処法**:
1. **CircuitPythonの再インストール**
   - 最新の安定版CircuitPythonファームウェアをダウンロード
   - BOOTSELモードで再書き込み

2. **ライブラリの確認**
   ```
   CIRCUITPY/lib/adafruit_hid/
   ```
   - adafruit_hidフォルダが正しくコピーされているか
   - バージョンの互換性確認

3. **code.pyのシンタックスエラー確認**
   - Thonnyでcode.pyを開いてエラーがないか確認

### 3. 段階的テスト手順

#### ステップ1: 基本USB HID テスト
```python
# 最小限のHIDテストコード
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
import time

kbd = Keyboard(usb_hid.devices)

while True:
    print("Sending 'A' key...")
    kbd.press(Keycode.A)
    kbd.release(Keycode.A)
    time.sleep(2)
```

#### ステップ2: ピン読み取りテスト
```python
# ピン状態確認コード
import board
import digitalio
import time

pin = digitalio.DigitalInOut(board.GP6)  # テストしたいピン
pin.direction = digitalio.Direction.INPUT
pin.pull = digitalio.Pull.UP

while True:
    print(f"GP6 state: {pin.value}")
    time.sleep(0.5)
```

#### ステップ3: 組み合わせテスト
デバッグファームウェア（debug_code.py）を使用

### 4. ハードウェア代替案

#### 案1: 外部プルアップ抵抗の追加
```
3.3V ──[10kΩ]── GPIOピン ──[スイッチ]── GND
```

#### 案2: ピン番号の変更
```python
# 他のピンで試してみる
PIN_MAPPING = {
    board.GP10: Keycode.UP_ARROW,    # GP6の代わり
    board.GP11: Keycode.DOWN_ARROW,  # GP7の代わり
    # ...
}
```

#### 案3: アナログピンでのテスト
```python
# デジタルピンが動作しない場合
import analogio
pin = analogio.AnalogIn(board.GP26)  # アナログ値で確認
```

### 5. 最終確認項目

実際の配線を目視で確認:
- [ ] スイッチからPicoまでの配線が正しい
- [ ] GNDが共通で接続されている
- [ ] 3.3V電源が安定している
- [ ] USBケーブルがデータ転送対応
- [ ] 他のUSBデバイスとの競合がない

PC側での確認:
- [ ] デバイスマネージャーでHIDデバイス認識
- [ ] Windowsのオンスクリーンキーボードでキー入力確認
- [ ] 他のアプリケーション（メモ帳等）でキー入力テスト