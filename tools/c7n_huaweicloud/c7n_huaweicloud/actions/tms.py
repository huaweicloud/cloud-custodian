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

    log = logging.getLogger("custodian.huaweicloud.actions.tms.CreateResourceTagAction")

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
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}
                     for resource in resources
                     if "tag_resource_type" in resource.keys() and len(resource['tag_resource_type']) > 0]

        for resource_batch in chunks(resources, self.resource_max_size):
            try:
                failed_resources = self.process_resource_set(tms_client, resource_batch, tags, project_id)
                self.handle_exception(failed_resources=failed_resources)
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
        response = client.create_resource_tag(request=request)
        failed_resource_ids = [failed_resource.get("resource_id", "") for failed_resource in
                               response.failed_resources()]
        self.log.info("Successfully tagged %s resources with %s tags", 
                      len(resource_batch) -len(failed_resource_ids), len(tags))
        return [resource for resource in resource_batch if resource["resource_id"] in failed_resource_ids]

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
                    owner
                    owner2

            policies:
            - name: multiple-untags-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: untag
                  tag_values:
                    owner: 123
                    owner2: 456
    """

    log = logging.getLogger("custodian.huaweicloud.actions.tms.DeleteResourceTagAction")

    schema = type_schema("remove-tag", aliases=('unmark', 'untag', 'remove-tag'),
                         tags={'type': 'string'}, tag_values={'type': 'object'})
    resource_max_size = 50
    tags_max_size = 10

    def validate(self):
        """validate"""
        if self.data.get('tags') and self.data.get('tag_values'):
            raise PolicyValidationError("Can not both use tags and tag_values at once")
        if not self.data.get('tag_values') or len(self.data.get('tag_values')) == 0:
            raise PolicyValidationError("Can not perform remove tag when tag_values is empty")
        if not self.data.get('tags') or len(self.data.get('tags')) == 0:
            raise PolicyValidationError("Can not perform remove tag when tags is empty")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        tag_values = self.data.get("tag_values", [])
        tags = self.data.get("tags", [])

        if tag_values:
            key_values = [{"key": k, "value": v} for k, v in tag_values.items()]
        else:
            key_values = [{"key": k} for k in tags.items()]

        if len(key_values) > self.tags_max_size:
            self.log.error("Can not remove tag more than %s tags at once", self.tags_max_size)
            raise PolicyValidationError("Can not remove tag more than %s tags at once", self.tags_max_size)

        tms_client = self.get_tag_client()
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}
                     for resource in resources
                     if "tag_resource_type" in resource.keys() and len(resource['tag_resource_type']) > 0]

        for resource_batch in chunks(resources, self.resource_max_size):
            try:
                failed_resources = self.process_resource_set(tms_client, resource_batch, key_values, project_id)
                self.handle_exception(failed_resources=failed_resources)
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
        response = client.delete_resource_tag(request=request)
        failed_resource_ids = [failed_resource.get("resource_id", "") for failed_resource in response.failed_resources()]
        self.log.info("Successfully remove tag %s resources with %s tags",
                      len(resource_batch) - len(failed_resource_ids), len(tags))
        return [resource for resource in resource_batch if resource["resource_id"] in failed_resource_ids]

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
                  old_key: owner-old
                  new_key: owner-new
    """

    log = logging.getLogger("custodian.huaweicloud.actions.tms.RenameResourceTagAction")

    schema = type_schema("rename-tag",
                         value={'type': 'string'},
                         old_key={'type': 'string'},
                         new_key={'type': 'string'})
    resource_max_size = 50

    def validate(self):
        """validate"""
        if not self.data.get('old_key'):
            raise PolicyValidationError("Can not perform rename tag without old_key")
        if not self.data.get('new_key'):
            raise PolicyValidationError("Can not perform rename tag without new_key")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        value = self.data.get('value', None)
        old_key = self.data.get('old_key')
        new_key = self.data.get('new_key')

        tms_client = self.get_tag_client()

        for resource in resources:
            try:
                if not value:
                    value = self.get_value_by_key(resource, old_key)

                if not value:
                    self.log.exception("No value of key %s in resource %s", old_key, resource["id"])

                old_tags = [{"key": old_key, "value": value}]
                new_tags = [{"key": new_key, "value": value}]
                resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}]
                self.process_resource_set(tms_client, resources, old_tags, new_tags, project_id)
            except exceptions.ClientRequestException as ex:
                self.log.exception(
                    f"Unable to rename tag resource {resource["id"]}, RequestId: {ex.request_id}, Reason: {ex.error_msg}")
                self.handle_exception(failed_resources=resource)
        return self.process_result(resources=resources)

    def perform_action(self, resource):
        pass

    def get_value_by_key(self, resource, key):
        if isinstance(resource, dict) and 'tags' in resource:
            tags = resource['tags']
            if isinstance(tags, dict):
                return tags.get(key)
            elif isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and key in tag:
                        return tag[key]
                    elif isinstance(tag, str) and f"{key}=" in tag:
                        parts = tag.split('=')
                        if parts[0] == key and len(parts) > 1:
                            return parts[1]
        return None

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


