# main.py - AI 语音助手 + AI 画图（生产修复与优化版）

import gc
import time
from machine import Pin
import network
import usocket as socket

try:
    import urequests
except ImportError:
    import requests as urequests

# 简单的 MicroPython URL 编码函数（支持中文和特殊字符）
def urlencode(str_val):
    result = ""
    for c in str_val:
        # 保留字母、数字及常见安全字符
        if (('a' <= c <= 'z') or ('A' <= c <= 'Z') or ('0' <= c <= '9') or c in '_.-~'):
            result += c
        else:
            # 转换为 UTF-8 字节并做百分号编码
            for b in c.encode('utf-8'):
                result += f"%{b:02X}"
    return result

# 脱机上电硬件救急：强行拉高背光和 CS 引脚
try:
    Pin(13, Pin.OUT).value(1)  # 背光引脚 Pin 13
    Pin(14, Pin.OUT).value(1)  # CS 引脚 Pin 14
    time.sleep_ms(100)
except:
    pass

from display_ui import UIManager  # 导入 UI 模块

# 1. 初始化 UI 管理器
ui = UIManager()
ui.render(title="系统启动中", content="正在初始化硬件与网络...", color=0xFFFF)

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
BOOT_PIN = 0     # ESP32-S3 板载 Boot 键 GPIO0 (语音对话)
VOL_UP_PIN = 40  # IO40 VOL+ (音量增加)
IMG_BTN_PIN = 39 # IO39 按键 (按住说话生成 AI 图片)

button = Pin(BOOT_PIN, Pin.IN, Pin.PULL_UP)
btn_vol_up = Pin(VOL_UP_PIN, Pin.IN, Pin.PULL_UP)
btn_img = Pin(IMG_BTN_PIN, Pin.IN, Pin.PULL_UP)  # 画图触发按键

recorder = AudioRecorder(sck_pin=5, ws_pin=4, sd_pin=6, sample_rate=8000)
player = AudioPlayer(
    sck_pin=15,
    ws_pin=16,
    sd_pin=7,
    vol_up_pin=VOL_UP_PIN,
    vol_down_pin=39,
    init_vol=0.4,
)


def refresh_ui(title, content="", color=0xFFFF):
    ui.render(title, content, color)


# ==========================================
# 开机网络健康度诊断 (真实上传测速)
# ==========================================
def test_wifi_on_startup(ui_callback):
    import gc
    try:
        import ssl
    except ImportError:
        import ussl as ssl

    ui_callback("网络测速", "正在测试云端上传网速...", color=0xFFE0)

    HOST = "api.siliconflow.cn"
    data_size = 32 * 1024  # 32KB 测试数据
    s = None

    try:
        t0 = time.ticks_ms()
        addr = socket.getaddrinfo(HOST, 443)[0][-1]

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(10.0)
        raw_sock.connect(addr)

        if hasattr(ssl, "wrap_socket"):
            s = ssl.wrap_socket(raw_sock, server_hostname=HOST)
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(raw_sock, server_hostname=HOST)

        s.write(
            f"POST /v1/audio/transcriptions HTTP/1.1\r\nHost: {HOST}\r\nContent-Length: {data_size}\r\nConnection: close\r\n\r\n".encode()
        )

        buf = b"A" * 2048
        sent = 0
        while sent < data_size:
            s.write(buf)
            sent += len(buf)

        t_used = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
        speed = (data_size / 1024.0) / t_used if t_used > 0 else 0

        print(f"📊 开机测速完成：上传速度 {speed:.1f} KB/s，耗时 {t_used:.2f}s")

        if speed < 6.0:
            return False, f"上传网速极慢! ({speed:.1f}KB/s)\n语音上传容易超时！"
        else:
            return True, f"网速正常 ({speed:.1f}KB/s)"

    except Exception as e:
        print(f"测速失败: {e}")
        return False, f"云端测速超时！\n上传网络极差或防火墙拦截"
    finally:
        if s:
            try:
                s.close()
            except:
                pass
        gc.collect()


# ==========================================
# 2. 网络初始化
# ==========================================
ssid, pwd = load_wifi_config()
connect_ok = False
current_ip = None

if ssid and pwd:
    print(f"正在连接无线网络: {ssid}...")
    try:
        connect_ok, current_ip = connect_router_wifi(ssid, pwd, refresh_ui)
    except Exception as e:
        print(f"❌ Wi-Fi 连接过程异常: {e}")
        refresh_ui(
            "配网模式",
            "WiFi连接失败，请用手机连接热点配网",
            color=0xF800,
        )

