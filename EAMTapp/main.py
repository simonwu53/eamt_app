from TGBot import Bot
import sys
import time
import logging

# Set logging
FORMAT = '[%(asctime)s [%(name)s][%(levelname)s]: %(message)s'
logging.basicConfig(format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, filename='./logs/EAMTapp.log')
LOG = logging.getLogger('EAMT-MAIN-SERVICE')


if __name__ == '__main__':
    TOKEN = sys.argv[1]
    bot = Bot(TOKEN)
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt as e:
        bot.on_stop()
