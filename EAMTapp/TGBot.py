import telepot
from telepot.loop import MessageLoop
import sqlite3
import sys
import logging
from time import sleep
from datetime import datetime, time
import pytz
from threading import Thread
from web import get_rooms, WebBrowser


# Set logging
FORMAT = '[%(asctime)s [%(name)s][%(levelname)s]: %(message)s'
logging.basicConfig(format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, filename='./logs/TGBot.log')
LOG = logging.getLogger('TGBot')

DB_PAth = './eamt_app.db'

# id=db primary key; uid=tg user id
str_create_users_table = """
    CREATE TABLE users (
        id integer PRIMARY KEY,
        uid integer NOT NULL,
        username text NOT NULL,
        first_name text NOT NULL, 
        last_name text NOT NULL,
        chat_id integer NOT NULL,
        language_code text NOT NULL )"""

str_create_rooms_table = """
    CREATE TABLE rooms (
        id integer PRIMARY KEY,
        room text NOT NULL,
        status text NOT NULL,
        holder text NOT NULL)"""

# date format  ISO8601 strings "YYYY-MM-DD HH:MM:SS.SSS"
str_create_reservations_table = """
    CREATE TABLE reservations (
        id integer PRIMARY KEY,
        room text NOT NULL,
        start text NOT NULL,
        end text NOT NULL,
        holder text NOT NULL)"""

str_create_messages_table = """
    CREATE TABLE messages (
        id integer PRIMARY KEY,
        sender text NOT NULL,
        message text NOT NULL,
        date integer NOT NULL)"""

str_insert_user = \
    """INSERT INTO users (uid, username, first_name, last_name, chat_id, language_code) VALUES (?, ?, ?, ?, ?, ?)"""
str_update_user = \
    """UPDATE users SET username = ?, first_name = ?, last_name = ?, chat_id = ?, language_code = ? WHERE uid = ?"""
str_insert_room = \
    """INSERT INTO rooms (room, status, holder) VALUES (?, ?, ?)"""
str_clear_rooms = """DELETE FROM rooms"""
str_query_tables = "SELECT name FROM sqlite_master WHERE type='table'"


