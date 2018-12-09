import os

PATH = os.getcwd()
import sys

sys.path.insert(0, os.path.join(PATH, 'EMTA/'))
import check_room

import telepot
from telepot.loop import MessageLoop
from telepot.delegate import pave_event_space, per_chat_id, create_open
import time
from threading import Thread

import logging

# fname = './logs/%s.log' % time.strftime("%Y-%m-%d-%H-%M", time.localtime())
# with open(fname, 'w') as f:
#     f.write('-----begining of the log------')
# logging.basicConfig(filename=fname, filemode='w', format='%(asctime)s - %(levelname)s:  %(message)s', level=logging.DEBUG)
logging.basicConfig(format='%(asctime)s - %(levelname)s:  %(message)s', level=logging.WARN)


class TelegramBot:
    def __init__(self, token, interval=30, debug=False, start_monitor=True):
        self.interval = interval
        self.debug = debug

        self.__monitor = None
        self.__tgbot = telepot.Bot(token)
        MessageLoop(self.__tgbot, self.__msg_handler).run_as_thread()

        self.__profiles = {}
        self.__read_later = []

        self.__threads = {}
        logging.warning('Telegram bot has been started.')
        if start_monitor:
            self.start_monitor()
        return

    def start_monitor(self):
        self.__monitor = check_room.MonitorBot(time_interval=self.interval, debug=self.debug)
        return

    def stop_monitor(self):
        if type(self.__monitor) != type(None):
            self.__monitor.terminate_bot()
        return

    def get_monitor_bot(self):
        return self.__monitor

    def show_read_later(self):
        cc = 0
        for msg in self.__read_later:
            print('------------------------------------------------------------------------')
            sender = msg['from']['first_name'] + ' ' + msg['from']['last_name']
            print('#%d. Sender: %s  Time: %s' % (cc, sender, time.ctime(msg['date'])))
            print('Content: ')
            print(msg['text'])
            cc += 1
        return

    def get_threads(self):
        print(self.__threads.keys())
        return self.__threads

    def get_profiles(self):
        return self.__profiles

    def __msg_handler(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        logging.warning('Received msg-> content_type: %s, chat_type: %s, chat_id: %d' %
                        (content_type, chat_type, chat_id))
        if self.debug:
            print(msg)

        if content_type == 'text':
            # CASE 1: new user
            if msg['text'].startswith('/register'):
                self.__register_new(chat_id, msg)

            # CASE 2: update profile
            elif msg['text'].startswith('/updateprofile'):
                self.__update_registration(chat_id, msg)

            # CASE 3: check queue size
            elif msg['text'].startswith('/queuesize'):
                self.__check_queue_size(chat_id)

            # CASW 4: check queue
            elif msg['text'].startswith('/queue'):
                self.__check_queue(chat_id, msg)

            # CASE 5&6: search room by name, search room by id
            elif msg['text'].startswith('/searchroombyname') or msg['text'].startswith('/searchroombyid'):
                self.__search_rooms(chat_id, msg)

            # CASE 7: search empty room
            elif msg['text'].startswith('/searchemptyroom'):
                rooms = self.__monitor.get_empty_rooms()
                reply = ''
                for room in rooms:
                    reply = reply + room + ': ' + rooms[room] + '\n'
                self.__tgbot.sendMessage(chat_id, 'Here is empty rooms: .')
                self.__tgbot.sendMessage(chat_id, reply)

            # CASE 8: reservations
            elif msg['text'].startswith('/reservations'):
                self.__check_reservations(chat_id, msg)

            # UNKNOWN CASE
            else:
                self.__tgbot.sendMessage(chat_id,
                                         'Unknown type of message. But I will save it :) and read later.')
                self.__read_later.append(msg)
        return

    def __register_new(self, chat_id, msg):
        command_info = msg['text'].split(' ')
        if len(command_info) < 3:
            self.__tgbot.sendMessage(chat_id,
                                     'Error: Please add your name after command and separate with a space.\n'
                                     'eg. /register first last')
        else:
            full_name = ' '.join(command_info[1:]).lower()
            if msg['chat']['username'] in self.__profiles:
                self.__tgbot.sendMessage(chat_id,
                                         'You already registered as %s.\n'
                                         'Update info use command /updateprofile.'
                                         % self.__profiles[msg['chat']['username']]['register_name'])
            else:
                self.__profiles[msg['chat']['username']] = {'chat':msg['chat'], 'register_name':full_name}
                self.__tgbot.sendMessage(chat_id,
                                         'Success! Now you are registered as: %s' % full_name)
        return

    def __update_registration(self, chat_id, msg):
        command_info = msg['text'].split(' ')
        if len(command_info) < 3:
            self.__tgbot.sendMessage(chat_id,
                                     'Error: Please add your name after command and separate with a space.\n'
                                     'eg. /updateprofile first last')
        else:
            full_name = ' '.join(command_info[1:]).lower()
            if msg['chat']['username'] in self.__profiles:
                self.__profiles[msg['chat']['username']] = {'chat': msg['chat'], 'register_name': full_name}
                self.__tgbot.sendMessage(chat_id,
                                         'Success! Now you are registered as: %s' % full_name)
            else:
                self.__tgbot.sendMessage(chat_id,
                                         'You are not registered yet!\nPlease use /register first!')
        return

    def __check_queue(self, chat_id, msg):
        if msg['chat']['username'] in self.__profiles:
            self.__tgbot.sendMessage(chat_id,
                                     'Queue monitor system started.')
            full_name = self.__profiles[msg['chat']['username']]['register_name']
            p_user = Thread(target=self.__queue_task, args=(chat_id, full_name))
            self.__threads[msg['chat']['username']] = p_user
            p_user.start()

        else:
            self.__tgbot.sendMessage(chat_id,
                                     'You are not registered yet\nPlease use /register first!')
        return

    def __queue_task(self, chat_id, name):
        last_position = -1
        cc = 0
        name = name.upper()
        name_list = name.split(' ')
        name_list[-1] = name_list[-1][:1]
        name = ' '.join(name_list)
        while True:
            query = self.__monitor.search_queue(name=name)
            if query.size == 0:
                self.__tgbot.sendMessage(chat_id,
                                         'Can not find your name in the queue. Monitor system terminated!')
                break

            position = query[0]['position']
            status = query[0]['status']

            if status == 1 and cc % 30 == 0:
                self.__tgbot.sendMessage(chat_id,
                                         'You can go to pick your key! position: %d!' % position)
                last_position = position

            if status == 1:
                cc += 1

            if position != last_position:
                total_number = self.__monitor.get_queue_size()
                self.__tgbot.sendMessage(chat_id,
                                         'You position has changed! %d/%d!' % (position, total_number))
                last_position = position

            time.sleep(1)
        return

    def __check_queue_size(self, chat_id):
        number = self.__monitor.get_queue_size()
        namelist = self.__monitor.search_queue()['name']
        str_namelist = '%s' % ', '.join(namelist)
        self.__tgbot.sendMessage(chat_id,
                                 'There are %d people in the waiting queue.\n'
                                 'Estimation function will come later.' % number)
        self.__tgbot.sendMessage(chat_id,
                                 'Name list in the queue: ' + str_namelist)
        return

    def __search_rooms(self, chat_id, msg):
        command_info = msg['text'].split(' ')
        if len(command_info) == 1:
            query = self.__monitor.search_rooms()
            reply = ''
            for room in query:
                reply = reply + room[0] + ' | ' + room[1] + ' | ' + room[2] + '\n'
            self.__tgbot.sendMessage(chat_id, 'Here is all practice rooms: ')
            self.__tgbot.sendMessage(chat_id, reply)
            return

        elif len(command_info) == 2:
            room_id = command_info[1]
            query = self.__monitor.search_rooms(room_id=room_id)

        elif len(command_info) > 2:
            name_info = list(map(lambda x: x.capitalize(), command_info[1:]))
            full_name = ' '.join(name_info)
            query = self.__monitor.search_rooms(name=full_name)

        else:
            str_command = '%s' % ' '.join(command_info[1:])
            self.__tgbot.sendMessage(chat_id,
                                     'Cant understand your query: ' + str_command)
            return

        if query.size == 0:
            self.__tgbot.sendMessage(chat_id,
                                     'Can not find the room by your given information.')
        else:
            infomation = query[0]
            self.__tgbot.sendMessage(chat_id,
                                     'Room id: %s, Remaining time: %s\n'
                                     'Name: %s.' % (infomation[0], infomation[1], infomation[2]))
        return

    def __check_reservations(self, chat_id, msg):
        command_info = msg['text'].split(' ')
        if len(command_info) == 1:
            query = self.__monitor.check_reservations()
            reply = ''
            for room in query:
                reservations = query[room]
                reserve_info = ''.join(reservations)
                reply = reply + room + ': ' + reserve_info + '\n'
            self.__tgbot.sendMessage(chat_id, 'Here is all reservations: ')
            self.__tgbot.sendMessage(chat_id, reply)

        elif len(command_info) == 2:
            room_id = command_info[1]
            query = self.__monitor.check_reservations(room_id=room_id)
            reply = ''.join(query)
            self.__tgbot.sendMessage(chat_id, 'Room: %s\n'
                                              'Info: %s' % (room_id, reply))
        else:
            self.__tgbot.sendMessage(chat_id, 'Unknown input: %s' % ' '.join(command_info[1:]))
        return

    def __on_stop(self):
        return


if __name__ == '__main__':
    TOKEN = sys.argv[1]  # get token from command-line
    bot = TelegramBot(TOKEN)
    try:
        while 1:
            time.sleep(10)
    except KeyboardInterrupt as e:
        print('> DEBUG: Terminating telegram bot...')
        bot.__on_stop()
        print('bye:)')
        del bot
