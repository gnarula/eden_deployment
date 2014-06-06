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
            "sudo": "yes",
            "vars": {
                "password": password,
                "template": template,
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
    playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
    stats = callbacks.AggregateStats()
    runner_cb = callbacks.PlaybookRunnerCallbacks(
        stats, verbose=utils.VERBOSITY)

    pb = ansible.playbook.PlayBook(
        playbook=playbook,
        inventory=inventory,
        callbacks=playbook_cb,
        runner_callbacks=runner_cb,
        stats=stats
    )

    return pb
