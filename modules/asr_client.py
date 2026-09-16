# asr_client.py - AI 语音识别客户端 (生产优化与防卡死完整版)

import gc
import os
import time
import ujson as json
import usocket as socket

try:
    import ssl
except ImportError:
    import ussl as ssl

# 硅基流动 API 配置
SILICONFLOW_KEY = "sk-lisenkrkcvdlmmavgytlsnpwpodcfyqrmnszopgzwpwespbe"
HOST = "api.siliconflow.cn"
PORT = 443
PATH = "/v1/audio/transcriptions"
MODEL_NAME = "TeleAI/TeleSpeechASR"


def transcribe_wav(filename="record.wav"):
    """将本地 WAV 音频文件发送至硅基流动云端进行语音转文本 (ASR)"""
    gc.collect()

    # 1. 检查文件有效性
    try:
        file_size = os.stat(filename)[6]
        # 文件过小（如只包含 WAV 头或不足 1 秒静音），放弃请求
        if file_size <= 1000:
            print("⚠️ 录音时间过短或为空白静音，跳过识别")
            return ""
        print(f"📡 正在上传 {filename} ({file_size} 字节) 进行语音识别...")
    except Exception as e:
        return f"Error: 文件不存在 - {e}"

    boundary = "----ESP32Boundary7MA4YWxkTrZu0gW"

    header_data = (
        "--" + boundary + "\r\n"
        'Content-Disposition: form-data; name="file"; filename="'
        + filename
        + '"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    )

    model_data = (
        "\r\n--"
        + boundary
        + "\r\n"
        'Content-Disposition: form-data; name="model"\r\n\r\n'
        + MODEL_NAME
        + "\r\n--"
        + boundary
        + "--\r\n"
    )

    content_length = len(header_data) + file_size + len(model_data)

    s = None
    try:
        # 2. 建立 Socket 与 SSL 连接
        addr_info = socket.getaddrinfo(HOST, PORT)
        addr = addr_info[0][-1]

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(10.0)  # 建立连接与后续传输超时设为 10 秒
        raw_sock.connect(addr)

        if hasattr(ssl, "wrap_socket"):
            s = ssl.wrap_socket(raw_sock, server_hostname=HOST)
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(raw_sock, server_hostname=HOST)

        # 🌟 修复关键：MicroPython 的 SSLSocket 没有 settimeout 方法，安全捕获忽略
        try:
            s.settimeout(10.0)
        except AttributeError:
            pass

        # 3. 发送 HTTP POST 请求头
        http_headers = (
            "POST " + PATH + " HTTP/1.1\r\n"
            "Host: " + HOST + "\r\n"
            "Authorization: Bearer " + SILICONFLOW_KEY + "\r\n"
            "Content-Type: multipart/form-data; boundary=" + boundary + "\r\n"
            "Content-Length: " + str(content_length) + "\r\n"
            "Connection: close\r\n\r\n"
        )
        s.write(http_headers.encode("utf-8"))
        s.write(header_data.encode("utf-8"))

        # 4. 分块流式读取本地 WAV 并写入网络 Socket
        with open(filename, "rb") as f:
            buf = bytearray(2048)
            while True:
                num_read = f.readinto(buf)
                if num_read <= 0:
                    break
                s.write(memoryview(buf)[:num_read])

        s.write(model_data.encode("utf-8"))
        print("⬆️ 音频数据上传完成，等待云端 ASR 返回结果...")

        # 5. 动态安全接收响应
        response_data = bytearray()
        start_time = time.time()
        MAX_WAIT_TIME = 30  # 全流程极限安全保底（单位：秒）

        while True:
            # 极限保底：若全流程超过 30 秒无响应，强制跳出，防止系统挂死
            if time.time() - start_time > MAX_WAIT_TIME:
                print("⏱️ ASR 整体处理超时，强制退出")
                break

            try:
                chunk = s.read(512)
                if not chunk:
                    break  # 服务器完成响应并关闭连接，正常退出

                response_data.extend(chunk)

                # 解析优化：若已拿到完整 JSON 数据结构，立即提前结束读取
                if (
                    b"{" in response_data
                    and b"}" in response_data
                    and response_data.rstrip().endswith(b"}")
                ):
                    break
            except OSError:
                # 只有当连续 10 秒完全没有任何数据传输时，才会触发这里的无响应超时
                print("⚠️ 网络无响应或链路断开，退出等待")
                break

        if not response_data:
            return ""

        response_str = response_data.decode("utf-8", "ignore")

        # 6. 解析并提取 JSON 文本
        json_start = response_str.find("{")
        json_end = response_str.rfind("}")
        if json_start != -1 and json_end != -1:
            res_json = json.loads(response_str[json_start : json_end + 1])
            text = res_json.get("text", "")
            return text.strip()
        else:
            return ""

    except Exception as e:
        print("ASR 处理异常:", e)
        return ""
    finally:
        if s:
            try:
                s.close()
            except:
                pass
        gc.collect()