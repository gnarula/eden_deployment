# -*- coding: utf-8 -*-

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

    return s3_rest_controller("setup", "deploy",
                              populate=dict(host="127.0.0.1",
                                            sitename=current.deployment_settings.get_base_public_url()
                                           )
                             )


def schedule_local(form):
    """
    Schedule a deployment using s3task.
    """

    # ToDo: support repo

    # Check if already deployed using coapp
    resource = s3db.resource("setup_deploy")
    rows = db(resource.table.type == "local").select()
    for row in rows:
        if row.scheduler_id.status == "COMPLETED":
            form.errors["host"] = "Local Deployment has been done previously"
            return
        elif row.scheduler_id.status == "RUNNING":
            form.errors["host"] = "Another Local Deployment is running. Please wait for it to complete"
            return

    row = s3db.setup_create_yaml_file(
        "127.0.0.1",
        form.vars.password,
        form.vars.web_server,
        form.vars.database_type,
        True,
        form.vars.hostname,
        form.vars.template,
        form.vars.sitename,
    )

    form.vars["scheduler_id"] = row.id
    form.vars["type"] = "local"
