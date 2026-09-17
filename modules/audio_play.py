from array import array
import struct
import time
from machine import I2S, Pin


class AudioPlayer:

    def __init__(
        self,
        sck_pin=15,
        ws_pin=16,
        sd_pin=7,
        vol_up_pin=None,
        vol_down_pin=None,
        init_vol=0.4,
    ):
        self.sck_pin = sck_pin
        self.ws_pin = ws_pin
        self.sd_pin = sd_pin

        # 音量范围设为 0.0 ~ 1.0
        self.volume = max(0.0, min(1.0, init_vol))

        # 配置按键 GPIO
        if isinstance(vol_up_pin, int):
            self.btn_up = Pin(vol_up_pin, Pin.IN, Pin.PULL_UP)
        else:
            self.btn_up = vol_up_pin

        if isinstance(vol_down_pin, int):
            self.btn_down = Pin(vol_down_pin, Pin.IN, Pin.PULL_UP)
        else:
            self.btn_down = vol_down_pin

        self._last_press_time = 0  # 按键防抖时间戳

    def volume_up(self, step=0.1):
        """供外部调用的音量增加方法"""
        self.volume = min(1.0, round(self.volume + step, 2))
        print(f"🔊 音量增加: {int(self.volume * 100)}%")

    def volume_down(self, step=0.1):
        """供外部调用的音量减少方法"""
        self.volume = max(0.0, round(self.volume - step, 2))
        print(f"🔉 音量降低: {int(self.volume * 100)}%")

    def _check_volume_buttons(self):
        """内部方法：播放过程中轮询按键动态修改音量"""
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_press_time) < 150:
            return

        if self.btn_up and self.btn_up.value() == 0:
            self.volume_up()
            self._last_press_time = now

        elif self.btn_down and self.btn_down.value() == 0:
            self.volume_down()
            self._last_press_time = now

    def play_wav(self, filename):
        """播放 WAV 文件，并在播放循环中响应按键调节音量"""
        try:
            f = open(filename, "rb")
        except OSError:
            print(f"❌ 无法打开音频文件: {filename}")
            return

        i2s = None
        with f:
            header = f.read(44)
            if len(header) < 44:
                print("❌ WAV 文件头错误")
                return

            num_channels = struct.unpack("<H", header[22:24])[0]
            sample_rate = struct.unpack("<I", header[24:28])[0]
            bits_per_sample = struct.unpack("<H", header[34:36])[0]

            audio_format = I2S.MONO if num_channels == 1 else I2S.STEREO

            try:
                # 初始化播放用 I2S
                i2s = I2S(
                    0,
                    sck=Pin(self.sck_pin),
                    ws=Pin(self.ws_pin),
                    sd=Pin(self.sd_pin),
                    mode=I2S.TX,
                    bits=bits_per_sample,
                    format=audio_format,
                    rate=sample_rate,
                    ibuf=4096,
                )

                chunk_size = 2048

                while True:
                    self._check_volume_buttons()

                    data = f.read(chunk_size)
                    if not data:
                        break

                    vol_scale = int(self.volume * 256)
                    samples = array("h", data)

                    if vol_scale < 256:
                        for i in range(len(samples)):
                            samples[i] = (samples[i] * vol_scale) >> 8

                    i2s.write(samples)

                time.sleep_ms(100)  # 播放余音

            finally:
                if i2s:
                    try:
                        i2s.deinit()  # 强行反初始化 I2S 0 外设
                    except:
                        pass
                time.sleep_ms(
                    100
                )  # 关键修改：给底层 ESP32 硬件驱动 100ms 复位时间