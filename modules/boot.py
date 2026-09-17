# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()

# boot.py
import uos
import machine
import sys

# 彻底关闭无串口连接时的标准输出阻塞
try:
    uos.dupterm(None, 1) # 解绑 UART0 交互，防止没有连电脑时 print 卡死主进程
except:
    pass