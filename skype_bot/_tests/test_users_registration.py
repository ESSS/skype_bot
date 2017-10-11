from __future__ import absolute_import, division, print_function, unicode_literals

import mock
import pytest
from mock import patch

import mongomock
from skype_bot.users_bot import UsersBot


@pytest.fixture(scope='module')
def users_bot():
    with mock.patch.object(UsersBot, '_get_jenkins_db', return_value=mongomock.MongoClient().db):
        yield UsersBot({
            'jenkins' : {'url' : 'jenkins/'},
            'mongodb' : {'url' : None}
        })



def test_find_build_jobs(users_bot):
    app = users_bot

    print(app._users_db.count())
    app._register_jenkins_user('jenkins_id', 'conversation_id', 'skype_name', 'skype_id')
    print(app._users_db)
    print(app._users_db.count())

    assert app.handle_message('job*', 'message', 'conversation_id', 'Test User', 'skype_id') == 'Unknown command: job*'

    jobs_list = ['job_1', 'job_12', 'job_2', 'job_21']
    with patch('skype_bot.jenkins_jobs.list_jobs', return_value=jobs_list):
        msg = app.handle_message('find: job*', 'message', 'conversation_id', 'Test User', 'skype_id')
        for job_name in jobs_list:
            assert '>{}<' .format(job_name) in msg

        msg = app.handle_message('find: job*1', 'message', 'conversation_id', 'Test User', 'skype_id')
        for job_name in ['job_1', 'job_21']:
            assert '>{}<' .format(job_name) in msg

        for job_name in ['job_12', 'job_2']:
            assert '>{}<' .format(job_name) not in msg

    app._register_jenkins_token('jenkins_id', 'conversation_id', 'skype_name', 'skype_id')

    with patch('skype_bot.jenkins_jobs.build_job', return_value=(200, ' Build')) as build_job:
        print(app.handle_message('build: 1', 'message', 'conversation_id', 'Test User', 'skype_id'))
        build_job.assert_called_once()
        build_job.assert_called_with('job_1', {'url': u'jenkins', 'token': u'jenkins_id', 'user': u'jenkins_id'})


def test_user_registration(users_bot):
    app = users_bot

    for user_info in app.iter_users_info():
        print(user_info)

    assert app.handle_message('help', 'message', 'conversation_id', 'Test User', 'test_id') == \
        app.UNKNOWN_USER_MSG

    
    jenkins_id = 'test_jenkins'
    assert app.handle_message('jenkins_id: {}'.format(jenkins_id), 'message', 'conversation_id', 'Test User', 'test_id') == \
        app.REGISTER_USER_MSG.format(jenkins_id)

    reg_users = list(app.iter_users_info())
    assert len(reg_users) == 1
    user_info = reg_users[0]
    assert user_info['jenkins_id'] == jenkins_id

    assert app.handle_message('rebuild'.format(jenkins_id), 'message', 'conversation_id', 'Test User', 'test_id') == \
        'Unable to get build number from message: "rebuild"'

    assert app.handle_message('rebuild: 1'.format(jenkins_id), 'message', 'conversation_id', 'Test User', 'test_id') == \
        'No history!'

    app._add_user_history(jenkins_id, 'job_name_1')
    app._add_user_history(jenkins_id, 'job_name_2')

    assert app.handle_message('rebuild: 1'.format(jenkins_id), 'message', 'conversation_id', 'Test User', 'test_id') == \
        app.UNKNOWN_USER_TOKEN_MSG.format('jenkins/')

    token = 'token_1'
    assert app.handle_message('jenkins_token: {}'.format(token), 'message', 'conversation_id', 'Test User', 'test_id') == \
        'Token registered'

    with patch('skype_bot.jenkins_jobs.rebuild_job', return_value=200):
        assert app.handle_message('rebuild: 1'.format(jenkins_id), 'message', 'conversation_id', 'Test User', 'test_id') == \
            'Build requested: <a href="jenkins/job/job_name_2">job_name_2</a>'
