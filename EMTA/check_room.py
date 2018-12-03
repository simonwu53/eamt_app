from bs4 import BeautifulSoup
from urllib.request import urlopen
import ssl
import telegram_send
import time


def run_fetcher():
    print('Updating soup...')
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
    print('Finding your name in the list...')
    items = soup.find_all(color='black')
    str_calling_list_est = items[0].b.text
    str_waiting_list_est = items[1].text

    calling_next = items[0].find_all_next(text=True)
    waiting_next = items[1].find_all_next(text=True)

    # init variables
    flag = False
    notify_call = True
    notify_wait = True
    count = 0

    # get calling list
    for each_name in calling_next[1:]:
        if each_name == name:
            count += 1
            flag = True
            if notify_call:
                telegram_send.send(messages=['Your place in the calling list is %d.' % count,
                                             'You can go to pick up your key now!'])
                notify_call = False
            print('Your place in the calling list is %d.' % count)
        elif each_name == '\n':
            continue
        elif each_name == 'JÄRJEKORRAS':
            break
        else:
            count += 1

    # get waiting list
    count = 0
    for each_name in waiting_next[2:]:
        if each_name == name:
            count += 1
            flag = True
            if notify_wait:
                telegram_send.send(messages=['Your place in the calling list is %d.' % count])
                notify_wait = False
            print('Your place in the waiting list is %d.' % count)
        elif each_name == '\n':
            continue
        elif each_name == 'VABANEVAD KLASSID:':
            print('Number of waiting list: %d' % count)
            break
        else:
            count += 1

    if not flag:
        print('You are not in the list!')
    return

def run(name):
    soup = run_fetcher()
    find_waiting_list(soup, name)
    return

def run_forever(name):
    try:
        print('Auto bot start running...')
        while True:
            run(name)
            time.sleep(30)
    except KeyboardInterrupt:
        print('bye:)')
    return


if __name__ == '__main__':
    url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
    soup = BeautifulSoup(make_request(url, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1)))
