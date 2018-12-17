# configure path: '/Users/simonwu/Library/Application Support/telegram-send'
from bs4 import BeautifulSoup
from urllib.request import urlopen
import requests
import ssl
import telegram_send
import time
from threading import Thread
import multiprocessing as mp
import numpy as np
import os
PATH = os.getcwd()

def run_fetcher(url):
    # print('> DEBUG: Updating soup from: ', url)
    soup = BeautifulSoup(make_request(url, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1)), features="lxml")
    return soup

def make_request(url, context=None):
    if type(context) != type(None):
        html = urlopen(url, context=context)
    else:
        html = urlopen(url)
    return html

def find_waiting_list(soup, name=None):
    items = soup.find_all(color='black')
    str_calling_list_est = items[0].b.text
    str_waiting_list_est = items[1].text

    calling_next = items[0].find_all_next(text=True)
    waiting_next = items[1].find_all_next(text=True)

    # init variables
    status = -1
    position = -1
    count = 0
    total_number = -1

    # get calling list
    for each_name in calling_next[1:]:
        if each_name == name:
            count += 1
            status = 1
            position = count

        elif each_name == '\n':
            break
        else:
            count += 1

    # get waiting list
    count = 0
    for each_name in waiting_next[1:]:
        if each_name == name:
            count += 1
            status = 0
            position = count

        elif 'inimest' in each_name:
            total_number = int(each_name[:2])
            break
        else:
            count += 1

    return status, position, total_number

def run_spy(name, debug=False, interval=30, init=3):

    try:
        print('> DEBUG: Hello! %s' % name)
        print('> DEBUG: Auto bot start running...')
        if not debug:
            telegram_send.send(messages=['Hello, %s. You will be notified when there are updates in the queue.' % name],
                               conf=os.path.join(PATH, 'EMTA/config/telegram-send-xun.conf'))
            telegram_send.send(messages=['Hello, %s. You will be notified when there are updates in the queue.' % name],
                               conf=os.path.join(PATH, 'EMTA/config/telegram-send-shan.conf'))

        # init
        wait_position = -1
        call_position = -1
        status = -1
        send_call = True
        send_wait = True
        count_init = 0

        while True:
            # get html and brew soup
            soup = run_fetcher('https://sise.ema.edu.ee/vaatleja/vabadruumid2.x')
            # update queue status
            status, position, num = find_waiting_list(soup, name)

            # check status
            if status == -1:
                print('> INFO: You are not in the list!')
                count_init += 1
                if count_init == init:
                    print("Auto shut down.")
                    raise KeyboardInterrupt

            elif status == 0:
                print('> INFO: You are in the waiting queue: %d/%d' % (position, num))
                if wait_position != position:
                    send_wait = True
                    wait_position = position

                if send_wait and not debug:
                    telegram_send.send(messages=['You are in the waiting queue: %d/%d' % (position, num)],
                                       conf=os.path.join(PATH, 'EMTA/config/telegram-send-xun.conf'))
                    telegram_send.send(messages=['You are in the waiting queue: %d/%d' % (position, num)],
                                       conf=os.path.join(PATH, 'EMTA/config/telegram-send-shan.conf'))
                    send_wait = False

            elif status == 1:
                print('> INFO: Your position in calling list: %d' % position)
                if call_position != position:
                    send_call = True
                    call_position = position

                if send_call and not debug:
                    telegram_send.send(messages=['You can go to pick up your key now!', 'position: %d.' % position],
                                       conf=os.path.join(PATH, 'EMTA/config/telegram-send-xun.conf'))
                    telegram_send.send(messages=['You can go to pick up your key now!', 'position: %d.' % position],
                                       conf=os.path.join(PATH, 'EMTA/config/telegram-send-shan.conf'))
                    send_call = False

            time.sleep(interval)
    except KeyboardInterrupt:
        print('> DEBUG: bye:)')
        if not debug:
            telegram_send.send(messages=['Bot has been shut down. Bye:)'],
                               conf=os.path.join(PATH, 'EMTA/config/telegram-send-xun.conf'))
            telegram_send.send(messages=['Bot has been shut down. Bye:)'],
                               conf=os.path.join(PATH, 'EMTA/config/telegram-send-shan.conf'))
    return


