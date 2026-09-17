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
print("显示：绿色 (GREEN)")# main.py - 增强健壮性与防崩溃处理的主流程


import time
import gc

# 脱机上电硬件救急：强行拉高背光和 CS 引脚
try:
    Pin(13, Pin.OUT).value(1) # 背光引脚 Pin 13 强行给高电平
    Pin(14, Pin.OUT).value(1) # CS 引脚 Pin 14 强行给高电平
    time.sleep_ms(100)        # 给电平稳定留出 100ms
except:
    pass

from display_ui import UIManager  # 导入全新的 UI 模块
ui = UIManager()
ui.render(title="系统启动中", content="正在初始化硬件与网络...", color=0xFFFF)

from machine import Pin
import network
from ai_client import chat_ask
from asr_client import transcribe_wav
from audio_play import AudioPlayer
from audio_recorder import AudioRecorder

from tts_client import text_to_speech
from wifi_manager import (
    connect_router_wifi,
    is_sta_connected,
    load_wifi_config,
    start_ap_web_server,
)


# ==========================================
# 1. 初始化 硬件、UI 与 全局对象
# ==========================================
BOOT_PIN = 0  # ESP32-S3 板载 Boot 键固定为 GPIO0
VOL_UP_PIN = 40  # IO40 VOL+
VOL_DOWN_PIN = 39  # IO39 VOL-

# 初始化按键引脚
button = Pin(BOOT_PIN, Pin.IN, Pin.PULL_UP)
btn_vol_up = Pin(VOL_UP_PIN, Pin.IN, Pin.PULL_UP)
btn_vol_down = Pin(VOL_DOWN_PIN, Pin.IN, Pin.PULL_UP)

# 初始化录音与播放模块
recorder = AudioRecorder(sck_pin=5, ws_pin=4, sd_pin=6, sample_rate=16000)
player = AudioPlayer(
    sck_pin=15,
    ws_pin=16,
    sd_pin=7,
    vol_up_pin=VOL_UP_PIN,
    vol_down_pin=VOL_DOWN_PIN,
    init_vol=0.4,
)



# 设置 UI 刷新全局回调函数 (适配 wifi_manager 内部调用)
def refresh_ui(title, content="", color=0xFFFF):
    ui.render(title, content, color)


# ==========================================
# 2. 网络初始化
# ==========================================
ssid, pwd = load_wifi_config()
connect_ok = False
current_ip = None

if ssid and pwd:
    print("正在连接无线网络...")    
    try:
        connect_ok, current_ip = connect_router_wifi(ssid, pwd,refresh_ui)
    except Exception as e:
        print(f"❌ Wi-Fi 连接过程异常: {e}")
        refresh_ui("配网模式", "WiFi连接失败，请用手机连接热点配网", color=0xF800)

if not connect_ok:    
    print("WiFi 连接失败，启动配网模式...")
    refresh_ui("配网模式", "WiFi连接失败，请用手机连接热点配网", color=0xF800)
    start_ap_web_server()
else:
    try:
        wlan = network.WLAN(network.STA_IF)
        if hasattr(network.WLAN, "PM_NONE"):
            wlan.config(pm=network.WLAN.PM_NONE)
    except Exception as e:
        print(f"⚠️ Wi-Fi 省电模式设置跳过: {e}")

wifi_online_last = False
refresh_ui("AI 语音助手", "系统已就绪！长按 Boot 键开始说话", color=0x07E0)

print("\n==================================")
print("👉 系统就绪！长按 Boot 键(GPIO0)说话")
print("🔊 VOL+(IO40) / VOL-(IO39) 调节音量")
print("==================================\n")

# 全局运行锁，防止用户瞎按/连击导致的硬件抢占与重复请求
is_processing = False