if not connect_ok:
    print("WiFi 连接失败，启动配网模式...")
    refresh_ui(
        "配网模式", "WiFi连接失败，请用手机连接热点配网", color=0xF800
    )
    start_ap_web_server(refresh_ui)
else:
    try:
        wlan = network.WLAN(network.STA_IF)
        if hasattr(network.WLAN, "PM_NONE"):
            wlan.config(pm=network.WLAN.PM_NONE)
    except Exception as e:
        print(f"⚠️ Wi-Fi 省电模式设置跳过: {e}")

    print("🔍 正在诊断网络真实上传速度...")
    is_net_ok, net_msg = test_wifi_on_startup(refresh_ui)

    if not is_net_ok:
        print(f"⚠️ 警告！网络诊断不合格: {net_msg}")
        refresh_ui("⚠️ 网络上传差", net_msg, color=0xF800)
        time.sleep(4)
    else:
        print(f"✅ 网络诊断通过: {net_msg}")

wifi_online_last = False
refresh_ui(
    "AI 语音助手",
    "系统已就绪！\n长按 Boot 键聊天\n长按 IO39 键画图",
    color=0x07E0,
)

print("\n==================================")
print("👉 Boot 键(GPIO0)：按住语音对话")
print("🎨 IO39 键：按住说话生成 AI 图片")
print("🔊 VOL+(IO40)：增加音量")
print("==================================\n")

is_processing = False

