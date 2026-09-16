import struct
import time
from machine import I2S, Pin


class AudioRecorder:

    def __init__(self, sck_pin=47, ws_pin=21, sd_pin=38, sample_rate=16000):
        self.sample_rate = sample_rate
        self.sck_pin = sck_pin
        self.ws_pin = ws_pin
        self.sd_pin = sd_pin
        self.audio_in = None

    def _init_i2s(self):
        return I2S(
            0,
            sck=Pin(self.sck_pin),
            ws=Pin(self.ws_pin),
            sd=Pin(self.sd_pin),
            mode=I2S.RX,
            bits=16,
            format=I2S.STEREO,
            rate=self.sample_rate,
            ibuf=4096,
        )

    def _create_wav_header(self, pcm_len):
        byte_rate = self.sample_rate * 1 * 2
        header = bytearray(44)
        header[0:4] = b"RIFF"
        struct.pack_into("<I", header, 4, pcm_len + 36)
        header[8:12] = b"WAVE"
        header[12:16] = b"fmt "
        struct.pack_into("<I", header, 16, 16)
        struct.pack_into("<H", header, 20, 1)  # PCM
        struct.pack_into("<H", header, 22, 1)  # Mono
        struct.pack_into("<I", header, 24, self.sample_rate)
        struct.pack_into("<I", header, 28, byte_rate)
        struct.pack_into("<H", header, 32, 2)
        struct.pack_into("<H", header, 34, 16)
        header[36:40] = b"data"
        struct.pack_into("<I", header, 40, pcm_len)
        return header

    # =========================================================
    # 【补全】：按键动态控制录音（按住录音，松开或超时自动停止）
    # =========================================================
    def record_to_wav(self, filename="record.wav", button_pin=None, max_seconds=15):
        """按住按键录音，松开按键或超时自动停止"""
        self.audio_in = self._init_i2s()

        raw_buf = bytearray(2048)
        mono_buf = bytearray(1024)

        max_bytes = self.sample_rate * 2 * max_seconds
        total_pcm_bytes = 0

        try:
            # 丢弃前几帧电路脉冲杂音
            for _ in range(5):
                self.audio_in.readinto(raw_buf)

            print(f"\n🔴 开始录音（最长 {max_seconds} 秒，松开按键停止）...")

            with open(filename, "wb") as f:
                f.write(bytearray(44))  # 预留 WAV 头

                start_time = time.time()

                while total_pcm_bytes < max_bytes:
                    # 检查按键状态：如果传入了按键引脚且按键被松开（为高电平 1），终止录音
                    if button_pin is not None and button_pin.value() == 1:
                        # 消抖判断：防止瞬间接触不良误判
                        time.sleep_ms(30)
                        if button_pin.value() == 1:
                            print("⏹️ 监测到按键松开，停止录音！")
                            break

                    num_read = self.audio_in.readinto(raw_buf)
                    if num_read > 0:
                        idx = 0
                        # 4 字节为一帧，提取右通道声音（i+2, i+3）
                        for i in range(0, num_read, 4):
                            mono_buf[idx] = raw_buf[i + 2]
                            mono_buf[idx + 1] = raw_buf[i + 3]
                            idx += 2

                        f.write(memoryview(mono_buf)[:idx])
                        total_pcm_bytes += idx

            # 重新写入正确的 WAV 文件头
            with open(filename, "r+b") as f:
                f.seek(0)
                f.write(self._create_wav_header(total_pcm_bytes))

            print(f"✅ 录音完成！时长: {time.time() - start_time:.1f}s，保存为: {filename}")

        finally:
            self.close()

    # 原有的固定时长录音保留
    def record_fixed_seconds(self, filename="record.wav", record_time=5):
        self.audio_in = self._init_i2s()

        raw_buf = bytearray(2048)
        mono_buf = bytearray(1024)

        target_bytes = self.sample_rate * 2 * record_time
        total_pcm_bytes = 0

        try:
            for _ in range(5):
                self.audio_in.readinto(raw_buf)

            print(f"\n🔴 开始录音（时长 {record_time} 秒）...")

            with open(filename, "wb") as f:
                f.write(bytearray(44))

                start_time = time.time()

                while total_pcm_bytes < target_bytes:
                    num_read = self.audio_in.readinto(raw_buf)
                    if num_read > 0:
                        idx = 0
                        for i in range(0, num_read, 4):
                            mono_buf[idx] = raw_buf[i + 2]
                            mono_buf[idx + 1] = raw_buf[i + 3]
                            idx += 2

                        f.write(memoryview(mono_buf)[:idx])
                        total_pcm_bytes += idx

            with open(filename, "r+b") as f:
                f.seek(0)
                f.write(self._create_wav_header(total_pcm_bytes))

            print(f"⏹️ 录音结束！用时: {time.time() - start_time:.1f}s")

        finally:
            self.close()

    def close(self):
        if self.audio_in is not None:
            try:
                self.audio_in.deinit()
            except Exception:
                pass
            self.audio_in = None


# 函数名兼容性绑定（无论 main.py 调用 record 还是 record_to_wav 都能跑）
AudioRecorder.record = AudioRecorder.record_to_wav