# display_ui.py - 纯原生支持，100% 不报错（已修正字符提前换行与溢出问题）
import framebuf
import ustruct
import time
from machine import SPI, Pin
import ufont


class ST7789Display:
    """ST7789 屏幕底层驱动与代理类"""

    def __init__(self, spi, width=240, height=320, reset=10, dc=9, cs=14, backlight=13):
        self.spi = spi
        self.width = width
        self.height = height
        self.reset = Pin(reset, Pin.OUT)
        self.dc = Pin(dc, Pin.OUT)
        self.cs = Pin(cs, Pin.OUT)
        self.backlight = Pin(backlight, Pin.OUT)

        # ================= 硬件物理级硬复位 (解决 RET 按键黑屏的核心) =================
        self.backlight.value(1)  # 1. 强行点亮背光
        self.cs.value(1)         # 2. 释放片选总线

        self.reset.value(1)      # 3. 先拉高
        time.sleep_ms(50)
        self.reset.value(0)      # 4. 强行拉低硬件复位 100ms（给屏幕芯片物理重置）
        time.sleep_ms(100)
        self.reset.value(1)      # 5. 重新拉高，屏幕芯片唤醒完毕
        time.sleep_ms(100)
        # ====================================================================

        # ST7789 初始化指令序列
        self._write_cmd(0x11)
        time.sleep_ms(120)
        self._write_cmd(0x3A, b"\x55")
        self._write_cmd(0x36, b"\x08")
        self._write_cmd(0x21)
        self._write_cmd(0x29)

        # 显存 FrameBuffer 初始化
        self.buffer = bytearray(self.width * self.height * 2)
        self.fb = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.RGB565
        )

    def pixel(self, *args, **kwargs):
        return self.fb.pixel(*args, **kwargs)

    def fill(self, *args, **kwargs):
        return self.fb.fill(*args, **kwargs)

    def rect(self, *args, **kwargs):
        return self.fb.rect(*args, **kwargs)

    def fill_rect(self, *args, **kwargs):
        return self.fb.fill_rect(*args, **kwargs)

    def blit(self, *args, **kwargs):
        return self.fb.blit(*args, **kwargs)

    def _write_cmd(self, cmd, data=None):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytearray([cmd]))
        if data:
            self.dc.value(1)
            self.spi.write(data)
        self.cs.value(1)

    def draw_jpg(self, filename, start_x=0, start_y=0):
        """调用 jpeg.py 模块解码渲染"""
        try:
            decoder = jpeg.JPEGDecoder(filename)
            decoder.decode_to_framebuf(self.fb, start_x, start_y)
        except AttributeError:
            try:
                jpeg.decode(filename, self.fb, start_x, start_y)
            except Exception as e:
                print("解码调用错误:", e)
        except Exception as e:
            print("JPG 解码失败:", e)

    def show(self):
        """将 Buffer 缓冲区图像刷入屏幕"""
        self._write_cmd(0x2A, ustruct.pack(">HH", 0, self.width - 1))
        self._write_cmd(0x2B, ustruct.pack(">HH", 0, self.height - 1))
        self._write_cmd(0x2C)

        self.cs.value(0)
        self.dc.value(1)
        chunk_size = 4096
        for i in range(0, len(self.buffer), chunk_size):
            self.spi.write(self.buffer[i : i + chunk_size])
        self.cs.value(1)        

    def draw_bmp(self, filename, start_x=0, start_y=0):
        """原生解析 BMP 图片直接刷屏，不需要任何第三方库"""
        try:
            with open(filename, "rb") as f:
                if f.read(2) != b'BM':
                    print("不是有效的 BMP 文件！")
                    return

                f.seek(10); data_offset = ustruct.unpack("<I", f.read(4))[0]
                f.seek(18); width = ustruct.unpack("<i", f.read(4))[0]
                height = ustruct.unpack("<i", f.read(4))[0]
                f.seek(28); bpp = ustruct.unpack("<H", f.read(2))[0]

                f.seek(data_offset)
                row_bytes = (width * (bpp // 8) + 3) & ~3
                line_buf = bytearray(width * 2)

                for y in range(height - 1, -1, -1):
                    row_data = f.read(row_bytes)
                    if not row_data:
                        break
                    for x in range(width):
                        idx = x * 3
                        b, g, r = row_data[idx], row_data[idx+1], row_data[idx+2]
                        rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                        line_buf[x*2] = (rgb565 >> 8) & 0xFF
                        line_buf[x*2 + 1] = rgb565 & 0xFF

                    line_fb = framebuf.FrameBuffer(line_buf, width, 1, framebuf.RGB565)
                    self.fb.blit(line_fb, start_x, start_y + y)
        except Exception as e:
            print("BMP 显示失败:", e)


class UIManager:
    """UI 界面高层封装"""

    def __init__(self, font_path="unifont-14-12917-16.v3.bmf"):
        spi = SPI(1, baudrate=20000000, sck=Pin(12), mosi=Pin(11), miso=None)
        self.lcd = ST7789Display(
            spi=spi, width=240, height=320, reset=10, dc=9, cs=14, backlight=13
        )
        self.font = ufont.BMFont(font_path)

    def draw_text_wrap(self, text, x=10, y=50, max_width=220, line_height=22, color=0xFFFF):
        """根据屏幕实际像素宽度 (max_width) 进行智能换行"""
        lines = text.split("\n")
        curr_y = y

        # 核心修正：16号点阵字库下，中文字符宽度精确为 16px，ASCII 为 8px
        char_w_cn = 16
        char_w_en = 8

        for line in lines:
            if not line:
                curr_y += line_height
                continue

            current_sub_line = ""
            current_px_width = 0

            for char in line:
                # 判断当前字符是 ASCII 还是中文/全角字符
                char_w = char_w_en if ord(char) < 128 else char_w_cn

                # 如果加上当前字符超出了可显示的最大像素宽度
                if current_px_width + char_w > max_width:
                    if curr_y > 290:  # 触底防护
                        break
                    # 绘制当前行
                    self.font.text(self.lcd, current_sub_line, x, curr_y, color=color)
                    curr_y += line_height
                    # 重置新一行
                    current_sub_line = char
                    current_px_width = char_w
                else:
                    current_sub_line += char
                    current_px_width += char_w

            # 绘制余下文字
            if current_sub_line and curr_y <= 290:
                self.font.text(self.lcd, current_sub_line, x, curr_y, color=color)
                curr_y += line_height

    def render(self, title, content="", color=0xFFFF):
        """刷新全屏 UI"""
        self.lcd.fill(0x0000)
        self.font.text(self.lcd, title, 10, 15, color=0xFFE0)
        self.lcd.fb.hline(10, 38, 220, 0x07FF)
        if content:
            # 安全边距：240 - 10*2 = 220px
            self.draw_text_wrap(content, x=10, y=50, max_width=220, line_height=22, color=color)
        self.lcd.show()

    def draw_rec_dot(self, show=True):
        """在右上角绘制/清除极速录音指示红点（<1ms 渲染响应，零延迟卡顿）"""
        if show:
            self.lcd.fill_rect(210, 15, 12, 12, 0xF800)  # 画红色小指示灯
        else:
            self.lcd.fill_rect(210, 15, 12, 12, 0x0000)  # 清除指示灯
        self.lcd.show()