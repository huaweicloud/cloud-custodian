# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdksecmaster.v2 import (
    ListPlaybooksRequest,
    UpdatePlaybookRequest,
    ModifyPlaybookInfo,
)

log = logging.getLogger("custodian.huaweicloud.resources.secmaster")


@resources.register("secmaster")
class Secmaster(QueryResourceManager):
    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_workspaces", "workspaces", "offset")
        id = "id"
        tag_resource_type = ""


@Secmaster.action_registry.register("enable-playbook")
class enablePlaybook(HuaweiCloudBaseAction):
    """enable-high-risk-alert-playbook.

    :Example:

    .. code-block:: yaml

        policies:
          - name: enable-high-risk-alert-playbook
            resource: huaweicloud.secmaster
            filters:
              - type: value
                key: name
                value: "Automatic notification of high-risk alerts"
            actions:
              - enable-playbook
    """

    schema = type_schema("enable-playbook", name={"type": "string"})

    def perform_action(self, resource):

        if resource["is_view"]:
            return

        workspace_id = resource["id"]
        client = self.manager.get_client()

        request = ListPlaybooksRequest(workspace_id=workspace_id, offset=0, limit=1000)
        request.content_type = "application/json;charset=UTF-8"
        response = client.list_playbooks(request)

        for data in response.data:
            if data.name != self.data.get(
                "name", "Automatic notification of high-risk alerts"
            ):
                continue
            if data.enabled:
                continue
            playbook_version_id = data.version_id
            playbook_id = data.id
            playbook_name = data.name
            body = ModifyPlaybookInfo(
                enabled=True, name=playbook_name, active_version_id=playbook_version_id
            )
            request = UpdatePlaybookRequest(
                playbook_id=playbook_id, workspace_id=workspace_id, body=body
            )
            response = client.update_playbook(request)

        return response
