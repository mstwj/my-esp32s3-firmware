# app_controller.py - 硬件驱动控制与相机/UI 交互模块
import time
from machine import Pin


class AppController:

    def __init__(self, ui, cam_ctrl):
        self.ui = ui
        self.cam = cam_ctrl

        # 硬件引脚配置
        self.boot_btn = Pin(0, Pin.IN, Pin.PULL_UP)  # IO0: 拍照/开关相机
        self.view_btn = Pin(46, Pin.IN, Pin.PULL_UP)  # IO46: 浏览/退出浏览
        self.mic_btn = Pin(14, Pin.IN, Pin.PULL_UP)  # IO14: 录音按键

        self.press_start_time = 0

    def enter_view_mode(self):
        """进入浏览照片模式（仅响应 IO46 退出浏览）"""
        filename = "photo.bmp"
        print("🔍 进入浏览模式，读取:", filename)

        try:
            with open(filename, "rb") as f:
                f.seek(66)
                bmp_data = f.read(320 * 240 * 2)

            if not bmp_data or len(bmp_data) != 320 * 240 * 2:
                self.ui.lcd.fill(0x0000)
                self.ui.font.text(
                    self.ui.lcd, "照片损坏/不完整", 40, 100, color=0xF800
                )
                self.ui.lcd.show()
                time.sleep_ms(1500)
                return

            # 显示存好的照片
            display_buf = self.cam.swap_endian(bmp_data)
            self.ui.lcd.push_camera_buf(display_buf, 320, 240)

            # 消抖：等待进入浏览模式的按键松开
            while self.view_btn.value() == 0:
                time.sleep_ms(20)

            # === 浏览模式专属独立子循环 ===
            while True:
                # 【唯一按键逻辑】：按下 IO46 退出浏览，返回实时预览
                if self.view_btn.value() == 0:
                    time.sleep_ms(20)
                    if self.view_btn.value() == 0:
                        print("🚪 退出浏览模式，返回实时画面模式")
                        while self.view_btn.value() == 0:
                            time.sleep_ms(20)
                        break  # 跳出浏览模式，恢复主循环

                time.sleep_ms(30)

        except OSError:
            print("⚠️ 未找到 photo.bmp！")
            self.ui.lcd.fill(0x0000)
            self.ui.font.text(
                self.ui.lcd, "尚未拍照无存图!", 40, 100, color=0xF800
            )
            self.ui.lcd.show()
            time.sleep_ms(1500)

    def handle_main_loop(self):
        """主循环处理：实时摄像头预览与拍照功能"""
        # === 1. 检测是否按下 IO46 进入浏览模式 ===
        if self.view_btn.value() == 0:
            time.sleep_ms(20)
            if self.view_btn.value() == 0:
                self.enter_view_mode()
                return

        # === 2. BOOT 按键 (IO0) 检测：短按拍照 / 长按开关相机 ===
        if self.boot_btn.value() == 0:
            if self.press_start_time == 0:
                self.press_start_time = time.ticks_ms()

            elif (
                time.ticks_diff(time.ticks_ms(), self.press_start_time) > 1500
            ):
                # 长按切换摄像头开关
                if self.cam.is_active:
                    self.cam.deinit_cam()
                    self.ui.lcd.fill(0x0000)
                    self.ui.font.text(
                        self.ui.lcd, "摄像头已关闭", 60, 100, color=0xF800
                    )
                    self.ui.lcd.show()
                else:
                    self.cam.init_cam()

                while self.boot_btn.value() == 0:
                    time.sleep_ms(20)
                self.press_start_time = 0

        else:
            if self.press_start_time > 0:
                duration = time.ticks_diff(
                    time.ticks_ms(), self.press_start_time
                )
                self.press_start_time = 0

                # 短按拍照
                if duration < 1000:
                    if self.cam.is_active:
                        print("📸 触发拍照中...")
                        buf = self.cam.capture_frame()
                        if buf:
                            # 闪烁白屏快门动画
                            try:
                                self.ui.lcd.fill(0xFFFF)
                                self.ui.lcd.show()
                            except Exception:
                                pass
                            time.sleep_ms(50)

                            # 保存图像
                            self.cam.save_photo_bmp(buf, "photo.bmp")

                            # 画面回显并提示
                            self.ui.lcd.push_camera_buf(buf, 320, 240)
                            time.sleep_ms(500)
                    else:
                        print("⚠️ 摄像头未开启！")

        # === 3. 摄像头开启时推流刷新 ===
        if self.cam.is_active:
            buf = self.cam.capture_frame()
            if buf:
                self.ui.lcd.push_camera_buf(buf, 320, 240)
            time.sleep_us(500)
        else:
            time.sleep_ms(50)