class NormalizeResourceTagAction(HuaweiCloudBaseAction):
    """Normaliz the specified tags from the specified resources.
    Set the tag value to uppercase, title, lowercase, replace, or strip text
    from a tag key

    :example:

        .. code-block :: yaml

            policies:
            - name: multiple-normalize-tag-example
              resource: huaweicloud.volume
              filters:
                - "tag:test-key": present
              actions:
              - type: normalize-tag
                key: lower_key
                action: lower

            policies:
            - name: multiple-normalize-tag-example
              resource: huaweicloud.volume
              filters:
                - "tag:test-key": present
              actions:
              - type: normalize-tag
                key: strip_key
                action: strip
                old_sub_str: a

            policies:
            - name: multiple-normalize-tag-example
              resource: huaweicloud.volume
              filters:
                - "tag:test-key": present
              actions:
              - type: normalize-tag
                key: strip_key
                action: strip
                old_sub_str: a
                new_sub_str: b

    """

    log = logging.getLogger("custodian.huaweicloud.actions.tms.NormalizeResourceTagAction")

    action_list = ['uppper', 'lower', 'title', 'strip', 'replace']
    schema = type_schema("normalize-tag",
                         key={'type': 'string'},
                         value={'type': 'string'},
                         action={'type': 'string',
                                 'items': {
                                     'enum': action_list
                                 }},
                         old_sub_str={'type': 'string'},
                         new_sub_str={'type': 'string'})
    resource_max_size = 50

    def validate(self):
        """validate"""
        if not self.data.get('key'):
            raise PolicyValidationError("Can not perform normalize tag without key")
        if not self.data.get('action') and self.data.get('action') not in self.action_list:
            raise PolicyValidationError("Can not perform normalize tag when action not in [uppper, lower, title, strip, replace]")
        action = self.data.get('action')
        if action == 'upper':


        return self

    def process(self, resources):
        project_id = self.get_project_id()

        key = self.data.get('key')
        action = self.data.get('action')
        old_value = self.data.get('value')
        old_sub_str = self.data.get('old_sub_str', "")
        new_sub_str = self.data.get('new_sub_str', "")
        new_value = self.get_new_value(old_value, action, old_sub_str, new_sub_str)

        old_tags = [{"key": key, "value": old_value}]
        new_tags = [{"key": key, "value": new_value}]

        tms_client = self.get_tag_client()

        count = len(resources)
        resources = self.filter_resources(resources)
        self.log.info("Filtered %s resources from %s resources", len(resources), count)
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}
                     for resource in resources
                     if "tag_resource_type" in resource.keys() and len(resource['tag_resource_type']) > 0]

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

    def get_new_value(self, value, action, old_sub_str, new_sub_str):
        if action == 'lower' and not value.islower():
            return value.lower()
        elif action == 'upper' and not value.isupper():
            return value.upper()
        elif action == 'title' and not value.istitle():
            return value.title()


    def filter_resources(self, resources):
        key = self.data.get('key', None)
        return [resource for resource in resources if key in resource.get('tags')]

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

