# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

from huaweicloudsdkiam.v3 import KeystoneListProjectsRequest
from huaweicloudsdktms.v1 import CreateResourceTagRequest, ReqCreateTag

from c7n.exceptions import PolicyValidationError, PolicyExecutionError

from c7n.utils import type_schema, chunks, local_session

from c7n_huaweicloud.actions import HuaweiCloudBaseAction

DEFAULT_TAG = "default_tag"


def register_tags_actions(actions):
    actions.register('mark', CreateResourceTagAction)
    actions.register('tag', CreateResourceTagAction)


class CreateResourceTagAction(HuaweiCloudBaseAction):

    log = logging.getLogger("custodian.huaweicloud.actions.CreateResourceTagAction")

    schema = type_schema("tag", aliases=('mark',),
                         tags={'type': 'object'},
                         key={'type': 'string'},
                         value={'type': 'string'},
                         tag={'type': 'string'})
    resource_max_size = 50
    tags_max_size = 10

    def validate(self):
        """validate"""
        if self.data.get('key') and self.data.get('tag'):
            raise PolicyValidationError("Can not both use key and tag at once")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        value = self.data.get('value')
        key = self.data.get('key') or self.data.get('tag') or DEFAULT_TAG
        tags = self.data.get("tags")

        if tags:
            tags = [{"key": k, "value": v} for k, v in tags.items()]
        else:
            tags = []

        if value:
            tags.append({"key": key, "value": value})

        if len(tags) > self.tags_max_size:
            self.log.error("Can not tag more than %s tags at once", self.tags_max_size)
            raise PolicyValidationError("Can not tag more than %s tags at once", self.tags_max_size)

        tms_client = self.get_tag_client()
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_type"]} for resource in resources]
        for resource_batch in chunks(resources, self.resource_max_size):
                self.process_resource_set(tms_client, resource_batch, tags, project_id)

    def perform_action(self, resource):
        pass


    def process_resource_set(self, client, resource_batch, tag_batch, project_id):
        request_body = ReqCreateTag(project_id=project_id, resources=resource_batch, tags=tag_batch)
        request = CreateResourceTagRequest(body=request_body)
        client.create_resource_tag(request=request)
        self.log.info("Successfully tagged %s resources with %s tags", len(resource_batch), len(tag_batch))


    def get_project_id(self):
        iam_client = local_session(self.manager.session_factory).client("iam")

        region = local_session(self.manager.session_factory).region
        request = KeystoneListProjectsRequest(name=region)
        response = iam_client.keystone_list_projects(request=request)
        for project in response.projects:
            if (region == project.name):
                return project.id

        self.log.error("Can not get project_id for %s", region)
        raise PolicyExecutionError("Can not get project_id for %s", region)
