# -*- coding: utf-8 -*-

""" Sahana Eden Deployments Model

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

__all__ = ("S3DeploymentModel",
           "S3DeploymentAlertModel",
           "deploy_rheader",
           "deploy_apply",
           "deploy_alert_select_recipients",
           "deploy_response_select_mission",
           )

try:
    # try stdlib (Python 2.6)
    import json
except ImportError:
    try:
        # try external module
        import simplejson as json
    except:
        # fallback to pure-Python module
        import gluon.contrib.simplejson as json

from gluon import *

from ..s3 import *
from s3layouts import S3AddResourceLink

# =============================================================================
class S3DeploymentModel(S3Model):

    names = ("deploy_mission",
             "deploy_mission_id",
             "deploy_mission_document",
             "deploy_application",
             "deploy_assignment",
             "deploy_assignment_appraisal",
             "deploy_assignment_experience",
             )

    def model(self):

        T = current.T
        db = current.db

        add_components = self.add_components
        configure = self.configure
        crud_strings = current.response.s3.crud_strings
        define_table = self.define_table
        super_link = self.super_link

        messages = current.messages
        NONE = messages["NONE"]
        UNKNOWN_OPT = messages.UNKNOWN_OPT

        human_resource_id = self.hrm_human_resource_id

        # ---------------------------------------------------------------------
        # Mission
        #
        mission_status_opts = {1 : T("Closed"),
                               2 : T("Open")
                               }
        tablename = "deploy_mission"
        define_table(tablename,
                     super_link("doc_id", "doc_entity"),
                     Field("name",
                           label = T("Name"),
                           represent = self.deploy_mission_name_represent,
                           requires = IS_NOT_EMPTY(),
                           ),
                     # @ToDo: Link to location via link table
                     # link table could be event_event_location for IFRC (would still allow 1 multi-country event to have multiple missions)
                     self.gis_location_id(),
                     # @ToDo: Link to event_type via event_id link table instead of duplicating
                     self.event_type_id(),
                     self.org_organisation_id(),
                     Field("code", length = 24,
                           represent = lambda v: s3_unicode(v) if v else NONE,
                           ),
                     Field("status", "integer",
                           default = 2,
                           label = T("Status"),
                           represent = lambda opt: \
                                       mission_status_opts.get(opt,
                                                               UNKNOWN_OPT),
                           requires = IS_IN_SET(mission_status_opts),
                           ),
                     # @todo: change into real fields written onaccept?
                     Field.Method("hrquantity",
                                  deploy_mission_hrquantity),
                     Field.Method("response_count",
                                  deploy_mission_response_count),
                     s3_comments(),
                     *s3_meta_fields())

        # CRUD Form
        crud_form = S3SQLCustomForm("name",
                                    "event_type_id",
                                    "location_id",
                                    "code",
                                    "status",
                                    # Files
                                    S3SQLInlineComponent(
                                        "document",
                                        name = "file",
                                        label = T("Files"),
                                        fields = ["file", "comments"],
                                        filterby = dict(field = "file",
                                                        options = "",
                                                        invert = True,
                                                        )
                                    ),
                                    # Links
                                    S3SQLInlineComponent(
                                        "document",
                                        name = "url",
                                        label = T("Links"),
                                        fields = ["url", "comments"],
                                        filterby = dict(field = "url",
                                                        options = None,
                                                        invert = True,
                                                        )
                                    ),
                                    #S3SQLInlineComponent("document",
                                                         #name = "file",
                                                         #label = T("Attachments"),
                                                         #fields = ["file",
                                                                   #"comments",
                                                                  #],
                                                         #),
                                    "comments",
                                    "created_on",
                                    )

        # Profile
        list_layout = deploy_MissionProfileLayout()
        alert_widget = dict(label = "Alerts",
                            insert = lambda r, list_id, title, url: \
                                   A(title,
                                     _href=r.url(component="alert",
                                                 method="create"),
                                     _class="action-btn profile-add-btn"),
                            label_create = "Create Alert",
                            type = "datalist",
                            list_fields = ["modified_on",
                                           "mission_id",
                                           "message_id",
                                           "subject",
                                           "body",
                                           ],
                            tablename = "deploy_alert",
                            context = "mission",
                            list_layout = list_layout,
                            pagesize = 10,
                            )

        list_fields = ["created_on",
                       "mission_id",
                       "comments",
                       "human_resource_id$id",
                       "human_resource_id$person_id",
                       "human_resource_id$organisation_id",
                       "message_id$body",
                       "message_id$from_address",
                       "message_id$attachment.document_id$file",
                       ]

        response_widget = dict(label = "Responses",
                               insert = False,
                               type = "datalist",
                               tablename = "deploy_response",
                               # Can't be 'response' as this clobbers web2py global
                               function = "response_message",
                               list_fields = list_fields,
                               context = "mission",
                               list_layout = list_layout,
                               # The popup datalist isn't currently functional (needs card layout applying) and not ideal UX anyway
                               #pagesize = 10,
                               pagesize = None,
                               )

        hr_label = current.deployment_settings.get_deploy_hr_label()
        if hr_label == "Member":
            label = "Members Deployed"
            label_create = "Deploy New Member"
        elif hr_label == "Staff":
            label = "Staff Deployed"
            label_create = "Deploy New Staff"
        elif hr_label == "Volunteer":
            label = "Volunteers Deployed"
            label_create = "Deploy New Volunteer"

        assignment_widget = dict(label = label,
                                 insert = lambda r, list_id, title, url: \
                                        A(title,
                                          _href=r.url(component="assignment",
                                                      method="create"),
                                          _class="action-btn profile-add-btn"),
                                 label_create = label_create,
                                 tablename = "deploy_assignment",
                                 type = "datalist",
                                 #type = "datatable",
                                 #actions = dt_row_actions,
                                 list_fields = [
                                     "human_resource_id$id",
                                     "human_resource_id$person_id",
                                     "human_resource_id$organisation_id",
                                     "start_date",
                                     "end_date",
                                     "job_title_id",
                                     "appraisal.rating",
                                     "mission_id",
                                 ],
                                 context = "mission",
                                 list_layout = list_layout,
                                 pagesize = None, # all records
                                 )

        docs_widget = dict(label = "Documents & Links",
                           label_create = "Add New Document / Link",
                           type = "datalist",
                           tablename = "doc_document",
                           context = ("~.doc_id", "doc_id"),
                           icon = "icon-paperclip",
                           # Default renderer:
                           #list_layout = s3db.doc_document_list_layouts,
                           )

        # Table configuration
        profile = URL(c="deploy", f="mission", args=["[id]", "profile"])
        configure(tablename,
                  create_next = profile,
                  crud_form = crud_form,
                  delete_next = URL(c="deploy", f="mission", args="summary"),
                  filter_widgets = [
                    S3TextFilter(["name",
                                  "code",
                                  "event_type_id$name",
                                  ],
                                 label=T("Search")
                                 ),
                    S3LocationFilter("location_id",
                                     label=messages.COUNTRY,
                                     widget="multiselect",
                                     levels=["L0"],
                                     hidden=True
                                     ),
                    S3OptionsFilter("event_type_id",
                                    widget="multiselect",
                                    hidden=True
                                    ),
                    S3OptionsFilter("status",
                                    options=mission_status_opts,
                                    hidden=True
                                    ),
                    S3DateFilter("created_on",
                                 hide_time=True,
                                 hidden=True
                                ),
                    ],
                  list_fields = ["name",
                                 (T("Date"), "created_on"),
                                 "event_type_id",
                                 (T("Country"), "location_id"),
                                 "code",
                                 (T("Responses"), "response_count"),
                                 (T(label), "hrquantity"),
                                 "status",
                                 ],
                  orderby = "deploy_mission.created_on desc",
                  profile_cols = 1,
                  profile_header = lambda r: \
                                   deploy_rheader(r, profile=True),
                  profile_widgets = [alert_widget,
                                     response_widget,
                                     assignment_widget,
                                     docs_widget,
                                     ],
                  summary = [{"name": "rheader",
                              "common": True,
                              "widgets": [{"method": self.add_button}]
                              },
                             {"name": "table",
                              "label": "Table",
                              "widgets": [{"method": "datatable"}]
                              },
                             {"name": "report",
                              "label": "Report",
                              "widgets": [{"method": "report",
                                           "ajax_init": True}],
                              },
                             {"name": "map",
                              "label": "Map",
                              "widgets": [{"method": "map",
                                           "ajax_init": True}],
                              },
                             ],
                  super_entity = "doc_entity",
                  update_next = profile,
                  )

        # Components
        add_components(tablename,
                       deploy_assignment = "mission_id",
                       deploy_alert = "mission_id",
                       deploy_response = "mission_id",
                       )

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Mission"),
            title_display = T("Mission"),
            title_list = T("Missions"),
            title_update = T("Edit Mission Details"),
            title_upload = T("Import Missions"),
            label_list_button = T("List Missions"),
            label_delete_button = T("Delete Mission"),
            msg_record_created = T("Mission added"),
            msg_record_modified = T("Mission Details updated"),
            msg_record_deleted = T("Mission deleted"),
            msg_list_empty = T("No Missions currently registered"))

        # Reusable field
        represent = S3Represent(lookup = tablename,
                                linkto = URL(f="mission",
                                             args=["[id]", "profile"]),
                                show_link = True)
                                
        mission_id = S3ReusableField("mission_id", "reference %s" % tablename,
                                     label = T("Mission"),
                                     ondelete = "CASCADE",
                                     represent = represent,
                                     requires = IS_ONE_OF(db,
                                                          "deploy_mission.id",
                                                          represent),
                                     )

        # ---------------------------------------------------------------------
        # Link table to link documents to missions, responses or assignments
        #
        tablename = "deploy_mission_document"
        define_table(tablename,
                     mission_id(),
                     self.msg_message_id(),
                     self.doc_document_id(),
                     *s3_meta_fields())

        # ---------------------------------------------------------------------
        # Application of human resources
        # - agreement that an HR is generally available for assignments
        # - can come with certain restrictions
        #
        tablename = "deploy_application"
        define_table(tablename,
                     human_resource_id(empty = False,
                                       label = T(hr_label)),
                     Field("active", "boolean",
                           default = True,
                           ),
                     *s3_meta_fields())

        configure(tablename,
                  delete_next = URL(c="deploy", f="human_resource", args="summary"),
                  )

        # ---------------------------------------------------------------------
        # Assignment of human resources
        # - actual assignment of an HR to a mission
        #
        tablename = "deploy_assignment"
        define_table(tablename,
                     mission_id(),
                     human_resource_id(empty = False,
                                       label = T(hr_label)),
                     self.hrm_job_title_id(),
                     # These get copied to hrm_experience
                     # rest of fields may not be filled-out, but are in attachments
                     s3_date("start_date", # Only field visible when deploying from Mission profile
                             label = T("Start Date"),
                             ),
                     s3_date("end_date",
                             label = T("End Date"),
                             ),
                     *s3_meta_fields())

        # Table configuration
        configure(tablename,
                  context = {"mission": "mission_id",
                             },
                  create_onaccept = self.deploy_assignment_create_onaccept,
                  update_onaccept = self.deploy_assignment_update_onaccept,
                  filter_widgets = [
                    S3TextFilter(["human_resource_id$person_id$first_name",
                                  "human_resource_id$person_id$middle_name",
                                  "human_resource_id$person_id$last_name",
                                  "mission_id$code",
                                 ],
                                 label=T("Search")
                                ),
                    S3OptionsFilter("mission_id$event_type_id",
                                    widget="multiselect",
                                    hidden=True
                                   ),
                    S3LocationFilter("mission_id$location_id",
                                     label=messages.COUNTRY,
                                     widget="multiselect",
                                     levels=["L0"],
                                     hidden=True
                                    ),
                    S3OptionsFilter("job_title_id",
                                    widget="multiselect",
                                    hidden=True,
                                   ),
                    S3DateFilter("start_date",
                                 hide_time=True,
                                 hidden=True,
                                ),
                  ],
                  summary = [
                      {"name": "table",
                       "label": "Table",
                       "widgets": [{"method": "datatable"}]
                      },
                      {"name": "report",
                       "label": "Report",
                       "widgets": [{"method": "report",
                                    "ajax_init": True}]
                      },
                  ],
                  )

        # Components
        add_components(tablename,
                       hrm_appraisal = {"name": "appraisal",
                                        "link": "deploy_assignment_appraisal",
                                        "joinby": "assignment_id",
                                        "key": "appraisal_id",
                                        "autodelete": False,
                                        },
                       )

        assignment_id = S3ReusableField("assignment_id",
                                        "reference %s" % tablename,
                                        ondelete = "CASCADE")

        # ---------------------------------------------------------------------
        # Link Assignments to Appraisals
        #
        tablename = "deploy_assignment_appraisal"
        define_table(tablename,
                     assignment_id(empty = False),
                     Field("appraisal_id", self.hrm_appraisal),
                     *s3_meta_fields())

        configure(tablename,
                  ondelete_cascade = \
                    self.deploy_assignment_appraisal_ondelete_cascade,
                  )

        # ---------------------------------------------------------------------
        # Link Assignments to Experience
        #
        tablename = "deploy_assignment_experience"
        define_table(tablename,
                     assignment_id(empty = False),
                     Field("experience_id", self.hrm_experience),
                     *s3_meta_fields())

        configure(tablename,
                  ondelete_cascade = \
                    self.deploy_assignment_experience_ondelete_cascade,
                  )

        # ---------------------------------------------------------------------
        # Assignment of assets
        #
        # @todo: deploy_asset_assignment
        
        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return dict(deploy_mission_id = mission_id,
                    )

    # -------------------------------------------------------------------------
    def defaults(self):
        """
            Safe defaults for model-global names in case module is disabled
        """

        dummy = S3ReusableField("dummy_id", "integer",
                                readable = False,
                                writable = False)

        return dict(deploy_mission_id = lambda **attr: dummy("mission_id"),
                    )

    # -------------------------------------------------------------------------
    @staticmethod
    def add_button(r, widget_id=None, visible=True, **attr):

        # Check permission only here, i.e. when the summary is
        # actually being rendered:
        if current.auth.s3_has_permission("create", r.tablename):
            return A(S3Method.crud_string(r.tablename,
                                          "label_create"),
                     _href=r.url(method="create", id=0, vars={}),
                     _class="action-btn",
                     )
        else:
            return ""
                
    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_mission_name_represent(name):

        table = current.s3db.deploy_mission
        mission = current.db(table.name == name).select(table.id,
                                                        limitby=(0, 1)
                                                        ).first()
        if not mission:
            return name

        return A(name,
                 _href=URL(c="deploy", f="mission",
                           args=[mission.id, "profile"]))
                
    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_assignment_create_onaccept(form):
        """
            Create linked hrm_experience record
        """

        db = current.db
        s3db = current.s3db
        form_vars = form.vars
        assignment_id = form_vars.id

        # Extract required data
        human_resource_id = form_vars.human_resource_id
        mission_id = form_vars.mission_id
        job_title_id = form_vars.mission_id
        
        if not mission_id or not human_resource_id:
            # Need to reload the record
            atable = db.deploy_assignment
            query = (atable.id == assignment_id)
            assignment = db(query).select(atable.mission_id,
                                          atable.human_resource_id,
                                          atable.job_title_id,
                                          limitby=(0, 1)).first()
            if assignment:
                mission_id = assignment.mission_id
                human_resource_id = assignment.human_resource_id
                job_title_id = assignment.job_title_id

        # Lookup the person ID
        hrtable = s3db.hrm_human_resource
        hr = db(hrtable.id == human_resource_id).select(hrtable.person_id,
                                                        limitby=(0, 1)
                                                        ).first()

        # Lookup mission details
        mtable = db.deploy_mission
        mission = db(mtable.id == mission_id).select(mtable.code,
                                                     mtable.location_id,
                                                     mtable.organisation_id,
                                                     limitby=(0, 1)
                                                     ).first()
        if mission:
            code = mission.code
            location_id = mission.location_id
            organisation_id = mission.organisation_id
        else:
            code = None
            location_id = None
            organisation_id = None

        # Create hrm_experience
        etable = s3db.hrm_experience
        id = etable.insert(person_id = hr.person_id,
                           code = code,
                           location_id = location_id,
                           job_title_id = job_title_id,
                           organisation_id = organisation_id,
                           start_date = form_vars.start_date,
                           # In case coming from update
                           end_date = form_vars.get("end_date", None),
                           )

        # Create link
        ltable = db.deploy_assignment_experience
        ltable.insert(assignment_id = assignment_id,
                      experience_id = id,
                      )

    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_assignment_experience_ondelete_cascade(row, tablename=None):
        """
            Remove linked hrm_experience record

            @param row: the link to be deleted
            @param tablename: the tablename (ignored)
        """

        s3db = current.s3db

        # Lookup experience ID
        table = s3db.deploy_assignment_experience
        link = current.db(table.id == row.id).select(table.id,
                                                     table.experience_id,
                                                     limitby=(0, 1)).first()
        if not link:
            return
        else:
            # Prevent infinite cascade
            link.update_record(experience_id=None)
            
        s3db.resource("hrm_experience", id=link.experience_id).delete()

    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_assignment_appraisal_ondelete_cascade(row, tablename=None):
        """
            Remove linked hrm_appraisal record

            @param row: the link to be deleted
            @param tablename: the tablename (ignored)
        """

        s3db = current.s3db

        # Lookup experience ID
        table = s3db.deploy_assignment_appraisal
        link = current.db(table.id == row.id).select(table.id,
                                                     table.appraisal_id,
                                                     limitby=(0, 1)).first()
        if not link:
            return
        else:
            # Prevent infinite cascade
            link.update_record(appraisal_id=None)

        s3db.resource("hrm_appraisal", id=link.appraisal_id).delete()

    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_assignment_update_onaccept(form):
        """
            Update linked hrm_experience record
        """

        db = current.db
        s3db = current.s3db
        form_vars = form.vars

        # Lookup Experience
        ltable = s3db.deploy_assignment_experience
        link = db(ltable.assignment_id == form_vars.id).select(ltable.experience_id,
                                                               limitby=(0, 1)
                                                               ).first()
        if link:
            # Update Experience
            # - likely to be just end_date
            etable = s3db.hrm_experience
            db(etable.id == link.experience_id).update(start_date = form_vars.start_date,
                                                       end_date = form_vars.end_date,
                                                       )
        else:
            # Create Experience
            S3DeploymentModel.deploy_assignment_create_onaccept(form)

# =============================================================================
class S3DeploymentAlertModel(S3Model):

    names = ("deploy_alert",
             "deploy_alert_recipient",
             "deploy_response",
             )

    def model(self):

        T = current.T

        add_components = self.add_components
        configure = self.configure
        crud_strings = current.response.s3.crud_strings
        define_table = self.define_table
        NONE = current.messages["NONE"]

        human_resource_id = self.hrm_human_resource_id
        message_id = self.msg_message_id
        mission_id = self.deploy_mission_id

        hr_label = current.deployment_settings.get_deploy_hr_label()

        contact_method_opts = {1: T("Email"),
                               2: T("SMS"),
                               #3: T("Twitter"),
                               #9: T("All"),
                               9: T("Both"),
                               }

        # ---------------------------------------------------------------------
        # Alert
        # - also the PE representing its Recipients
        #
        tablename = "deploy_alert"
        define_table(tablename,
                     self.super_link("pe_id", "pr_pentity"),
                     mission_id(
                        requires = IS_ONE_OF(current.db,
                                             "deploy_mission.id",
                                             S3Represent(lookup="deploy_mission"),
                                             filterby="status",
                                             filter_opts=(2,),
                                             ),
                        ),
                     Field("contact_method", "integer",
                           default = 1,
                           label = T("Send By"),
                           represent = lambda opt: \
                            contact_method_opts.get(opt, NONE),
                           requires = IS_IN_SET(contact_method_opts),
                           ),
                     Field("subject", length=78,    # RFC 2822
                           label = T("Subject"),
                           # Not used by SMS
                           #requires = IS_NOT_EMPTY(),
                           ),
                     Field("body", "text",
                           label = T("Message"),
                           represent = lambda v: v or NONE,
                           requires = IS_NOT_EMPTY(),
                           ),
                     # Link to the Message once sent
                     message_id(readable = False),
                     *s3_meta_fields())

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Alert"),
            title_display = T("Alert Details"),
            title_list = T("Alerts"),
            title_update = T("Edit Alert Details"),
            title_upload = T("Import Alerts"),
            label_list_button = T("List Alerts"),
            label_delete_button = T("Delete Alert"),
            msg_record_created = T("Alert added"),
            msg_record_modified = T("Alert Details updated"),
            msg_record_deleted = T("Alert deleted"),
            msg_list_empty = T("No Alerts currently registered"))

        # CRUD Form
        crud_form = S3SQLCustomForm("mission_id",
                                    "contact_method",
                                    "subject",
                                    "body",
                                    "modified_on",
                                    )

        # Table Configuration
        configure(tablename,
                  super_entity = "pr_pentity",
                  context = {"mission": "mission_id"},
                  crud_form = crud_form,
                  list_fields = ["mission_id",
                                 "contact_method",
                                 "subject",
                                 "body",
                                 "alert_recipient.human_resource_id",
                                 ],
                  )

        # Components
        add_components(tablename,
                       deploy_alert_recipient = {"name": "recipient",
                                                 "joinby": "alert_id",
                                                 },
                       hrm_human_resource = {"name": "select",
                                             "link": "deploy_alert_recipient",
                                             "joinby": "alert_id",
                                             "key": "human_resource_id",
                                             "autodelete": False,
                                             },
                       )

        # Custom method to send alerts
        self.set_method("deploy", "alert",
                        method = "send",
                        action = self.deploy_alert_send)

        # Reusable field
        represent = S3Represent(lookup=tablename)
        alert_id = S3ReusableField("alert_id", "reference %s" % tablename,
                                   label = T("Alert"),
                                   ondelete = "CASCADE",
                                   represent = represent,
                                   requires = IS_ONE_OF(db, "deploy_alert.id",
                                                        represent),
                                   )

        # ---------------------------------------------------------------------
        # Recipients of the Alert
        #
        tablename = "deploy_alert_recipient"
        define_table(tablename,
                     alert_id(),
                     human_resource_id(empty = False,
                                       label = T(hr_label)),
                     *s3_meta_fields())

        # CRUD Strings
        crud_strings[tablename] = Storage(
            label_create = T("Add Recipient"),
            title_display = T("Recipient Details"),
            title_list = T("Recipients"),
            title_update = T("Edit Recipient Details"),
            title_upload = T("Import Recipients"),
            label_list_button = T("List Recipients"),
            label_delete_button = T("Delete Recipient"),
            msg_record_created = T("Recipient added"),
            msg_record_modified = T("Recipient Details updated"),
            msg_record_deleted = T("Recipient deleted"),
            msg_list_empty = T("No Recipients currently defined"))

        # ---------------------------------------------------------------------
        # Responses to Alerts
        #
        tablename = "deploy_response"
        define_table(tablename,
                     mission_id(),
                     human_resource_id(label = T(hr_label)),
                     message_id(label = T("Message"),
                                writable = False),
                     s3_comments(),
                     *s3_meta_fields())

        crud_form = S3SQLCustomForm("mission_id",
                                    "human_resource_id",
                                    "message_id",
                                    "comments",
                                    # @todo:
                                    #S3SQLInlineComponent("document"),
                                    )

        # Table Configuration
        configure(tablename,
                  context = {"mission": "mission_id"},
                  crud_form = crud_form,
                  #editable = False,
                  insertable = False,
                  update_onaccept = self.deploy_response_update_onaccept,
                  )

        # CRUD Strings
        NO_MESSAGES = T("No Messages found")
        crud_strings[tablename] = Storage(
            title_display = T("Response Message"),
            title_list = T("Response Messages"),
            title_update = T("Edit Response Details"),
            label_list_button = T("All Response Messages"),
            label_delete_button = T("Delete Message"),
            msg_record_deleted = T("Message deleted"),
            msg_no_match = NO_MESSAGES,
            msg_list_empty = NO_MESSAGES)

        # ---------------------------------------------------------------------
        # Pass names back to global scope (s3.*)
        #
        return dict()

    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_alert_send(r, **attr):
        """
            Custom Method to send an Alert
        """

        alert_id = r.id
        if r.representation != "html" or not alert_id or r.component:
            raise HTTP(501, BADMETHOD)
        
        # Must have permission to update the alert in order to send it
        authorised = current.auth.s3_has_permission("update", "deploy_alert",
                                                    record_id = alert_id)
        if not authorised:
            r.unauthorised()

        T = current.T
        record = r.record
        # Always redirect to the Mission Profile
        mission_id = record.mission_id
        next_url = URL(f="mission", args=[mission_id, "profile"])

        # Check whether the alert has already been sent
        # - alerts should be read-only after creation
        if record.message_id:
            current.session.error = T("This Alert has already been sent!")
            redirect(next_url)

        db = current.db
        s3db = current.s3db
        table = s3db.deploy_alert

        contact_method = record.contact_method

        # Check whether there are recipients
        ltable = db.deploy_alert_recipient
        query = (ltable.alert_id == alert_id) & \
                (ltable.deleted == False)
        if contact_method == 9:
            # Save a subsequent query
            recipients = db(query).select(ltable.human_resource_id)
        else:
            recipients = db(query).select(ltable.id,
                                          limitby=(0, 1)).first()
        if not recipients:
            current.session.error = T("This Alert has no Recipients yet!")
            redirect(next_url)

        # Send Message
        message = record.body
        msg = current.msg

        if contact_method == 2:
            # Send SMS
            message_id = msg.send_by_pe_id(record.pe_id,
                                           contact_method = "SMS",
                                           message=message,
                                           )

        elif contact_method == 9:
            # Send both
            # Create separate alert for this
            id = table.insert(body = message,
                              contact_method = 2,
                              mission_id = mission_id,
                              created_by = record.created_by,
                              created_on = record.created_on,
                              )
            new_alert = dict(id=id)
            s3db.update_super(table, new_alert)

            # Add Recipients
            for row in recipients:
                ltable.insert(alert_id = id,
                              human_resource_id = row.human_resource_id,
                              )

            # Send SMS
            message_id = msg.send_by_pe_id(new_alert["pe_id"],
                                           contact_method = "SMS",
                                           message=message,
                                           )

            # Update the Alert to show it's been Sent
            db(table.id == id).update(message_id=message_id)

        if contact_method in (1, 9):
            # Send Email

            # Embed the mission_id to parse replies
            # = @ToDo: Use a Message Template to add Footer (very simple one for RDRT)
            message = "%s\n:mission_id:%s:" % (message, mission_id)

            # Lookup from_address
            # @ToDo: Allow multiple channels to be defined &
            #        select the appropriate one for this mission
            ctable = s3db.msg_email_channel
            channel = db(ctable.deleted == False).select(ctable.username,
                                                         ctable.server,
                                                         limitby = (0, 1)
                                                         ).first()
            if not channel:
                current.session.error = T("Need to configure an Email Address!")
                redirect(URL(f="email_channel"))

            from_address = "%s@%s" % (channel.username, channel.server)

            message_id = msg.send_by_pe_id(record.pe_id,
                                           subject=record.subject,
                                           message=message,
                                           from_address=from_address,
                                           )

        # Update the Alert to show it's been Sent
        data = dict(message_id=message_id)
        if contact_method == 2:
            # Clear the Subject
            data["subject"] = None
        elif contact_method == 9:
            # Also modify the contact_method to show that this is the email one
            data["contact_method"] = 1

        db(table.id == alert_id).update(**data)

        # Return to the Mission Profile
        current.session.confirmation = T("Alert Sent")
        redirect(next_url)

    # -------------------------------------------------------------------------
    @staticmethod
    def deploy_response_update_onaccept(form):
        """
            Update the doc_id in all attachments (doc_document) to the
            hrm_human_resource the response is linked to.

            @param form: the form
        """

        db = current.db
        s3db = current.s3db

        data = form.vars
        if not data or "id" not in data:
            return

        # Get message ID and human resource ID
        if "human_resource_id" not in data or "message_id" not in data:
            rtable = s3db.deploy_response
            response = db(rtable.id == data.id).select(rtable.human_resource_id,
                                                       rtable.message_id,
                                                       limitby=(0, 1)
                                                       ).first()
            if not response:
                return
            human_resource_id = response.human_resource_id
            message_id = response.message_id
        else:
            human_resource_id = data.human_resource_id
            message_id = data.message_id

        # Update doc_id in all attachments (if any)
        dtable = s3db.doc_document
        ltable = s3db.deploy_mission_document
        query = (ltable.message_id == response.message_id) & \
                (dtable.id == ltable.document_id) & \
                (ltable.deleted == False) & \
                (dtable.deleted == False)
        attachments = db(query).select(dtable.id)
        if attachments:
            # Get the doc_id from the hrm_human_resource
            doc_id = None
            if human_resource_id:
                htable = s3db.hrm_human_resource
                hr = db(htable.id == human_resource_id).select(htable.doc_id,
                                                               limitby=(0, 1)
                                                               ).first()
                if hr:
                    doc_id = hr.doc_id
            db(dtable.id.belongs(attachments)).update(doc_id=doc_id)
        return
            
# =============================================================================
def deploy_rheader(r, tabs=[], profile=False):
    """ Deployment Resource Headers """

    if r.representation != "html":
        # RHeaders only used in interactive views
        return None

    record = r.record
    if not record:
        # List or Create form: rheader makes no sense here
        return None

    has_permission = current.auth.s3_has_permission
    T = current.T
        
    table = r.table
    tablename = r.tablename

    rheader = None
    
    resourcename = r.name
    if resourcename == "alert":

        alert_id = r.id
        db = current.db
        ltable = db.deploy_alert_recipient
        query = (ltable.alert_id == alert_id) & \
                (ltable.deleted == False)
        recipients = db(query).count()

        unsent = not r.record.message_id
        authorised = has_permission("update", tablename, record_id=alert_id)
        
        if unsent and authorised:
            send_button = BUTTON(T("Send Alert"), _class="alert-send-btn")
            if recipients:
                send_button.update(_onclick="window.location.href='%s'" %
                                            URL(c="deploy",
                                                f="alert",
                                                args=[alert_id, "send"]))
            else:
                send_button.update(_disabled="disabled")
        else:
            send_button = ""

        # Tabs
        tabs = [(T("Message"), None),
                (T("Recipients (%(number)s Total)") %
                   dict(number=recipients),
                 "recipient"),
                ]
        if unsent and authorised:
            # Insert tab to select recipients
            tabs.insert(1, (T("Select Recipients"), "select"))
            
        rheader_tabs = s3_rheader_tabs(r, tabs)

        rheader = DIV(TABLE(TR(TH("%s: " % table.mission_id.label),
                               table.mission_id.represent(record.mission_id),
                               send_button,
                               ),
                            TR(TH("%s: " % table.subject.label),
                               record.subject
                               ),
                            ), rheader_tabs, _class="alert-rheader")

    elif resourcename == "mission":

        if not profile and not r.component:
            rheader = ""
        else:
            crud_string = S3Method.crud_string
            record = r.record
            title = crud_string(r.tablename, "title_display")
            if record:
                title = "%s: %s" % (title, record.name)
                edit_btn = ""
                if profile and \
                   current.auth.s3_has_permission("update",
                                                  "deploy_mission",
                                                  record_id=r.id):
                    crud_button = S3CRUD.crud_button
                    edit_btn = crud_button(T("Edit"),
                                           _href=r.url(method="update"))

                label = lambda f, table=table, record=record, **attr: \
                               TH("%s: " % table[f].label, **attr)
                value = lambda f, table=table, record=record, **attr: \
                               TD(table[f].represent(record[f]), **attr)
                rheader = DIV(H2(title),
                              TABLE(TR(label("event_type_id"),
                                       value("event_type_id"),
                                       label("location_id"),
                                       value("location_id"),
                                       label("code"),
                                       value("code"),
                                       ),
                                    TR(label("created_on"),
                                       value("created_on"),
                                       label("status"),
                                       value("status"),
                                       ),
                                    TR(label("comments"),
                                       value("comments",
                                             _class="mission-comments",
                                             _colspan="6",
                                             ),
                                       ),
                            ),
                            _class="mission-rheader"
                          )
                if edit_btn:
                    rheader[-1][0].append(edit_btn)
            else:
                rheader = H2(title)

    return rheader

# =============================================================================
def deploy_mission_hrquantity(row):
    """ Number of human resources deployed """

    if hasattr(row, "deploy_mission"):
        row = row.deploy_mission
    try:
        mission_id = row.id
    except AttributeError:
        return 0

    db = current.db
    table = db.deploy_assignment
    count = table.id.count()
    row = db(table.mission_id == mission_id).select(count).first()
    if row:
        return row[count]
    else:
        return 0

# =============================================================================
def deploy_mission_response_count(row):
    """ Number of responses to a mission """

    if hasattr(row, "deploy_mission"):
        row = row.deploy_mission
    try:
        mission_id = row.id
    except AttributeError:
        return 0

    db = current.db
    table = db.deploy_response
    count = table.id.count()
    row = db(table.mission_id == mission_id).select(count).first()
    if row:
        return row[count]
    else:
        return 0

# =============================================================================
def deploy_member_filter():
    """
        Filter widgets for members (hrm_human_resource), used in
        custom methods for member selection, e.g. deploy_apply
        or deploy_alert_select_recipients
    """

    T = current.T
    widgets = [S3TextFilter(["person_id$first_name",
                             "person_id$middle_name",
                             "person_id$last_name",
                             ],
                            label=T("Name"),
                            ),
               S3OptionsFilter("organisation_id",
                               widget="multiselect",
                               filter=True,
                               hidden=True,
                               ),
               S3OptionsFilter("credential.job_title_id",
                               # @ToDo: Label setting
                               label = T("Sector"),
                               widget="multiselect",
                               hidden=True,
                               ),
               ]
    settings = current.deployment_settings
    if settings.get_org_regions():
        if settings.get_org_regions_hierarchical():
            widgets.insert(1, S3HierarchyFilter("organisation_id$region_id",
                                                lookup="org_region",
                                                hidden=True,
                                                ))
        else:
            widgets.insert(1, S3OptionsFilter("organisation_id$region_id",
                                              widget="multiselect",
                                              filter=True,
                                              ))
    return widgets
    
# =============================================================================
def deploy_apply(r, **attr):
    """
        Custom method to select new RDRT members

        @todo: make workflow re-usable for manual assignments
    """

    # Requires permission to create deploy_application
    authorised = current.auth.s3_has_permission("create", "deploy_application")
    if not authorised:
        r.unauthorised()

    T = current.T
    s3db = current.s3db

    get_vars = r.get_vars
    response = current.response
    #settings = current.deployment_settings

    if r.http == "POST":
        added = 0
        post_vars = r.post_vars
        if all([n in post_vars for n in ("add", "selected", "mode")]):
            selected = post_vars.selected
            if selected:
                selected = selected.split(",")
            else:
                selected = []

            db = current.db
            atable = s3db.deploy_application
            if selected:
                # Handle exclusion filter
                if post_vars.mode == "Exclusive":
                    if "filterURL" in post_vars:
                        filters = S3URLQuery.parse_url(post_vars.ajaxURL)
                    else:
                        filters = None
                    query = ~(FS("id").belongs(selected))
                    hresource = s3db.resource("hrm_human_resource",
                                              filter=query, vars=filters)
                    rows = hresource.select(["id"], as_rows=True)
                    selected = [str(row.id) for row in rows]

                query = (atable.human_resource_id.belongs(selected)) & \
                        (atable.deleted != True)
                rows = db(query).select(atable.id,
                                        atable.active)
                rows = dict((row.id, row) for row in rows)
                for human_resource_id in selected:
                    try:
                        hr_id = int(human_resource_id.strip())
                    except ValueError:
                        continue
                    if hr_id in rows:
                        row = rows[hr_id]
                        if not row.active:
                            row.update_record(active=True)
                            added += 1
                    else:
                        atable.insert(human_resource_id=human_resource_id,
                                      active=True)
                        added += 1
        # @ToDo: Move 'RDRT' label to settings
        current.session.confirmation = T("%(number)s RDRT members added") % \
                                       dict(number=added)
        if added > 0:
            redirect(URL(f="human_resource", args=["summary"], vars={}))
        else:
            redirect(URL(f="application", vars={}))

    elif r.http == "GET":

        # Filter widgets
        filter_widgets = deploy_member_filter()

        # List fields
        list_fields = ["id",
                       "person_id",
                       "job_title_id",
                       "organisation_id",
                       ]
        
        # Data table
        resource = r.resource
        totalrows = resource.count()
        if "iDisplayLength" in get_vars:
            display_length = int(get_vars["iDisplayLength"])
        else:
            display_length = 25
        limit = 4 * display_length
        filter, orderby, left = resource.datatable_filter(list_fields, get_vars)
        resource.add_filter(filter)
        data = resource.select(list_fields,
                               start=0,
                               limit=limit,
                               orderby=orderby,
                               left=left,
                               count=True,
                               represent=True)
        filteredrows = data["numrows"]
        dt = S3DataTable(data["rfields"], data["rows"])
        dt_id = "datatable"

        # Bulk actions
        # @todo: generalize label
        dt_bulk_actions = [(T("Add as RDRT Members"), "add")]

        if r.representation == "html":
            # Page load
            resource.configure(deletable = False)

            #dt.defaultActionButtons(resource)
            profile_url = URL(f = "human_resource",
                              args = ["[id]", "profile"])
            S3CRUD.action_buttons(r,
                                  deletable = False,
                                  read_url = profile_url,
                                  update_url = profile_url)
            response.s3.no_formats = True

            # Data table (items)
            items = dt.html(totalrows,
                            filteredrows,
                            dt_id,
                            dt_displayLength=display_length,
                            dt_ajax_url=URL(c="deploy",
                                            f="application",
                                            extension="aadata",
                                            vars={},
                                            ),
                            dt_bFilter="false",
                            dt_pagination="true",
                            dt_bulk_actions=dt_bulk_actions,
                            )

            # Filter form
            if filter_widgets:

                # Where to retrieve filtered data from:
                _vars = resource.crud._remove_filters(r.get_vars)
                filter_submit_url = r.url(vars=_vars)

                # Where to retrieve updated filter options from:
                filter_ajax_url = URL(f="human_resource",
                                      args=["filter.options"],
                                      vars={})

                get_config = resource.get_config
                filter_clear = get_config("filter_clear", True)
                filter_formstyle = get_config("filter_formstyle", None)
                filter_submit = get_config("filter_submit", True)
                filter_form = S3FilterForm(filter_widgets,
                                           clear=filter_clear,
                                           formstyle=filter_formstyle,
                                           submit=filter_submit,
                                           ajax=True,
                                           url=filter_submit_url,
                                           ajaxurl=filter_ajax_url,
                                           _class="filter-form",
                                           _id="datatable-filter-form",
                                           )
                fresource = current.s3db.resource(resource.tablename)
                alias = resource.alias if r.component else None
                ff = filter_form.html(fresource,
                                      r.get_vars,
                                      target="datatable",
                                      alias=alias)
            else:
                ff = ""
                
            output = dict(items = items,
                          # @todo: generalize
                          title = T("Add RDRT Members"),
                          list_filter_form = ff)

            response.view = "list_filter.html"
            return output

        elif r.representation == "aadata":
            # Ajax refresh
            if "sEcho" in get_vars:
                echo = int(get_vars.sEcho)
            else:
                echo = None
            items = dt.json(totalrows,
                            filteredrows,
                            dt_id,
                            echo,
                            dt_bulk_actions=dt_bulk_actions)
            response.headers["Content-Type"] = "application/json"
            return items

        else:
            r.error(501, current.ERROR.BAD_FORMAT)
    else:
        r.error(405, current.ERROR.BAD_METHOD)

# =============================================================================
def deploy_alert_select_recipients(r, **attr):
    """
        Custom method to select Recipients for an Alert
    """

    alert_id = r.id
    if r.representation not in ("html", "aadata") or \
       not alert_id or \
       not r.component:
        r.error(405, current.ERROR.BAD_METHOD)

    # Must have permission to update the alert in order to add recipients
    authorised = current.auth.s3_has_permission("update", "deploy_alert",
                                                record_id = alert_id)
    if not authorised:
        r.unauthorised()

    T = current.T
    s3db = current.s3db

    response = current.response
    member_query = FS("application.active") == True

    if r.http == "POST":

        added = 0
        post_vars = r.post_vars
        if all([n in post_vars for n in ("select", "selected", "mode")]):
            selected = post_vars.selected
            if selected:
                selected = selected.split(",")
            else:
                selected = []

            db = current.db
            # Handle exclusion filter
            if post_vars.mode == "Exclusive":
                if "filterURL" in post_vars:
                    filters = S3URLQuery.parse_url(post_vars.filterURL)
                else:
                    filters = None
                query = member_query & \
                        (~(FS("id").belongs(selected)))

                hresource = s3db.resource("hrm_human_resource",
                                          filter=query, vars=filters)
                rows = hresource.select(["id"], as_rows=True)
                selected = [str(row.id) for row in rows]

            rtable = s3db.deploy_alert_recipient
            query = (rtable.alert_id == alert_id) & \
                    (rtable.human_resource_id.belongs(selected)) & \
                    (rtable.deleted != True)
            rows = db(query).select(rtable.human_resource_id)
            skip = set(row.human_resource_id for row in rows)

            for human_resource_id in selected:
                try:
                    hr_id = int(human_resource_id.strip())
                except ValueError:
                    continue
                if hr_id in skip:
                    continue
                rtable.insert(alert_id=alert_id,
                              human_resource_id=human_resource_id,
                              )
                added += 1
        if not selected:
            response.warning = T("No Recipients Selected!")
        else:
            response.confirmation = T("%(number)s Recipients added to Alert") % \
                                     dict(number=added)

    get_vars = r.get_vars or {}
    settings = current.deployment_settings
    resource = s3db.resource("hrm_human_resource",
                             filter=member_query, vars=r.get_vars)

    # Filter widgets
    filter_widgets = deploy_member_filter()

    # List fields
    list_fields = ["id",
                   "person_id",
                   "job_title_id",
                   "organisation_id",
                   ]

    # Data table
    totalrows = resource.count()
    if "iDisplayLength" in get_vars:
        display_length = int(get_vars["iDisplayLength"])
    else:
        display_length = 25
    limit = 4 * display_length
    filter, orderby, left = resource.datatable_filter(list_fields, get_vars)
    resource.add_filter(filter)
    data = resource.select(list_fields,
                           start=0,
                           limit=limit,
                           orderby=orderby,
                           left=left,
                           count=True,
                           represent=True)

    filteredrows = data["numrows"]
    dt = S3DataTable(data["rfields"], data["rows"])
    dt_id = "datatable"

    # Bulk actions
    dt_bulk_actions = [(T("Select as Recipients"), "select")]

    if r.representation == "html":
        # Page load
        resource.configure(deletable = False)

        #dt.defaultActionButtons(resource)
        response.s3.no_formats = True

        # Data table (items)
        items = dt.html(totalrows,
                        filteredrows,
                        dt_id,
                        dt_displayLength=display_length,
                        dt_ajax_url=r.url(representation="aadata"),
                        dt_bFilter="false",
                        dt_pagination="true",
                        dt_bulk_actions=dt_bulk_actions,
                        )

        # Filter form
        if filter_widgets:

            # Where to retrieve filtered data from:
            _vars = resource.crud._remove_filters(r.get_vars)
            filter_submit_url = r.url(vars=_vars)

            # Where to retrieve updated filter options from:
            filter_ajax_url = URL(f="human_resource",
                                  args=["filter.options"],
                                  vars={})

            get_config = resource.get_config
            filter_clear = get_config("filter_clear", True)
            filter_formstyle = get_config("filter_formstyle", None)
            filter_submit = get_config("filter_submit", True)
            filter_form = S3FilterForm(filter_widgets,
                                       clear=filter_clear,
                                       formstyle=filter_formstyle,
                                       submit=filter_submit,
                                       ajax=True,
                                       url=filter_submit_url,
                                       ajaxurl=filter_ajax_url,
                                       _class="filter-form",
                                       _id="datatable-filter-form",
                                       )
            fresource = current.s3db.resource(resource.tablename)
            alias = resource.alias if r.component else None
            ff = filter_form.html(fresource,
                                  r.get_vars,
                                  target="datatable",
                                  alias=alias)
        else:
            ff = ""

        output = dict(items=items,
                      title=T("Select Recipients"),
                      list_filter_form=ff)

        # Maintain RHeader for consistency
        if attr.get("rheader"):
            rheader = attr["rheader"](r)
            if rheader:
                output["rheader"] = rheader

        response.view = "list_filter.html"
        return output

    elif r.representation == "aadata":
        # Ajax refresh
        if "sEcho" in get_vars:
            echo = int(get_vars.sEcho)
        else:
            echo = None
        items = dt.json(totalrows,
                        filteredrows,
                        dt_id,
                        echo,
                        dt_bulk_actions=dt_bulk_actions)
        response.headers["Content-Type"] = "application/json"
        return items

    else:
        r.error(501, current.ERROR.BAD_FORMAT)

# =============================================================================
def deploy_response_select_mission(r, **attr):
    """
        Custom method to Link a Response to a Mission &/or Human Resource
    """

    message_id = r.record.message_id if r.record else None
    if r.representation not in ("html", "aadata") or not message_id or not r.component:
        r.error(405, current.ERROR.BAD_METHOD)

    T = current.T
    db = current.db
    s3db = current.s3db

    atable = s3db.msg_attachment
    dtable = db.doc_document
    query = (atable.message_id == message_id) & \
            (atable.document_id == dtable.id)
    atts = db(query).select(dtable.id,
                            dtable.file,
                            dtable.name,
                            )
        
    response = current.response
    mission_query = FS("mission.status") == 2

    get_vars = r.get_vars or {}
    mission_id = get_vars.get("mission_id", None)
    if mission_id:
        hr_id = get_vars.get("hr_id", None)
        if not hr_id:
            # @ToDo: deployment_setting for 'Member' label
            current.session.warning = T("No Member Selected!")
            # Can still link to the mission, member can be set
            # manually in the mission profile
            s3db.deploy_response.insert(message_id = message_id,
                                        mission_id = mission_id,
                                        )
        else:
            s3db.deploy_response.insert(message_id = message_id,
                                        mission_id = mission_id,
                                        human_resource_id = hr_id,
                                        )
        # Are there any attachments?
        if atts:
            ltable = s3db.deploy_mission_document
            if hr_id:
                # Set documents to the Member's doc_id
                hrtable = s3db.hrm_human_resource
                doc_id = db(hrtable.id == hr_id).select(hrtable.doc_id,
                                                        limitby=(0, 1)
                                                        ).first().doc_id
            for a in atts:
                # Link to Mission
                document_id = a.id
                ltable.insert(mission_id = mission_id,
                              message_id = message_id,
                              document_id = document_id)
                if hr_id:
                    db(dtable.id == document_id).update(doc_id = doc_id)

        #mission = XML(A(T("Mission"),
        #                _href=URL(c="deploy", f="mission",
        #                          args=[mission_id, "profile"])))
        #current.session.confirmation = T("Response linked to %(mission)s") % \
        #                                    dict(mission=mission)
        current.session.confirmation = T("Response linked to Mission")
        redirect(URL(c="deploy", f="email_inbox"))

    settings = current.deployment_settings
    resource = s3db.resource("deploy_mission",
                             filter=mission_query, vars=r.get_vars)

    # Filter widgets
    filter_widgets = s3db.get_config("deploy_mission", "filter_widgets")

    # List fields
    list_fields = s3db.get_config("deploy_mission", "list_fields")
    list_fields.insert(0, "id")

    # Data table
    totalrows = resource.count()
    if "iDisplayLength" in get_vars:
        display_length = int(get_vars["iDisplayLength"])
    else:
        display_length = 25
    limit = 4 * display_length
    filter, orderby, left = resource.datatable_filter(list_fields, get_vars)
    if not orderby:
        # Most recent missions on top
        orderby = "deploy_mission.created_on desc"
    resource.add_filter(filter)
    data = resource.select(list_fields,
                           start=0,
                           limit=limit,
                           orderby=orderby,
                           left=left,
                           count=True,
                           represent=True)

    filteredrows = data["numrows"]
    dt = S3DataTable(data["rfields"], data["rows"])
    dt_id = "datatable"

    if r.representation == "html":
        # Page load
        resource.configure(deletable = False)

        record = r.record
        action_vars = dict(mission_id="[id]")

        # Can we identify the Member?
        from ..s3.s3parser import S3Parsing
        from_address = record.from_address
        hr_id = S3Parsing().lookup_human_resource(from_address)
        if hr_id:
            action_vars["hr_id"] = hr_id

        s3 = response.s3
        s3.actions = [dict(label=str(T("Select Mission")),
                           _class="action-btn",
                           url=URL(f="email_inbox",
                                   args=[r.id, "select"],
                                   vars=action_vars,
                                   )),
                      ]
        s3.no_formats = True

        # Data table (items)
        items = dt.html(totalrows,
                        filteredrows,
                        dt_id,
                        dt_displayLength=display_length,
                        dt_ajax_url=r.url(representation="aadata"),
                        dt_bFilter="false",
                        dt_pagination="true",
                        )

        # Filter form
        if filter_widgets:

            # Where to retrieve filtered data from:
            _vars = resource.crud._remove_filters(r.get_vars)
            filter_submit_url = r.url(vars=_vars)

            # Where to retrieve updated filter options from:
            filter_ajax_url = URL(f="mission",
                                  args=["filter.options"],
                                  vars={})

            get_config = resource.get_config
            filter_clear = get_config("filter_clear", True)
            filter_formstyle = get_config("filter_formstyle", None)
            filter_submit = get_config("filter_submit", True)
            filter_form = S3FilterForm(filter_widgets,
                                       clear=filter_clear,
                                       formstyle=filter_formstyle,
                                       submit=filter_submit,
                                       ajax=True,
                                       url=filter_submit_url,
                                       ajaxurl=filter_ajax_url,
                                       _class="filter-form",
                                       _id="datatable-filter-form",
                                       )
            fresource = s3db.resource(resource.tablename)
            alias = resource.alias if r.component else None
            ff = filter_form.html(fresource,
                                  r.get_vars,
                                  target="datatable",
                                  alias=alias)
        else:
            ff = ""

        output = dict(items=items,
                      title=T("Select Mission"),
                      list_filter_form=ff)

        # Add RHeader
        if hr_id:
            from_address = A(from_address,
                             _href=URL(c="deploy", f="human_resource",
                                       args=[hr_id, "profile"],
                                       )
                             )
            row = ""
        else:
            id = "deploy_response_human_resource_id__row"
            # @ToDo: deployment_setting for 'Member' label
            title = T("Select Member")
            label = "%s:" % title
            field = s3db.deploy_response.human_resource_id
            # @ToDo: Get fancier & auto-click if there is just a single Mission
            script = \
'''S3.update_links=function(){
 var value=$('#deploy_response_human_resource_id').val()
 if(value){
  $('.action-btn.link').each(function(){
   var url=this.href
   var posn=url.indexOf('&hr_id=')
   if(posn>0){url=url.split('&hr_id=')[0]+'&hr_id='+value
   }else{url+='&hr_id='+value}
   $(this).attr('href',url)})}}'''
            s3.js_global.append(script)
            post_process = '''S3.update_links()'''
            widget = S3HumanResourceAutocompleteWidget(post_process=post_process)
            widget = widget(field, None)
            comment = DIV(_class="tooltip",
                          _title="%s|%s" % (title,
                                            current.messages.AUTOCOMPLETE_HELP))
            # @ToDo: Handle non-callable formstyles
            row = s3.crud.formstyle(id, label, widget, comment)
            if isinstance(row, tuple):
                row = TAG[""](row[0],
                              row[1],
                              )
        # Any attachments?
        if atts:
            attachments = TABLE(TR(TH("%s: " % T("Attachments"))))
            for a in atts:
                url = URL(c="default", f="download",
                          args=a.file)
                attachments.append(TR(TD(A(I(" ", _class="icon icon-paperclip"),
                                           a.name,
                                           _href=url))))
        else:
            attachments = ""
        # @ToDo: Add Reply button
        rheader = DIV(row,
                      TABLE(TR(TH("%s: " % T("From")),
                               from_address,
                               ),
                            TR(TH("%s: " % T("Date")),
                               record.created_on,
                               ),
                            TR(TH("%s: " % T("Subject")),
                               record.subject,
                               ),
                            TR(TH("%s: " % T("Message Text")),
                               ),
                            ),
                            DIV(record.body, _class="message-body s3-truncate"),
                            attachments,
                            )
        output["rheader"] = rheader
        s3_trunk8(lines=5)
        
        response.view = "list_filter.html"
        return output

    elif r.representation == "aadata":
        # Ajax refresh
        if "sEcho" in get_vars:
            echo = int(get_vars.sEcho)
        else:
            echo = None
        items = dt.json(totalrows,
                        filteredrows,
                        dt_id,
                        echo,
                        dt_bulk_actions=dt_bulk_actions)
        response.headers["Content-Type"] = "application/json"
        return items

    else:
        r.error(501, current.ERROR.BAD_FORMAT)

# =============================================================================
class deploy_MissionProfileLayout(S3DataListLayout):
    """ DataList layout for Mission Profile """

    # -------------------------------------------------------------------------
    def __init__(self):
        """ Constructor """

        self.dcount = {}
        self.avgrat = {}
        self.deployed = set()
        self.appraisals = {}

    # -------------------------------------------------------------------------
    def prep(self, resource, records):
        """
            Bulk lookups for cards

            @param resource: the resource
            @param records: the records as returned from S3Resource.select
        """

        db = current.db
        s3db = current.s3db
        
        tablename = resource.tablename
        if tablename == "deploy_alert":

            # Recipients, aggregated by region
            record_ids = set(record["_row"]["deploy_alert.id"]
                             for record in records)
            
            rtable = s3db.deploy_alert_recipient
            htable = s3db.hrm_human_resource
            otable = s3db.org_organisation
            
            left = [htable.on(htable.id==rtable.human_resource_id),
                    otable.on(otable.id==htable.organisation_id)]
                    
            alert_id = rtable.alert_id
            query = (alert_id.belongs(record_ids)) & \
                    (rtable.deleted != True)
                    
            region_id = otable.region_id
            number_of_recipients = htable.id.count()
            rows = current.db(query).select(alert_id,
                                            region_id,
                                            number_of_recipients,
                                            left=left,
                                            groupby=[alert_id, region_id])

            recipient_numbers = {}
            for row in rows:
                alert = row[alert_id]
                if alert in recipient_numbers:
                    recipient_numbers[alert].append(row)
                else:
                    recipient_numbers[alert] = [row]
            self.recipient_numbers = recipient_numbers

            # Representations of the region_ids
            represent = otable.region_id.represent
            represent.none = current.T("No Region")
            region_ids = [row[region_id] for row in rows]
            self.region_names = represent.bulk(region_ids)

        elif tablename == "deploy_response":

            dcount = self.dcount
            avgrat = self.avgrat
            deployed = self.deployed
            
            mission_id = None

            for record in records:
                raw = record["_row"]
                human_resource_id = raw["hrm_human_resource.id"]
                if human_resource_id:
                    dcount[human_resource_id] = 0
                    avgrat[human_resource_id] = None
                if not mission_id:
                    # Should be the same for all rows
                    mission_id = raw["deploy_response.mission_id"]

            hr_ids = dcount.keys()
            if hr_ids:

                # Number of previous deployments
                table = s3db.deploy_assignment
                human_resource_id = table.human_resource_id
                deployment_count = table.id.count()
                
                query = (human_resource_id.belongs(hr_ids)) & \
                        (table.deleted != True)
                rows = db(query).select(human_resource_id,
                                        deployment_count,
                                        groupby = human_resource_id,
                                        )
                for row in rows:
                    dcount[row[human_resource_id]] = row[deployment_count]

                # Members deployed for this mission
                query = (human_resource_id.belongs(hr_ids)) & \
                        (table.mission_id == mission_id) & \
                        (table.deleted != True)
                rows = db(query).select(human_resource_id)
                for row in rows:
                    deployed.add(row[human_resource_id])

                # Average appraisal rating
                atable = s3db.hrm_appraisal
                htable = s3db.hrm_human_resource
                human_resource_id = htable.id
                average_rating = atable.rating.avg()
                
                query = (human_resource_id.belongs(hr_ids)) & \
                        (htable.person_id == atable.person_id) & \
                        (atable.deleted != True) & \
                        (atable.rating != None) & \
                        (atable.rating > 0)

                rows = db(query).select(human_resource_id,
                                        average_rating,
                                        groupby = human_resource_id,
                                        )
                for row in rows:
                    avgrat[row[human_resource_id]] = row[average_rating]
                    
        elif tablename == "deploy_assignment":

            record_ids = set(record["_row"]["deploy_assignment.id"]
                             for record in records)
            
            atable = s3db.hrm_appraisal
            ltable = s3db.deploy_assignment_appraisal
            query = (ltable.assignment_id.belongs(record_ids)) & \
                    (ltable.deleted != True) & \
                    (atable.id == ltable.appraisal_id)
            rows = current.db(query).select(ltable.assignment_id,
                                            ltable.appraisal_id,
                                            )
            appraisals = {}
            for row in rows:
                appraisals[row.assignment_id] = row.appraisal_id
            self.appraisals = appraisals

        return

    # -------------------------------------------------------------------------
    def render_header(self, list_id, item_id, resource, rfields, record):
        """
            Render the card header

            @param list_id: the HTML ID of the list
            @param item_id: the HTML ID of the item
            @param resource: the S3Resource to render
            @param rfields: the S3ResourceFields to render
            @param record: the record as dict
        """

        # No card header in this layout
        return None

    # -------------------------------------------------------------------------
    def render_body(self, list_id, item_id, resource, rfields, record):
        """
            Render the card body

            @param list_id: the HTML ID of the list
            @param item_id: the HTML ID of the item
            @param resource: the S3Resource to render
            @param rfields: the S3ResourceFields to render
            @param record: the record as dict
        """

        db = current.db
        s3db = current.s3db
        has_permission = current.auth.s3_has_permission

        table = resource.table
        tablename = resource.tablename

        T = current.T
        pkey = str(resource._id)
        raw = record["_row"]
        record_id = raw[pkey]

        # Specific contents and workflow
        contents = workflow = None

        if tablename == "deploy_alert":

            # Message subject as title
            subject = record["deploy_alert.subject"]

            rows = self.recipient_numbers.get(record_id)
            total_recipients = 0
            if rows:
                
                # Labels
                hr_label = current.deployment_settings.get_deploy_hr_label()
                HR_LABEL = T(hr_label)
                if hr_label == "Member":
                    HRS_LABEL = T("Members")
                elif hr_label == "Staff":
                    HRS_LABEL = HR_LABEL
                elif hr_label == "Volunteer":
                    HRS_LABEL = T("Volunteers")
                    
                htable = s3db.hrm_human_resource
                otable = s3db.org_organisation
                region = otable.region_id
                rcount = htable.id.count()
                represent = region.represent
                
                region_names = self.region_names
                
                no_region = None
                recipients = []
                for row in rows:
                    # Region
                    region_id = row[region]
                    region_name = represent(region_id)
                    region_filter = {
                        "recipient.human_resource_id$" \
                        "organisation_id$region_id__belongs": region_id
                    }
                    # Number of recipients
                    num = row[rcount]
                    total_recipients += num
                    label = HR_LABEL if num == 1 else HRS_LABEL
                    # Link
                    link = URL(f = "alert",
                               args = [record_id, "recipient"],
                               vars = region_filter)
                    # Recipient list item
                    recipient = SPAN("%s (" % region_name,
                                     A("%s %s" % (num, label),
                                       _href=URL(f = "alert",
                                                 args = [record_id, "recipient"],
                                                 vars = region_filter),
                                       ),
                                     ")"
                                )
                    if region_id:
                        recipients.extend([recipient, ", "])
                    else:
                        no_region = [recipient, ", "]
                # Append "no region" at the end of the list
                if no_region:
                    recipients.extend(no_region)
                recipients = TAG[""](recipients[:-1])
            else:
                recipients = T("No Recipients Selected")

            # Modified-date corresponds to sent-date
            modified_on = record["deploy_alert.modified_on"]

            # Has this alert been sent?
            sent = True if raw["deploy_alert.message_id"] else False
            if sent:
                status = SPAN(I(_class="icon icon-sent"),
                              T("sent"), _class="alert-status")
            else:
                status = SPAN(I(_class="icon icon-unsent"),
                              T("not sent"), _class="red alert-status")

            # Message
            message = record["deploy_alert.body"]

            # Contents
            contents = DIV(
                           DIV(
                               DIV(subject,
                                   _class="card-title"),
                               DIV(recipients,
                                   _class="card-category"),
                               _class="media-heading"
                            ),
                            DIV(modified_on, status, _class="card-subtitle"),
                            DIV(message, _class="message-body s3-truncate"),
                            _class="media-body",
                       )

            # Workflow
            if not sent and total_recipients and \
               has_permission("update", table, record_id=record_id):
                send = A(I(" ", _class="icon icon-envelope-alt"),
                         SPAN(T("Send this Alert"),
                              _class="card-action"),
                         _onclick="window.location.href='%s'" %
                                  URL(c="deploy", f="alert",
                                      args=[record_id, "send"]),
                         _class="action-lnk",
                       )
                workflow = [send]

        elif tablename == "deploy_response":

            human_resource_id = raw["hrm_human_resource.id"]

            # Title linked to member profile
            if human_resource_id:
                person_id = record["hrm_human_resource.person_id"]
                profile_url = URL(f="human_resource", args=[human_resource_id, "profile"])
                profile_title = T("Open Member Profile (in a new tab)")
                person = A(person_id,
                        _href=profile_url,
                        _target="_blank",
                        _title=profile_title)
            else:
                person_id = "%s (%s)" % \
                            (T("Unknown"), record["msg_message.from_address"])
                person = person_id

            # Organisation
            organisation = record["hrm_human_resource.organisation_id"]

            # Created_on corresponds to received-date
            created_on = record["deploy_response.created_on"]

            # Message Data
            message = record["msg_message.body"]

            # Dropdown of available documents
            documents = raw["doc_document.file"]
            if documents:
                if not isinstance(documents, list):
                    documents = [documents]
                bootstrap = current.response.s3.formstyle == "bootstrap"
                if bootstrap:
                    docs = UL(_class="dropdown-menu",
                            _role="menu",
                            )
                else:
                    docs = SPAN(_id="attachments",
                                _class="profile-data-value",
                                )
                retrieve = db.doc_document.file.retrieve
                for doc in documents:
                    try:
                        doc_name = retrieve(doc)[0]
                    except (IOError, TypeError):
                        doc_name = current.messages["NONE"]
                    doc_url = URL(c="default", f="download",
                                args=[doc])
                    if bootstrap:
                        doc_item = LI(A(I(_class="icon-file"),
                                        " ",
                                        doc_name,
                                        _href=doc_url,
                                        ),
                                    _role="menuitem",
                                    )
                    else:
                        doc_item = A(I(_class="icon-file"),
                                    " ",
                                    doc_name,
                                    _href=doc_url,
                                    )
                    docs.append(doc_item)
                    docs.append(", ")
                if bootstrap:
                    docs = DIV(A(I(_class="icon-paper-clip"),
                                SPAN(_class="caret"),
                                _class="btn dropdown-toggle",
                                _href="#",
                                **{"_data-toggle": "dropdown"}
                                ),
                            doc_list,
                            _class="btn-group attachments dropdown pull-right",
                            )
                else:
                    # Remove final comma
                    docs.components.pop()
                    docs = DIV(LABEL("%s:" % T("Attachments"),
                                    _class = "profile-data-label",
                                    _for="attachments",
                                    ),
                            docs,
                            _class = "profile-data",
                            )
            else:
                docs = ""

            # Number of previous deployments and average rating
            # (looked up in-bulk in self.prep)
            if hasattr(self, "dcount"):
                dcount = self.dcount.get(human_resource_id, 0)
            if hasattr(self, "avgrat"):
                avgrat = self.avgrat.get(human_resource_id)
            dcount_id = "profile-data-dcount-%s" % record_id
            avgrat_id = "profile-data-avgrat-%s" % record_id
            dinfo = DIV(LABEL("%s:" % T("Previous Deployments"),
                              _for=dcount_id,
                              _class="profile-data-label"),
                        SPAN(dcount,
                             _id=dcount_id,
                             _class="profile-data-value"),
                        LABEL("%s:" % T("Average Rating"),
                              _for=avgrat_id,
                              _class="profile-data-label"),
                        SPAN(avgrat,
                             _id=avgrat_id,
                             _class="profile-data-value"),
                        _class="profile-data",
                    )

            # Comments
            comments_id = "profile-data-comments-%s" % record_id
            comments = DIV(LABEL("%s:" % T("Comments"),
                                _for=comments_id,
                                _class="profile-data-label"),
                        SPAN(record["deploy_response.comments"],
                                _id=comments_id,
                                _class="profile-data-value s3-truncate"),
                        _class="profile-data",
                        )

            # Contents
            contents = DIV(
                            DIV(
                                DIV(person,
                                    _class="card-title"),
                                DIV(organisation,
                                    _class="card-category"),
                                _class="media-heading",
                            ),
                            DIV(created_on, _class="card-subtitle"),
                            DIV(message, _class="message-body s3-truncate"),
                            docs,
                            dinfo,
                            comments,
                            _class="media-body",
                        )

            # Workflow
            if human_resource_id:
                if hasattr(self, "deployed") and human_resource_id in self.deployed:
                    deploy = A(I(" ", _class="icon icon-deployed"),
                               SPAN(T("Member Deployed"),
                                    _class="card-action"),
                               _class="action-lnk"
                             )
                elif has_permission("create", "deploy_assignment"):
                    mission_id = raw["deploy_response.mission_id"]
                    url = URL(f="mission",
                              args=[mission_id, "assignment", "create"],
                              vars={"member_id": human_resource_id})
                    deploy = A(I(" ", _class="icon icon-deploy"),
                               SPAN(T("Deploy this Member"),
                                    _class="card-action"),
                               _href=url,
                               _class="action-lnk"
                             )
                else:
                    deploy = None
                if deploy:
                    workflow = [deploy]

        elif tablename == "deploy_assignment":

            human_resource_id = raw["hrm_human_resource.id"]

            # Title linked to member profile
            profile_url = URL(f="human_resource", args=[human_resource_id, "profile"])
            profile_title = T("Open Member Profile (in a new tab)")
            person = A(record["hrm_human_resource.person_id"],
                       _href=profile_url,
                       _target="_blank",
                       _title=profile_title)

            # Organisation
            organisation = record["hrm_human_resource.organisation_id"]

            fields = dict((rfield.colname, rfield) for rfield in rfields)
            render = lambda colname: self.render_column(item_id,
                                                        fields[colname],
                                                        record)

            # Contents
            contents = DIV(
                            DIV(
                                DIV(person,
                                    _class="card-title"),
                                DIV(organisation,
                                    _class="card-category"),
                                _class="media-heading"),
                            render("deploy_assignment.start_date"),
                            render("deploy_assignment.end_date"),
                            render("deploy_assignment.job_title_id"),
                            render("hrm_appraisal.rating"),
                            _class="media-body",
                       )

            # Workflow actions
            appraisal = self.appraisals.get(record_id)
            person_id = raw["hrm_human_resource.person_id"]
            if appraisal and \
               has_permission("update", "hrm_appraisal", record_id=appraisal.id):
                # Appraisal already uploaded => edit
                EDIT_APPRAISAL = T("Open Appraisal")
                url = URL(c="deploy", f="person",
                          args=[person_id,
                                "appraisal",
                                appraisal.id,
                                "update.popup"
                               ],
                          vars={"refresh": list_id,
                                "record": record_id
                               })
                edit = A(I(" ", _class="icon icon-paperclip"),
                         SPAN(EDIT_APPRAISAL, _class="card-action"),
                         _href=url,
                         _class="s3_modal action-lnk",
                         _title=EDIT_APPRAISAL,
                       )
                workflow = [edit]

            elif has_permission("update", table, record_id=record_id):
                # No appraisal uploaded yet => upload
                # Currently we assume that anyone who can edit the
                # assignment can upload the appraisal
                _class = "action-lnk"
                UPLOAD_APPRAISAL = T("Upload Appraisal")
                mission_id = raw["deploy_assignment.mission_id"]
                url = URL(c="deploy", f="person",
                          args=[person_id,
                                "appraisal",
                                "create.popup"
                               ],
                          vars={"mission_id": mission_id,
                                "refresh": list_id,
                                "record": record_id,
                               })
                upload = A(I(" ", _class="icon icon-paperclip"),
                           SPAN(UPLOAD_APPRAISAL, _class="card-action"),
                           _href=url,
                           _class="s3_modal action-lnk",
                           _title=UPLOAD_APPRAISAL,
                         )
                workflow = [upload]

        body = DIV(_class="media")

        # Body icon
        icon = self.render_icon(list_id, resource)
        if icon:
            body.append(icon)

        # Toolbox and workflow actions
        toolbox = self.render_toolbox(list_id, resource, record)
        if toolbox:
            if workflow:
                toolbox.insert(0, DIV(workflow, _class="card-actions"))
            body.append(toolbox)

        # Contents
        if contents:
            body.append(contents)

        return body

    # -------------------------------------------------------------------------
    def render_icon(self, list_id, resource):
        """
            Render the body icon

            @param list_id: the list ID
            @param resource: the S3Resource
        """

        tablename = resource.tablename

        if tablename == "deploy_alert":
            icon = "alert.png"
        elif tablename == "deploy_response":
            icon = "email.png"
        elif tablename == "deploy_assignment":
            icon = "member.png"
        else:
            return None

        return A(IMG(_src=URL(c="static", f="themes",
                              args=["IFRC", "img", icon]),
                     _class="media-object",
                 ),
                 _class="pull-left",
               )

    # -------------------------------------------------------------------------
    def render_toolbox(self, list_id, resource, record):
        """
            Render the toolbox

            @param list_id: the HTML ID of the list
            @param resource: the S3Resource to render
            @param record: the record as dict
        """

        table = resource.table
        tablename = resource.tablename
        record_id = record[str(resource._id)]

        open_url = update_url = None
        if tablename == "deploy_alert":
            open_url = URL(f="alert", args=[record_id])

        elif tablename == "deploy_response":
            update_url = URL(f="response_message",
                            args=[record_id, "update.popup"],
                            vars={"refresh": list_id, "record": record_id})

        elif tablename == "deploy_assignment":
            update_url = URL(c="deploy", f="assignment",
                            args=[record_id, "update.popup"],
                            vars={"refresh": list_id, "record": record_id})

        has_permission = current.auth.s3_has_permission
        crud_string = S3Method.crud_string

        toolbox = DIV(_class="edit-bar fright")

        if update_url and \
           has_permission("update", table, record_id=record_id):
            btn = A(I(" ", _class="icon icon-edit"),
                    _href=update_url,
                    _class="s3_modal",
                    _title=crud_string(tablename, "title_update"))
            toolbox.append(btn)
        elif open_url:
            btn = A(I(" ", _class="icon icon-file-alt"),
                    _href=open_url,
                    _title=crud_string(tablename, "title_display"))
            toolbox.append(btn)

        if has_permission("delete", table, record_id=record_id):
            btn = A(I(" ", _class="icon icon-trash"),
                    _class="dl-item-delete",
                    _title=crud_string(tablename, "label_delete_button"))
            toolbox.append(btn)

        return toolbox

    # -------------------------------------------------------------------------
    def render_column(self, item_id, rfield, record):
        """
            Render a data column.

            @param item_id: the HTML element ID of the item
            @param rfield: the S3ResourceField for the column
            @param record: the record (from S3Resource.select)
        """

        colname = rfield.colname
        if colname not in record:
            return None

        value = record[colname]
        value_id = "%s-%s" % (item_id, rfield.colname.replace(".", "_"))

        label = LABEL("%s:" % rfield.label,
                      _for = value_id,
                      _class = "profile-data-label")

        value = SPAN(value,
                     _id = value_id,
                     _class = "profile-data-value")

        return TAG[""](label, value)

# END =========================================================================
