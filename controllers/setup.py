# -*- coding: utf-8 -*-

"""
Setup Tool
"""

module = request.controller
resourcename = request.function

if not settings.has_module(module):
    raise HTTP(404, body="Module disabled: %s" % module)

import os, socket, time, yaml

def index():
    """ Show the index """

    return dict()

def local_deploy():
    s3db.configure("setup_local_deploy", onvalidation=schedule_local)
    s3.actions = [
                    {
                        "label": str(current.T("View Status")),
                        "url": URL(c="setup", f="view_local", args=["[id]"]),
                        "_class": "action-btn",
                    },
                 ]

    return s3_rest_controller()

def schedule_local(form):
    """
    Schedule a deployment using s3task.
    """

    # ToDo: support repo

    deployment = [
        {
            "hosts": "127.0.0.1",
            "connection": "local",
            "sudo": "yes",
            "vars": {
                "hostname": socket.gethostname(), # get current hostname
                "password": form.vars.password,
                "template": form.vars.template,
                "sitename": current.deployment_settings.get_base_public_url(),
            },
            "roles": [
                "common",
                form.vars.web_server,
                form.vars.database_type,
                "configure",
            ]
        }
    ]

    directory = os.path.join(current.request.folder, "yaml")
    file_path = os.path.join(directory, "local.yml")
    with open(file_path, "w") as yaml_file:
        yaml_file.write(yaml.dump(deployment, default_flow_style=False))

    task = "deployment_%d" % int(time.time())
    row = current.s3task.schedule_task(
        task,
        vars={"playbook": file_path},
        function_name="deploy_locally",
        repeats=1,
        timeout=3600,
        sync_output=60
    )

    form.vars["scheduler_id"] = row.id

def view_local():
    resource = s3db.resource("setup_local_deploy")
    row = db(resource.table.id == request.args[0]).select().first()
    scheduler_obj = db(db.scheduler_task.id == row.scheduler_id).select().first()

    scheduler_run = db(db.scheduler_run.task_id == row.scheduler_id).select().first()

    return dict(status=scheduler_obj.status, output=scheduler_run.run_output, traceback=scheduler_run.traceback)