import gc
import json
import os
import urequests


class AIBMPClient:

    def __init__(self):
        self.sf_api_url = "https://api.siliconflow.cn/v1/images/generations"
        self.sf_api_key = (
            "sk-lisenkrkcvdlmmavgytlsnpwpodcfyqrmnszopgzwpwespbe"
        )
        self.sf_model = "Tongyi-MAI/Z-Image"
        self.sf_image_size = "768x1024"

        self.convert_url = "https://www.passnow.tech/convert.php"
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )

    def _generate_png_url(self, prompt, status_cb=None):
        if status_cb:
            status_cb("AI 正在绘图中...")

        clean_prompt = str(prompt).strip().replace("\n", " ").replace("\r", "")
        print("🎨 1. 调用 AI 生图接口... 提示词:", clean_prompt)

        payload = {
            "model": self.sf_model,
            "prompt": clean_prompt,
            "image_size": self.sf_image_size,
        }
        headers = {
            "Authorization": "Bearer " + self.sf_api_key,
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": self.ua,
        }

        gc.collect()
        json_bytes = json.dumps(payload).encode("utf-8")
        resp = urequests.post(self.sf_api_url, headers=headers, data=json_bytes)

        if resp.status_code != 200:
            err_msg = resp.text
            resp.close()
            raise RuntimeError("AI生图失败: " + str(resp.status_code))

        data = resp.json()
        resp.close()
        gc.collect()

        img_url = None
        for key in ("images", "data"):
            arr = data.get(key)
            if isinstance(arr, list) and len(arr) > 0:
                img_url = arr[0].get("url")
                if img_url:
                    break

        if not img_url:
            raise RuntimeError("未在响应中找到图片 URL")

        return img_url

    def _download_png_bytes(self, png_url, status_cb=None):
        if status_cb:
            status_cb("正在下载高清原图...")

        print("📥 2. 下载 PNG 原图到内存...")
        gc.collect()

        resp = urequests.get(png_url, headers={"User-Agent": self.ua})
        if resp.status_code != 200:
            resp.close()
            raise RuntimeError("下载 PNG 失败")

        img_bytes = resp.content
        resp.close()
        gc.collect()

        print(f"✅ PNG 下载完成: {len(img_bytes)} 字节")
        return img_bytes

    def _upload_to_convert_php(
        self,
        image_bytes,
        save_path="output.bmp",
        bmp_w=240,
        bmp_h=320,
        status_cb=None,
    ):
        if status_cb:
            status_cb("正在云端转码 BMP...")

        print("🚀 3. 打包上传至 convert.php...")

        boundary = "----ESP32S3Boundary123456789"
        body = []

        body.append(f"--{boundary}\r\n".encode("utf-8"))
        body.append(
            'Content-Disposition: form-data; name="format"\r\n\r\n'.encode(
                "utf-8"
            )
        )
        body.append(f"{'bmp'}\r\n".encode("utf-8"))

        body.append(f"--{boundary}\r\n".encode("utf-8"))
        body.append(
            'Content-Disposition: form-data; name="width"\r\n\r\n'.encode(
                "utf-8"
            )
        )
        body.append(f"{bmp_w}\r\n".encode("utf-8"))

        body.append(f"--{boundary}\r\n".encode("utf-8"))
        body.append(
            'Content-Disposition: form-data; name="height"\r\n\r\n'.encode(
                "utf-8"
            )
        )
        body.append(f"{bmp_h}\r\n".encode("utf-8"))

        body.append(f"--{boundary}\r\n".encode("utf-8"))
        body.append(
            'Content-Disposition: form-data; name="image";'
            ' filename="gen.png"\r\n'.encode("utf-8")
        )
        body.append("Content-Type: image/png\r\n\r\n".encode("utf-8"))
        body.append(image_bytes)
        body.append("\r\n".encode("utf-8"))

        body.append(f"--{boundary}--\r\n".encode("utf-8"))

        payload = b"".join(body)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": self.ua,
        }

        gc.collect()
        resp = urequests.post(
            self.convert_url, headers=headers, data=payload
        )

        if resp.status_code != 200:
            resp.close()
            raise RuntimeError(f"convert.php 转换失败: {resp.status_code}")

        res_json = resp.json()
        resp.close()
        gc.collect()

        if not res_json.get("ok") or not res_json.get("url"):
            raise RuntimeError("convert.php 转换未成功")

        bmp_download_url = res_json["url"]

        if status_cb:
            status_cb("正在获取显示图像...")

        print("📥 4. 下载最终 BMP...")
        bmp_resp = urequests.get(
            bmp_download_url, headers={"User-Agent": self.ua}, stream=True
        )

        if bmp_resp.status_code != 200:
            bmp_resp.close()
            raise RuntimeError("下载 BMP 结果失败")

        first_chunk = bmp_resp.raw.read(1024)
        if not first_chunk or not first_chunk.startswith(b"BM"):
            bmp_resp.close()
            raise RuntimeError("云端返回数据格式非法 (非 BMP)")

        with open(save_path, "wb") as f:
            f.write(first_chunk)
            while True:
                chunk = bmp_resp.raw.read(1024)
                if not chunk:
                    break
                f.write(chunk)

        bmp_resp.close()
        gc.collect()
        return save_path

    def generate_image(
        self, prompt, save_bmp_path="output.bmp", status_cb=None
    ):
        png_url = self._generate_png_url(prompt, status_cb=status_cb)
        png_bytes = self._download_png_bytes(png_url, status_cb=status_cb)
        
        # ✅ 修改为 save_path=save_bmp_path 即可
        return self._upload_to_convert_php(
            png_bytes, save_path=save_bmp_path, status_cb=status_cb
        )