#!/usr/bin/env python
import fnmatch
import inspect
import re

from skype_bot import jenkins_jobs
from skype_bot.jenkins_jobs import get_build_test_errors, get_building_jobs, get_job_url, stop_job
from skype_bot.skype_message import SkypeMessage


#===================================================================================================
# JobsHistory
#===================================================================================================
class JobsHistory(object):


    def __init__(self, jobs_db):
        self.jobs_db = jobs_db


    def get_history(self, jenkins_id):
        if self.jobs_db is not None:
            users_history = list(self.jobs_db.find({'jenkins_id' : jenkins_id}))
            if users_history and len(users_history) == 1:
                return users_history[0]

    def get_jobs_history(self, jenkins_id):
        user_history = self.get_history(jenkins_id)
        print jenkins_id, user_history
        if user_history:
            return user_history['history']
        else:
            return []


    def add_job(self, jenkins_id, job_name):
        user_history = self.get_history(jenkins_id)
        if user_history:
            history = user_history['history']
            try:
                entry_index = history.index(job_name)
            except ValueError:
                pass
            else:
                history.pop(entry_index)

            history.insert(0, job_name)
            print('save', user_history)
            self.jobs_db.save(user_history)

        elif self.jobs_db:
            self.jobs_db.insert_one({
                'jenkins_id' : jenkins_id,
                'history' : [job_name]
            })


#===================================================================================================
# UsersBot
#===================================================================================================
class UsersBot(object):

    def __init__(self, _config):

        self.config = _config

        self.jenkins_config = _config.get('jenkins', {'url' : ''})

        self._users_data = {}

        self._users_db = None
        self._users_history = None
        mongodb_config = _config.get('mongodb')
        if mongodb_config:
            self._setup_mongo_db(mongodb_config.get('url'))

        self.register_handlers()


    # JenkinsDB ------------------------------------------------------------------------------------
    def _get_jenkins_db(self, mongodb_url):
        if mongodb_url is not None:
            from pymongo import MongoClient

            self.mongo_client = client = MongoClient(mongodb_url)
            return client.jenkins


    def _setup_mongo_db(self, mongodb_url):
        jenkins_db = self._get_jenkins_db(mongodb_url)
        print('jenkins_db', jenkins_db)
        if jenkins_db is not None:
            self._users_db = jenkins_db.skype_users
            self._users_history = JobsHistory(jenkins_db.users_jobs)


    def _get_users_db(self):
        return self._users_db

    def _get_user_history(self, jenkins_id):
        if self._users_history:
            return self._users_history.get_jobs_history(jenkins_id)
        else:
            return []


    def _add_user_history(self, jenkins_id, job_name):
        if self._users_history:
            return self._users_history.add_job(jenkins_id, job_name)

    def _setup_users(self):
        users_db = self._get_users_db()
        if users_db:
            for user_info in users_db.find():
                self._known_contacts.append(user_info)

    # Users Data -----------------------------------------------------------------------------------
    def _add_user_data(self, skype_id, name, data):
        try:
            user_data = self._users_data[skype_id]
        except:
            user_data = self._users_data[skype_id] = {}

        user_data[name] = data

    def _get_user_data(self, skype_id, name):
        try:
            user_data = self._users_data[skype_id]
        except:
            return None

        return user_data.get(name)


    # Jenkins --------------------------------------------------------------------------------------
    def iter_users_info(self):
        for user_info in self._users_db.find():
            yield user_info

    def get_jenkins_conversation_id(self, jenkins_id):
        user_info = self._users_db.find_one({'jenkins_id' : jenkins_id})
        if user_info:
            return user_info['conversation_id']
        else:
            return None

        for user_info in self._known_contacts:
            if user_info['jenkins_id'] == jenkins_id:
                return user_info['conversation_id']

    def get_contact_info(self, skype_id):
        return self._users_db.find_one({'skype_id' : skype_id})

    def get_contact_jenkins_id(self, skype_id):
        user_info = self._users_db.find_one({'skype_id' : skype_id})
        if user_info:
            return user_info['jenkins_id']
        else:
            return None

    UNKNOWN_USER_TOKEN_MSG = "For you to become a big boy. I need your jenkins token" \
        "\nPlease obtain you token from: http://your.jenkins.server/me/configure" \
        "and get me your API Token." \
        "\nRegister with: jenkins_token: your_api_token"


    def get_contact_jenkins_config(self, skype_id):
        '''
        Jenkins, URL, user and token
        '''
        user_info = self.get_contact_info(skype_id)
        if user_info is None:
            return self.UNKNOWN_USER_MSG

        jenkins_token = user_info.get('jenkins_token')
        if jenkins_token is None:
            return self.UNKNOWN_USER_TOKEN_MSG

        return {
            'url' : self.jenkins_config['url'],
            'user' : user_info['jenkins_id'],
            'token' : user_info['jenkins_token'],
        }


    def _register_jenkins_user(self, jenkins_id, conversation_id, skype_name, skype_id):
        contact_info = self.get_contact_info(skype_id)
        new_contact_info = {
            'jenkins_id' : jenkins_id,
            'skype_id' : skype_id,
            'skype_name' : skype_name,
            'conversation_id' : conversation_id
        }
        if contact_info is None:
            print 'new_contact_info' , new_contact_info
