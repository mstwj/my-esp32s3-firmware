# tts_client.py
import gc
import json
import urequests

URL = "https://api.siliconflow.cn/v1/audio/speech"
API_KEY = (
    "sk-lisenkrkcvdlmmavgytlsnpwpodcfyqrmnszopgzwpwespbe"  # 你的 API Key
)


def clean_text(text):
    """过滤特殊字符，防止请求报错"""
    if not text:
        return ""
    cleaned_chars = []
    for char in text:
        code = ord(char)
        if (
            (32 <= code <= 126)
            or (0x4E00 <= code <= 0x9FA5)
            or (0x3000 <= code <= 0x303F)
            or (0xFF00 <= code <= 0xFFEF)
        ):
            cleaned_chars.append(char)
    return "".join(cleaned_chars).strip()


def text_to_speech(text, filename="tts_output.wav"):
    safe_text = clean_text(text)
    print(f"🤖 [TTS] 过滤后的合成文本: '{safe_text}'")

    if not safe_text:
        print("❌ [TTS] 文本为空，取消请求")
        return False

    payload = {
        "model": "FunAudioLLM/CosyVoice2-0.5B",
        "input": safe_text,
        "voice": "FunAudioLLM/CosyVoice2-0.5B:anna",
        "response_format": "wav",  # 直接让 API 返回 WAV 格式给 ESP32 播放
        "stream": False,
    }

    headers = {
        "Authorization": "Bearer " + API_KEY,
        "Content-Type": "application/json",
    }

    print("🤖 [TTS] 正在请求文本转语音...")
    try:
        json_bytes = json.dumps(payload).encode("utf-8")
        response = urequests.post(URL, data=json_bytes, headers=headers)

        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            response.close()
            gc.collect()
            print("🔊 [TTS] 语音合成成功！")
            return True
        else:
            print(f"❌ [TTS] 状态码错误: {response.status_code}")
            print(response.text)
            response.close()
            return False

    except Exception as e:
        print("❌ [TTS] 请求发生异常:", e)
        return False