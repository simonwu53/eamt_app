# configure path: '/Users/simonwu/Library/Application Support/telegram-send'
from bs4 import BeautifulSoup
from urllib.request import urlopen
import ssl
import telegram_send
import time
from threading import Thread
import os
PATH = os.getcwd()

def run_fetcher():
    print('> DEBUG: Updating soup...')
    url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
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
            soup = run_fetcher()
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

class ClassRoom_Bot():
    def __init__(self, name, time_interval=30):
        self.__name_list = [name]
        self.__time_interval = time_interval
        self.__records = {}  # time: status
        self.__threads = {}
        self.__soup = None
        self.__url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
        self.__terminate = False

        # init user promt
        p_usr = Thread(target=self.usr_interface)
        self.__threads['usr_prompt'] = p_usr
        p_usr.start()
        # init soup brewer
        brewer = Thread(target=self.soup_brewer)
        self.__threads['soup_brewer'] = brewer
        brewer.start()
        return

    def run_server(self):
        return

    def init_server(self):
        return

    def init_spy(self):
        return

    def terminate_thread(self, t_name):
        p = self.__threads[t_name]
        # send sigkill
        return

    def spy_worker(self):

        return

    def soup_brewer(self):
        print('Brewer started.')
        while True:
            if self.__terminate:
                print('Terminating brewer...')
                break
            self.__soup = run_fetcher()
            time.sleep(self.__time_interval)
        print('Brewer stopped.')
        return

    def usr_interface(self):
        return

    # functions to control the bot
    def terminate_bot(self):
        print('Terminating the bot...')
        self.__terminate = True

        for t in self.__threads:
            print('Waiting thread %s to stop.' % t)
            self.__threads[t].join()
        print('Bye.')
        return

    def show_threads(self):
        print('Working threads: ')
        print(self.__threads.keys())
        return

    def get_soup(self):
        return self.__soup

    def add_name(self, name):
        if type(name) == type(str):
            self.__name_list.append(name)
            print('Your name: %s added.' % name)
        else:
            print('Please input a valid name!')
        return


if __name__ == '__main__':
    url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
    soup = BeautifulSoup(make_request(url, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1)))
