#!/usr/bin/env python
"""Capture playbook result and send to Jenkins or the message bus.

Currently the script is deliverying message to Jenkins since the 
message bus UMB is not on production until some time Oct 2016. 
To enable the functionality of deliverying message to UMB,
one need to change the global variable USE_UMB to True.

Also grabs information like the ServiceNow ticket URL from playbook
variables. Can be included with a role and enabled/disabled via
playbook variable `report_to_messagebus`, which can be specified as an
extra variable, in a role, or elsewhere.

"""

# NOTES: if sending message to UMB, need to install the proton lib first 

# NOTES: Variable file contains the necessary information for triggering the
# jenkins job in a local host. When swithing the environment, the user or the
# jenkins project, the variable file will need to be updated.

from __future__ import absolute_import, division, print_function, unicode_literals

import contextlib
import functools
import json
import os
import re
import requests
import shutil
import sys
import tempfile
import time

try:
    import cStringIO as StringIO
except:
    import StringIO
    
from ansible.utils.display import Display
from ansible.plugins.callback.default import CallbackModule

USE_UMB = False
TICKET_DEBUG_REGEX = 'TICKET:(.+)'


@contextlib.contextmanager
def capture(buffer):
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = buffer
    sys.stderr = buffer
    yield
    sys.stdout = old_stdout
    sys.stderr = old_stderr


class CaptureDisplay(Display):
    """Capture plugin output to stdout and stderr."""
    def __init__(self, *args, **kwargs):
        super(CaptureDisplay, self).__init__(*args, **kwargs)
        self.output = StringIO.StringIO()

    def display(self, *args, **kwargs):
        with capture(self.output):
            super(CaptureDisplay, self).display(*args, **kwargs)

    def get_output(self):
        return self.output.getvalue()


try:
    import proton
    from proton import Message, SSLDomain
    from proton.handlers import MessagingHandler
    from proton.reactor import Container

    class Sender(MessagingHandler):
        def __init__(self, server, topic, certificate, key, message):
            super(Sender, self).__init__()
            self.server = server
            self.topic = topic
            self.certificate = certificate
            self.key = key
            self.message = message

        def on_start(self, event):
            # Write the UMB cert and key out to disk but immediately delete
            # them once the connection has been established. There may be a
            # better way to do this if we can be assured of a secure directory.
            temp_dir = tempfile.mkdtemp()
            mktemp = functools.partial(tempfile.NamedTemporaryFile,
                                       delete=False,
                                       dir=temp_dir)
            
            try:
                temp_cert = mktemp()
                temp_key = mktemp()
                temp_cert.write(self.certificate)
                temp_key.write(self.key)
                temp_cert.close()
                temp_key.close()
                
                domain = SSLDomain(SSLDomain.MODE_CLIENT)
                domain.set_credentials(temp_cert.name, temp_key.name, b'')
                conn = event.container.connect(self.server, ssl_domain=domain)
            finally:
                shutil.rmtree(temp_dir)
                    
            event.container.create_sender(conn, "topic://" + self.topic)
        

        def on_sendable(self, event):
            message = Message(body=json.dumps(self.message))
            # We have to manually set this - Proton won't do it for us
            message.creation_time = time.time()
            print(message)
            event.sender.send(message)
            event.sender.close()
                                              

        def on_settled(self, event):
            event.connection.close()

                
    PROTON_AVAILABLE = True
except ImportError:
    PROTON_AVAILABLE = False


