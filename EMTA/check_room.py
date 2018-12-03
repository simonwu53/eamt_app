from bs4 import BeautifulSoup
from urllib.request import urlopen
import ssl
import telegram_send
import time
import multiprocessing as mp


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
            print('Number of waiting list: ' + each_name[:2])
            total_number = int(each_name[:2])
            break
        else:
            count += 1

    return status, position, total_number

def run(name):
    soup = run_fetcher()
    status, position, num = find_waiting_list(soup, name)
    return status, position, num

def run_forever(name, debug=False, interval=30):
    try:
        print('Auto bot start running...')
        if not debug:
            telegram_send.send(messages=['Hello, %s. You will be notified when there are updates in the queue.' % name])

        # init
        wait_position = -1
        call_position = -1
        status = -1
        send_call = True
        send_wait = True

        while True:
            status, position, num = run(name)

            # check status
            if status == -1:
                print('You are not in the list!')

            elif status == 0:
                print('Your position in waiting list: %d' % position)
                if wait_position != position:
                    send_wait = True
                    wait_position = position

                if send_wait and not debug:
                    telegram_send.send(messages=['You are in the waiting queue: %d/%d' % (position, num)])
                    send_wait = False

            elif status == 1:
                print('Your position in calling list: %d' % position)
                if call_position != position:
                    send_call = True
                    call_position = position

                if send_call and not debug:
                    telegram_send.send(messages=['You can go to pick up your key now!', 'position: %d.' % position])
                    send_call = False

            time.sleep(interval)
    except KeyboardInterrupt:
        print('bye:)')
    return

class ClassRoom_Bot():
    def __init__(self, name):
        self.name = name
        self.records = {}  # time: status
        self.threads = []
        return

    def run_server(self):
        p1 = mp.Process(target=run_forever, args=(self.name,), name='server_bot')
        self.threads.append(p)
        p2 = mp.Process(target=self.usr_interface, args=(self,), name='usr')
        return

    def usr_interface(self):
        return


if __name__ == '__main__':
    url = 'https://sise.ema.edu.ee/vaatleja/vabadruumid2.x'
    soup = BeautifulSoup(make_request(url, context=ssl.SSLContext(ssl.PROTOCOL_TLSv1)))
