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
__all__ = ["S3LocalDeployModel",]

from gluon import *

from ..s3 import *

class S3LocalDeployModel(S3Model):

    names = ["setup_local_deploy",]

    def model(self):

        T = current.T
        s3 = current.response.s3

        tablename = "setup_local_deploy"

        self.define_table(tablename,
            Field("web_server",
                  label=T("Web Server"),
                  required=True,
                  requires=IS_IN_SET(["apache", "cherokee"])),
            Field("database_type",
                  label=T("Database"),
                  required=True,
                  requires=IS_IN_SET(["mysql", "postgresql"])),
            Field("password",
                  "password",
                  required=True,
                  readable=False,
                  label=T("Database Password")),
            Field("status",
                  "integer",
                  requires=IS_IN_SET([0,1]),
                  default=0,
                  represent=lambda status,row: 'Deployed' if status else 'Undeployed',
                  writable=False), # 0 - queued 1 - deployed
            Field("repo",
                  label=T("Eden Repo git URL"),
                  default="https://github.com/flavour/eden"), # TODO: Add more advanced options
            Field("template",
                  label=T("Template"),
                  default="default"),
            Field("scheduler_id",
                  "reference scheduler_task",
                  writable=False,
                  readable=False,
                  unique=True),
            *s3_meta_fields())

        # CRUD Strings
        s3.crud_strings[tablename] = Storage(
            title_create = T("Add Deployment"),
            title_list = T("View Deployments"),
            title_update = T("Edit Deployment"),
            subtitle_create = T("Add Deployment"),
            label_create_button = T("Add Deployment"),
            label_list_button = T("View Deployments"),
            label_delete_button = T("Delete Deployment"),
            msg_record_created = T("Deployment Created"),
            msg_record_modified = T("Deployment updated"),
            msg_record_deleted = T("Deployment deleted"),
            msg_list_empty = T("No Deployment Saved yet")
        )

        self.configure(tablename,
            editable=False,
            deletable=False,
            insertable=True,
            listadd=False
        )

        return dict()

    def defaults(self):
        """
        Safe defaults for model-global names in case module is disabled
        """
        return dict()