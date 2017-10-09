#!/usr/bin/env python
import json
import logging

import requests

from flask import Flask, request
from skype_bot.config import get_config
from skype_bot.users_bot import UsersBot


#===================================================================================================
# Bot
#===================================================================================================
class Bot(Flask):

    api_url = 'https://api.skype.net'

    bot_endpoint = '/api/messages'

    # default port value, can be overriden in config
    bot_port = 3978
    # default hostname, can be overriden in config
    bot_host = 'localhost'


    def __init__(self, _config=None, config_filename=None):
        super(Bot, self).__init__(__name__)

        config = get_config(_config, config_filename)

        self.bot_name = config['bot_name']
        self.bot_password = config['bot_password']
        self.bot_app_id = config['bot_app_id']
        if 'port' in config:
            self.bot_port = config['port']
        if 'hostname' in config:
            self.bot_host = config['hostname']
        if 'logging_level' in config:
            logging.basicConfig(level=config['logging_level'],
                                format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s')

        self.auth = self._get_auth(self.bot_app_id, self.bot_password)

        self.users_bot = UsersBot(config)

        self.add_url_rule('/api/messages', view_func=self.api_messages, methods=['POST'])
        self.add_url_rule('/job/started', view_func=self.job_started, methods=['GET'])
        self.add_url_rule('/job/completed', view_func=self.job_completed, methods=['GET'])


    def _get_auth(self, app_id, app_password):
        from auth import Auth
        return Auth(app_id, app_password)

    def job_started(self, *args):
        '''
        ?event=${event.name}&duration=${run.duration}&timestamp=${run.timestamp.timeInMillis}&number=${run.number}&userId=${run.getCause(hudson.model.Cause.UserIdCause).getUserId()}&job_name=${run.project.name}&result=${run.result}&url=${run.getUrl()}

        e.g.: ?event=jenkins.job.started
            &timestamp=1507137597368
            &number=1
            &userId=tnobrega
            &job_name=etk-fb-ETK-ROCKY-v4.0-merge-master-win64-35
            &builtOn=dev-windows10-win-sv01-ci02
            &url=job/etk-fb-ETK-ROCKY-v4.0-merge-master-win64-35/1/
        '''
        print('Started:', request.args)
        conversation_id, message = self.users_bot.get_started_message(request.args)
        self.send(conversation_id, message)
        return ''

    def job_completed(self, *args):
        '''
        ?event=${event.name}&duration=${run.duration}&timestamp=${run.timestamp.timeInMillis}&number=${run.number}&userId=${run.getCause(hudson.model.Cause.UserIdCause).getUserId()}&job_name=${run.project.name}&result=${run.result}&url=${run.getUrl()}

        e.g.: ?event=jenkins.job.completed
            &duration=1940528
            &timestamp=1507139746158
            &number=3
            &userId=tnobrega
            &job_name=rocky30-fb-ETK-ROCKY-v4.0-merge-master-linux64
            &result=FAILURE
            &url=job/rocky30-fb-ETK-ROCKY-v4.0-merge-master-linux64/3/
        '''
        print('job_completed', request.args)
        conversation_id, message = self.users_bot.get_completed_message(request.args)
        self.send(conversation_id, message)
        return ''


    def api_messages(self):
        """
        Function accepts incoming requests from MS server, parses it and passes to custom handlers.
        Request format example:
            {u'recipient': {u'id': u'28:4f7d6c06-bb77-4f4a-b33c-51485be54c67', u'name': u'duxa-bot'}, u'from': {u'id': u'29:1dHAIi7JbBz8fGKackEJ6fT2Fs5Ov_IsOp1T5tlm1xQE', u'name': u'Andrey Mironenko'}, u'timestamp': u'2016-11-05T18:31:00.795Z', u'channelId': u'skype', u'conversation': {u'id': u'29:1dHAIi7JbBz8fGKackEJ6fT2Fs5Ov_IsOp1T5tlm1xQE'}, u'serviceUrl': u'https://skype.botframework.com', u'action': u'add', u'type': u'contactRelationUpdate', u'id': u'6xsmnHhoMQM'}
            {u'recipient': {u'id': u'28:4f7d6c06-bb77-4f4a-b33c-51485be54c67', u'name': u'duxa-bot'}, u'from': {u'id': u'29:1dHAIi7JbBz8fGKackEJ6fT2Fs5Ov_IsOp1T5tlm1xQE', u'name': u'Andrey Mironenko'}, u'timestamp': u'2016-11-05T18:08:41.59Z', u'channelId': u'skype', u'conversation': {u'id': u'29:1dHAIi7JbBz8fGKackEJ6fT2Fs5Ov_IsOp1T5tlm1xQE'}, u'serviceUrl': u'https://skype.botframework.com', u'action': u'remove', u'type': u'contactRelationUpdate', u'id': u'6Txlawp2K7d'}

        :return: empty response
        """
        self.logger.debug(request.headers)
        if not self.auth.verify_request(request.headers['Authorization']):
            self.logger.info('Unverified request. Ignoring.')
            return ''

        request_json = request.json
        request_type = request_json['type']
        conversation_id = request_json['conversation']['id']

        # answer to MS server ping request
        if request_type == 'ping':
            self.send(conversation_id=conversation_id, message='')
            self.logger.debug('Ping request received.')
            return ''

        sender_name = request_json['from']['name']
        sender_id = request_json['from']['id']

        # handle relation update request
        if request_type == 'contactRelationUpdate':
            action = request_json['action']
            # call user handler if it's set
            self.logger.debug('contactRelationUpdate: sender: {}, action: {}'.format(sender_name, action))
            return ''

        # all other requests
        self.logger.debug(request.json)
        message = request_json['text']

        return self._handle_delivered_message(message, request_type, conversation_id, sender_name, sender_id)


    def _handle_delivered_message(self, message, request_type, conversation_id, sender_name, sender_id):
        try:
            answer = self.users_bot.handle_message(message, request_type, conversation_id, sender_name, sender_id)
        except Exception as e:
            self.logger.exception(e)
            raise Exception(e)

        try:
            self.send(conversation_id=conversation_id, message=answer)
        except Exception as e:
            self.logger.exception(e)
            raise Exception(e)

        return ''


    # Messages -------------------------------------------------------------------------------------
    def get_bearer_token(self):
        return self.auth.get_bearer_token()

    def send(self, conversation_id, message):
        """
        Function sends a message to a conversation identified by conversation_id
        :param conversation_id:
        :param message: message string
        :return: HTTP response status
        """
        send_url = '/v3/conversations/{}/activities'
        data = {'text': message,
                'type': 'message/text',
                }
        headers = {'Authorization': 'Bearer ' + self.get_bearer_token()}
        post_url = (self.api_url + send_url).format(conversation_id)
        try :
            result = requests.post(url=post_url, data=json.dumps(data), headers=headers)
            return result.status_code
        except Exception as e:
            self.logger.exception(e)
            raise Exception(e)

    def run(self, port=None, host=None):
        super(Bot, self).run(debug=True, port=self.bot_port, host=self.bot_host)
