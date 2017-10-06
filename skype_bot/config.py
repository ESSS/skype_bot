from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import os


#===================================================================================================
# get_config
#===================================================================================================
def get_config(config=None, config_location=None):
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
        logging.warning('There was no YAML file found. \
                             If you have a config.yaml file make sure it is in the working directory and try again.')
        return {}
