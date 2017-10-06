from __future__ import absolute_import, division, print_function, unicode_literals

import json
import urllib
from datetime import datetime

import requests

FAIL_TO_RETRIEVE = -1, 'Unable to retrieve jenkins data!'

#===================================================================================================
#
#===================================================================================================
def get_job_url(job_name, config):
    return config['url'] + 'job/' + job_name

def get_jenkins_config(config):
    return config['url'], config['user'], config['token']


def get_job_parameters(job_name, config):
    jenkins_url, user, token = get_jenkins_config(config)

    url = jenkins_url + 'job/' + job_name + \
        '/api/json?pretty=true&tree=actions[parameterDefinitions[name]]'

    print(url)
    r = requests.get(url, auth=(user, token))
    if r.status_code != 200:
        return None

    try:
        result = json.loads(r.text)
    except:
        return None

    actions = result.get('actions')
    if actions:
        for action in actions:
            parameterDefinitions = action.get('parameterDefinitions')
            if parameterDefinitions:
                params = []
                for param in parameterDefinitions:
                    params.append(param['name'])
                return params

    return []


def get_jenkins_json_request(query_url, config):
    '''
    returns None if fails to request
    '''
    jenkins_url, user, token = get_jenkins_config(config)

    url = jenkins_url + query_url

    r = requests.get(url, auth=(user, token))
    if r.status_code not in [200, 201]:
        return None

    try:
        return json.loads(r.text)
    except:
        return {}


def post_jenkins_json_request(query_url, config):
    jenkins_url, user, token = get_jenkins_config(config)

    url = jenkins_url + query_url

    r = requests.post(url, auth=(user, token))
    print(query_url, r.status_code)
    return r.status_code == 201


def get_build_parameters(job_name, build_number, config):
    if build_number is None:
        build_number = 'lastBuild'

    query = 'job/{}/{}/api/json?pretty=true&tree=actions[parameters[name,value]]'.format(job_name, build_number)

    json_result = get_jenkins_json_request(query, config)
    if json_result is None:
        return None

    if json_result:
        actions = json_result.get('actions')
        if actions:
            for action in actions:
                parameters = action.get('parameters')
                if parameters:
                    result = []
                    for parameter in parameters:
                        result.append((parameter['name'], parameter['value']))
                    return result


def get_last_build_info(job_name, config):
    '''
    return a dict like:
    {
      "_class" : "hudson.model.FreeStyleBuild",
      "building" : true,
      "number" : 14
    }
    '''
    build_number = 'lastBuild'
    query = 'job/{}/{}/api/json?pretty=true&tree=building,number'.format(job_name, build_number)

    return get_jenkins_json_request(query, config)


def list_jobs(config):
    result = get_jenkins_json_request('api/json?pretty=true&tree=jobs[fullName]', config)

    if result is None or 'jobs' not in result:
        return []

    return [job['fullName'] for job in result['jobs']]


def rebuild_job(job_name, config):
    parameters = get_build_parameters(job_name, None, config)
    if parameters is None:
        return FAIL_TO_RETRIEVE

    if len(parameters) > 0:
        post_url = 'job/{}/buildWithParameters?{}'.format(job_name, urllib.urlencode(parameters))
    else:
        post_url = 'job/{}/build'.format(job_name)

    if post_jenkins_json_request(post_url, config):
        return 0, 'Rebuild triggered: {}'.format(job_name)
    else:
        return FAIL_TO_RETRIEVE


def get_builds(job_name, config):
    result = get_jenkins_json_request('job/{}/api/json?pretty=true&tree=builds[number]'.format(job_name), config)
    if result is None or 'builds' not in result:
        return None

    return result['builds']

def build_job(job_name, config):
    builds = get_builds(job_name, config)

    if builds is None:
        return FAIL_TO_RETRIEVE

    if len(builds) == 0:
        # Jobs was never built
        params = get_job_parameters(job_name, config)
        if params is None:
            return FAIL_TO_RETRIEVE

        if len(params) == 0:
            post_url = 'job/{}/build'.format(job_name)
        else:
            post_url = 'job/{}/buildWithParameters'.format(job_name)

        if post_jenkins_json_request(post_url, config):
            return 0, 'Build triggered: {}'.format(job_name)
        else:
            return FAIL_TO_RETRIEVE

    else:
        return rebuild_job(job_name, config)


def stop_job(job_name, config):
    last_build_info = get_last_build_info(job_name, config)
    if last_build_info is None:
        return 'Job build not found'

    building = last_build_info.get('building')
    if building:
        post_url = 'job/{}/{}/stop'.format(job_name, last_build_info['number'])
        return unicode(post_jenkins_json_request(post_url, config))

    elif building == False:
        return 'Job is no longer running: ' + job_name

    return 'Unable to determine job progress: ' + job_name


def get_build_test_errors(job_name, build_number, config):
    jenkins_url, user, token = get_jenkins_config(config)

    if build_number is None:
        build_number = 'lastBuild'

    # A more complete query can be done:
    # '/{}/testReport/api/json?pretty=true&tree=suites[cases[className,name,status,errorStackTrace]]'.format(build_number)
    url = jenkins_url + 'job/' + job_name + \
        '/{}/testReport/api/json?pretty=true&tree=suites[cases[name,status]]'.format(build_number)
    r = requests.get(url, auth=(user, token))
    if r.status_code != 200:
        return []

    try:
        result = json.loads(r.text)
    except:
        return []

    try:
        cases = result['suites'][0]['cases']
    except:
        print('Failed to get cases')
        return []


    errors = []
    for case in cases:
        if case['status'] not in ['PASSED', 'SKIPPED', 'FIXED']:
            errors.append(case)

    return errors


def format_build_info(last_build):
    for key, _value in list(last_build.items()):
#         if key == 'timestamp':
#             last_build['timestamp'] = datetime.fromtimestamp(last_build['timestamp'] / 1000)
#             last_build['took'] = (datetime.now() - last_build['timestamp'])
#         elif key == 'duration':
#             last_build['duration'] = last_build['duration'] / 1000.0 / 60.0 # minutes

        if key == 'actions':
            for actions in _value:
                if 'causes' in actions:
                    for cause in actions['causes']:
                        if 'userId' in cause:
                            last_build['userId'] = cause['userId']
                            last_build['userName'] = cause['userName']
            del last_build['actions']

    return last_build


def get_job_last_build(job_name):
    url = jenkins_url + 'job/'  + job_name + '/lastBuild/api/json?pretty=true&tree=building,number,duration,builtOn,timestamp,result,estimatedDuration,actions[causes[*]]'
    r = requests.get(url, auth=(JENKINS_USER, JENKINS_TOKEN))
    if r.status_code != 200:
        print('Failed to get building jobs')
        return {}

    result = json.loads(r.text)
    return format_build_info(result)


def get_building_jobs(config):
    url = config['url'] + 'api/json?pretty=true&tree=jobs[fullName,lastBuild[building,number,duration,builtOn,timestamp,result,estimatedDuration,actions[causes[*]]]]'
    JENKINS_USER = config['user']
    JENKINS_TOKEN = config['token']
    r = requests.get(url, auth=(JENKINS_USER, JENKINS_TOKEN))

    result = json.loads(r.text)
    jobs = result['jobs']

    building_jobs = {}
    for job in jobs:
        if job['lastBuild'] is not None and job['lastBuild']['building']:
            job_build = format_build_info(job['lastBuild'])
#             job_build['fullName'] = job['fullName']
            building_jobs[job['fullName']] = job_build

    return building_jobs
