from bs4 import BeautifulSoup
from bs4.element import Tag
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
from datetime import datetime, time
from collections import namedtuple


# Set logging
FORMAT = '[%(asctime)s [%(name)s][%(levelname)s]: %(message)s'
logging.basicConfig(format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, filename='./logs/EAMTapp.log')
LOG = logging.getLogger('EAMTapp')

# fetch urls
URL_ROOMS = 'https://sise.ema.edu.ee/vaatleja/vabadruumid.x'
URL_QUEUE = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
URL_ROOM_RESERV = 'https://sise.ema.edu.ee/vaatleja/parem2.x?ruum=%s&vaade=week&week=%d&year=%d&mon=%d'
URL_ROOMS_LIST  = 'https://sise.ema.edu.ee/vaatleja/parem2.x'


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
        if entry.startswith('BLACKBOX'):
            room_num = 'BLACKBOX'
            entry = entry[8:]
        elif entry.startswith('D_FUAJEE'):
            room_num = 'D_FUAJEE'
            entry = entry[8:]
        elif entry.startswith('SAKALA'):
            room_num = 'SAKALA'
            entry = entry[6:]
        elif entry.startswith('SUUR_SAAL'):
            room_num = 'SUUR_SAAL'
            entry = entry[9:]
        else:
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
                continue
            status = entry[:res.end()]
            entry = entry[res.end():]

        # get person name
        name = entry.upper()
        if name == '':
            name = 'UNKNOWN'

        # assemble list
        rooms_formatted.append((room_num, status, name))
    return rooms_formatted


def get_rooms_list(soup=None):
    if soup is None:
        # get rooms html from url
        soup = BeautifulSoup(requests.get(URL_ROOMS_LIST).text, features='lxml')

    # get <select> tag with all rooms as options
    res = soup.find('select', attrs={'name':'ruum'})
    # get rooms values
    rooms_list = list(map(lambda x: x['value'] if isinstance(x, Tag) else '', res.children))
    # remove empty string
    rooms_list = list(filter(None, rooms_list))
    return rooms_list


def get_room_reservation(room, week, year, month, soup=None):
    Reservation = namedtuple('Reservation', ['weekday', 'time_start', 'time_end', 'description'])
    weekly_reservations = []

    if soup is None:
        # get rooms html from url
        soup = BeautifulSoup(requests.get(URL_ROOM_RESERV%(room, week, year, month)).text, features='lxml')

    # all reservations are in the <div> tags
    divs = soup.find_all('div')

    # sometimes can't get target html
    if not divs:
        LOG.error('Could not find any <div> tags in the reservation!')
        return []

    # each reservation has two <div> tags
    for div_tag in divs:
        # only use the one has child tags
        if not div_tag.contents:
            continue

        # get weekday
        left_margin_res = re.search('left:(\d*)px', div_tag['style'])
        left_margin = int(div_tag['style'][left_margin_res.start()+5:left_margin_res.end()-2])
        weekday = int((left_margin - 50) / 100) + 1  # value varies from 1 to 7

        # get time/duration
        duration_res = re.search('\d\d:\d\d-\d\d:\d\d', div_tag.center.text)  # e.g. '13:00-14:00'
        duration = div_tag.center.text[duration_res.start():duration_res.end()].split('-')  # e.g. ['13:00','14:00']
        start_hour, start_minute = duration[0].split(':')  # e.g. ['13','00']
        start_time = time(hour=int(start_hour), minute=int(start_minute))  # datetime.time(13, 0)
        end_hour, end_minute = duration[1].split(':')  # e.g. ['14','00']
        end_time = time(hour=int(end_hour), minute=int(end_minute))  # datetime.time(14, 0)

        # get description
        description = div_tag.center.text[duration_res.end():].strip('\r\n ').replace('\r\n', ' ')
        weekly_reservations.append(Reservation(weekday, start_time, end_time, description))

    # reorder & return results
    return sorted(sorted(weekly_reservations, key=lambda x: x.time_start), key=lambda x: x.weekday)


class WebBrowser:
    def __init__(self):
        LOG.info('PhantomJS Web Browser is ready!')
        return

    def get_dailymeal(self):
        LOG.info('Fetching daily meal menu...')
        driver = PhantomJS()
        output = None
        # open page in headless browser
        driver.get('https://sise.ema.edu.ee/')
        # parse page source in bs4
        soup = BeautifulSoup(driver.page_source, features='lxml')
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
        driver.quit()
        return output

    def on_stop(self):
        # close driver
        LOG.info('Web Browser driver has stopped.')
        return
