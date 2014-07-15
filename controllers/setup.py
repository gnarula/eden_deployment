# -*- coding: utf-8 -*-

import os

"""
Setup Tool
"""

module = request.controller
resourcename = request.function

if not settings.has_module(module):
    raise HTTP(404, body="Module disabled: %s" % module)

def index():
    """ Show the index """

    return dict()


def local_deploy():
    s3db.configure("setup_deploy", onvalidation=schedule_local)
    s3.actions = [
        {
            "label": str(current.T("View Status")),
            "url": URL(c="setup", args=["[id]/read"]),
            "_class": "action-btn",
        },
    ]

    def prep(r):
        resource = r.resource
        query = (db.setup_deploy.type == "local")

        # make some fields optional
        db.setup_deploy.remote_user.required = False
        db.setup_deploy.remote_user.writable = False
        db.setup_deploy.remote_user.readable = False

        db.setup_deploy.private_key.required = False
        db.setup_deploy.private_key.writable = False
        db.setup_deploy.private_key.readable = False

        resource.add_filter(query)

        if r.method in ("create", None):
            appname = request.application
            s3.scripts.append("/%s/static/scripts/S3/s3.setup.js" % appname)
        return True

    s3.prep = prep

    def postp(r, output):
        db.setup_deploy.prepop_options.requires = None
        if r.method == "read":
            record = r.record
            output["item"][0].append(TR(TD(LABEL("Status"), _class="w2p_fl")))
            output["item"][0].append(TR(TD(record.scheduler_id.status)))
            if record.scheduler_id.status == "FAILED":
                resource = s3db.resource("scheduler_run")
                row = db(resource.table.task_id == record.scheduler_id).select().first()
                output["item"][0].append(TR(TD(LABEL("Traceback"), _class="w2p_fl")))
                output["item"][0].append(TR(TD(row.traceback)))
                output["item"][0].append(TR(TD(LABEL("Output"), _class="w2p_fl")))
                output["item"][0].append(TR(TD(row.run_output)))
        return output

    s3.postp = postp

    return s3_rest_controller("setup", "deploy",
                              populate=dict(host="127.0.0.1",
                                            sitename=current.deployment_settings.get_base_public_url()
                                           )
                             )


def remote_deploy():
    s3db.configure("setup_deploy", onvalidation=schedule_remote)
    s3.actions = [
        {
            "label": str(current.T("View Status")),
            "url": URL(c="setup", args=["[id]/read"]),
            "_class": "action-btn",
        },
    ]

    def prep(r):
        resource = r.resource
        query = (db.setup_deploy.type == "remote")
        resource.add_filter(query)
        return True

    s3.prep = prep

    def postp(r, output):
        if r.method == "read":
            record = r.record
            output["item"][0].append(TR(TD(LABEL("Status"), _class="w2p_fl")))
            output["item"][0].append(TR(TD(record.scheduler_id.status)))
            if record.scheduler_id.status == "FAILED":
                resource = s3db.resource("scheduler_run")
                row = db(resource.table.task_id == record.scheduler_id).select().first()
                output["item"][0].append(TR(TD(LABEL("Traceback"), _class="w2p_fl")))
                output["item"][0].append(TR(TD(row.traceback)))
                output["item"][0].append(TR(TD(LABEL("Output"), _class="w2p_fl")))
                output["item"][0].append(TR(TD(row.run_output)))

        return output

    s3.postp = postp

    return s3_rest_controller("setup", "deploy")

def schedule_local(form):
    """
    Schedule a deployment using s3task.
    """

    # ToDo: support repo

    # Check if already deployed using coapp
    resource = s3db.resource("setup_deploy")
    rows = db(resource.table.type == "local").select()
    prod = False

    for row in rows:
        if row.scheduler_id.status == "COMPLETED":
            if row.prepop == form.vars.prepop:
                form.errors["prepop"] = "%s site has been installed previously" % row.prepop
                return
            if row.prepop == "prod":
                prod = True
        elif row.scheduler_id.status == "RUNNING" or row.scheduler_id.status == "ASSIGNED":
            form.errors["host"] = "Another Local Deployment is running. Please wait for it to complete"
            return

    if form.vars.prepop == "test" and not prod:
        form.errors["prepop"] = "Production site must be installed before test"
        return

    if form.vars.prepop == "demo" and not prod:
        demo_type = "beforeprod"
    elif form.vars.prepop == "demo" and prod:
        demo_type = "afterprod"
    else:
        demo_type = None

    row = s3db.setup_create_yaml_file(
        "127.0.0.1",
        form.vars.password,
        form.vars.web_server,
        form.vars.database_type,
        form.vars.prepop,
        ','.join(form.vars.prepop_options),
        form.vars.distro,
        True,
        form.vars.hostname,
        form.vars.template,
        form.vars.sitename,
        demo_type=demo_type
    )

    form.vars["scheduler_id"] = row.id
    form.vars["type"] = "local"

def schedule_remote(form):
    """
    Schedule a deployment using s3task.
    """

    # ToDo: support repo

    # Check if already deployed using coapp
    resource = s3db.resource("setup_deploy")
    rows = db(resource.table.type == "remote" and resource.table.host == form.vars.host).select()
    for row in rows:
        if row.scheduler_id.status == "COMPLETED":
            form.errors["host"] = "Deployment on this host has been done previously"
            return
        elif row.scheduler_id.status == "RUNNING" or row.scheduler_id.status == "ASSIGNED":
            form.errors["host"] = "Deployment on this host is running. Please wait for it to complete"
            return


    row = s3db.setup_create_yaml_file(
        form.vars.host,
        form.vars.password,
        form.vars.web_server,
        form.vars.database_type,
        form.vars.prepop,
        form.vars.distro,
        False,
        form.vars.hostname,
        form.vars.template,
        form.vars.sitename,
        os.path.join(request.folder, "uploads", form.vars.private_key.filename),
        form.vars.remote_user,
    )

    form.vars["scheduler_id"] = row.id
    form.vars["type"] = "remote"

def prepop_setting():
    if request.ajax == True:
        template = request.post_vars.get("template")
        module_name = "applications.eden_deployment.private.templates.%s.config" % template
        __import__(module_name)
        config = sys.modules[module_name]
        prepopulate_options = config.settings.base.get("prepopulate_options")
        if isinstance(prepopulate_options, dict):
            if "mandatory" in prepopulate_options:
                del prepopulate_options["mandatory"]
            return json.dumps(prepopulate_options.keys())
        else:
            return json.dumps(["mandatory"])
