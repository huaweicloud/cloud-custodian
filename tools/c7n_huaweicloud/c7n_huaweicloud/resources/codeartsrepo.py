# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import time

from huaweicloudsdkcodehub.v4 import CreateProjectProtectedBranchesRequest
from huaweicloudsdkcodehub.v4 import ListProjectProtectedBranchesRequest
from huaweicloudsdkcodehub.v4 import ProjectSettingsInheritCfgDto
from huaweicloudsdkcodehub.v4 import ProtectedActionBasicApiDto
from huaweicloudsdkcodehub.v4 import ProtectedBranchBodyApiDto
from huaweicloudsdkcodehub.v4 import SettingsInheritCfgBodyApiDto
from huaweicloudsdkcodehub.v4 import ShowProjectWatermarkRequest
from huaweicloudsdkcodehub.v4 import UpdateProjectSettingsInheritCfgRequest
from huaweicloudsdkcodehub.v4 import UpdateProjectWatermarkRequest
from huaweicloudsdkcodehub.v4 import UpdateWatermarkDto
from huaweicloudsdkcore.exceptions import exceptions

from c7n.filters import Filter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.codeartsrepo-project")


@resources.register("codeartsrepo-project")
class CodeArtsRepoProject(QueryResourceManager):
    class resource_type(TypeInfo):
        service = "codeartsrepo-project"
        enum_spec = ("list_projects_v4", "projects", "offset")
        id = "project_id"
        tag_resource_type = False


