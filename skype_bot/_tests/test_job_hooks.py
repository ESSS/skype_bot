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
def test_job_started():
    app = Bot(bot_config)

    start_date = datetime(2017, 1, 1)
    timestamp = time.mktime(start_date.timetuple())

    params = {
        'event' : 'jenkins.job.started',
        'timestamp' : '%d' % (timestamp * 1000),
        'number' : '1',
        'userId' : 'tnobrega',
        'job_name' : 'etk-fb-ETK-ROCKY-v4.0-merge-master-win64-35',
        'builtOn' : 'dev-windows10-win-sv01-ci02',
        'url' : 'job/etk-fb-ETK-ROCKY-v4.0-merge-master-win64-35/1/',
    }

    encoded_params = urllib.urlencode(params)

    app._jenkins_contacts['tnobrega'] = 'id'

    with mock.patch.object(Bot, 'send', return_value=200) as send_mock:
        with app.test_client() as c:
            resp = c.get('/job/started?' + encoded_params)
            assert resp.status_code == 200
            assert send_mock.call_count == 1
            send_mock.assert_called_with(
                u'id',
                '(skate) <b>Started:</b>'
                ' <a href="/job/etk-fb-ETK-ROCKY-v4.0-merge-master-win64-35">etk-fb-ETK-ROCKY-v4.0-merge-master-win64-35</a>'
                '\nStarted: <b>2017-01-01 00:00:00</b>'
                '\nBuilt On: <b>dev-windows10-win-sv01-ci02</b>'
            )

    params = {
        'event' : 'jenkins.job.completed',
        'duration' : '4938350',
        'timestamp' : '%d' % (timestamp * 1000),
        'number' : '10',
        'userId' : 'tnobrega',
        'job_name' : 'rocky30-fb-ROCKY-5028-linux-tests-linux64',
        'result' : 'SUCCESS',
        'url' : 'job/rocky30-fb-ROCKY-5028-linux-tests-linux64/10/',
    }
    encoded_params = urllib.urlencode(params)

    with mock.patch.object(Bot, 'send', return_value=200) as send_mock:
        with app.test_client() as c:
            resp = c.get('/job/completed?' + encoded_params)
            assert resp.status_code == 200
            assert send_mock.call_count == 1
            send_mock.assert_called_with(
                u'id',
                ';) <b>Finished:</b>'
                ' <a href="/job/rocky30-fb-ROCKY-5028-linux-tests-linux64">rocky30-fb-ROCKY-5028-linux-tests-linux64</a>'
                '\nDuration: <b>82.31</b>'
                '\nStarted: <b>2017-01-01 00:00:00</b>'
            )