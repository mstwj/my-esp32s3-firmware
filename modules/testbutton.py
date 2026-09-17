import time
from machine import Pin

# 根据原理图定义按键引脚 (配置为输入 + 内部上拉)
btn_vol_up = Pin(40, Pin.IN, Pin.PULL_UP)  # VOL+ 按键
btn_vol_down = Pin(39, Pin.IN, Pin.PULL_UP)  # VOL- 按键
btn_boot = Pin(0, Pin.IN, Pin.PULL_UP)  # BOOT1 按键

print("=== 按键测试程序已启动 ===")
print("请按下开发板上的按键...")

# 记录按键上一次的状态，防止持续长按时重复刷屏
last_state = {
    "VOL+": btn_vol_up.value(),
    "VOL-": btn_vol_down.value(),
    "BOOT": btn_boot.value(),
}


def check_button(pin, name):
    current_val = pin.value()
    # 逻辑低电平 (0) 表示按下
    if current_val == 0 and last_state[name] == 1:
        time.sleep_ms(20)  # 20ms 软件消抖
        if pin.value() == 0:
            print(f"[按键触发] {name} 按下！")
            last_state[name] = 0
    elif current_val == 1 and last_state[name] == 0:
        last_state[name] = 1


while True:
    check_button(btn_vol_up, "VOL+")
    check_button(btn_vol_down, "VOL-")
    check_button(btn_boot, "BOOT")

    time.sleep_ms(10)  # 主循环适当休眠，降低 CPU 占用