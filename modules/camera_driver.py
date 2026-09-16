import camera
import time

CAM_PINS = dict(
    d0=11,
    d1=9,
    d2=8,
    d3=10,
    d4=12,
    d5=18,
    d6=17,
    d7=16,
    format=0,  # RGB565 直出
    framesize=camera.FRAME_QVGA,  # 320x240
    fb_location=camera.PSRAM,  # 🌟 关键！强制要求 Camera 把 FrameBuffer 放到 PSRAM，腾出内部 SRAM 给 Wi-Fi
    xclk_freq=20000000,
    vsync=6,
    href=7,
    siod=4,
    sioc=5,
    pwdn=-1,
    reset=-1,
    xclk=15,
    pclk=13,    
)


class CameraController:

    def __init__(self):
        self.is_active = False

    def init_cam(self):
        """初始化摄像头"""
        try:
            camera.deinit()
            time.sleep_ms(100)
        except Exception:
            pass
        try:
            camera.init(0, **CAM_PINS)
            self.is_active = True
            print("🎉 摄像头初始化成功！")
            
            # 1. 设置垂直翻转 (0: 正常, 1: 翻转)
            camera.flip(1)
            # 2. 设置水平镜像 (0: 正常, 1: 镜像)
            camera.mirror(0)
            
            return True
        
        except Exception as e:
            self.is_active = False
            print(f"❌ 摄像头初始化失败: {e}")
            return False

    def deinit_cam(self):
        """关闭摄像头"""
        try:
            camera.deinit()
        except Exception:
            pass
        self.is_active = False
        print("🛑 摄像头已关闭！")

    def capture_frame(self):
        """抓取一帧图像"""
        if self.is_active:
            return camera.capture()
        return None

    @staticmethod
    def swap_endian(buf):
        """将 RGB565 大端/小端数据互换"""
        data = bytearray(len(buf))
        for i in range(0, len(buf), 2):
            data[i] = buf[i + 1]
            data[i + 1] = buf[i]
        return data

    def save_photo_bmp(self, buf, filename="photo.bmp", width=320, height=240):
        """生成标准 BMP 头并存入 Flash"""
        raw_size = width * height * 2
        file_size = 66 + raw_size

        header = bytearray(54)
        header[0:2] = b"BM"
        header[2:6] = file_size.to_bytes(4, "little")
        header[10:14] = (66).to_bytes(4, "little")
        header[14:18] = (40).to_bytes(4, "little")
        header[18:22] = width.to_bytes(4, "little")
        header[22:26] = (-height).to_bytes(4, "little")
        header[26:28] = (1).to_bytes(2, "little")
        header[28:30] = (16).to_bytes(2, "little")
        header[30:34] = (3).to_bytes(4, "little")
        header[34:38] = raw_size.to_bytes(4, "little")

        masks = bytearray(b"\x00\xf8\x00\x00\xe0\x07\x00\x00\x1f\x00\x00\x00")
        bmp_header = header + masks

        bmp_pixel_data = self.swap_endian(buf)
        with open(filename, "wb") as f:
            f.write(bmp_header)
            f.write(bmp_pixel_data)
        print(f"✅ 照片保存成功: {filename}")