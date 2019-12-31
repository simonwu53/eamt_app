from TGBot import Bot
import time
import logging
import argparse

# Set logging
FORMAT = '[%(asctime)s [%(name)s][%(levelname)s]: %(message)s'
logging.basicConfig(format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, filename='./logs/EAMTapp.log')
LOG = logging.getLogger('EAMT-MAIN-SERVICE')


if __name__ == '__main__':
    # setup argparser
    parser = argparse.ArgumentParser()
    # data_group = parser.add_mutually_exclusive_group()
    parser.add_argument('--no_room_monitor', action='store_true', default=False,
                        help='Do not start room monitor.')
    parser.add_argument('--no_web_driver', action='store_true', default=False,
                        help='Do not start web driver to fetch JS web site.')
    parser.add_argument('-t', '--token', type=str,  help='TG bot token.')
    parser.add_argument('-i', '--interval', type=int, default=10,
                        help='Refresh interval by seconds for room monitor.')

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
    bot = Bot(args.token, room_monitor=room_monitor, start_webdriver=start_webdriver, interval=args.interval)
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt as e:
        bot.on_stop()
