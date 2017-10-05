#!/usr/bin/env python
import json
import logging
import os
import re
import inspect

import requests

from auth import Auth
from flask import Flask, request
from skype_bot.jenkins_jobs import get_job_url
from skype_bot.skype_message import SkypeMessage


class Bot(Flask):

    api_url = 'https://api.skype.net'

    bot_endpoint = '/api/messages'

    # default port value, can be overriden in config
    bot_port = 3978
    # default hostname, can be overriden in config
    bot_host = 'localhost'


    def __init__(self, _config=None, config_filename=None):
        super(Bot, self).__init__(__name__)

        config = self.get_config(_config, config_filename)

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
        
        self.auth = Auth(self.bot_app_id, self.bot_password)

        self.default_handler = None
        self.relation_update_handler = None
        self.add_to_contactlist_handler = None
        self.remove_from_contactlist_handler = None

        self._known_contacts = []
        self.jenkins_config = config.get('jenkins', {'url' : ''})
        self.register_handlers()
        
        self.mongodb_url = None
        self._users_db = None
        mongodb_config = config.get('mongodb')
        if mongodb_config:
            self.mongodb_url = mongodb_config.get('url')
            self._setup_users()

        self.add_url_rule('/api/messages', view_func=self.api_messages, methods=['POST'])
        self.add_url_rule('/job/started', view_func=self.job_started, methods=['GET'])
        self.add_url_rule('/job/completed', view_func=self.job_completed, methods=['GET'])

    # Bot ------------------------------------------------------------------------------------------
    def get_config(self, config, config_location):
        import yaml

        if config is not None:
            return config

        if config_location is None:
            config_location = '{}/config.yaml'.format(os.getcwd())
        try:
            with open(config_location, 'r') as stream:
                try:
                    return yaml.load(stream)
                except yaml.YAMLError:
                    raise(Exception('There was a error parsing the config.yaml YAML file.'))
        except:
            self.logger.warning('There was no YAML file found. \
                                 If you have a config.yaml file make sure it is in the working directory and try again.')
            return {}

    # JenkinsDB ------------------------------------------------------------------------------------
    def _get_users_db(self):
        if self.mongodb_url is not None and self._users_db is None:
            from pymongo import MongoClient
            
            client = MongoClient(self.mongodb_url)
            print(client.server_info())
        
            self._users_db =client.jenkins.skype_users
            
        return self._users_db
            
             
    
    def _setup_users(self):
        users_db = self._get_users_db()
        if users_db:
            for user_info in users_db.find():
                self._known_contacts.append(user_info)


    # Jenkins --------------------------------------------------------------------------------------
    def iter_users_info(self):
        for user_info in self._known_contacts:
            yield user_info
        
    def get_jenkins_conversation_id(self, jenkins_id):
        for user_info in self._known_contacts:
            if user_info['jenkins_id'] == jenkins_id:
                return user_info['conversation_id']
    
    def get_contact_info(self, skype_id):
        for user_info in self._known_contacts:
            if skype_id == user_info['skype_id']:
                return user_info
        
    def get_contact_jenkins_id(self, skype_id):
        for user_info in self._known_contacts:
            if skype_id == user_info['skype_id']:
                return user_info['jenkins_id']
            
    def _register_jenkins_user(self, jenkins_id, conversation_id, skype_name, skype_id):
        contact_info = self.get_contact_info(skype_id)
        new_contact_info = {
            'jenkins_id' : jenkins_id,
            'skype_id' : skype_id,
            'skype_name' : skype_name,
            'conversation_id' : conversation_id
        }
        if contact_info is None:
            print ' new_contact_info' , new_contact_info
            self._known_contacts.append(new_contact_info)
            users_db = self._get_users_db()
            if users_db is not None:
                print ' Insert:', users_db.insert(new_contact_info)
            
        else:
            contact_info.update(new_contact_info)
            users_db = self._get_users_db()
            if users_db is not None:
                db_records = list(users_db.find({'skype_id' : skype_id }))
                print db_records
                assert len(db_records) <= 1
                if len(db_records) == 1:
                    db_contact_info = db_records[0] 
                    db_contact_info.update(contact_info)
                    users_db.save(db_contact_info)
            


    def _send_start_message(self, build_info):
        '''

        :param build_info:
        '''
        from datetime import datetime

        user_id = build_info['userId']
        conversation_id = self.get_jenkins_conversation_id(user_id)
        if conversation_id is None:
            return

        job_name = build_info['job_name']
        job_link = SkypeMessage.link(get_job_url(job_name, self.jenkins_config), job_name)

        message = '(skate) <b>Started:</b> {}'.format(job_link)

        start_millis = int(build_info['timestamp'])
        start_time = datetime.fromtimestamp(start_millis / 1000)
        message += '\nStarted: <b>{}</b>'.format(start_time)
        message += '\nBuilt On: <b>{}</b>'.format(build_info['builtOn'])
        self.send(conversation_id, message)


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
        self._send_start_message(request.args)
        return ''


    def _send_completed_message(self, build_info):
        '''

        :param build_info:
        '''
        from datetime import datetime

        user_id = build_info['userId']
        conversation_id = self.get_jenkins_conversation_id(user_id)
        if conversation_id is None:
            return

        job_name = build_info['job_name']
        job_link = SkypeMessage.link(get_job_url(job_name, self.jenkins_config), job_name)

        result_emoji = {
            'SUCCESS' : ';)',
            'FAILURE' : '(no)',
            'ABORTED' : '(devil)',
        }
        job_result = build_info['result']
        message = '{} <b>Finished:</b> {}'.format(result_emoji.get(job_result, ''), job_link)

        message += '\nResult: <b>{}</b>'.format(job_result)
        message += '\nDuration: <b>{:.2f}</b>'.format(float(build_info['duration']) / 1000.0 / 60.0)

        start_millis = int(build_info['timestamp'])
        start_time = datetime.fromtimestamp(start_millis / 1000)
        message += '\nStarted: <b>{}</b>'.format(start_time)

        self.send(conversation_id, message)


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
        self._send_completed_message(request.args)
        return ''