# ==========================================
# 3. 业务主循环
# ==========================================
while True:
    try:
        gc.collect()
        online = is_sta_connected()

        if online != wifi_online_last:
            if online:
                print(f"✅ 网络已连接, IP 地址: {current_ip}")
                refresh_ui(
                    "网络已连接",
                    f"IP: {current_ip}\nBoot键聊天 | IO39画图",
                    color=0x07E0,
                )
            else:
                print("⚠️ 网络连接中断！")
                refresh_ui(
                    "网络中断",
                    "WiFi 连接已断开，请检查网络设置",
                    color=0xF800,
                )
            wifi_online_last = online

        # 1. 监测按键音量增加 (IO40)
        if not is_processing and btn_vol_up.value() == 0:
            time.sleep_ms(20)
            if btn_vol_up.value() == 0:
                player.volume_up()
                while btn_vol_up.value() == 0:
                    time.sleep_ms(20)

        # 2. 监测 IO39 画图按键（对接 passnow.tech 接口 - 增加安全闭环与流式下载）
        if not is_processing and btn_img.value() == 0:
            time.sleep_ms(20)
            if btn_img.value() == 0:
                is_processing = True
                resp = None
                img_resp = None
                try:
                    refresh_ui(
                        "AI 画图模式",
                        "麦克风就绪，请说出要画的内容...",
                        color=0xFFE0,
                    )
                    time.sleep_ms(300)

                    refresh_ui(
                        "正在倾听描述",
                        "请描述画面... (松开按键结束)",
                        color=0x07FF,
                    )
                    recorder.record_to_wav(
                        "record.wav", btn_img, max_seconds=15
                    )

                    if not is_sta_connected():
                        refresh_ui(
                            "网络错误",
                            "网络已断开，无法生成图片！",
                            color=0xF800,
                        )
                        continue

                    refresh_ui(
                        "识别提示词", "正在上传语音解析内容...", color=0xFFE0
                    )
                    prompt_text = transcribe_wav("record.wav")

                    if prompt_text and not str(prompt_text).startswith("Error"):
                        refresh_ui(
                            "AI 画图生成中",
                            f"提示词：{prompt_text}\n\n状态：正在请求后端生成...",
                            color=0xFFE0,
                        )

                        # 对中文提示词进行安全 URL 编码
                        encoded_prompt = urlencode(prompt_text)
                        api_url = f"https://www.passnow.tech/generate_bmp.php?prompt={encoded_prompt}"
                        print(f"🎨 正在请求生图 API: {api_url}")
                        
                        resp = urequests.get(api_url)
                        data = resp.json()
                        img_url = data.get("url")
                        
                        if not img_url:
                            raise Exception("后端未返回有效的图片下载链接")

                        refresh_ui(
                            "AI 画图生成中",
                            f"提示词：{prompt_text}\n\n状态：正在下载图像...",
                            color=0xFFE0,
                        )
                        print(f"📥 正在从链接下载图片: {img_url}")
                        
                        # 使用流式分块写入文件，避免大文件一次性爆内存
                        img_resp = urequests.get(img_url)
                        bmp_path = "output.bmp"
                        with open(bmp_path, "wb") as f:
                            while True:
                                chunk = img_resp.raw.read(512)
                                if not chunk:
                                    break
                                f.write(chunk)

                        # 刷屏显示 BMP 图像
                        print("🖼️ 正在刷新屏幕显示 BMP 图片...")
                        ui.lcd.draw_bmp(bmp_path, start_x=0, start_y=0)
                        ui.lcd.show()
                        print("✨ 图片渲染完成！")

                        time.sleep(5)
                    else:
                        refresh_ui(
                            "识别失败",
                            "没有听清画面描述，请重试",
                            color=0xF800,
                        )
                        time.sleep(2)

                except Exception as img_err:
                    print(f"💥 画图流程发生异常: {img_err}")
                    refresh_ui(
                        "画图失败", f"错误原因：{img_err}", color=0xF800
                    )
                    time.sleep(2)

                finally:
                    # 确保无论成败都关闭 HTTP 连接，防止 Socket 泄漏
                    if img_resp:
                        try: img_resp.close()
                        except: pass
                    if resp:
                        try: resp.close()
                        except: pass

                    try:
                        recorder.close()
                    except:
                        pass
                    is_processing = False
                    gc.collect()
                    refresh_ui(
                        "AI 语音助手",
                        "待机中\nBoot键聊天 | IO39画图",
                        color=0x07E0,
                    )

        # 3. 监测 Boot 键 (GPIO0) - 正常 AI 语音对话
        if not is_processing and button.value() == 0:
            time.sleep_ms(20)
            if button.value() == 0:
                is_processing = True

                try:
                    refresh_ui(
                        "准备录音", "麦克风就绪，请按住说话...", color=0xFFE0
                    )
                    time.sleep_ms(300)

                    refresh_ui(
                        "正在倾听",
                        "请说话... (松开按键结束)",
                        color=0x07FF,
                    )

                    print("\n🎙️ 听到按键，开始录音...")
                    recorder.record_to_wav(
                        "record.wav", button, max_seconds=15
                    )

                    if not is_sta_connected():
                        print("❌ 网络断开，无法上传音频！")
                        refresh_ui(
                            "网络错误",
                            "网络连接中断，无法上传音频！",
                            color=0xF800,
                        )
                        continue

                    print("🔍 正在识别语音...")
                    refresh_ui(
                        "语音识别", "正在上传音频并识别...", color=0xFFE0
                    )
                    user_text = transcribe_wav("record.wav")
                    print(f"🗣️ 用户说: {user_text}")

                    if user_text and not str(user_text).startswith("Error"):
                        refresh_ui(
                            "AI 思考中",
                            f"我：{user_text}\n\nAI 正在思考回答...",
                            color=0xFFE0,
                        )
                        print("🤖 正在请求 AI 大模型...")
                        ai_reply = chat_ask(user_text)
                        print(f"💡 AI 回答: {ai_reply}")

                        if (
                            ai_reply
                            and not ai_reply.startswith("HTTP")
                            and not ai_reply.startswith("Error")
                        ):
                            refresh_ui(
                                "AI 思考中",
                                f"我：{user_text}\n\n正在合成语音...",
                                color=0xFFE0,
                            )
                            tts_success = text_to_speech(
                                ai_reply, filename="tts_output.wav"
                            )

                            if tts_success:
                                print(
                                    "🔊 声文同步：播放语音并展示文字..."
                                )
                                refresh_ui("AI 回复", ai_reply, color=0xFFFF)
                                player.play_wav("tts_output.wav")
                            else:
                                refresh_ui("AI 回复", ai_reply, color=0xFFFF)
                        else:
                            print("⚠️ AI 返回异常文本，跳过 TTS 播报")
                    else:
                        err_str = str(user_text)
                        if (
                            "ETIMEDOUT" in err_str
                            or "116" in err_str
                            or "timeout" in err_str.lower()
                        ):
                            refresh_ui(
                                "上传超时",
                                "网络传输超时！\n1. 请检查Wi-Fi\n2. 尝试缩短说话时间",
                                color=0xF800,
                            )
                        else:
                            refresh_ui(
                                "识别失败",
                                "没有听清您说的话，请重试",
                                color=0xF800,
                            )
                        time.sleep(2)

                except Exception as req_err:
                    print(f"💥 业务交互流程发生捕获异常: {req_err}")
                    refresh_ui(
                        "发生异常", f"系统处理异常：{req_err}", color=0xF800
                    )
                    time.sleep(1.5)

                finally:
                    try:
                        recorder.close()
                    except:
                        pass
                    is_processing = False
                    gc.collect()
                    refresh_ui(
                        "AI 语音助手",
                        "待机中\nBoot键聊天 | IO39画图",
                        color=0x07E0,
                    )

    except Exception as main_err:
        print(f"🚨 主循环异常捕获: {main_err}")
        is_processing = False
        time.sleep(1)

    time.sleep(0.05)
