from typing import Collection
import requests
from lxml import etree
import time
import random
from queue import SimpleQueue, Empty

from util import DouUtil
from actions import RespGen
from mySelectors import NewPostSelector
from util import requestsWrapper

log = DouUtil.log


def get_headers(fileName=None):
    name = 'headers.txt'
    if (fileName is not None):
        name = fileName
    name = 'resources/' + name
    headers = {}
    with open(name, "r", encoding='utf-8') as f_headers:
        hdrs = f_headers.readlines()
    for line in hdrs:
        key, value = line.split(": ")
        headers[key] = value.strip()
    return headers


def login(url, pwd, userName, session):
    loginData = {'ck': '', 'name': userName,
                 'password': pwd, 'remember': 'true'}
    loginHeaders = get_headers('login_headers.txt')
    l = session.post(url, data=loginData, headers=loginHeaders)

    if l.status_code == requests.codes['ok'] or l.status_code == requests.codes['found']:
        print("Login Successfully")
        return True
    else:
        print("Failed to Login")
        log.error("Failed to Login", l.status_code)
        session.close()
        return False


def composeCmnt(session, response):
    print(response)
    cmntForm = {
      'ck': '', 
      # 'rv_comment':  response['ans'],
'rv_comment':  response,
                'start': 0, 
                'submit_btn': '发送'}
    cmntForm['ck'] = DouUtil.getCkFromCookies(session)
    return cmntForm


def prepareCaptcha(data, session, postUrl, r=None) -> dict:
    pic_url, pic_id = DouUtil.getCaptchaInfo(session, postUrl, r)
    verifyCode = ''
    # 图片保存到本地，返回文件名
    pic_path = DouUtil.save_pic_to_disk(pic_url, session)
    log.debug(pic_url, pic_path)
    verifyCode = DouUtil.getTextFromPic(pic_path)
    return data
    # return verifyCode


def postCmnt(session, postUrl, request, response):
    data = composeCmnt(session._session, response)
    cmntUrl = postUrl + 'add_comment'
    print('response: ', response)
    # r = session.post(cmntUrl, data=data, headers={'Referer': postUrl}, files=response.get('files'))
    r = session.post(cmntUrl, data=data, headers={'Referer': postUrl})
    print(r,etree.HTML(r.content))
    # r = session.get(postUrl)
    code = str(r.status_code)
    
    if (code.startswith('4') or code.startswith('5')) and not code.startswith('404'):
        log.error(r.status_code)
        raise Exception
    # 获取验证码
    elif 0 != len(etree.HTML(r.content).xpath("//img[@id='captcha_image']")):
        log.warning(r.status_code)
        data = prepareCaptcha(data, session, postUrl, r)
        r = session.post(cmntUrl, data=data)
        retry = 1
        while 0 != len(etree.HTML(r.content).xpath("//img[@id='captcha_image']")):
            if retry <= 0:
                retry -= 1
                break
            data = prepareCaptcha(data, session, postUrl, r)

            r = session.post(cmntUrl, data=data)
            retry -= 1

        if retry < 0:
            log.error(r.status_code)
            DouUtil.alertUser()
            pic_url, pic_id = DouUtil.getCaptchaInfo(session, postUrl, r)
            code = DouUtil.callAdmin(session, pic_url, postUrl)
            # data.update({'captcha-solution': code, 'captcha-id': pic_id})

            r = session.post(cmntUrl, data=data)
            if 0 != len(
                    etree.HTML(r.content).xpath("")):
                raise Exception

        log.info("Success.", request + '  --' + data['rv_comment'])
    else:
        log.info("Success.", request + '  --' + data['rv_comment'])


def main():
    # 生成回复
    respGen = RespGen.RespGen()
    
    # 同步队列
    q = SimpleQueue()
    # 获取密码配置等
    cred = DouUtil.getCred()
    pwd = cred['pwd']
    userName = cred['userName']
    loginReqUrl = ''

    print('---1---',pwd,userName)

    # s = requests.Session()
    reqWrapper = requestsWrapper.ReqWrapper()
    s = reqWrapper._session
    s.headers.update({
        'Host': 'www.douban.com',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    print('----2----',DouUtil.loadCookies())
    s.cookies.update(DouUtil.loadCookies())

    slctr = NewPostSelector.NewPostSelector(q, reqWrapper)

    print('----3----',slctr)
    timeToSleep = 5
    combo = 0

    while True:
        # 要回复的队列
        q = slctr.select()
        if q.qsize() == 0:
            log.debug("sleep fro emty queue: ", timeToSleep)
            time.sleep(timeToSleep)
        else:
            timeToSleep = 5
        log.info("****selection, q size: ", q.qsize(), "timeToSleep: " + str(timeToSleep) + "****")
        try:
            file = open('resources/record.txt', 'a', encoding='utf-8')
            recorder = open('resources/histo.txt', "a", encoding='utf-8')

            while q.qsize() > 0:
                tup = q.get(timeout=3)
                #标题 网址 
                question, postUrl, userID = tup[0], tup[1], tup[2]
                print('----5---',question, postUrl, userID)

                resp = respGen.getResp(question, userID)
                print('----6---',resp)
                
                postCmnt(reqWrapper, postUrl, question, resp)

                sleepCmnt = random.randint(20, 30)
                log.debug("sleep cmnt: ", sleepCmnt)

                # 记录回过的帖子
                recorder.write(postUrl.split('/')[5] + '\n')
                # 回复记录
                # record = question + ': ' + resp['ans'] + '\n'
                record = question + ': ' + resp + '\n'
                print('-----record----',record)
                file.write(record)

        except Empty:
            log.info("Emptied q, one round finished")
        finally:
            file.close()
            recorder.close()
            DouUtil.flushCookies(s)


if __name__ == '__main__':
    main()