class Bot:
    def __init__(self, token, room_monitor=True, start_webdriver=True, interval=30,
                 monitor_night_pause=(22, 8), monitor_time_zone='Europe/Tallinn'):
        # protected variables
        self.__token = token
        self.__tgbot = None
        self.__is_running = True
        self.__threads = {}
        self.__browser = None
        self.__refresh_interval = interval
        self.__night_hours = monitor_night_pause

        # params
        self.timezone = monitor_time_zone

        # connect to db
        LOG.info('Connecting to database.')
        self.con = self.__db_connect()  # NB! this can be used only in the main thread!!!!
        self.cur = self.con.cursor()
        LOG.info('Database connected.')

        # initialize db if there's no table
        self.cur.execute(str_query_tables)
        res = self.cur.fetchall()
        if len(res) == 0:
            LOG.info('Initialize database.')
            self.__init_database()
            LOG.info('Initialization done.')

        # start TG bot
        LOG.info('Create TG Bot.')
        self.__tgbot = telepot.Bot(self.__token)
        MessageLoop(self.__tgbot, self.__msg_handler).run_as_thread()
        LOG.info('TG Bot has started.')

        if room_monitor:
            self.rooms_monitor(interval=self.__refresh_interval, night_pause=self.__night_hours)
        if start_webdriver:
            self.__browser = WebBrowser()
        return

    def __db_connect(self, path=DB_PAth):
        con = sqlite3.connect(path)
        return con

    def __init_database(self):
        # create tables
        self.cur.execute(str_create_users_table)
        self.cur.execute(str_create_rooms_table)
        self.cur.execute(str_create_reservations_table)
        self.cur.execute(str_create_messages_table)
        # commit the change
        self.con.commit()
        return

    def __add_new_user(self, cur, uid, username, first_name, last_name, chat_id, language_code):
        """
        Add new user to users table
        :param cur: db cursor
        :param uid: TG id
        :param username: TG username
        :param first_name: TG first name
        :param last_name: TG last name
        :param chat_id: Chat id that user connected with this bot
        :param language_code: TG user language code
        return: 1 -- success, 0 -- failed
        """
        LOG.info('Adding new user -> (uid=%d, name=%s %s, chat_id=%d)' % (uid, first_name, last_name, chat_id))
        # check if user already exists
        res = self.__get_user(uid=uid, cur=cur)

        # no record, new user
        if len(res) == 0:
            cur.execute(str_insert_user, (uid, username, first_name, last_name, chat_id, language_code))
            LOG.info('New user added.')
            _ = self.__send_msg(chat_id, 'Register success! Your name %s %s and current chat is bond with EAMT Bot.' %
                                (first_name, last_name))
            return 1

        # user exists
        else:
            # duplicated user!! only use first query, it should be one
            if len(res) > 1:
                LOG.error('Duplicated user found in database! -> Name: %s %s' % (first_name, last_name))

            # only use the first info
            res = res[0]
            username, first_name, last_name, chat_id_old = res
            _ = self.__send_msg(chat_id, 'You have registered as %s %s (%s) with chat_id %d.' %
                                (first_name, last_name, username, chat_id_old))
            LOG.info('User already exists.')
            return 0

    def __update_user(self, cur, uid, username, first_name, last_name, chat_id, language_code):
        """
        Update user profile (table) based on TG id (uid)
        :param cur: db cursor
        :param uid: TG id
        :param username: TG username
        :param first_name: update first name
        :param last_name: update last name
        :param chat_id: bond bot with a new chat
        :param language_code: TG user language code
        return: 1 -- success, 0 -- failed
        """
        LOG.info('Update existing user  -> (uid=%d, name=%s %s, chat_id=%d)' % (uid, first_name, last_name, chat_id))
        # check if exists
        res = self.__get_user(uid=uid, cur=cur)
        if len(res) == 0:
            LOG.warning('User not found.')
            _ = self.__send_msg(chat_id, 'You have not registered yet. Please use /register command to register first.')
            return 0

        # update
        cur.execute(str_update_user, (username, first_name, last_name, chat_id, language_code, uid))
        LOG.info('User updated.')
        _ = self.__send_msg(chat_id, 'Your profile has been updated! '
                                     'Your name %s %s and current chat is bond with EAMT Bot.' %
                            (first_name, last_name))
        return 1

    def __get_user(self, uid, cur=None, key=None, fields="username, first_name, last_name, chat_id"):
        """
        query user by id or uid, query fields can be customized
        :param uid: TG id
        :param cur: db cursor. if None, the main thread's cursor will be used (will cause error in other threads)
        :param key: user table primary key
        :param fields: query fields in a tuple
        return: list of query, can be a empty list
        """
        query = "SELECT %s FROM users WHERE %s = ?"
        if cur is None:
            cur = self.cur

        if key is None:
            query = query % (fields, 'uid')
            cur.execute(query, (uid,))
        else:
            query = query % (fields, 'id')
            cur.execute(query, (key,))
        return cur.fetchall()

    def __get_userid(self, first_name, last_name, cur=None):
        """
        query user's primary key by first name and last name
        :param first_name: TG user first name
        :param last_name: TG user last name
        :param cur: db cursor. if None, the main thread's cursor will be used (will cause error in other threads)
        return: list of query, can be a empty list
        """
        if cur is None:
            cur = self.cur

        cur.execute("SELECT id FROM users WHERE first_name = ? AND last_name = ?", (first_name, last_name))
        return cur.fetchall()

    def __add_new_rooms(self, cur, rooms):
        """
        Add rooms to table (room_number, remaining_time, room_holder)
        :param cur: db cursor
        :param rooms: list of rooms information
        """
        for room in rooms:
            room_num, status, holder = room
            cur.execute(str_insert_room, (room_num, status, holder))
        LOG.info('Inserted %d new rooms.' % len(rooms))
        return

    def __get_room(self, cur=None, full_name=None, room_num=None):
        """
        Search room by holder's name or room number
        :param cur: db cursor
        :param full_name: full name want to query
        :param room_num: room number want to query
        return query result list, could be an empty list
        """
        if cur is None:
            cur = self.cur

        if full_name is not None:
            LOG.info('Querying room info by name: %s' % full_name)
            full_name = full_name.upper()
            cur.execute('SELECT room, status, holder FROM rooms WHERE holder = ?', (full_name,))
            return cur.fetchall()

        if room_num is not None:
            LOG.info('Querying room info by room number: %s' % room_num)
            room_num = room_num.upper()
            cur.execute('SELECT room, status, holder FROM rooms WHERE room = ?', (room_num,))
            return cur.fetchall()

        LOG.error(f'Invalid room query: name={full_name}, num={room_num}')
        return []

    def __clear_rooms(self, cur=None):
        if cur is None:
            cur = self.cur

        cur.execute(str_clear_rooms)
        LOG.info('Table: rooms cleared.')
        return

    def __msg_handler(self, msg):
        # create db connection in new thread
        con = self.__db_connect()
        cur = con.cursor()

        # abstract of msg
        content_type, chat_type, chat_id = telepot.glance(msg)
        LOG.info('Received msg -> content_type: %s, chat_type: %s, chat_id: %d' % (content_type, chat_type, chat_id))

        # only process text message currently
        if content_type == 'text':

            # CASE 1: new user
            if msg['text'].startswith('/register'):
                sender = msg['from']
                msg_split = msg['text'].split(' ')

                res = 0
                try:
                    # only register command
                    if len(msg_split) == 1:
                        res = self.__add_new_user(cur=cur, uid=sender['id'], username=sender['username'],
                                                  first_name=sender['first_name'], last_name=sender['last_name'],
                                                  chat_id=chat_id, language_code=sender['language_code'])
                    # register command with names
                    elif len(msg_split) == 2:
                        LOG.error('Incomplete name in registration! Name: %s' % msg_split[1])
                        _ = self.__send_msg(chat_id=chat_id,
                                            msg='Incomplete name in registration! '
                                                'Please provide both first name and last name.')
                    else:
                        # remove command
                        msg_split = msg_split[1:]
                        # assemble first name, last name
                        first_name = msg_split[0]
                        last_name = ' '.join(msg_split[1:])
                        res = self.__add_new_user(cur=cur, uid=sender['id'], username=sender['username'],
                                                  first_name=first_name, last_name=last_name,
                                                  chat_id=chat_id, language_code=sender['language_code'])
                    if res:
                        con.commit()
                except sqlite3.ProgrammingError as err:
                    # roll back db to last commit
                    con.rollback()
                    LOG.error(err)

            # CASE 2: update profile
            elif msg['text'].startswith('/updateprofile'):
                sender = msg['from']
                msg_split = msg['text'].split(' ')

                res = 0
                try:
                    # only register command
                    if len(msg_split) == 1:
                        res = self.__update_user(cur=cur, uid=sender['id'], username=sender['username'],
                                                 first_name=sender['first_name'], last_name=sender['last_name'],
                                                 chat_id=chat_id, language_code=sender['language_code'])
                    # register command with names
                    elif len(msg_split) == 2:
                        LOG.error('Incomplete name in updating user profile! Name: %s' % msg_split[1])
                        _ = self.__send_msg(chat_id=chat_id,
                                            msg='Incomplete name in updating user profile! '
                                                'Please provide both first name and last name.')
                    else:
                        # remove command
                        msg_split = msg_split[1:]
                        # assemble first name, last name
                        first_name = msg_split[0]
                        last_name = ' '.join(msg_split[1:])
                        res = self.__update_user(cur=cur, uid=sender['id'], username=sender['username'],
                                                 first_name=first_name, last_name=last_name,
                                                 chat_id=chat_id, language_code=sender['language_code'])
                    if res:
                        con.commit()
                except sqlite3.ProgrammingError as err:
                    # roll back db to last commit
                    con.rollback()
                    LOG.error(err)

            # CASE 3: check rooms
            elif msg['text'].startswith('/rooms'):
                if not self.__is_running:
                    _ = self.__send_msg(chat_id, 'Room monitor is not running. Can not perform request.')
                    LOG.error('Rooms are queried while monitor not running.')

                else:
                    cur.execute('SELECT room, status, holder FROM rooms')
                    rooms = cur.fetchall()
                    if not rooms:
                        _ = self.__send_msg(chat_id, 'No room is in use currently.')
                    else:
                        # format the feedback
                        formatted_result = [f"{room_num:<8}{status:<10}{holder:>5}" for room_num, status, holder in rooms]
                        room_num, status, holder = "Room", "Time", "Name"
                        msg = '\n'.join([f"{room_num:<8}{status:<10}{holder:>5}"] + formatted_result)
                        _ = self.__send_msg(chat_id, msg)

            # CASE 4: get daily menu
            elif msg['text'].startswith('/dailymeal'):
                if self.__browser is None:
                    _ = self.__send_msg(chat_id, 'Web driver is not running. Can not perform request.')
                    LOG.error('JS Web requested while web driver not running.')

                else:
                    msg = self.__send_msg(chat_id, 'Fetching menu, please wait...')
                    menu = self.__browser.get_dailymeal()

                    if menu is not None:
                        _ = self.__update_msg(chat_id, msg['message_id'], menu)
                    else:
                        _ = self.__update_msg(chat_id, msg['message_id'], 'Can not fetch menu! Please try again later!')
                        LOG.warning('No daily meal menu fetched!')

            # CASE 5: search room by name
            elif msg['text'].startswith('/searchroombyname'):
                if len(msg['text'].split(' ')) == 1:
                    LOG.error('Querying room without input a name!')
                    _ = self.__send_msg(chat_id,
                                        "Error. You should input full name after command, using spaces as separators.")

                else:
                    # remove header
                    msg = msg['text'][18:]
                    res = self.__get_room(cur=cur, full_name=msg)
                    if not res:
                        _ = self.__send_msg(chat_id, "No result. (Could not find)")
                        LOG.info('Room not found.')
                    else:
                        # format the feedback
                        formatted_result = [f"{room_num:<8}{status:<10}{holder:>5}" for room_num, status, holder in res]
                        room_num, status, holder = "Room", "Time", "Name"
                        msg = '\n'.join([f"{room_num:<8}{status:<10}{holder:>5}"] + formatted_result)
                        _ = self.__send_msg(chat_id, msg)
                        LOG.info('Room found. %s' % formatted_result[0])

            # CASE 6: search room by id
            elif msg['text'].startswith('/searchroombyid'):
                if len(msg['text'].split(' ')) == 1:
                    LOG.error('Querying room without input room id!')
                    _ = self.__send_msg(chat_id,
                                        "Error. You should input room id after command, using spaces as separators.")

                else:
                    # remove header
                    msg = msg['text'][16:]
                    res = self.__get_room(cur=cur, room_num=msg)
                    if not res:
                        _ = self.__send_msg(chat_id, "No result. (Could not find)")
                        LOG.info('Room not found.')
                    else:
                        # format the feedback
                        formatted_result = [f"{room_num:<8}{status:<10}{holder:>5}" for room_num, status, holder in res]
                        room_num, status, holder = "Room", "Time", "Name"
                        msg = '\n'.join([f"{room_num:<8}{status:<10}{holder:>5}"] + formatted_result)
                        _ = self.__send_msg(chat_id, msg)
                        LOG.info('Room found. %s' % formatted_result[0])

            # CASE 7: reservations
            elif msg['text'].startswith('/reservations'):
                _ = self.__send_msg(chat_id, 'Not implemented. Unknown command. 1')

            # CASES NOT COVERED
            else:
                _ = self.__send_msg(chat_id, 'Not implemented. Unknown command. 2')

        # all other message types will be ignored
        else:
            LOG.warning('Message dropped! Unsupported type: %s' % content_type)

        # close db connection
        con.close()
        return

    def rooms_monitor(self, interval, night_pause):
        night_start, night_end = night_pause
        LOG.info('Starting rooms monitor, interval %d. Night range (%d:00-%d:00)' % (interval, night_start, night_end))

        def task():
            con = self.__db_connect()
            cur = con.cursor()

            while True:
                if not self.__is_running:
                    con.close()
                    break

                # check current time
                current_time = self.tic_tic()
                if current_time >= time(night_start, 00) or current_time <= time(night_end, 00):
                    sleep(interval)
                    continue

                # fetch rooms info
                try:
                    # clear rooms table
                    self.__clear_rooms(cur=cur)

                    # get rooms in use
                    rooms = get_rooms()
                    # if no room is in use, wait until next refresh
                    if rooms is None:
                        con.commit()
                        sleep(interval)
                        continue

                    # refresh rooms with new entries
                    self.__add_new_rooms(cur=cur, rooms=rooms)
                    # commit changes
                    con.commit()
                except sqlite3.ProgrammingError as err:
                    # roll back db to last commit
                    con.rollback()
                    LOG.error(err)
                # wait until next refresh
                sleep(interval)
            return

        monitor = Thread(target=task)
        self.__threads['monitor'] = monitor
        monitor.start()
        LOG.info('Monitor has started.')
        return

    def __send_msg(self, chat_id, msg):
        msg = self.__tgbot.sendMessage(chat_id, msg)
        LOG.info('Bot message sent -> (chat_id=%d, text=%s)' % (chat_id, msg))

        # # other way to send msg use config file
        # telegram_send.send(messages=['Hello, %s. You will be notified when there are updates in the queue.' % name],
        #                    conf=os.path.join(PATH, 'EMTA/config/telegram-send-shan.conf'))
        return msg

    def __update_msg(self, chat_id, msg_id, msg):
        msg = self.__tgbot.editMessageText((chat_id, msg_id), text=msg)
        LOG.info('Bot message updated -> (chat_id=%d, text=%s)' % (chat_id, msg))
        return msg

    def tic_tic(self):
        """Return current time (datetime.time() object)"""
        return datetime.now(pytz.timezone(self.timezone)).time()

    def on_stop(self):
        LOG.info('Terminating TG Bot...')
        # set running status to false
        self.__is_running = False
        # close web browser
        self.__browser.on_stop()
        # close db connection
        self.con.close()
        # wait until threads terminated
        LOG.info('Waiting threads to be terminated...')
        for k in self.__threads:
            self.__threads[k].join()
        LOG.info('Bye.')
        return


if __name__ == '__main__':
    TOKEN = sys.argv[1]
    bot = Bot(TOKEN)
    try:
        while True:
            sleep(10)
    except KeyboardInterrupt as e:
        bot.on_stop()
