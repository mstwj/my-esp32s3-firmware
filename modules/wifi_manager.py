import network
import socket
import time
import os
import machine

# WiFi常量配置
AP_SSID = "ESP32-Recorder"
AP_PWD = ""
WIFI_CFG_FILE = "wifi.cfg"

sta_wlan = network.WLAN(network.STA_IF)
sta_wlan.active(True)

ap_wlan = network.WLAN(network.AP_IF)


def load_wifi_config():
    """读取保存的WiFi账号密码"""
    try:
        with open(WIFI_CFG_FILE, "r") as f:
            ssid = f.readline().strip()
            pwd = f.readline().strip()
            return ssid, pwd
    except OSError:
        return None, None


def save_wifi_config(ssid, pwd):
    """保存WiFi账号密码到文件"""
    with open(WIFI_CFG_FILE, "w") as f:
        f.write(f"{ssid}\n{pwd}\n")


def connect_router_wifi(ssid, pwd, ui_callback=None):
    """STA连接路由器WiFi

    ui_callback(text1, text2): 界面刷新回调函数，如果为 None 则自动使用 print 打印
    返回：(成功标志, ip地址)
    """

    def notify(title, msg):
        if ui_callback:
            ui_callback(title, msg)
        else:
            print(f"[{title}] {msg}")

    # 优先清理 AP 模式，激活 STA 模式
    ap_wlan.active(False)
    sta_wlan.active(True)

    if sta_wlan.isconnected():
        ip = sta_wlan.ifconfig()[0]
        return True, ip

    notify("Connect WIFI...", ssid)
    try:
        sta_wlan.disconnect()
        time.sleep(0.1)
        sta_wlan.connect(ssid, pwd)
    except OSError:
        pass

    wait = 0
    # 缩短超时等待时间为 15 秒 (30 * 0.5s)
    while not sta_wlan.isconnected() and wait < 30:
        time.sleep(0.5)
        wait += 1

    if sta_wlan.isconnected():
        ip = sta_wlan.ifconfig()[0]
        notify("WIFI OK", f"IP:{ip}")
        return True, ip
    else:
        # 关键修正：连接失败必须强行断开并彻底关闭 STA 网卡
        sta_wlan.disconnect()
        sta_wlan.active(False)
        time.sleep(0.5)
        notify("WIFI Connect Fail", "Enter AP Mode")
        return False, None


def start_ap_web_server(ui_callback=None):
    """开启AP热点 + Web配网服务"""
    # 1. 彻底断开并关闭 STA 模式
    try:
        sta_wlan.disconnect()
        sta_wlan.active(False)
    except:
        pass
    time.sleep_ms(300)
    
    # 启动 AP 模式
    ap_wlan.active(True)
    time.sleep_ms(300)  # 给底层 Wi-Fi 驱动 300ms 启动时间
    ap_wlan.config(essid=AP_SSID, authmode=network.AUTH_OPEN)
    time.sleep(0.5)

    print(f"✅ 热点已成功开启：{AP_SSID}，请用手机连接后访问 192.168.4.1")

    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>ESP32 WIFI配置</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
    </head>
    <body>
        <h3>WiFi参数设置</h3>
        <form action="/save" method="post">
            SSID:<br>
            <input type="text" name="ssid"><br><br>
            PASSWORD:<br>
            <input type="text" name="pwd"><br><br>
            <input type="submit" value="保存并重启">
        </form>
    </body>
    </html>
    """

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    
    if ui_callback:
        ui_callback("AP MODE", "192.168.4.1")

    while True:
        try:
            conn, addr = s.accept()
            req = conn.recv(1024).decode()

            if "POST /save" in req:
                try:
                    body = req.split("\r\n\r\n")[1]
                    # 解析 URL 编码格式的参数
                    params = dict(x.split("=") for x in body.split("&"))
                    new_ssid = params["ssid"].replace("+", " ")
                    new_pwd = params["pwd"].replace("+", " ")
                    
                    # 简单的 URL 解码（处理常见的特殊字符 %20 等）
                    for k, v in [("%20", " "), ("%21", "!"), ("%40", "@"), ("%23", "#")]:
                        new_ssid = new_ssid.replace(k, v)
                        new_pwd = new_pwd.replace(k, v)

                    save_wifi_config(new_ssid, new_pwd)

                    resp = """HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

<h3>保存成功！设备即将重启接入新 WiFi</h3>
<script>setTimeout(()=>{window.location.reload()},3000)</script>
"""
                    conn.send(resp.encode("utf-8"))
                    conn.close()
                    time.sleep(1.5)
                    s.close()
                    machine.reset()  # 重启设备连接新 Wi-Fi
                except Exception as e:
                    conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n参数解析错误！".encode("utf-8"))
                    conn.close()
            else:
                conn.send(f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n{html_page}".encode("utf-8"))
                conn.close()
        except Exception as e:
            print("Web Server Error:", e)


def is_sta_connected():
    return sta_wlan.isconnected()


def get_ip():
    if sta_wlan.isconnected():
        return sta_wlan.ifconfig()[0]
    return None