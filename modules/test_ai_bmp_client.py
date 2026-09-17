from ai_bmp_client import ImageGenerator
from display_ui import UIManager

# 1. 初始化屏幕与 AI 生成器
ui = UIManager()
ai = ImageGenerator(api_key="sk-lisenkrkcvdlmmavgytlsnpwpodcfyqrmnszopgzwpwespbe")

# 2. 提示文字反馈
ui.render("AI 绘图", "正在生成并下载图片，请稍候...")

# 3. 输入提示词，生成并保存 output.bmp
bmp_file = ai.generate_image("一个赛博朋克风格的工厂机器人", save_bmp_path="output.bmp")

# 4. 显示最终图片到屏幕
ui.lcd.draw_bmp(bmp_file, start_x=0, start_y=0)
ui.lcd.show()