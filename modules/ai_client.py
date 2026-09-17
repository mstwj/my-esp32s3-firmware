# ai_client.py - 使用原生 Socket 避开 urequests 超时缺陷

import gc
import ujson as json
import usocket as socket

try:
    import ssl
except ImportError:
    import ussl as ssl

SILICONFLOW_KEY = "sk-lisenkrkcvdlmmavgytlsnpwpodcfyqrmnszopgzwpwespbe"
HOST = "api.siliconflow.cn"
PORT = 443
PATH = "/v1/chat/completions"
MODEL_NAME = "deepseek-ai/DeepSeek-V4-Flash"


def chat_ask(user_content: str) -> str:
    gc.collect()

    # 1. 严格控制字数与提示词，大幅减少大模型思考与传输时间
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个语音助手。请用自然口语化的中文回答。"
                    "回答必须极简，严格控制在150字以内，不超过两句话。"
                    "严禁使用 Emoji 表情、颜文字或 Markdown 符号。"
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 100,
        "temperature": 0.3,
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    print("Sending Payload Size:", len(payload_bytes))

    s = None
    try:
        # 解析 IP
        addr_info = socket.getaddrinfo(HOST, PORT)
        addr = addr_info[0][-1]

        # 2. 原生 Socket 创建，设置 60 秒硬超时（解决 ETIMEDOUT 的关键）
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(60)
        raw_sock.connect(addr)

        # TLS 包装
        if hasattr(ssl, "wrap_socket"):
            s = ssl.wrap_socket(raw_sock, server_hostname=HOST)
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(raw_sock, server_hostname=HOST)

        # 3. 发送 HTTP POST 请求头
        http_headers = (
            f"POST {PATH} HTTP/1.1\r\n"
            f"Host: {HOST}\r\n"
            f"Authorization: Bearer {SILICONFLOW_KEY}\r\n"
            f"Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(payload_bytes)}\r\n"
            f"Connection: close\r\n\r\n"
        )

        s.write(http_headers.encode("utf-8"))
        s.write(payload_bytes)

        # 4. 块读取响应，读完 JSON 即刻断开，绝不无效死等
        response_data = bytearray()
        while True:
            chunk = s.read(1024)
            if not chunk:
                break
            response_data.extend(chunk)

            # 匹配完整的 JSON 数据包结尾
            if b"}" in chunk and b"{" in response_data:
                # 简单校验 JSON 闭合
                if response_data.rstrip().endswith(b"}"):
                    break

        if not response_data:
            return "网络响应超时，请重试"

        response_str = response_data.decode("utf-8", "ignore")

        # 解析 JSON
        json_start = response_str.find("{")
        json_end = response_str.rfind("}")

        if json_start != -1 and json_end != -1:
            res_json = json.loads(response_str[json_start : json_end + 1])
            if "choices" in res_json and len(res_json["choices"]) > 0:
                content = res_json["choices"][0]["message"].get("content", "").strip()
                return content if content else "No content"
            else:
                return "AI 未返回有效文本"
        else:
            return f"HTTP 响应异常"

    except Exception as e:
        print(f"⚠️ AI 请求异常: {e}")
        return "网络响应超时，请重试"
    finally:
        if s:
            try:
                s.close()
            except:
                pass
        gc.collect()