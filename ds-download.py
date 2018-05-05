# -*- encoding:utf-8 -*-
# 用法如下
from DSAPI import DownloadStation
# 输入群晖的url,用户名,密码
ds = DownloadStation('url', 'usr', 'psw')
# 显示下载任务列表
ds.showTask()
# 增加下载任务
ds.createTask('download_url')
ds.logout()



