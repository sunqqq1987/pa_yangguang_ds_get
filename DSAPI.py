#! /usr/bin/env python
# -*- coding: utf-8 -*-
# 使用Synology Download Station API远程控制文件下载
# http://download.synology.com/download/other/Synology_Download_Station_Official_API_V3.pdf
# 修改自这里https://jeeker.net/article/remote-control-synology-download-station/
# 使用原博客的urllib2不会整,使用requests库改写

import os
import sys
import requests
from argparse import ArgumentParser


CommonCodeDesc = {
    100: 'Unknown error',
    101: 'Invalid parameter',
    102: 'The requested API does not exist',
    103: 'The requested method does not exist',
    104: 'The requested version does not support the functionality',
    105: 'The logged in session does not have permission',
    106: 'Session timeout',
    107: 'Session interrupted by duplicate login'
                }

AuthCodeDesc = {
    400: 'No such account or incorrect password',
    401: 'Guest account disabled',
    402: 'Account disabled',
    403: 'Wrong password',
    404: 'Permission denied'
                }

DSTaskCodeDesc = {
    400: 'File upload failed',
    401: 'Max number of tasks reached',
    402: 'Destination denied',
    403: 'Destination does not exist',
    404: 'Invalid task id',
    405: 'Invalid task action'
                }

DS_VERSION = '0.1'
# headers_base = {'User-Agent': UserAgent().random}
session = requests.session()


