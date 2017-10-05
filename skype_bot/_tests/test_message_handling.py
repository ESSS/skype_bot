from __future__ import absolute_import, division, print_function, unicode_literals

import time
import urllib
from datetime import datetime

import mock

from skype_bot.bot import Bot

bot_config = {
    'bot_name': 'my-bot',
    'bot_password': '<your bot password here>',  # example 'UeteHnfdQgieutiYLHTQE9F'
    'bot_app_id':   '<your app id here>',         # example '4f7bcc06-bb22-4f4a-b44c-51485be54c67'
    'logging_level': 0,
    'port': 3978,
    'hostname': 'localhost',

    'jenkins' : {
        'url' : '/',
    }
}

# @mock.patch.object(Bot, 'send', return_value=200)
def test_register_user():
    app = Bot(bot_config)

    assert app.handle_message('Hello', 'message', 'conversation_id', 'Test User', 'sender_id') == app.UNKNOWN_USER_MSG
    
    jenkins_id = 'test_jenkins'
    assert app.handle_message('jenkins_id: {}'.format(jenkins_id), 'message', 'conversation_id', 'Test User', 'sender_id') == \
        app.REGISTER_USER_MSG.format(jenkins_id)
        
    help_message = app.handle_message('help', 'message', 'conversation_id', 'Test User', 'sender_id')
    assert '<b>status</b>' in help_message
    
    print(app.handle_message('status', 'message', 'conversation_id', 'Test User', 'sender_id'))
