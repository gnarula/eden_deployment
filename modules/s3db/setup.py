# -*- coding: utf-8 -*-

""" Sahana Eden Setup Model

@copyright: 2011-2014 (c) Sahana Software Foundation
@license: MIT

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""
__all__ = ["S3DeployModel",
           "setup_create_yaml_file",
           "setup_create_playbook",
           "setup_log",
           ]

from ..s3 import *
from gluon import *
import ansible.playbook
import ansible.inventory
from ansible import callbacks
from ansible import utils
import os
import socket
import time
import yaml


TIME_FORMAT = "%b %d %Y %H:%M:%S"
MSG_FORMAT = "%(now)s - %(category)s - %(data)s\n\n"


class S3DeployModel(S3Model):

    names = ["setup_deploy", ]

    def model(self):

        T = current.T
        s3 = current.response.s3

        tablename = "setup_deploy"

        self.define_table(tablename,
                          Field("host",
                                label=T("Server IP"),
                                required=True,
                                ),
                          Field("sitename",
                                label=T("Site URL"),
                                required=True,
                                ),
                          Field("hostname",
                                label="Hostname",
                                required=True,
                                ),
                          Field("web_server",
                                label=T("Web Server"),
                                required=True,
                                requires=IS_IN_SET(["apache", "cherokee"]),
                                ),
                          Field("database_type",
                                label=T("Database"),
                                required=True,
                                requires=IS_IN_SET(["mysql", "postgresql"]),
                                ),
                          Field("password", "password",
                                required=True,
                                readable=False,
                                label=T("Database Password"),
                                ),
                          Field("repo",
                                label=T("Eden Repo git URL"),
                                # TODO: Add more advanced options
                                default="https://github.com/flavour/eden",
                                ),
                          Field("template",
                                label=T("Template"),
                                default="default",
                                ),
                          Field("scheduler_id", "reference scheduler_task",
                                writable=False,
                                unique=True
                                ),
                          Field("type",
                                writable=False,
                                readable=False,
                                required=True,
                                ),
                          *s3_meta_fields()
                          )

        # CRUD Strings
        s3.crud_strings[tablename] = Storage(
            title_create=T("Add Deployment"),
            title_list=T("View Deployments"),
            title_update=T("Edit Deployment"),
            subtitle_create=T("Add Deployment"),
            label_create_button=T("Add Deployment"),
            label_list_button=T("View Deployments"),
            label_delete_button=T("Delete Deployment"),
            msg_record_created=T("Deployment Created"),
            msg_record_modified=T("Deployment updated"),
            msg_record_deleted=T("Deployment deleted"),
            msg_list_empty=T("No Deployment Saved yet")
        )

        self.configure(tablename,
                       editable=False,
                       deletable=False,
                       insertable=True,
                       listadd=True
                       )

        return dict()

    def defaults(self):
        """
        Safe defaults for model-global names in case module is disabled
        """
        return dict()


def setup_create_yaml_file(host, password, web_server, database_type,
                           local=False, hostname=None,
                           template="default", sitename=None):

    roles_path = "../private/playbook/roles/"

    deployment = [
        {
            "hosts": host,
            "connection": "local",
            "sudo": True,
            "vars": {
                "password": password,
                "template": template,
                "web_server": web_server
            },
            "roles": [
                "%scommon" % roles_path,
                "%s%s" % (roles_path, web_server),
                "%s%s" % (roles_path, database_type),
                "%sconfigure" % roles_path,
            ]
        }
    ]

    if web_server == "cherokee":
        deployment[0]["roles"].insert(2, "%suwsgi" % roles_path)

    if local:
        deployment[0]["connection"] = "local"

    if not hostname:
        deployment[0]["vars"]["hostname"] = socket.gethostname()
    else:
        deployment[0]["vars"]["hostname"] = hostname

    if not sitename:
        deployment[0]["vars"]["sitename"] = \
            current.deployment_settings.get_base_public_url()
    else:
        deployment[0]["vars"]["sitename"] = sitename

    directory = os.path.join(current.request.folder, "yaml")
    name = "deployment_%d" % int(time.time())
    file_path = os.path.join(directory, "%s.yml" % name)

    if not os.path.isdir(directory):
        os.mkdir(directory)
    with open(file_path, "w") as yaml_file:
        yaml_file.write(yaml.dump(deployment, default_flow_style=False))

    row = current.s3task.schedule_task(
        name,
        vars={"playbook": file_path},
        function_name="deploy_locally",
        repeats=1,
        timeout=3600,
        sync_output=300
    )

    return row


def setup_create_playbook(playbook, hosts):

    inventory = ansible.inventory.Inventory(hosts)
    #playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
    stats = callbacks.AggregateStats()
    # runner_cb = callbacks.PlaybookRunnerCallbacks(
    #     stats, verbose=utils.VERBOSITY)

    head, tail = os.path.split(playbook)
    deployment_name = tail.rsplit(".")[0]

    cb = CallbackModule(deployment_name)

    pb = ansible.playbook.PlayBook(
        playbook=playbook,
        inventory=inventory,
        callbacks=cb,
        runner_callbacks=cb,
        stats=stats
    )

    return pb


def setup_log(filename, category, data):
    if type(data) == dict:
        if 'verbose_override' in data:
            # avoid logging extraneous data from facts
            data = 'omitted'
        else:
            data = data.copy()
            invocation = data.pop('invocation', None)
            data = json.dumps(data)
            if invocation is not None:
                data = json.dumps(invocation) + " => %s " % data

    path = os.path.join(current.request.folder, "yaml", "%s.log" % filename)
    now = time.strftime(TIME_FORMAT, time.localtime())
    fd = open(path, "a")
    fd.write(MSG_FORMAT % dict(now=now, category=category, data=data))
    fd.close()


class CallbackModule(object):

    """
    logs playbook results, per deployment in eden/yaml
    """
    def __init__(self, filename):
        self.filename = filename

    def on_any(self, *args, **kwargs):
        pass

    def on_failed(self, host, res, ignore_errors=False):
        setup_log(self.filename, 'FAILED', res)

    def on_ok(self, host, res):
        setup_log(self.filename, 'OK', res)

    def on_error(self, host, msg):
        setup_log(self.filename, 'ERROR', msg)

    def on_skipped(self, host, item=None):
        setup_log(self.filename, 'SKIPPED', '...')

    def on_unreachable(self, host, res):
        setup_log(self.filename, 'UNREACHABLE', res)

    def on_no_hosts(self):
        pass

    def on_async_poll(self, host, res, jid, clock):
        pass

    def on_async_ok(self, host, res, jid):
        pass

    def on_async_failed(self, host, res, jid):
        setup_log(self.filename, 'ASYNC_FAILED', res)

    def on_start(self):
        pass

    def on_notify(self, host, handler):
        pass

    def on_no_hosts_matched(self):
        pass

    def on_no_hosts_remaining(self):
        pass

    def on_task_start(self, name, is_conditional):
        pass

    def on_vars_prompt(self, varname, private=True, prompt=None,
                                encrypt=None, confirm=False, salt_size=None,
                                salt=None, default=None):
        pass

    def on_setup(self):
        pass

    def on_import_for_host(self, host, imported_file):
        setup_log(self.filename, 'IMPORTED', imported_file)

    def on_not_import_for_host(self, host, missing_file):
        setup_log(self.filename, 'NOTIMPORTED', missing_file)

    def on_play_start(self, pattern):
        pass

    def on_stats(self, stats):
        pass
