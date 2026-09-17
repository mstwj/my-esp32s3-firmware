# audio_recorder.py - 8-bit 减半体积极致优化版

import struct
import time
from machine import I2S, Pin


class AudioRecorder:

    def __init__(self, sck_pin=5, ws_pin=6, sd_pin=4, sample_rate=8000):
        self.sample_rate = sample_rate
        self.sck_pin = sck_pin
        self.ws_pin = ws_pin
        self.sd_pin = sd_pin
        self.audio_in = None

    def _init_i2s(self):
        """初始化 I2S 硬件"""
        for retry in range(3):
            try:
                return I2S(
                    0,
                    sck=Pin(self.sck_pin),
                    ws=Pin(self.ws_pin),
                    sd=Pin(self.sd_pin),
                    mode=I2S.RX,
                    bits=16,  # 硬件采 16 位保证信号质量
                    format=I2S.STEREO,
                    rate=self.sample_rate,
                    ibuf=4096,
                )
            except OSError as e:
                time.sleep_ms(50)
                if retry == 2:
                    raise e

    def _create_wav_header(self, pcm_len, channels=1, bits_per_sample=8):
        """生成标准 WAV 文件头 (默认为 8-bit)"""
        byte_rate = self.sample_rate * channels * (bits_per_sample // 8)
        block_align = channels * (bits_per_sample // 8)

        header = bytearray(44)
        header[0:4] = b"RIFF"
        struct.pack_into("<I", header, 4, pcm_len + 36)
        header[8:12] = b"WAVE"
        header[12:16] = b"fmt "
        struct.pack_into("<I", header, 16, 16)
        struct.pack_into("<H", header, 20, 1)  # PCM 格式
        struct.pack_into("<H", header, 22, channels)
        struct.pack_into("<I", header, 24, self.sample_rate)
        struct.pack_into("<I", header, 28, byte_rate)
        struct.pack_into("<H", header, 32, block_align)
        struct.pack_into("<H", header, 34, bits_per_sample)
        header[36:40] = b"data"
        struct.pack_into("<I", header, 40, pcm_len)
        return header

    def record_to_wav(self, filename, button_pin, max_seconds=15):
        """秒级响应录音：抽取高8位(8-bit)，体积减半"""
        self.audio_in = self._init_i2s()

        raw_buf = bytearray(2048)
        mono_8bit_buf = bytearray(512)  # 2048 字节 Raw 提取出 512 字节的单声道 8-bit
        total_pcm_bytes = 0

        # 8000Hz 8-bit 单声道，1 秒仅占用 8000 字节
        max_pcm_bytes = self.sample_rate * 1 * max_seconds

        try:
            # 丢弃 1 个 Buffer 剔除按键电平冲击
            self.audio_in.readinto(raw_buf)

            print(
                f"🎙️ 麦克风已就绪(8-bit超轻模式)，立即说话！(最长 {max_seconds} 秒)..."
            )

            with open(filename, "wb") as f:
                f.write(bytearray(44))  # 预留 WAV 头

                # 监听按键采集音频
                while (
                    button_pin.value() == 0 and total_pcm_bytes < max_pcm_bytes
                ):
                    num_read = self.audio_in.readinto(raw_buf)
                    if num_read > 0:
                        # 极致转换：提取双声道 16bit 里的左声道高 8 位，并转化为无符号 8bit (0~255)
                        idx = 0
                        for i in range(0, num_read, 4):
                            # raw_buf[i+1] 是 signed 16-bit 的高字节，加 128 转成 WAV 标准的 unsigned 8-bit
                            mono_8bit_buf[idx] = (raw_buf[i + 1] + 128) & 0xFF
                            idx += 1

                        f.write(memoryview(mono_8bit_buf)[:idx])
                        total_pcm_bytes += idx

                # 回填 WAV 头 (指定为 bits_per_sample=8)
                f.seek(0)
                header = self._create_wav_header(
                    total_pcm_bytes, channels=1, bits_per_sample=8
                )
                f.write(header)

            duration = total_pcm_bytes / self.sample_rate
            print(
                f"⏹️ 录音完成！时长: {duration:.1f}s, 文件大小: {total_pcm_bytes + 44} 字节"
            )

        finally:
            self.close()

    def close(self):
        """释放 I2S 资源"""
        if self.audio_in is not None:
            try:
                self.audio_in.deinit()
            except Exception:
                pass
            self.audio_in = None
            time.sleep_ms(50)