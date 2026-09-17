from machine import Pin
import time
from audio_recorder import AudioRecorder

# ---------------- 1. 硬件引脚配置 ----------------
I2S_WS = 4  # IO4_WS
I2S_SCK = 5  # IO5_SCK
I2S_SD = 6  # IO6_SD
BOOT_PIN = 0  # ESP32-S3 板载 Boot 键固定为 GPIO0

WAV_FILE = "record.wav"

# 初始化 Boot 按键 (GPIO0 默认高电平，按下时变为 0)
button = Pin(BOOT_PIN, Pin.IN, Pin.PULL_UP)

# 初始化录音模块
recorder = AudioRecorder(
    sck_pin=I2S_SCK, ws_pin=I2S_WS, sd_pin=I2S_SD, sample_rate=16000
)

print("\n==================================")
print("👉 系统就绪！按住 Boot 键(GPIO0)录音，松开结束")
print("==================================\n")

# ---------------- 2. 主循环监听 ----------------
try:
    while True:
        # 检测按键按下 (0 代表按下)
        if button.value() == 0:
            time.sleep_ms(30)  # 按键消抖
            if button.value() == 0:
                print("\n🎙️ 检测到按键按下，开始录音...")

                # 调用按键录音函数：传入文件名和按键 Pin 对象
                recorder.record_to_wav(WAV_FILE, button)

                print("\n----------------------------------")
                print("👉 等待下一次按键对话...")

        time.sleep_ms(50)  # 降低 CPU 占用

except Exception as e:
    print("运行异常:", e)

finally:
    recorder.close()
    print("录音设备已释放。")