class CallbackModule(CallbackModule):
    CALLBACK_NAME = 'report_status'
    CALLBACK_TYPE = 'selfservice'

    SUCCESS_STATUS = 'SUCCESS'
    FAILURE_STATUS = 'FAILURE'

    def __init__(self, *args, **kwargs):
        super(CallbackModule, self).__init__(*args, **kwargs)
        self._display = CaptureDisplay(verbosity=4)
        self.status = self.SUCCESS_STATUS
        self.ticket_msgs = []

    def v2_runner_on_ok(self, result):
        super(CallbackModule, self).v2_runner_on_ok(result)
        # Any debug message starting with 'TICKET:' will be considered data
        # for reporting back to the user.

        print("testtesttest")
        print(result._result)
        print("hee")
        print(result)
        print("_______")
        print(result._task.get_vars())
        print("~~")
        print(result._task.get('msg'))
        print("where")
        print(result._result.get('_ansible_delegated_vars', None))
        print("hhhh")
        
        if result._task.action == 'debug':
            msg = result._task.args.get('msg')
            if msg:
                match = re.match(TICKET_DEBUG_REGEX, msg)
                if match:
                    ticket_msg = match.group(1).strip()
                    if ticket_msg:
                        self.ticket_msgs.append(ticket_msg)

    def v2_playbook_on_play_start(self, play):
        super(CallbackModule, self).v2_playbook_on_play_start(play)
        '''
        manager = play.get_variable_manager()
        variables = manager.get_vars(play.get_loader(), play=play)

        self.enabled = variables.get('report_to_messagebus', False)
        self.ticket = variables.get('service_now_url')
        self.messagebus = variables.get('message_bus')
        self.messagebus_topic = variables.get('message_bus_topic')
        self.messagebus_crt = variables.get('message_bus_cert')
        self.messagebus_key = variables.get('message_bus_key')

        self.jenkins_env = variables.get('jenkins_environment')
        if self.jenkins_env == 'test':
            self.jenkins_url_addr = variables.get('jenkins_test_url')
            self.jenkins_usrname = variables.get('jenkins_test_usr')
            self.jenkins_api_token = variables.get('jenkins_test_usr_api_token')
        elif self.jenkins_env == 'stage':
            self.jenkins_url_addr = variables.get('jenkins_stage_url')
            self.jenkins_usrname = variables.get('jenkins_stage_usr')
            self.jenkins_api_token = variables.get('jenkins_stage_usr_api_token')
        elif self.jenkins_env == 'prod':
            self.jenkins_url_addr = variables.get('jenkins_prod_url')
            self.jenkins_usrname = variables.get('jenkins_prod_usr')
            self.jenkins_api_token = variables.get('jenkins_prod_usr_api_token')
        else:
            raise ValueError('Unknown jenkins environment "{}"'.format(self.jenkins_env))'''

    def v2_runner_on_failed(self, result, ignore_errors=False):
        super(CallbackModule, self).v2_runner_on_failed(result, ignore_errors)
        if not ignore_errors:
            self.status = self.FAILURE_STATUS

    def v2_runner_on_unreachable(self, result):
        super(CallbackModule, self).v2_runner_on_unreachable(result)
        self.status = self.FAILURE_STATUS

    def v2_playbook_on_stats(self, stats):
        super(CallbackModule, self).v2_playbook_on_stats(stats)

        status_message = {
            'status': self.status,
            'job_id': os.environ.get('JOB_ID', None),
            'service_now_url': self.ticket,
            'user_data': '\n'.join(self.ticket_msgs),
            #'output': self._display.get_output(),
            'output': None,
        }
        print(status_message)

        if USE_UMB:
            if not PROTON_AVAILABLE:
                raise ImportError('qpid-proton is not installed')

            Container(Sender(
                self.messagebus, self.messagebus_topic,
                self.messagebus_crt, self.messagebus_key,
                status_message)).run()
        else:
            # The jenkins job will expect to receive all params in uppercase.
            params = {k.upper(): v for k,v in status_message.iteritems()}
            url = self.jenkins_url_addr + '/buildWithParameters'
            auth = requests.auth.HTTPBasicAuth(self.jenkins_usrname,
                                               self.jenkins_api_token)
            rsp = requests.post(url, params=params, auth=auth)

            if rsp.status_code != 201:
                raise IOError('Failed to trigger jenkins job with URL: {}. '
                              'Response code was: {}'.format(url, rsp.status_code))
