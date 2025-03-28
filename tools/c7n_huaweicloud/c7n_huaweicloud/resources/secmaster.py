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
        tag_resource_type = "secmaster"


@Secmaster.action_registry.register("updatePlaybook")
class updatePlaybook(HuaweiCloudBaseAction):
    """Deletes EVS Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-unencrypted-volume
            resource: huaweicloud.secmaster
            flters:
              - type: value
                key: metadata.__system__encrypted
                value: "高危告警自动通知"
            actions:
              - updatePlaybook
    """

    schema = type_schema("updatePlaybook")


def perform_action(self, resource):
    print(resource)
    if resource["is_view"]:
        return

    workspace_id = resource["id"]
    client = self.manager.get_client()

    request = ListPlaybooksRequest(workspace_id=workspace_id, offset=0, limit=1000)
    request.content_type = "application/json;charset=UTF-8"
    response = client.list_playbooks(request)

    for data in response.data:
        if data.name != "高危告警自动通知":
            continue

        playbook_id = data.id
        body = ModifyPlaybookInfo(enabled=True)
        request = UpdatePlaybookRequest(
            playbook_id=playbook_id, workspace_id=workspace_id, body=body
        )
        response = client.update_playbook(request)

    return response
