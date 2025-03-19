# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging
from logging import exception
from pydoc import render_doc

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiam.v3 import KeystoneListProjectsRequest
from huaweicloudsdktms.v1 import CreateResourceTagRequest, ReqCreateTag, ReqDeleteTag, DeleteResourceTagRequest

from c7n.exceptions import PolicyValidationError, PolicyExecutionError

from c7n.utils import type_schema, chunks, local_session

from c7n_huaweicloud.actions import HuaweiCloudBaseAction


def register_tms_actions(actions):
    actions.register('mark', CreateResourceTagAction)
    actions.register('tag', CreateResourceTagAction)

    actions.register('unmark', DeleteResourceTagAction)
    actions.register('untag', DeleteResourceTagAction)
    actions.register('remove-tag', DeleteResourceTagAction)
    actions.register('rename-tag', RenameResourceTagAction)


class CreateResourceTagAction(HuaweiCloudBaseAction):
    """Applies one or more tags to the specified resources.

    :example:

        .. code-block :: yaml

            policies:
            - name: multiple-tags-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: tag
                  tags:
                    owner: 123
                    owner2: 456
    """

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
        if not self.data.get('key') and not self.data.get('tag') and self.data.get('value'):
            raise PolicyValidationError("value must be used with key or tag")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        value = self.data.get('value')
        key = self.data.get('key') or self.data.get('tag')
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
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_type"]}
                     for resource in resources
                     if "tag_type" in resource.keys() and len(resource['tag_type']) > 0]

        for resource_batch in chunks(resources, self.resource_max_size):
            try:
                self.process_resource_set(tms_client, resource_batch, tags, project_id)
            except exceptions.ClientRequestException as ex:
                self.log.exception(
                    f"Unable to tagged {len(resource_batch)} resources RequestId: {ex.request_id}, Reason: {ex.error_msg}")
                self.handle_exception(failed_resources=resource_batch)
        return self.process_result(resources=resources)

    def perform_action(self, resource):
        pass

    def handle_exception(self, failed_resources, resources):
        self.failed_resources.extend(failed_resources)
        for failed_resource in failed_resources:
            resources.remove(failed_resource)

    def process_resource_set(self, client, resource_batch, tags, project_id):
        request_body = ReqCreateTag(project_id=project_id, resources=resource_batch, tags=tags)
        request = CreateResourceTagRequest(body=request_body)
        client.create_resource_tag(request=request)
        self.log.info("Successfully tagged %s resources with %s tags", len(resource_batch), len(tags))

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

class DeleteResourceTagAction(HuaweiCloudBaseAction):
    """Removes the specified tags from the specified resources.

    :example:

        .. code-block :: yaml

            policies:
            - name: multiple-untags-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: untag
                  tags:
                    owner: 123
                    owner2: 456
    """

    log = logging.getLogger("custodian.huaweicloud.actions.DeleteResourceTagAction")

    schema = type_schema("remove-tag", aliases=('unmark', 'untag', 'remove-tag'),
                         tags={'type': 'object'})
    resource_max_size = 50
    tags_max_size = 10

    def validate(self):
        """validate"""
        if not self.data.get('tags') or len(self.data.get('tags')) == 0:
            raise PolicyValidationError("Can not perform remove tag without tags")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        tags = self.data.get("tags")

        if tags:
            tags = [{"key": k, "value": v} for k, v in tags.items()]
        else:
            tags = []

        if len(tags) > self.tags_max_size:
            self.log.error("Can not remove tag more than %s tags at once", self.tags_max_size)
            raise PolicyValidationError("Can not remove tag more than %s tags at once", self.tags_max_size)

        tms_client = self.get_tag_client()
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_type"]}
                     for resource in resources
                     if "tag_type" in resource.keys() and len(resource['tag_type']) > 0]

        for resource_batch in chunks(resources, self.resource_max_size):
            try:
                self.process_resource_set(tms_client, resource_batch, tags, project_id)
            except exceptions.ClientRequestException as ex:
                self.log.exception(
                    f"Unable to remove tag {len(resource_batch)} resources RequestId: {ex.request_id}, Reason: {ex.error_msg}")
                self.handle_exception(failed_resources=resource_batch)
        return self.process_result(resources=resources)

    def perform_action(self, resource):
        pass

    def handle_exception(self, failed_resources, resources):
        self.failed_resources.extend(failed_resources)
        for failed_resource in failed_resources:
            resources.remove(failed_resource)

    def process_resource_set(self, client, resource_batch, tags, project_id):
        request_body = ReqDeleteTag(project_id=project_id, resources=resource_batch, tags=tags)
        request = DeleteResourceTagRequest(body=request_body)
        client.delete_resource_tag(request=request)
        self.log.info("Successfully remove tag %s resources with %s tags", len(resource_batch), len(tags))

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


class RenameResourceTagAction(HuaweiCloudBaseAction):
    """Rename the specified tags from the specified resources.

    :example:

        .. code-block :: yaml

            policies:
            - name: multiple-rename-tag-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: rename-tag
                  value: 123
                  old_key: owner-old
                  new_key: owner-new
    """

    log = logging.getLogger("custodian.huaweicloud.actions.RenameResourceTagAction")

    schema = type_schema("rename-tag",
                         value={'type': 'string'},
                         old_key={'type': 'string'},
                         new_key={'type': 'string'})
    resource_max_size = 50

    def validate(self):
        """validate"""
        if not self.data.get('value'):
            raise PolicyValidationError("Can not perform rename tag without value")
        if not self.data.get('old_key'):
            raise PolicyValidationError("Can not perform rename tag without old_key")
        if not self.data.get('new_key'):
            raise PolicyValidationError("Can not perform rename tag without new_key")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        value = self.data.get('value')
        old_key = self.data.get('old_key')
        new_key = self.data.get('new_key')

        old_tags = [{"key": old_key, "value": value}]
        new_tags = [{"key": new_key, "value": value}]

        tms_client = self.get_tag_client()
        resources = self.filter_resources(resources)
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_type"]}
                     for resource in resources
                     if "tag_type" in resource.keys() and len(resource['tag_type']) > 0]

        for resource_batch in chunks(resources, self.resource_max_size):
            try:
                self.process_resource_set(tms_client, resource_batch, old_tags, new_tags, project_id)
            except exceptions.ClientRequestException as ex:
                self.log.exception(
                    f"Unable to rename tag {len(resource_batch)} resources RequestId: {ex.request_id}, Reason: {ex.error_msg}")
                self.handle_exception(failed_resources=resource_batch)
        return self.process_result(resources=resources)

    def perform_action(self, resource):
        pass

    def filter_resources(self, resources):
        old_key = self.data.get('old_key')
        return [resource for resource in resources if old_key in resource.get('tags')]

    def handle_exception(self, failed_resources, resources):
        self.failed_resources.extend(failed_resources)
        for failed_resource in failed_resources:
            resources.remove(failed_resource)

    def process_resource_set(self, client, resource_batch, old_tags, new_tags, project_id):
        request_body = ReqDeleteTag(project_id=project_id, resources=resource_batch, tags=old_tags)
        request = DeleteResourceTagRequest(body=request_body)
        client.delete_resource_tag(request=request)
        self.log.info("Successfully remove tag %s resources with %s tags", len(resource_batch), len(old_tags))

        request_body = ReqCreateTag(project_id=project_id, resources=resource_batch, tags=new_tags)
        request = CreateResourceTagRequest(body=request_body)
        client.create_resource_tag(request=request)
        self.log.info("Successfully tagged %s resources with %s tags", len(resource_batch), len(new_tags))

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
