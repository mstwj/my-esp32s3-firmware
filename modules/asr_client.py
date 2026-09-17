# asr_client.py - AI 语音识别客户端 (云端推理长超时优化版)

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
    """
    将本地 WAV 音频文件发送至硅基流动云端进行语音转文本 (ASR)
    """
    gc.collect()  # 发送前主动清理内存

    try:
        file_size = os.stat(filename)[6]
        print(f"📡 正在上传 {filename} ({file_size} 字节) 进行语音识别...")
    except Exception as e:
        return f"Error: 文件不存在 - {e}"

    boundary = "----ESP32Boundary7MA4YWxkTrZu0gW"

    header_data = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    )

    model_data = (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"{MODEL_NAME}\r\n"
        f"--{boundary}--\r\n"
    )

    content_length = len(header_data) + file_size + len(model_data)

    s = None
    try:
        # 1. 建立基础 Socket 链接
        addr_info = socket.getaddrinfo(HOST, PORT)
        addr = addr_info[0][-1]

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 核心设置：设置 30 秒长超时，防止云端大模型推理慢导致的读超时
        raw_sock.settimeout(60.0)
        raw_sock.connect(addr)

        # 2. 包装 SSL 加密层
        if hasattr(ssl, "wrap_socket"):
            s = ssl.wrap_socket(raw_sock, server_hostname=HOST)
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(raw_sock, server_hostname=HOST)

        # 3. 发送 HTTP 请求头
        http_headers = (
            f"POST {PATH} HTTP/1.1\r\n"
            f"Host: {HOST}\r\n"
            f"Authorization: Bearer {SILICONFLOW_KEY}\r\n"
            f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
            f"Content-Length: {content_length}\r\n"
            f"Connection: close\r\n\r\n"
        )
        s.write(http_headers.encode("utf-8"))
        s.write(header_data.encode("utf-8"))

        # 4. 流式高效发送音频 Payload
        with open(filename, "rb") as f:
            buf = bytearray(2048)
            while True:
                num_read = f.readinto(buf)
                if num_read <= 0:
                    break
                s.write(memoryview(buf)[:num_read])

        s.write(model_data.encode("utf-8"))
        print("⬆️ 音频数据已全部发完，等待云端 ASR 推理返回...")

        # 5. 接收云端返回的识别结果
        response_data = bytearray()
        while True:
            chunk = s.read(1024)
            if not chunk:
                break
            response_data.extend(chunk)
            # 匹配到完整 JSON 字符串即可提前退出
            if b"}" in chunk and b"{" in response_data:
                break

        if not response_data:
            return "Error: 服务器未返回数据"

        response_str = response_data.decode("utf-8", "ignore")

        # 6. 解析结果中的文本
        json_start = response_str.find("{")
        json_end = response_str.rfind("}")
        if json_start != -1 and json_end != -1:
            res_json = json.loads(response_str[json_start : json_end + 1])
            text = res_json.get("text", "")
            return text.strip()
        else:
            return f"Error: 响应格式异常 - {response_str[:100]}"

    except Exception as e:
        print("ASR 详细错误:", e)
        return f"Error: {str(e)}"
    finally:
        if s:
            try:
                s.close()
            except:
                pass
        gc.collect()  # 释放请求过程中占用的内存