#             self._known_contacts.append(new_contact_info)
            users_db = self._get_users_db()
            if users_db is not None:
                print ' Insert:', users_db.insert(new_contact_info)

        else:
            contact_info.update(new_contact_info)
            print 'updating contact_info' , contact_info
            users_db = self._get_users_db()
            users_db.save(contact_info)


    def _register_jenkins_token(self, jenkins_token, conversation_id, skype_name, skype_id):
        contact_info = self.get_contact_info(skype_id)
        if contact_info is None:
            return self.UNKNOWN_USER_MSG

        else:
            contact_info['jenkins_token'] = jenkins_token
            users_db = self._get_users_db()
            users_db.save(contact_info)
            return 'Token registered'


    def _build_job_message(self, caption, job_name, build_info):
        from datetime import datetime

        job_link = SkypeMessage.link(get_job_url(job_name, self.jenkins_config), job_name)

        message = '(skate) <b>{}:</b> {}'.format(caption, job_link)

        start_millis = int(build_info['timestamp'])
        start_time = datetime.fromtimestamp(start_millis / 1000)
        message += '\nStarted: <b>{}</b>'.format(start_time)
        message += '\nBuilding On: <b>{}</b>'.format(build_info['builtOn'])

        return message


    def get_job_link_message(self, job_name):
        return SkypeMessage.link(get_job_url(job_name, self.jenkins_config), job_name)


    def get_started_message(self, build_info):
        '''
        :param build_info:
        '''
        from datetime import datetime

        jenkins_id = build_info['userId']
        conversation_id = self.get_jenkins_conversation_id(jenkins_id)
        if conversation_id is None:
            return None, None

        job_name = build_info['job_name']
        self._add_user_history(jenkins_id, job_name)

        job_link = SkypeMessage.link(get_job_url(job_name, self.jenkins_config), job_name)

        message = '(skate) <b>Started:</b> {}'.format(job_link)

        start_millis = int(build_info['timestamp'])
        start_time = datetime.fromtimestamp(start_millis / 1000)
        message += '\nStarted: <b>{}</b>'.format(start_time)
        message += '\nBuilt On: <b>{}</b>'.format(build_info['builtOn'])
        return conversation_id, message


    def get_completed_message(self, build_info):
        '''

        :param build_info:
        '''
        from datetime import datetime

        user_id = build_info['userId']
        conversation_id = self.get_jenkins_conversation_id(user_id)
        if conversation_id is None:
            return None, None

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

        build_number = build_info.get('number')
        if job_result == 'FAILURE' and build_number is not None:
            test_errors = get_build_test_errors(job_name, int(build_number), self.jenkins_config)
            message += '\n<b>Errors:</b>'
            if len(test_errors) == 0:
                message += ' Unable to collect'
            else:
                message += ' {}'.format(len(test_errors))

            i = 0;
            for error in test_errors:
                message += '   <b>{}</b>\n'.format(error['name'])
                i += 1
                if i >= 10:
                    break

            if len(test_errors) > 10:
                message += '<b>There is more</b>\n'


        return conversation_id, message


    REGISTER_USER_MSG = "Thanks. You are registered as: '{}'"
    UNKNOWN_USER_MSG = "Sorry. I don't know you yet.\nReply with your jenkins user name in the form: jenkins_id: your_id"

    def _parse_single_text_command(self, name, message_text):
        match = re.search('{}:?\s*([^\s]+)'.format(name), message_text, re.IGNORECASE)
        if match:
            return match.group(1)

    def _parse_int_command(self, name, message_text):
        match = re.search('{}:?\s*(\d+)'.format(name), message_text, re.IGNORECASE)
        if match:
            return match.group(1)


    def _handle_new_user(self, message_text, message_type, conversation_id, sender_name, sender_id):
