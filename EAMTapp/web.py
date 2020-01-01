from bs4 import BeautifulSoup
from urllib.request import urlopen
import requests
from selenium.webdriver import PhantomJS
from selenium.webdriver.common.keys import Keys
import ssl
import time
from threading import Thread
import multiprocessing as mp
import numpy as np
import os
import logging
import re


# Set logging
FORMAT = '[%(asctime)s [%(name)s][%(levelname)s]: %(message)s'
logging.basicConfig(format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, filename='./logs/EAMTapp.log')
LOG = logging.getLogger('EAMTapp')

# fetch urls
URL_ROOMS = 'https://sise.ema.edu.ee/vaatleja/vabadruumid.x'
URL_QUEUE = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'


# independent webcrawl, no driver needed
def get_rooms(soup=None):
    if soup is None:
        # get rooms html from url
        soup = BeautifulSoup(requests.get(URL_ROOMS).text, features='lxml')
    # only keep text information, remove tags
    context = soup.get_text()
    # find table start position
    res = re.search('KINNISED RUUMID\n\n\n\n\n\xa0', context)
    if res is None:
        LOG.warning('No room is currently in use.')
        return None
    # keep table information
    context = context[res.end():]
    # get list of rooms
    rooms = context.split('\xa0')
    rooms_formatted = []
    for entry in rooms:
        # get room number
        room_num = entry[:4]
        entry = entry[4:]
        # get room status
        if entry[:4] == 'läbi':
            status = 'läbi'
            entry = entry[4:]
        else:
            res = re.search('\d+:\d+|\d+', entry)
            if res is None:
                LOG.error('Can not parse the status of Room: %s' % room_num)
            status = entry[:res.end()]
            entry = entry[res.end():]

        # get person name
        name = entry.upper()
        if name == '':
            name = 'UNKNOWN'

        # assemble list
        rooms_formatted.append((room_num, status, name))
    return rooms_formatted


class WebBrowser:
    def __init__(self):
        LOG.info('Starting PhantomJS Web Browser...')
        # headless driver
        self.__browser = PhantomJS()
        LOG.info('Web Browser is ready!')
        return

    def get_dailymeal(self):
        LOG.info('Fetching daily meal menu...')
        output = None
        # open page in headless browser
        self.__browser.get('https://sise.ema.edu.ee/')
        # parse page source in bs4
        soup = BeautifulSoup(self.__browser.page_source, features='lxml')
        # get a list of columns from the page source
        res = soup.findAll(attrs={'class': 'rcorners2', 'colspan': '1'})

        # sift targets, get 'KOHVIK' text
        for r in res:
            # each "r" is a bs4 <td> Tag
            if r.b.text != 'KOHVIK':
                continue
            # we get text in this Tag, modify string a bit, and convert to a lsit
            menu = r.get_text(separator='\n').strip('\n').replace('\n\n', '\n').split('\n')
            # make sure there's no empty string in menu
            menu = list(filter(None, menu))

            # check if there is daily menu today
            if len(menu) == 1:
                LOG.warning('No daily meal today.')
                return None

            # title and date of the menu
            title = menu[0] + '\n' + menu[1] + '\n'

            # sift menu, only keep English part
            menu = list(map(lambda i: menu[i], range(3, len(menu), 2)))
            # assemble menu content
            dishes = '\n'.join(menu)

            output = title + dishes

            LOG.info('Sent %d menu dishes to server.' % len(menu))
        return output

    def on_stop(self):
        # close driver
        self.__browser.quit()
        LOG.info('Web Browser driver has stopped.')
        return