class MonitorBot:
    def __init__(self, time_interval=30, debug=False):
        """
        a bot monitoring the queue system.

        :param time_interval: update time interval
        """
        self.time_interval = time_interval
        self.debug = debug

        self.__queue_list = np.full(200, -1, dtype=np.dtype([('name', 'U32'),
                                                             ('status', np.int8),
                                                             ('position', np.int16),
                                                             ('origin', np.int16),
                                                             ('start_ts', np.float64),
                                                             ('end_ts', np.float64),
                                                             ('processed', np.int8)]))
        self.__reservations = {}
        self.__available_rooms = {}
        self.__total_waiting = 0
        self.__practice_room = []

        self.__study_material = []

        self.__threads = {}
        self.__soup_1 = None
        self.__soup_2 = None
        self.__task = mp.Queue()
        self.__queue_url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
        self.__room_url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid.x'
        self.__terminate = False

        if not self.debug:
            # init run
            brewer = Thread(target=self.soup_brewer)
            self.__threads['soup_brewer'] = brewer
            brewer.start()
            server = Thread(target=self.web_job)
            self.__threads['server'] = server
            server.start()
        return

    def run_server(self):
        server = Thread(target=self.web_job)
        self.__threads['server'] = server
        server.start()
        return

    def run_brewer(self):
        brewer = Thread(target=self.soup_brewer)
        self.__threads['soup_brewer'] = brewer
        brewer.start()
        return

    def web_job(self):
        print('> DEBUG: Server started.')
        while True:
            order = self.__task.get()

            # print('> DEBUG: Updating information...')

            # init lists
            self.reset_vaba_room_reservation()

            if order == 'job':
                soup_1 = self.__soup_1
                soup_2 = self.__soup_2

                waiting_list = soup_1.find_all(text='JÄRJEKORRAS')[0].find_all_next(text=True)
                calling_list = soup_1.find_all(text='OODATUD VALVELAUDA')[0].find_all_next(text=True)
                raw_free_classes = soup_1.find_all(text='VABANEVAD KLASSID:')[0].find_all_next(text=True)

                # init variables
                count = 0
                self.__queue_list['processed'] = 0

                # get waiting list
                new_idx = np.where(self.__queue_list['name']=='-1')[0]
                pivot = 0
                for person in waiting_list:
                    if 'inimest' in person:
                        self.__total_waiting = int(person[:2])
                        count = 0
                        break
                    else:
                        count += 1
                        if person in self.__queue_list['name']:
                            idx = np.where(self.__queue_list['name']==person)[0][0]

                            self.__queue_list[idx]['position'] = count
                            self.__queue_list[idx]['processed'] = 1
                        else:
                            self.__queue_list[new_idx[pivot]] = (person, 0, count, count, time.time(), -1, 1)
                            pivot += 1

                # get calling list
                for person in calling_list:
                    if person == '\n':
                        count = 0
                        break
                    else:
                        count += 1
                        if person in self.__queue_list['name']:
                            idx = np.where(self.__queue_list['name'] == person)[0][0]
                            if self.__queue_list[idx]['end_ts'] == -1:
                                self.__queue_list[idx]['end_ts'] = time.time()
                                # add study material
                                self.__study_material.append((self.__queue_list[idx]['origin'],
                                                              self.__queue_list[idx]['start_ts'],
                                                              self.__queue_list[idx]['end_ts']
                                                              ))

                            self.__queue_list[idx]['status'] = 1
                            self.__queue_list[idx]['processed'] = 1
                            self.__queue_list[idx]['position'] = count
                        else:
                            self.__queue_list[new_idx[pivot]] = (person, 1, count, count, -1, time.time(), 1)
                            pivot += 1

                # clean up vanished names
                idx_dump =np.where((self.__queue_list['name']!='-1')*(self.__queue_list['processed']==0))
                self.__queue_list[idx_dump] = -1

                # get room list
                free_classes = []
                cache = []
                for item in raw_free_classes:
                    if item == '\xa0':
                        free_classes.append(cache)
                        cache = []
                        continue
                    else:
                        cache.append(item)
                free_classes = free_classes[1:]

                for room_info in free_classes:
                    room_id = room_info[0]
                    status = room_info[1]
                    name = room_info[2]

                    # add available rooms
                    if status == 'vaba':
                        self.__available_rooms[room_id] = name
                    # update reservations
                    if len(room_info) > 3:
                        reservations = room_info[3:]
                        self.__reservations[room_id] = reservations

                # soup 2
                all_rooms = []
                cache = []
                for item in soup_2.find_all('td'):
                    if item.text == '\xa0':
                        all_rooms.append(cache)
                        cache = []
                        continue
                    else:
                        cache.append(item.text)
                all_rooms = all_rooms[1:]
                self.__practice_room = np.zeros(len(all_rooms), dtype=np.dtype([('room_id', 'U4'),
                                                                                ('remaining', 'U5'),
                                                                                ('name', 'U32')]))
                for i in range(self.__practice_room.shape[0]):
                    self.__practice_room[i] = tuple(all_rooms[i])

            elif order == 'stop':
                print('> DEBUG: Terminate server!')
                break
            else:
                print('> ERROR: Unknown task type. ', order)

            if self.debug:
                print('name list: ')
                print(self.__queue_list[self.__queue_list['name']!='-1'])
                print('available rooms: ')
                print(self.__available_rooms)
                print('reservations: ')
                print(self.__reservations)
                print('all queue size: ')
                print(self.__total_waiting)
                print('all practice rooms: ')
                print(self.__practice_room)
                print('debug mode is on, auto terminated.')
                break
            else:
                print('> DEBUG: Information updated.')
        return

    def reset_vaba_room_reservation(self):
        self.__reservations = {}
        self.__available_rooms = {}
        self.__total_waiting = 0
        self.__practice_room = []
        return

    def soup_brewer(self):
        print('> DEBUG: Brewer started.')
        while True:
            if self.__terminate:
                print('Terminating brewer...')
                self.__task.put('stop')
                break
            # self.__soup_1 = run_fetcher(self.__queue_url)
            # self.__soup_2 = run_fetcher(self.__room_url)
            self.__soup_1 = BeautifulSoup(requests.get(self.__queue_url, verify=False).text, features="lxml")
            self.__soup_2 = BeautifulSoup(requests.get(self.__room_url, verify=False).text, features="lxml")
            self.__task.put('job')
            time.sleep(self.time_interval)
        print('Brewer stopped.')
        return

    def on_quit(self):
        # saving study materials
        print('> DEBUG: saving materials...')
        study = np.array(self.__study_material)
        fname = time.strftime("%Y-%M-%d-%H-%M", time.localtime(time.time()))+'.npz'
        np.savez_compressed(os.path.join('./data/', fname), data=study)
        print('> DEBUG: all saved.')
        return

    # functions to control the bot
    def terminate_bot(self):
        print('> DEBUG: Terminating the bot...')
        self.__terminate = True

        for t in self.__threads:
            print('> DEBUG: Waiting thread %s to stop.' % t)
            self.__threads[t].join()

        # saving states
        print('> DEBUG: Saving states...')
        self.on_quit()
        print('Bye.')
        return

    def show_threads(self):
        print('Working threads: ')
        print(self.__threads.keys())
        return self.__threads

    def get_soup(self):
        return self.__soup_1, self.__soup_2

    def feed_soup(self, soup1=None, soup2=None):
        self.__soup_1 = soup1
        self.__soup_2 = soup2
        self.__task.put('job')
        return

    def get_study_material(self):
        return self.__study_material

    # querying
    def search_queue(self, name=None):
        if type(name) != type(None):
            query = self.__queue_list[self.__queue_list['name'] == name]
        else:
            return self.__queue_list[self.__queue_list['name']!='-1']

        return query

    def get_empty_rooms(self):
        return self.__available_rooms

    def get_queue_size(self):
        return self.__total_waiting

    def search_rooms(self, name=None, room_id=None):
        if type(name) != type(None):
            query = self.__practice_room[self.__practice_room['name']==name]
        elif type(room_id) != type(None):
            query = self.__practice_room[self.__practice_room['room_id'] == room_id]
        else:
            return self.__practice_room

        return query

    def check_reservations(self, room_id=None):
        if type(room_id) != type(None):
            if room_id in self.__reservations:
                return self.__reservations[room_id]
            else:
                return 0
        else:
            return self.__reservations

    def get_estimation_time(self):
        return 

if __name__ == '__main__':
    pass
