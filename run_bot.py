#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

from skype_bot.bot import Bot

bot_config = {
    'bot_name': 'my-bot',
   'bot_password': '<your bot password here>',  # example 'UeteHnfdQgieutiYLHTQE9F'
   'bot_app_id':   '<your app id here>',         # example '4f7bcc06-bb22-4f4a-b44c-51485be54c67'
   'logging_level': logging.DEBUG,
   'port': 3978,
   'hostname': '0.0.0.0',

   'jenkins' : {
        'url' : 'jenkins_url/',
        'user' : 'user_name',
        'token' : 'user_token',
    },
}


def handle_message(text, type, conversation_id, sender_name, sender_id):
    print("Message from {} received. Text: {}, type: {}, conversion_id: {}".format(sender_name, text, type,
                                                                                   conversation_id))
    return 'message received'


my_bot = Bot()
my_bot.set_default_message_handler(handle_message)
app = my_bot

if __name__ == "__main__":
    my_bot.run()
