#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

import logging.config
import yaml

log_config = yaml.load(open('logging.yaml'))
logging.config.dictConfig(log_config)

from skype_bot.bot import Bot

my_bot = Bot()
app = my_bot

if __name__ == "__main__":
    my_bot.run()
