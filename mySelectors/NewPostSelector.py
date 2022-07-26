from lxml import etree
import time
import requests

from queue import SimpleQueue

groupID='672143'

class NewPostSelector:
    def __init__(self, queue, session):
        self.q = queue
        self.s = session
        # 历史集合
        self.histo = set() 
        # 文件中获取已有历史，初始化一次
        self.loadHistoFromFile()

    # 选择哪些帖子要回复
    def select(self):
        groupUrl = 'https://www.douban.com/group/'+groupID
        # time.sleep(5)
        items = self.getItems(groupUrl)
        print('----',items)
        self.putItems(items)

        return self.q

    def getItems(self, url):
        xpExp = "//table[@class='olt']/tr"
        # 获取该地址的内容,小组首页的列表
        r = self.s.get(url)
        items = self.parseHtml(r, xpExp)
        print('----',url,r,items[0])
        return items

    def putItems(self, items):
        length = 0
        # pair.get('title'), pair.get('href'), cnt, userID
        for tup in items:
            # tup = i.get('title'), i.get('href')
            title = tup[0] # 帖子标题

            cnt = tup[2] # 帖子回复数
            try:
                href = tup[1].split('/')[5] #帖子id
                #帖子评论数大于20或者在history中有记录，跳过
                if cnt > 0 or href in self.histo:
                    continue
                 
                
                self.histo.add(href) 
                # file.write(href+'\n')
                self.q.put((tup[0], tup[1], tup[3]))
                # print("Put in: ", tup[0])
                length += 1 #记录每一次处理过的次数
                if length > 10:
                    return
            except AttributeError:
                print(tup)

    def loadHistoFromFile(self, fileName='resources/histo.txt'):
        with open(fileName, "r", encoding='utf-8') as file:
            lines = file.readlines()
            for l in lines:
                l = l.strip()
                if (len(l) == 0):
                    continue
                self.histo.add(l)

    def loadHistoFromWeb(self, url='https://www.douban.com/group/'+groupID):
        newSet = set()
        time.sleep(5)
        r = self.s.get(url)

        items = self.parseHtml(r)
        items = items[20:]
        for tup in items:
            href = tup[1].split('/')[5].strip()
            newSet.add(href)

        # self.persistHisto(newSet)
        self.histo.update(newSet)

    def persistHisto(self, setToWrite, fileName='resources/histo.txt'):
        with open(fileName, "a", encoding='utf-8') as file:
            for href in setToWrite:
                file.write(str(href) + '\n')

    def parseHtml(self, html, xpExp="defaultExp"):
        # print('----',etree.HTML(html.content))
        eles = etree.HTML(html.content).xpath(xpExp)
        file = open('html.html', 'a', encoding='utf-8')
        # lxml库的etree模块，然后声明了一段HTML文本，调用HTML类进行初始化，这样就成功构造了一个XPath解析对象。这里需要注意的是，HTML文本中的最后一个li节点是没有闭合的，但是etree.HTML模块可以自动修正HTML文本。这里我们调用tostring()方法即可输出修正后的HTML代码，但是结果是bytes类型。这里利用decode()方法将其转成str类型，结果如下 https://blog.csdn.net/qq_38410428/article/details/82792730
        file.write(etree.tostring(etree.HTML(html.text)).decode('utf-8'))
        print('--eles--',eles[0].getchildren())
        # 截取前面的置顶
        eles = eles[1:]
        items = []
        for ele in eles:
            li = ele.getchildren()
            # 评论数
            cnt = li[2].text 
            pair, cnt, userID = li[0].getchildren()[0].attrib, li[2].text, \
                               li[1].getchildren()[0].attrib['href'].split('/')[4]
            if cnt is None:
                cnt = 0
            else:
                cnt = int(cnt)
            tup = pair.get('title'), pair.get('href'), cnt, userID
            items.append(tup)

        return items


if __name__ == '__main__':
    q = SimpleQueue()
    s = requests.session()
    s.headers.update({
        'Host': 'www.douban.com',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    n = NewPostSelector(q, s)
    # n.loadHistoFromWeb()
    bigQ = n.select()
    while bigQ.qsize() > 0:
        print(bigQ.get(timeout=3))