#         jenkins_id_match = re.search('jenkins_id:\s*([^\s]+)', message_text, re.IGNORECASE)
        jenkins_id = self._parse_single_text_command('jenkins_id', message_text)
        if jenkins_id:
            self._register_jenkins_user(jenkins_id, conversation_id, sender_name, sender_id)
            return self.REGISTER_USER_MSG.format(jenkins_id)
        else:
            return self.UNKNOWN_USER_MSG

    def jenkins_token(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Register your jenkins token
           <b>usage</b>: jenkins_token your_token
        '''
        jenkins_token = self._parse_single_text_command('jenkins_token', message_text)
        if jenkins_token is None:
            return 'Unable to get build number from message: "{}"'.format(message_text)

        return self._register_jenkins_token(jenkins_token, conversation_id, skype_name, skype_id)

    def stop(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Stops the given job index from your running list from status command
           <b>usage</b>: stop running_id
        '''
        job_number = self._parse_int_command('stop', message_text)
        if job_number is None:
            return 'Unable to get build number from message: "{}"'.format(message_text)

        jenkins_id = self.get_contact_jenkins_id(skype_id)
        if jenkins_id is None:
            return 'No jobs, since you are not registered! ;)'

        jobs_list = self._get_user_data(skype_id, self.USER_RUNNING_JOBS)
        if jobs_list is None or len(jobs_list) == 0:
            return 'No running jobs. Update this list from status command'

        job_number = int(job_number) - 1
        if job_number < 0 or job_number > len(jobs_list):
            return 'Invalid history number: {}'.format(job_number)

        job_name = jobs_list[job_number]
        return_code, message = stop_job(job_name, self.jenkins_config)
        if return_code == 0:
            return 'Stop requested: {}'.format(self.get_job_link_message(job_name))
        else:
            return 'Stop request failed: {}'.format(message)


    def rebuild(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Rebuilds the given job index from your <b>history</b>.
        If the job is parametrized, the same parameters from last run will be used.
           <b>usage</b>: rebuild history_id
        '''
        history_number = self._parse_int_command('rebuild', message_text)
        if history_number is None:
            return 'Unable to get build number from message: "{}"'.format(message_text)

        jenkins_id = self.get_contact_jenkins_id(skype_id)
        if jenkins_id is None:
            return 'No history, since you are not registered! ;)'

        history = self._get_user_history(jenkins_id)
        if history is None or len(history) == 0:
            return 'No history!'

        history_number = int(history_number) - 1
        if history_number < 0 or history_number > len(history):
            return 'Invalid history number: {}'.format(history_number)

        jenkins_config = self.get_contact_jenkins_config(skype_id)
        if type(jenkins_config) == str:
            return jenkins_config

        job_name = history[history_number]
        jenkins_jobs.rebuild_job(job_name, jenkins_config)
        return 'Build requested: {}'.format(self.get_job_link_message(job_name))


    def history(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Return a list of your last 5 jobs
           <b>usage</b>: history
        '''
        jenkins_id = self.get_contact_jenkins_id(skype_id)
        if jenkins_id is None:
            return 'No history, since you are not registered! ;)'

        history = self._get_user_history(jenkins_id)
        if history is None or len(history) == 0:
            return 'No history!'

        msg = 'Last build jobs:'
        for i, job_name in enumerate(history):
            msg += '\n  - {}: {}'.format(i+1, self.get_job_link_message(job_name))
        return msg


    USER_JOBS_LIST = 'jobs_find'

    def find(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Find jobs with a given pattern
           <b>usage</b>: find rocky30*5050*linux64
        '''
        self._add_user_data(skype_id, self.USER_JOBS_LIST, None)

        pattern = self._parse_single_text_command('find', message_text)
        if pattern is None:
            return 'No pattern from message: {}'.format(message_text)

        jobs_list = jenkins_jobs.list_jobs(self.jenkins_config)
        if len(jobs_list) == 0:
            return 'No jobs found!'

        filtered_list = []
        for job_name in jobs_list:
            if fnmatch.fnmatch(job_name, pattern):
                filtered_list.append(job_name)

        if len(filtered_list) == 0:
            return 'Found no jobs matching: {}'.format(pattern)

        message = '<b>Found jobs:</b>'
        for i, job_name in enumerate(filtered_list[:10]):
            if fnmatch.fnmatch(job_name, pattern):
                message += '\n{} - {}'.format(i+1, self.get_job_link_message(job_name))

        if len(filtered_list[:-10]) > 10:
            message += '<b>\n...</b>'

        self._add_user_data(skype_id, self.USER_JOBS_LIST, filtered_list)
        return message

    def build(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Builds a previously listed job from <b>find</b> command
           <b>usage</b>: build: job_list_number
        '''
        job_number = self._parse_int_command('build', message_text)
        if job_number is None:
            return 'No build number from message: {}'.format(message_text)

        jobs_list = self._get_user_data(skype_id, self.USER_JOBS_LIST)
        if jobs_list is None:
            return 'No listed jobs! Create your list using command find:...'

        job_number = int(job_number) - 1
        if job_number >= len(jobs_list):
            return 'Invalid job number {}, list contains only: {} items'.format(job_number, len(jobs_list))

        jenkins_config = self.get_contact_jenkins_config(skype_id)
        if type(jenkins_config) == str:
            return jenkins_config

        job_name = jobs_list[job_number]
        return_code, message = jenkins_jobs.build_job(job_name, jenkins_config)
        if return_code == 0:
            return 'Build requested: {}'.format(self.get_job_link_message(job_name))
        else:
            return 'Build request failed: {}'.format(message)

    USER_RUNNING_JOBS = 'running_jobs'

    def status(self, message_text, message_type, conversation_id, skype_name, skype_id):
        '''
        Return current running jobs status started by you!
           <b>usage</b>: status
        '''
        self._add_user_data(skype_id, self.USER_RUNNING_JOBS, None)

        building_jobs = get_building_jobs(self.jenkins_config)
        if len(building_jobs) == 0:
            return ' There is not jobs running!'

        msg = 'There are {} jobs running!'.format(len(building_jobs))

        jenkins_id = self.get_contact_jenkins_id(skype_id)
        user_jobs = []
        for job_name, job_info in building_jobs.items():
            if job_info.get('userId') == jenkins_id:
                user_jobs.append(job_name)

        if len(user_jobs) == 0:
            msg += '\nYou have none jobs running!'

        else:
            msg += '\nYou have {} jobs running:'.format(len(user_jobs))

            for i, job_name in enumerate(user_jobs):
                msg += ' \n{} - '.format(i+1) + self._build_job_message('Running', job_name, building_jobs[job_name])

            self._add_user_data(skype_id, self.USER_RUNNING_JOBS, user_jobs)

        return msg

    def help(self, message_text, message_type, conversation_id, sender_name, sender_id):
        msg = 'Commands:'
        for handler_function in self.message_handlers:
            if handler_function != self.help:
                msg += '\n(ninja) <b>{}</b>'.format(handler_function.__name__)
                msg += '\n' + inspect.getdoc(handler_function)

        return msg

    def register_handlers(self):
        self.message_handlers = []

        self.message_handlers.append(self.help)
        self.message_handlers.append(self.status)
        self.message_handlers.append(self.history)
        self.message_handlers.append(self.rebuild)
        self.message_handlers.append(self.find)
        self.message_handlers.append(self.build)
        self.message_handlers.append(self.stop)
        self.message_handlers.append(self.jenkins_token)


    def iter_handlers(self):
        for handler_function in self.message_handlers:
            yield re.compile('{}'.format(handler_function.__name__)), handler_function

    UNKNOWN_CMD = 'Unknown command: {}'

    def handle_message(self, message_text, message_type, conversation_id, sender_name, sender_id):
        # Pre-process message, to remove edited data
        # Skype send an edit message as: "Edited previous message: your_previous_message<e_m ts="1507311221
        edited_message_match = re.match('Edited\sprevious\smessage:\s(.+?)(?=<e_m)', message_text)
        if edited_message_match:
            message_text = edited_message_match.group(1)
        
        jenkins_id = self.get_contact_jenkins_id(sender_id)
        if jenkins_id is None:
            return self._handle_new_user(message_text, message_type, conversation_id, sender_name, sender_id)

        for regex, message_handler in self.iter_handlers():
            if regex.match(message_text):
                return message_handler(message_text, message_type, conversation_id, sender_name, sender_id)

        return self.UNKNOWN_CMD.format(message_text)