@CodeArtsRepoProject.filter_registry.register('not-opened')
class WatermarkFilter(Filter):
    schema = type_schema("opened")

    def process(self, resources, event=None):
        """ CodeArts Repo watermark not opened filter
        Filters the project that not opened watermark
        :example:
        .. code-block:: yaml

            policies:
              - name: not-opened
              resource: huaweicloud.codeartsrepo-project
              filters:
                - tyee: opened
        """
        results = []
        for resource in resources:
            time.sleep(1)
            project_id = resource["id"]
            # no permission
            response, has_permission = self.query_project_watermark_status(project_id)
            if not has_permission:
                continue
            # watermark has opened
            response = json.loads(str(response))
            is_open_watermark = response.get("watermark")
            if is_open_watermark:
                log.info(
                    "[filters]-{codehub-project-filter-watermark} watermark of project_id: [%s] "
                    "already opened, skip.", project_id)
                continue
            # can not update
            can_update = response.get("can_update")
            if not can_update:
                log.warning("[filters]-{codehub-project-filter-watermark} no permission open "
                            "project watermark for project_id: [%s], skip.", project_id)
                continue
            results.append(resource)
        return results

    def get_codehub_client(self):
        return local_session(self.manager.session_factory).client("codeartsrepo")

    def query_project_watermark_status(self, project_id):
        request = ShowProjectWatermarkRequest()
        request.project_id = project_id
        try:
            response = self.get_codehub_client().show_project_watermark(request)
            log.info(
                "[filters]-{codehub-project-filter-watermark} with project_id: [%s]"
                "query project watermark success, response: [%s]",
                project_id, response)
        except exceptions.ClientRequestException as e:
            if e.status_code == 403:
                log.warning(
                    "[filters]-{codehub-project-filter-watermark} with request:[%s]"
                    "query project watermark no permission, cause: "
                    "status_code[%s] request_id[%s]", request, e.status_code, e.request_id)
                return {}, False
            log.error(
                "[filters]-{codehub-project-filter-watermark} with request:[%s]"
                "query project watermark status failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                request, e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response, True


@CodeArtsRepoProject.action_registry.register("open-watermark")
class CodeaArtsRepoProjectOpenWaterMark(HuaweiCloudBaseAction):
    """ CodeArtsRepo open watermark for project.

    :Example:

    .. code-block:: yaml

        policies:
          - name: CodeArtsRepo-project-open-watermark
          resource: huaweicloud.codeartsrepo-project
          filters:
            - type: value
              key: id
              value: ${id}
          actions:
            - type: open-watermark

    """
    schema = type_schema("open-watermark")

    def perform_action(self, resource):
        time.sleep(1)
        project_id = resource["id"]
        try:
            response, has_permission = self.open_project_watermark(project_id)
            if not has_permission:
                return {}
            log.info(
                "[actions]-{codehub-project-open-watermark} open project watermark for"
                " project_id: [%s] success.", project_id)
        except exceptions.ClientRequestException:
            log.error("[actions]-{codehub-project-open-watermark} for project_id:[%s] "
                      "failed.", project_id)
            raise
        return response

    def get_codehub_client(self):
        return local_session(self.manager.session_factory).client("codeartsrepo")

    def open_project_watermark(self, project_id):
        request = UpdateProjectWatermarkRequest()
        request.project_id = project_id
        request.body = UpdateWatermarkDto(
            watermark=True
        )
        try:
            response = self.get_codehub_client().update_project_watermark(request)
            log.info(
                "[actions]-{codehub-project-open-watermark} with project_id:[%s] "
                "open project watermark success.", project_id)
        except exceptions.ClientRequestException as e:
            if e.status_code == 403:
                log.warning(
                    "[actions]-{codehub-project-open-watermark} with request:[%s]"
                    "open project watermark no permission, cause: "
                    "status_code[%s] request_id[%s]", request, e.status_code, e.request_id)
                return {}, False
            log.error(
                "[actions]-{codehub-project-open-watermark} with request:[%s]"
                "open project watermark failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                request, e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response, True


@CodeArtsRepoProject.filter_registry.register('not-protected')
class ProtectedBranchFilter(Filter):
    schema = type_schema("protected")

    def process(self, resources, event=None):
        """ CodeArts Repo watermark not opened filter
        Filters the project that not opened watermark
        :example:
        .. code-block:: yaml

            policies:
              - name: not-protected
              resource: huaweicloud.codeartsrepo-project
              filters:
                - tyee: protected
        """
        results = []
        for resource in resources:
            time.sleep(1)
            project_id = resource["id"]
            # no permission
            protected_branches, has_permission = self.query_project_protected_branches(project_id)
            if not has_permission:
                continue

            # no need to protecte
            if not self.need_create_protected_branches(protected_branches):
                log.info(
                    "[filter]-{codehub-project-protected-branches} has protected branches for"
                    " project_id: [%s], skip.", project_id)
                continue

            results.append(resource)
        return results

    def get_codehub_client(self):
        return local_session(self.manager.session_factory).client("codeartsrepo")

    def need_create_protected_branches(self, protected_branches):
        if len(protected_branches) > 0:
            return False
        else:
            return True

    def query_project_protected_branches(self, project_id):
        request = ListProjectProtectedBranchesRequest()
        request.project_id = project_id
        request.user_actions = True
        protected_branches = []
        offset = 0
        limit = 20
        while True:
            request.offset = offset
            request.limit = limit
            try:
                response = self.get_codehub_client().list_project_protected_branches(request)
                log.info(
                    "[filter]-{codehub-project-protected-branches} with project_id: [%s]"
                    "query project protected branches success, response: [%s]",
                    project_id, response)
                response = json.loads(str(response))
                if response.get("body") is None:
                    break
                if len(protected_branches) == 0:
                    protected_branches = response.get("body")
                else:
                    protected_branches.extend(response.get("body"))
                if len(protected_branches) < limit:
                    break
                offset += limit
            except exceptions.ClientRequestException as e:
                if e.status_code == 403:
                    # user has no permission to process
                    log.warning(
                        "[filter]-{codehub-project-protected-branches}  with request:[%s]"
                        "query project protected branches no permission, cause: "
                        "status_code[%s] request_id[%s]", request, e.status_code, e.request_id)
                    return [], False
                log.error(
                    "[filter]-{codehub-project-protected-branches}  with request:[%s]"
                    "query project protected branches failed, cause: "
                    "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                    request, e.status_code, e.request_id, e.error_code, e.error_msg)
                raise
        return protected_branches, True


@CodeArtsRepoProject.action_registry.register("create-protected-branches")
class CodeaArtsRepoProjectCreateProtectedBranches(HuaweiCloudBaseAction):
    """ CodeArtsRepo create protected branches for project.

    :Example:

    .. code-block:: yaml

        policies:
          - name: CodeArtsRepo-project-create-protected-branches
          resource: huaweicloud.codeartsrepo-project
          filters:
            - type: value
              key: id
              value: ${id}
          actions:
            - type: create-protected-branches
    """

    schema = type_schema("create-protected-branches")

    def perform_action(self, resource):
        time.sleep(1)
        response = {}
        project_id = resource["id"]
        branch_name = "*"
        push_action = "push"
        push_enable = True
        push_user_ids = []
        push_user_team_ids = []
        push_related_role_ids = []
        merge_action = "merge"
        merge_enable = True
        merge_user_ids = []
        merge_user_team_ids = []
        merge_related_role_ids = []

        try:
            list_actions_body = [
                ProtectedActionBasicApiDto(
                    action=push_action,
                    enable=push_enable,
                    user_ids=push_user_ids,
                    user_team_ids=push_user_team_ids,
                    related_role_ids=push_related_role_ids
                ),
                ProtectedActionBasicApiDto(
                    action=merge_action,
                    enable=merge_enable,
                    user_ids=merge_user_ids,
                    user_team_ids=merge_user_team_ids,
                    related_role_ids=merge_related_role_ids
                )
            ]
            response, has_permission = self.create_project_protected_branches(project_id,
                                                                              list_actions_body,
                                                                              branch_name)
            if not has_permission:
                return response
            log.info(
                "[actions]-{codehub-project-create-protected-branches} create protected branches "
                "for project_id: [%s] success.", project_id)
        except exceptions.ClientRequestException:
            log.error("[actions]-{codehub-project-create-protected-branches} for "
                      "project_id:[%s] failed.", project_id)
            raise
        return response

    def get_codehub_client(self):
        return local_session(self.manager.session_factory).client("codeartsrepo")

    def create_project_protected_branches(self, project_id, list_actions_body, branch_name):
        request = CreateProjectProtectedBranchesRequest()
        request.project_id = project_id
        request.body = ProtectedBranchBodyApiDto(
            actions=list_actions_body,
            name=branch_name
        )

        try:
            response = self.get_codehub_client().create_project_protected_branches(request)
            log.info(
                "[actions]-{codehub-project-create-protected-branches} with project_id:[%s] "
                "create project protected branches success.", project_id)
        except exceptions.ClientRequestException as e:
            if e.status_code == 403:
                # user has no permission to process
                log.warning(
                    "[actions]-{codehub-project-create-protected-branches} with request:[%s]"
                    "create project protected branches no permission, cause: "
                    "status_code[%s] request_id[%s]", request, e.status_code, e.request_id)
                return [], False
            log.error(
                "[actions]-{codehub-project-create-protected-branches} with request:[%s]"
                "create project protected branches failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                request, e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response, True


@CodeArtsRepoProject.action_registry.register("set-project-inherit-settings")
class CodeaArtsRepoProjectSetSettings(HuaweiCloudBaseAction):
    """ CodeArtsRepo set project settings.

    :Example:

    .. code-block:: yaml

        policies:
          - name: CodeArtsRepo-project-set-settings
          resource: huaweicloud.codeartsrepo-project
          filters:
            - type: value
              key: id
              value: ${id}
          actions:
            - type: set-project-inherit-settings
              protected_branches_enable: True
              watermark_enable: True

    """
    schema = type_schema("set-project-inherit-settings",
                         protected_branches_enable={'type': 'boolean'},
                         watermark_enable={'type': 'boolean'})

    def perform_action(self, resource):
        time.sleep(1)
        project_id = resource["id"]
        protected_branches_enable = self.data.get("protected_branches_enable")
        watermark_enable = self.data.get("watermark_enable")

        if protected_branches_enable:
            protected_branches_inherit_mod = "force_inherit"
        else:
            protected_branches_inherit_mod = "custom"
        if watermark_enable:
            watermark_inherit_mod = "force_inherit"
        else:
            watermark_inherit_mod = "custom"

        list_data_body = [
            ProjectSettingsInheritCfgDto(
                name="protected_branches",
                inherit_mod=protected_branches_inherit_mod,
            ),
            ProjectSettingsInheritCfgDto(
                name="watermark",
                inherit_mod=watermark_inherit_mod,
            )
        ]
        try:
            response = self.set_project_settings(project_id, list_data_body)
            log.info(
                "[actions]-{codehub-project-set-settings} set settings "
                "protected_branches and watermark "
                "for project_id: [%s] success.", project_id)
        except exceptions.ClientRequestException:
            log.error(
                "[actions]-{codehub-project-set-settings} set settings "
                "protected_branches and watermark "
                "for project_id:[%s] failed.", project_id)
            raise
        return response

    def get_codehub_client(self):
        return local_session(self.manager.session_factory).client("codeartsrepo")

    def set_project_settings(self, project_id, list_data_body):
        request = UpdateProjectSettingsInheritCfgRequest()
        request.project_id = project_id

        request.body = SettingsInheritCfgBodyApiDto(
            data=list_data_body
        )
        try:
            response = self.get_codehub_client().update_project_settings_inherit_cfg(request)
            log.info(
                "[actions]-{codehub-project-set-settings} with project_id:[%s] "
                "set project settings success.", project_id)
        except exceptions.ClientRequestException as e:
            if e.status_code == 403:
                log.warning(
                    "[actions]-{codehub-project-set-settings} has no permission to set settings "
                    "protected_branches and watermark with request:[%s]", request)
                return {}
            log.error(
                "[actions]-{codehub-project-set-settings} with request:[%s]"
                "set project settings failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                request, e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response
