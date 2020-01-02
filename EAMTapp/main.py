from TGBot import Bot
import logging
import argparse
import signal
import os

# Set logging
FORMAT = '[%(asctime)s [%(name)s][%(levelname)s]: %(message)s'
logging.basicConfig(format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, filename='./logs/EAMTapp.log')
LOG = logging.getLogger('EAMT-MAIN-SERVICE')


def main():
    # setup argparser
    parser = argparse.ArgumentParser()
    # data_group = parser.add_mutually_exclusive_group()
    parser.add_argument('--no_room_monitor', action='store_true', default=False,
                        help='Do not start room monitor.')
    parser.add_argument('--no_web_driver', action='store_true', default=False,
                        help='Do not start web driver to fetch JS web site.')
    parser.add_argument('-t', '--token', type=str, help='TG bot token.')
    parser.add_argument('-i', '--interval', type=int, default=30,
                        help='Refresh interval by seconds for room monitor.')
    parser.add_argument('-tz', '--timezone', type=str, default='Europe/Tallinn', help='Set timezone of the bot.')
    parser.add_argument('--night_start', type=int, default=22,
                        help='Start hour of night. Bot will terminate refreshing during night hours.')
    parser.add_argument('--night_end', type=int, default=8,
                        help='End hour of night. Bot will terminate refreshing during night hours.')

    # templates
    # parser.add_argument('--model', type=str, help='help')
    # parser.add_argument('--origin', action='store_false', default=True, help='help')
    # parser.add_argument('--split', type=float, default=0.2, help='help')
    # parser.add_argument('--epoch', type=int, default=1, help='help')

    args = parser.parse_args()
    room_monitor = True
    start_webdriver = True
    if args.no_room_monitor:
        room_monitor = False
    if args.no_web_driver:
        start_webdriver = False
    night_hours = (args.night_start, args.night_end)
    bot = Bot(args.token, room_monitor=room_monitor, start_webdriver=start_webdriver, interval=args.interval,
              monitor_time_zone=args.timezone, monitor_night_pause=night_hours)

    def receiveSignal(signum, frame):
        LOG.info('Received: %d, Current PID: %d' % (signum, os.getpid()))
        bot.on_stop()
        return

    # register signal
    signal.signal(signal.SIGTERM, receiveSignal)
    signal.signal(signal.SIGINT, receiveSignal)

    # wait until a signal has been caught
    signal.pause()
    return


if __name__ == '__main__':
    main()
