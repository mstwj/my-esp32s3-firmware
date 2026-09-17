import urequests
import json

# 1. 请求后端 API 生成图片
prompt_text = "画一只猫咪"
api_url = f"https://www.passnow.tech/generate_bmp.php?prompt={prompt_text}"

print("正在请求后端生成图片...")
resp = urequests.get(api_url)
data = resp.json()
print("收到后端响应:", data)

# 2. 获取生成的 bmp 图片下载链接
img_url = data["url"]

# 3. 下载 BMP 图片并保存到 ESP32 本地（或直接写入 SD 卡）
print("正在下载 BMP 图片...")
img_resp = urequests.get(img_url)

with open("output.bmp", "wb") as f:
    f.write(img_resp.content)

print("图片已成功保存至:output.bmp")

# 释放 HTTP 响应连接
resp.close()
img_resp.close()