class DownloadStation:
    def __init__(self, url, usr, pwd):
        self.NAS_URL = url
        self.NAS_USR = usr
        self.NAS_PWD = pwd
        self.sessionID = ''
        self.tryLogin()
        self.debugInfo = {}
        self.lastError = ''
        # 设置: 网址 用户 密码

    def post(self, cgipath, data, subdir=''):
        if not isinstance(data, dict):
            print('data error')
            return
        if 'version' not in data:
            data.update({'version': 1})
        if '_sid' not in data:
            data.update({'_sid': self.sessionID})
        url = self.NAS_URL+'/webapi/'+cgipath
        try:
            requst = session.get(url, params=data)
        # print(requst.url)
            res = requst.json()
        except Exception as e:
            print(e)
            res = {'error': {'code': -1}, 'success': False}
        # print(res)
        return res

    def login(self):
        print(self.sessionID)
        data = {
            'api':     'SYNO.API.Auth',
            'method':  'login',
            'version':  2,
            'account':  self.NAS_USR,
            'passwd':   self.NAS_PWD,
            'session': 'DownloadStation',
                }
        res = self.post('auth.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        self.sessionID = res['data']['sid']

    def logout(self):
        data = {
            'api':     'SYNO.API.Auth',
            'method':  'logout',
            'session': 'DownloadStation'
            }
        res = self.post('auth.cgi', data)
        self.sessionID = ''

    def tryLogin(self):
        if self.sessionID == '':  # 如果session为空,则登陆
            self.login()

    def test(self):
        self.tryLogin()
        data = {
            'api':     'SYNO.DownloadStation.Info',
            'method':  'getinfo'
        }
        res = self.post('DownloadStation/info.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        manager_info = ', and you are manager.' if res['data']['is_manager'] else '.'
        info = 'everything is ok, the version of Download Station is {}{}'.format(res['data']['version_string'], manager_info)
        print(info)

    # 显示当前下载速度
    def showStatistic(self):
        self.tryLogin()
        data = {
            'api':     'SYNO.DownloadStation.Statistic',
            'method':  'getinfo'
            }
        res = self.post('DownloadStation/statistic.cgi', data, 'DownloadStation')
        if not self.isSuccess(res):
            self.die(self.lastError)
        speed_download = self.humanSize(res['data']['speed_download'])
        speed_upload = self.humanSize(res['data']['speed_upload'])
        info = '{:15} download {:10} upload {:10}'.format('Speed:', speed_download, speed_upload)
        print(info)
        if 'emule_speed_download' in res['data']:
            emule_speed_download = self.humanSize(res['data']['emule_speed_download'])
            emule_speed_upload = self.humanSize(res['data']['emule_speed_upload'])
            info = '{:15} download {:10} upload {:10}'.format('eMule Speed:', emule_speed_download, emule_speed_upload)
            print(info)
        else:
            print('eMule disabled.')

    # 显示当前任务信息
    def showTask(self, simple=False, include_seeding=False):
        self.tryLogin()
        if not simple:
            self.showStatistic()
        data = {
            'api':         'SYNO.DownloadStation.Task',
            'method':      'list',
            'additional':  'transfer'
            }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        if not include_seeding:
            res['data']['tasks'] = filter(lambda t: t['status'] != 'seeding', res['data']['tasks'])
        # if len(res['data']['tasks']) == 0:
        #     print('Task list is empty.')
        #     return
        title = '{:10}{:15}{:10}{:15}{:15}{}'.format('Type', 'Status', 'Size', 'Downloaded', 'Speed', 'Title')
        if simple:
            title = '{:40}{}'.format('Task ID', 'Title')
        print(title)

        for task in res['data']['tasks']:
            task['size'] = self.humanSize(task['size'])
            task['add_size_d'] = self.humanSize(task['additional']['transfer']['size_downloaded'])
            task['add_sued'] = self.humanSize(task['additional']['transfer']['size_uploaded'])
            task['add_speed_d'] = self.humanSize(task['additional']['transfer']['speed_download'])
            task['add_su'] = self.humanSize(task['additional']['transfer']['speed_upload'])
            info = '{type:10}{status:15}{size:10}{add_size_d:15}{add_speed_d:15}{title:30}'.format(**task)
            if simple:
                info = '{id:40}{title}'.format(**task)
            print(info)

    # 创建新的下载任务 参数可以是本地文件或链接
    def createTask(self, link_or_file):
        self.tryLogin()
        if not isinstance(link_or_file, (str,  list)):
            self.die('arguments error')
        uris = ','.join(link_or_file) if isinstance(link_or_file, list) else link_or_file
        try:
            if os.path.isfile(uris):
                # 使用file参数似乎有问题 自己读
                with open(uris, 'r') as fp:
                    uris = ','.join(map(lambda s: s.strip('\n \t\r'), fp.readlines()))
        except Exception as e:
            print(e)
            pass
        data = {
            'api':     'SYNO.DownloadStation.Task',
            'method':  'create',
            'uri':     uris
            }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die( self.lastError )
        print('task created.')

    # 清理错误 及 已完成的任务
    # eMule任务中 有seeding状态的无法删除
    def cleanTask(self):
        self.tryLogin()
        # 获取任务列表
        data = {
            'api':         'SYNO.DownloadStation.Task',
            'method':      'list',
            }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        need_clean = {}
        for task in res['data']['tasks']:
            # 错误 已完成 的清理
            if task['status'] == 'error' or task['status'] == 'finished':
                need_clean.update({task['id']: task['title']})
        if not len(need_clean):
            print('there is no task need to clean.')
            return
        data = {
            'api':     'SYNO.DownloadStation.Task',
            'method':  'delete',
            'id':      ','.join(need_clean.keys())
            }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        for task in res['data']:
            clean_res = 'clean success:' if task['error'] == 0 else 'clean fail(%d):' % task['error']
            title = need_clean[task['id']] if task['id'] in need_clean else task['id']
            info = '{:20}{}'.format(clean_res, title)
            print(info)

    def pauseTask(self, task_id=''):
        self.tryLogin()
        # 未自定id则暂停所有
        if not task_id:
            # 获取任务列表
            data = {
                'api':         'SYNO.DownloadStation.Task',
                'method':      'list',
                }
            res = self.post('DownloadStation/task.cgi', data)
            if not self.isSuccess(res):
                self.die(self.lastError)
            ids = []
            for task in res['data']['tasks']:
                # eMule做种的任务无法暂停
                if not task['status'] == 'seeding':
                    ids.append(task['id'])
            if not len(ids):
                self.die('there is no task can be paused.')
            task_id = ',' . join(ids)

        data = { 'api': 'SYNO.DownloadStation.Task',
                 'method': 'pause',
                 'id':      task_id
        }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        for task in res['data']:
            info = 'pause success:' if task['error'] == 0 else 'pause fail(%d):' % task['error']
            print('{:20}{}'.format(info, task['id']))

    def resumeTask(self, task_id=''):
        self.tryLogin()
        # 未自定id则恢复所有
        if not task_id:
            # 获取任务列表
            data = {
                'api':         'SYNO.DownloadStation.Task',
                'method':      'list',
                }
            res = self.post('DownloadStation/task.cgi', data)
            if not self.isSuccess(res):
                self.die(self.lastError)
            ids = []
            for task in res['data']['tasks']:
                if task['status'] == 'paused':
                    ids.append(task['id'])
            if not len(ids):
                self.die('there is no task can be paused.')
            task_id = ',' . join(ids)
        data = { 'api':     'SYNO.DownloadStation.Task',
                 'method':  'resume',
                 'id':      task_id
        }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        for task in res['data']:
            info = 'resume success:' if task['error'] == 0 else 'resume fail(%d):' % task['error']
            print('{:20}{}'.format(info, task['id']))

    def deleteTask(self, task_id):
        self.tryLogin()
        # 获取待删除任务信息
        data = {
            'api':     'SYNO.DownloadStation.Task',
            'method':  'getinfo',
            'id':      task_id
            }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die(self.lastError)
        if not len(res['data']['tasks']):
            self.die('task is non-existent.')
        # 如果任务未完成 且 无错误 请求确认
        need_confirm = False
        for task in res['data']['tasks']:
            if task['status'] != 'error' and task['status'] != 'finished':
                need_confirm = True
                print( '{:20}{:40}{}'.format('task uncompleted:', task['id'], task['title']) )
        if need_confirm:
            if not raw_input('are you sure to delete it(yes/no)?:') == 'yes':
                return
        # 删除
        data = {
            'api':     'SYNO.DownloadStation.Task',
            'method':  'delete',
            'id':      task_id
            }
        res = self.post('DownloadStation/task.cgi', data)
        if not self.isSuccess(res):
            self.die( self.lastError )
        print('task deleted.')

    def eMule(self, is_enable):
        data = {
            'api':             'SYNO.DownloadStation.Info',
            'method':          'setserverconfig',
            'emule_enabled':   'false' if not is_enable else 'true'
            }
        res = self.post('DownloadStation/info.cgi', data)
        if not self.isSuccess(res):
            self.die( self.lastError )
        print('eMule was %s' % ('enabled' if is_enable else 'disabled'))

    def isSuccess(self, res):
        if not isinstance(res, dict) or 'success' not in res:
            self.lastError = 'something error'
            return False
        if res['success']:
            self.lastError = ''
            return True
        self.lastError = 'Fail. error code: %d' % res['error']['code'] if 'error' in res and 'code' in res['error'] else 'something error'
        return False

    def humanSize(self, byte):
        if isinstance(byte, str):
            byte = int(byte) if byte.isnumeric() else 0
        size = byte / 1024.0
        unit = 'KB'
        if size > 1024:
            size = size / 1024.0
            unit = 'MB'
        if size > 1024:
            size = size / 1024.0
            unit = 'GB'
        return '{:.2f}{}'.format(size, unit)

    def die(self, msg=''):
        if len(msg):
            sys.stderr.write(msg + '\n')
        sys.exit(1)


def main():
    parser = ArgumentParser(prog='ds', description='Synology NAS Download Station Tool.')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + DS_VERSION)
    subparsers = parser.add_subparsers(title='subcommands', dest='sub_cmd')

    # 任务信息
    sub_info_parser = subparsers.add_parser('info', help='show task infomation')
    sub_info_parser.add_argument('--simple', action='store_true', default=False, help='only show task id and title')
    sub_info_parser.add_argument('--all', action='store_true', default=False, help='show all task')

    # 创建新任务
    sub_create_parser = subparsers.add_parser('create', help='create new task')
    sub_create_parser.add_argument('link_or_file', nargs=1, help='single link or a file which include multi-links')

    # 清理任务
    sub_clean_parser = subparsers.add_parser('clean', help='clean error or completed task')

    # 暂停任务
    sub_pause_parser = subparsers.add_parser('pause', help='pause task')
    sub_pause_parser.add_argument('task_id', action='store', nargs='?', default='')

    # 恢复任务
    sub_resume_parser = subparsers.add_parser('resume', help='resume task')
    sub_resume_parser.add_argument('task_id', nargs='?', default = '')

    # 删除任务
    sub_delete_parser = subparsers.add_parser('delete', help='delete task')
    sub_delete_parser.add_argument('task_id')

    # eMule控制
    sub_emule_parser = subparsers.add_parser('emule', help='enable or disable eMule')
    sub_emule_parser.add_argument('operate', choices=['on', 'off'])

    # 测试
    sub_test_parser = subparsers.add_parser('test', help='test API')

    # 如果没有参数则默认输出info
    args = parser.parse_args(['info']) if len(sys.argv) == 1 else parser.parse_args()

    cmd_map = { 'info': lambda: ds.showTask(args.simple, args.all),
                'create': lambda: ds.createTask(args.link_or_file),
                'clean': lambda: ds.cleanTask(),
                'pause': lambda: ds.pauseTask(args.task_id),
                'resume': lambda: ds.resumeTask(args.task_id),
                'delete': lambda: ds.deleteTask(args.task_id),
                'emule': lambda: ds.eMule(True if args.operate == 'on' else False),
                'test': lambda: ds.test()
    }
    if args.sub_cmd in cmd_map:
        ds = DownloadStation('url', 'usr', 'psw')
        cmd_map[args.sub_cmd]()
        # ds.createTask('magnet:?xt=urn:btih:6d798742806a2e12dd41ff9d760193641b59728c&dn=%e9%98%b3%e5%85%89%e7%94%b5%e5%bd%b1www.ygdy8.com.%e7%ba%a2%e6%b5%b7%e8%a1%8c%e5%8a%a8.HD.1080p.%e5%9b%bd%e8%af%ad%e4%b8%ad%e5%ad%97.mp4&tr=udp%3a%2f%2ftracker.leechers-paradise.org%3a6969%2fannounce&tr=udp%3a%2f%2feddie4.nl%3a6969%2fannounce&tr=udp%3a%2f%2fshadowshq.eddie4.nl%3a6969%2fannounce&tr=udp%3a%2f%2ftracker.opentrackr.org%3a1337%2fannounce')
        ds.logout()
    else:
        print('something error.')


if __name__ == '__main__':
    main()
