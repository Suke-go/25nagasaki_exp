from machine import Pin, ADC
import time

# ── ピン定義（レバーを GP6〜GP9 に変更）
UP   = Pin(6,  Pin.IN, Pin.PULL_UP)
DOWN = Pin(7,  Pin.IN, Pin.PULL_UP)
LEFT = Pin(8,  Pin.IN, Pin.PULL_UP)
RIGHT= Pin(9,  Pin.IN, Pin.PULL_UP)
BTN1 = Pin(2, Pin.IN, Pin.PULL_UP)
BTN2 = Pin(3, Pin.IN, Pin.PULL_UP)

GSR  = ADC(26)  # GP26 = ADC0

def lv(p):  # 押=0をそのまま0/1で見たいときの変換
    return 0 if p.value()==0 else 1

while True:
    gsr = GSR.read_u16()  # 0..65535（0〜3.3Vに対応）
    print({"U":lv(UP),"D":lv(DOWN),"L":lv(LEFT),"R":lv(RIGHT),
           "B1":lv(BTN1),"B2":lv(BTN2),"GSR":gsr})
    time.sleep_ms(20)
