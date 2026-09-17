# testwifi.py - 真实上传网速与 HTTPS 稳定性测试 (已修复 SSLTimeout 属性问题)

import gc
import time
import network
import usocket as socket

try:
    import ssl
except ImportError:
    import ussl as ssl

HOST = "api.siliconflow.cn"
PORT = 443


def test_upload_speed(data_size_kb=64):
    gc.collect()
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print("❌ 错误：Wi-Fi 未连接！")
        return False, 0

    rssi = wlan.status("rssi") if hasattr(wlan, "status") else -99
    print(f"\n📡 【Wi-Fi 信号】: {rssi} dBm")

    total_bytes = data_size_kb * 1024
    print(f"🚀 正在向 {HOST} 发起 {data_size_kb} KB SSL 真实上传测速...")

    s = None
    try:
        t_start = time.ticks_ms()

        # 1. 建立底层 Raw Socket 并设置 20 秒超时
        addr_info = socket.getaddrinfo(HOST, PORT)
        addr = addr_info[0][-1]

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(20.0)  # 底层 Socket 保持长超时
        raw_sock.connect(addr)

        # 2. SSL 包装 (不直接对 s 调用 settimeout)
        if hasattr(ssl, "wrap_socket"):
            s = ssl.wrap_socket(raw_sock, server_hostname=HOST)
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(raw_sock, server_hostname=HOST)

        # 3. 构造 HTTP Header
        http_header = (
            f"POST /v1/audio/transcriptions HTTP/1.1\r\n"
            f"Host: {HOST}\r\n"
            f"Content-Length: {total_bytes}\r\n"
            f"Content-Type: application/octet-stream\r\n"
            f"Connection: close\r\n\r\n"
        )
        s.write(http_header.encode("utf-8"))

        # 4. 循环发送数据并统计耗时
        dummy_chunk = b"X" * 2048  # 每次发 2KB
        sent_bytes = 0

        t_trans_start = time.ticks_ms()

        while sent_bytes < total_bytes:
            s.write(dummy_chunk)
            sent_bytes += len(dummy_chunk)
            if sent_bytes % (16 * 1024) == 0:
                print(f"   已上传 {sent_bytes // 1024} KB / {data_size_kb} KB...")

        t_trans_end = time.ticks_ms()

        # 计算纯上传速度
        trans_time_sec = (time.ticks_diff(t_trans_end, t_trans_start)) / 1000.0
        if trans_time_sec <= 0:
            trans_time_sec = 0.001

        speed_kbps = (total_bytes / 1024.0) / trans_time_sec

        print("\n---------------- 测速结果 ----------------")
        print(f"⏱️ 64KB 上传耗时: {trans_time_sec:.2f} 秒")
        print(f"⚡ 实际上传网速: {speed_kbps:.2f} KB/s")

        est_200k_time = 200.0 / speed_kbps
        print(f"📊 预测上传 200KB 录音需要: {est_200k_time:.1f} 秒")

        if speed_kbps < 8.0:
            print("🔴 判定：上传网速极慢 ( < 8 KB/s)，必定触发语音识别超时！")
            return False, speed_kbps
        else:
            print("🟢 判定：上传网速良好！")
            return True, speed_kbps

    except Exception as e:
        print(f"\n❌ 上传测速失败/卡死超时: {e}")
        return False, 0
    finally:
        if s:
            try:
                s.close()
            except:
                pass
        gc.collect()


if __name__ == "__main__":
    test_upload_speed(64)