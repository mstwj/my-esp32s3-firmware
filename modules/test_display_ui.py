# main.py - 色彩、文字与 JPG 显示综合测试脚本

import time
from display_ui import UIManager

# 启动时先等 200 毫秒，等电源电压完全稳定 -- 为什么等200,因为按下RET按钮,重新启动的时候黑屏
time.sleep_ms(200)

# 1. 初始化 UI 管理器
ui = UIManager()

# RGB565 颜色定义
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
WHITE = 0xFFFF
BLACK = 0x0000

print("=== 开始屏幕 RGB 色彩与 UI 功能测试 ===")

# --- 阶段 1：红、绿、蓝三色测试 ---
ui.lcd.fill(RED)
ui.lcd.show()
print("显示：红色 (RED)")
time.sleep(1)

ui.lcd.fill(GREEN)
ui.lcd.show()
print("显示：绿色 (GREEN)")
time.sleep(1)

ui.lcd.fill(BLUE)
ui.lcd.show()
print("显示：蓝色 (BLUE)")
time.sleep(1)

# --- 阶段 2：UI 文本渲染测试 ---
ui.render(title="系统测试", content="红绿蓝三色测试完成！\n即将进行 JPG 图片解码与显示测试。", color=WHITE)
print("显示：界面文字测试")
time.sleep(2)


# 方案 A：全屏清屏后只画 JPG 图片
ui.lcd.fill(BLACK)
ui.lcd.draw_bmp("test.bmp", start_x=0, start_y=0)
ui.lcd.show()

time.sleep(3)

print("=== 所有功能测试完成 ===")