#     @self.app.route('/api/messages', methods=['POST'])
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
            if self.relation_update_handler is not None:
                self.relation_update_handler(action=action, sender_id=sender_id, sender_name=sender_name)
            if action == 'add':
                # add to contact list
                self.logger.info('Bot was added to the contact list of {}'.format(request_json['from']['name']))
                if self.self.add_to_contactlist_handler is not None:
                    hello_message = self.add_to_contactlist_handler(sender_id=sender_id, sender_name=sender_name)
                    self.send(conversation_id=conversation_id, message=hello_message)

            if action == 'remove':
                # remove request_json['from']['name'] from contact list
                self.logger.info('Bot was removed from the contact list of {}'.format(request_json['from']['name']))
                if self.remove_from_contactlist_handler is not None:
                    self.remove_from_contactlist_handler(sender_id=sender_id, sender_name=sender_name)
            return ''

        # all other requests
        self.logger.debug(request.json)
        message = request_json['text']

        try:
            answer = self.handle_message(message, request_type, conversation_id, sender_name, sender_id)
        except Exception as e:
            self.logger.exception(e)
            raise Exception(e)

        print 'Answear:', answer
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

    REGISTER_USER_MSG = "Thanks. You are registered as: '{}'"
    UNKNOWN_USER_MSG = "Sorry. I don't know you yet.\nReply with your jenkins user name in the form: 'jenkins_id: your_id"
        
    def _handle_new_user(self, message_text, message_type, conversation_id, sender_name, sender_id):
        jenkins_id_match = re.search('jenkins_id:\s([^\s]+)', message_text)
        if jenkins_id_match:
            jenkins_id = jenkins_id_match.group(1)
            self._register_jenkins_user(jenkins_id, conversation_id, sender_name, sender_id)
            return self.REGISTER_USER_MSG.format(jenkins_id)
        else:            
            return self.UNKNOWN_USER_MSG 

    def status(self, message_text, message_type, conversation_id, sender_name, sender_id):
        '''
        Return current running jobs status started by you!
        
        usage: status
        '''
        return 'status'


    def help(self, message_text, message_type, conversation_id, sender_name, sender_id):
        msg = 'Commands:'
        for handler_function in self.message_handlers:
            if handler_function != self.help:
                msg += '\n<b>{}</b>'.format(handler_function.__name__)
                msg += '\n' + inspect.getdoc(handler_function)
                
        return msg

    def register_handlers(self):
        self.message_handlers = []
        
        self.message_handlers.append(self.help)
        self.message_handlers.append(self.status)
        
    def iter_handlers(self):
        for handler_function in self.message_handlers:
            yield re.compile('{}'.format(handler_function.__name__)), handler_function
        

    def handle_message(self, message_text, message_type, conversation_id, sender_name, sender_id):
        jenkins_id = self.get_contact_jenkins_id(sender_id)
        if jenkins_id is None:
            return self._handle_new_user(message_text, message_type, conversation_id, sender_name, sender_id)
        
        for regex, message_handler in self.iter_handlers():
            if regex.match(message_text):
                return message_handler(message_text, message_type, conversation_id, sender_name, sender_id)
        

    def set_default_message_handler(self, function):  # get_message(text, type, conversation_id)
        self.default_handler = function

    def set_relation_update_handler(self, function):
        self.relation_update_handler = function

    def run(self, port=None, host=None):
        super(Bot, self).run(debug=True, port=self.bot_port, host=self.bot_host)
