# -*- encoding:utf-8 -*-
# 爬取阳光电影网最新电影,获取文件名\FTP下载地址\磁力链
#
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import re

# 浏览器文件头
headers_base = {'User-Agent': UserAgent().random}
# 创建session
session = requests.session()


# 获取磁力链接
def get_magnet_url(movieurl):
    open_movie_url = session.get(movieurl)
    open_movie_url.encoding = 'gb2312'
    soup1 = BeautifulSoup(open_movie_url.text, "html.parser")
    # 解析磁力链
    tag1 = soup1.findAll('a', text='磁力链下载点击这里')
    for tag in tag1:
        download_url = tag.get('href')
        return download_url


# 获取FTP下载地址
def get_ftp_url(movieurl):
    open_movie_url = session.get(movieurl)
    open_movie_url.encoding = 'gb2312'
    soup1 = BeautifulSoup(open_movie_url.text, "html.parser")
    # 解析ftp下载地址
    tag1 = soup1.findAll('a', text=re.compile(r'ftp.*'))
    for tag in tag1:
        download_url = tag.get('href')
        return download_url


# 主页地址
host_url = 'http://www.ygdy8.com'
# 最新电影地址
home_url = 'http://www.ygdy8.com/html/gndy/dyzz/index.html'
open_url = session.get(home_url)
open_url.encoding = 'gb2312'
soup0 = BeautifulSoup(open_url.text, "html.parser")
# 获取文件打开网址
tag0 = soup0.findAll('a', class_="ulink")

for i in tag0:
    movie_url = i.get('href')
    print(i.get_text())
    print('访问地址:', host_url + movie_url)
    print(get_ftp_url(host_url + movie_url))  # 获取ftp地址
    print(get_magnet_url(host_url + movie_url))  # 获取磁力链



