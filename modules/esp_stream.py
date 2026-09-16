# esp_stream.py - TCP 长连接推流端（带开机测速预热）
import time
import camera
import network
import usocket as socket

WIFI_SSID = "Aoyan"
WIFI_PASS = "A15344803439b"
PC_IP = "192.168.0.118"
PC_PORT = 9999  # 对应 PC 端 Python TCP 接收服务器的端口

# 1. 连 Wi-Fi 并关闭节能模式
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if not wlan.isconnected():
    print("🌐 正在连接 Wi-Fi...")
    wlan.connect(WIFI_SSID, WIFI_PASS)
    while not wlan.isconnected():
        time.sleep_ms(500)

# 关闭 Wi-Fi 节能，全速射频
try:
    wlan.config(pm=0xa411)
except:
    pass

print("✅ Wi-Fi 连接成功！IP:", wlan.ifconfig()[0])

# 2. 初始化摄像头 (QVGA 320x240)
try:
    camera.deinit()
    time.sleep_ms(200)
except:
    pass

camera.init(
    0,
    d0=11, d1=9, d2=8, d3=10,
    d4=12, d5=18, d6=17, d7=16,
    format=camera.JPEG,
    framesize=camera.FRAME_QVGA,  # 320x240
    xclk_freq=10000000,
    vsync=6, href=7, siod=4, sioc=5,
    pwdn=-1, reset=-1, xclk=15, pclk=13
)
print("🎉 摄像头初始化成功！")
time.sleep(1)

# 3. 建立 TCP 长连接的主循环（支持自动断线重连）
while True:
    print(f"🔗 正在连接推流服务端 {PC_IP}:{PC_PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # 禁用 Nagle 算法，发完即走
    try:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except:
        pass

    try:
        s.connect((PC_IP, PC_PORT))
        print("🚀 TCP 长连接建立成功！")
        
        # 【新增】开机快速测速预热
        print("🔍 正在评估当前网络吞吐量...")
        test_buf = b"\xFF" * 4096
        speed_start = time.ticks_ms()
        sent_kb = 0
        for _ in range(5):
            s.send(len(test_buf).to_bytes(4, 'big'))
            s.send(test_buf)
            sent_kb += 4
        speed_elapsed = time.ticks_diff(time.ticks_ms(), speed_start) / 1000.0
        if speed_elapsed > 0:
            print(f"📊 当前链路评估带宽: {sent_kb / speed_elapsed:.2f} KB/s")
        
        print("🎥 开始正式高速推流...")
        frame_count = 0
        fps_timer = time.ticks_ms()

        while True:
            buf = camera.capture()
            if not buf or len(buf) < 100:
                time.sleep_ms(10)
                continue

            # 发送协议：先发 4 字节的图片长度，再发图片内容
            img_len = len(buf)
            s.send(img_len.to_bytes(4, 'big'))
            s.send(buf)

            frame_count += 1
            if time.ticks_diff(time.ticks_ms(), fps_timer) >= 1000:
                print(f"📈 长连接实时推流帧率 (FPS): {frame_count} | 当前帧大小: {img_len} 字节")
                frame_count = 0
                fps_timer = time.ticks_ms()

    except Exception as err:
        print(f"⚠️ TCP 异常断开: {err}")
        try:
            s.close()
        except:
            pass
        print("🔄 2秒后尝试重新连接...")
        time.sleep(2) # 断线重连等待you yige 