# ==========================================
# 3. 业务主循环
# ==========================================
while True:
    try:
        gc.collect()  # 循环首行主动 GC，保证内存健康
        online = is_sta_connected()

        # 网络状态变化监测
        if online != wifi_online_last:
            if online:
                print(f"✅ 网络已连接, IP 地址: {current_ip}")
                refresh_ui("网络已连接", f"IP: {current_ip}\n系统就绪，长按 Boot 键说话！", color=0x07E0)
            else:
                print("⚠️ 网络连接中断！")
                refresh_ui("网络中断", "WiFi 连接已断开，请检查网络设置", color=0xF800)
            wifi_online_last = online

        # ---------------- 监测 VOL+ 按键 ----------------
        if not is_processing and btn_vol_up.value() == 0:
            time.sleep_ms(20)  # 消抖
            if btn_vol_up.value() == 0:
                player.volume_up()
                while btn_vol_up.value() == 0:
                    time.sleep_ms(20)

        # ---------------- 监测 VOL- 按键 ----------------
        if not is_processing and btn_vol_down.value() == 0:
            time.sleep_ms(20)  # 消抖
            if btn_vol_down.value() == 0:
                player.volume_down()
                while btn_vol_down.value() == 0:
                    time.sleep_ms(20)

        # ---------------- 监测 Boot 录音按键 ----------------
        if not is_processing and button.value() == 0:
            time.sleep_ms(50)  # 加强按键防抖
            if button.value() == 0:
                is_processing = True  # 加锁，屏蔽后续重复按键触发

                try:
                    # 步骤 1：录音（带 50s 兜底上限）
                    print("\n🎙️ 听到按键，开始录音...")
                    refresh_ui("正在倾听", "正在录音中，松开或结束说话...", color=0x07FF)
                    recorder.record_to_wav("record.wav", button, max_seconds=50)

                    # 强网络校验
                    if not is_sta_connected():
                        print("❌ 网络断开，无法上传音频！")
                        refresh_ui("网络错误", "网络连接中断，无法上传音频！", color=0xF800)
                        continue

                    # 步骤 2：语音识别 (ASR)
                    print("🔍 正在识别语音...")
                    refresh_ui("语音识别", "正在识别您的语音内容...", color=0xFFE0)
                    user_text = transcribe_wav("record.wav")
                    print(f"🗣️ 用户说: {user_text}")

                    # 步骤 3：AI 思考与回答
                    if user_text and not str(user_text).startswith("Error"):
                        refresh_ui("AI 思考中", f"我：{user_text}\n\nAI 正在思考回答...", color=0xFFE0)
                        print("🤖 正在请求 AI 大模型...")
                        ai_reply = chat_ask(user_text)
                        print(f"💡 AI 回答: {ai_reply}")
                        
                        refresh_ui("AI 回复", ai_reply, color=0xFFFF)

                        # 步骤 4：文本转语音 (TTS)
                        if (
                            ai_reply
                            and not ai_reply.startswith("HTTP")
                            and not ai_reply.startswith("Error")
                        ):
                            tts_success = text_to_speech(
                                ai_reply, filename="tts_output.wav"
                            )

                            # 步骤 5：音频播放
                            if tts_success:
                                print("🔊 正在播放语音回答...")
                                player.play_wav("tts_output.wav")
                        else:
                            print("⚠️ AI 返回异常文本，跳过 TTS 播报")
                    else:
                        print("⚠️ 没有听清或识别失败，请重试")
                        refresh_ui("识别失败", "没有听清您说的话，请重试", color=0xF800)
                        time.sleep(1)

                except Exception as req_err:
                    print(f"💥 业务交互流程发生捕获异常: {req_err}")
                    refresh_ui("发生异常", "业务交互流程发生捕获异常，请重试", color=0xF800)

                finally:
                    # 无论成功或失败，强制安全复位硬件与状态
                    try:
                        recorder.close()
                    except:
                        pass
                    is_processing = False  # 解锁
                    gc.collect()
                    refresh_ui("AI 语音助手", "待机中，长按 Boot 键开始下一次对话", color=0x07E0)
                    print("\n----------------------------------")
                    print("👉 等待下一次按键对话...")

    except Exception as main_err:
        # 顶层兜底防护，绝对防止主循环崩溃退出
        print(f"🚨 主循环异常捕获: {main_err}")
        is_processing = False
        time.sleep(1)

    time.sleep(0.05)

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


