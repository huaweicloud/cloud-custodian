# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import concurrent.futures
import logging
import random
from datetime import datetime, timedelta

from dateutil import tz as tzutil
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiam.v3 import KeystoneListProjectsRequest
from huaweicloudsdktms.v1 import CreateResourceTagRequest, ReqCreateTag, ReqDeleteTag, \
    DeleteResourceTagRequest

from c7n.exceptions import PolicyValidationError, PolicyExecutionError
from c7n.filters.offhours import Time

from c7n.utils import type_schema, chunks, local_session

from c7n_huaweicloud.actions import HuaweiCloudBaseAction

MAX_WORKERS = 5
MAX_TAGS_SIZE = 10
RESOURCE_MAX_SIZE = 50
DEFAULT_TAG = "mark-for-op-tag"


def register_tms_actions(actions):
    actions.register('mark', CreateResourceTagAction)
    actions.register('tag', CreateResourceTagAction)

    actions.register('unmark', DeleteResourceTagAction)
    actions.register('untag', DeleteResourceTagAction)
    actions.register('remove-tag', DeleteResourceTagAction)

    actions.register('rename-tag', RenameResourceTagAction)
    actions.register('normalize-tag', NormalizeResourceTagAction)

    actions.register('tag-trim', TrimResourceTagAction)

    actions.register('mark-for-op', CreateResourceTagDelayedAction)


class CreateResourceTagAction(HuaweiCloudBaseAction):
    """Applies one or more tags to the specified resources.

    :example:

        . code-block :: yaml

            policies:
            - name: multiple-tags-example
              resource: huaweicloud.evs-volume
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

    log = logging.getLogger("custodian.actions.tag")

    schema = type_schema("tag", aliases=('mark',),
                         tags={'type': 'object'},
                         key={'type': 'string'},
                         value={'type': 'string'},
                         tag={'type': 'string'})

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

        if len(tags) > MAX_TAGS_SIZE:
            self.log.error("Can not tag more than %s tags at once", MAX_TAGS_SIZE)
            raise PolicyValidationError("Can not tag more than %s tags at once", MAX_TAGS_SIZE)

        tms_client = self.get_tag_client()
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}
                     for resource in resources
                     if "tag_resource_type" in resource.keys() and len(
                resource['tag_resource_type']) > 0]
        self.log.debug("Start tag, tags:[%s], resources:[%s]", tags, resources)
        for resource_batch in chunks(resources, RESOURCE_MAX_SIZE):
            try:
                failed_resources = self.process_resource_set(tms_client, resource_batch, tags,
                                                             project_id)
                self.handle_exception(failed_resources=failed_resources, resources=resources)
            except exceptions.ClientRequestException as ex:
                for failed_resource_res in resource_batch:
                    self.log.warning(
                        f"[actions]-tag The resource:{self.manager.ctx.policy.resource_type} "
                        f"with id:[{failed_resource_res['resource_id']}] create tag is failed. "
                        f"cause: : {ex.error_msg}, "
                        f"status: {ex.status_code}, "
                        f"requestId: {ex.request_id}")
                self.handle_exception(failed_resources=resource_batch, resources=resources)
        for success_resource_res in resources:
            self.log.info(
                f"[actions]-tag The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{success_resource_res['resource_id']}] create tag is success. ")
        return self.process_result(resources=[resource["resource_id"] for resource in resources])

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
        failed_resource_ids = [failed_resource.resource_id for failed_resource in
                               response.failed_resources]
        if len(failed_resource_ids) > 0:
            for failed_resource_res in response.failed_resources:
                self.log.warning(
                    f"[actions]-tag The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{failed_resource_res.resource_id}] create tag is failed. "
                    f"cause: {failed_resource_res.error_msg}")
        return [resource for resource in resource_batch if
                resource["resource_id"] in failed_resource_ids]

    def get_project_id(self):
        try:
            iam_client = local_session(self.manager.session_factory).client("iam-v3")

            region = local_session(self.manager.session_factory).region
            request = KeystoneListProjectsRequest(name=region)
            response = iam_client.keystone_list_projects(request=request)
            self.log.debug("[actions]-tag query the service:"
                           "[/v3/projects] is success.")
            for project in response.projects:
                if region == project.name:
                    return project.id

            self.log.error("Can not get project_id for %s", region)
            raise PolicyExecutionError("Can not get project_id for %s", region)
        except exceptions.ClientRequestException as ex:
            self.log.error(f"[actions]-tag query the service:"
                           f"[/v3/projects] is failed."
                           f"cause: : {ex.error_msg}, "
                           f"status: {ex.status_code}, "
                           f"requestId: {ex.request_id}")
            raise


class DeleteResourceTagAction(HuaweiCloudBaseAction):
    """Removes the specified tags from the specified resources.

    :example:

        . code-block :: yaml

            policies:
            - name: multiple-untags-example
              resource: huaweicloud.evs-volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: remove-tag
                  tags:
                    - owner
                    - owner2

            policies:
            - name: multiple-untags-example
              resource: huaweicloud.evs-volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: remove-tag
                  tag_values:
                    owner: 123
                    owner2: 456
    """

    log = logging.getLogger("custodian.actions.remove-tag")

    schema = type_schema("remove-tag", aliases=('unmark', 'untag', 'remove-tag'),
                         tags={'type': 'array'}, tag_values={'type': 'object'})

    def validate(self):
        """validate"""
        if self.data.get('tags') and self.data.get('tag_values'):
            raise PolicyValidationError("Can not both use tags and tag_values at once")
        return self

    def process(self, resources):
        project_id = self.get_project_id()

        tag_values = self.data.get("tag_values", [])
        tags = self.data.get("tags", [])

        if tag_values:
            key_values = [{"key": k, "value": v} for k, v in tag_values.items()]
        else:
            key_values = [{"key": k} for k in tags]

        if len(key_values) > MAX_TAGS_SIZE:
            self.log.error("Can not remove tag more than %s tags at once", MAX_TAGS_SIZE)
            raise PolicyValidationError("Can not remove tag more than %s tags at once",
                                        MAX_TAGS_SIZE)

        tms_client = self.get_tag_client()
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}
                     for resource in resources
                     if "tag_resource_type" in resource.keys() and len(
                resource['tag_resource_type']) > 0]
        self.log.debug("Start remove-tag, tags:[%s], resources:[%s]", tags, resources)
        for resource_batch in chunks(resources, RESOURCE_MAX_SIZE):
            try:
                failed_resources = self.process_resource_set(tms_client, resource_batch, key_values,
                                                             project_id)
                self.handle_exception(failed_resources=failed_resources, resources=resources)
            except exceptions.ClientRequestException as ex:
                for failed_resource_res in resource_batch:
                    self.log.warning(
                        f"[actions]-remove-tag "
                        f"The resource:{self.manager.ctx.policy.resource_type} "
                        f"with id:[{failed_resource_res['resource_id']}] remove tag is failed. "
                        f"cause: : {ex.error_msg}, "
                        f"status: {ex.status_code}, "
                        f"requestId: {ex.request_id}")
                self.handle_exception(failed_resources=resource_batch, resources=resources)
        for success_resource_res in resources:
            self.log.info(
                f"[actions]-reomve-tag The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{success_resource_res['resource_id']}] remove tag is success. ")
        return self.process_result(resources=[resource["resource_id"] for resource in resources])

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
        failed_resource_ids = [failed_resource.resource_id for failed_resource in
                               response.failed_resources]
        if len(failed_resource_ids) > 0:
            for failed_resource_res in response.failed_resources:
                self.log.warning(
                    f"[actions]-remove-tag The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{failed_resource_res.resource_id}] delete tag is failed. "
                    f"cause: {failed_resource_res.error_msg}")
        return [resource for resource in resource_batch if
                resource["resource_id"] in failed_resource_ids]

    def get_project_id(self):
        try:
            iam_client = local_session(self.manager.session_factory).client("iam-v3")

            region = local_session(self.manager.session_factory).region
            request = KeystoneListProjectsRequest(name=region)
            response = iam_client.keystone_list_projects(request=request)
            self.log.debug("[actions]-remove-tag query the service:"
                           "[/v3/projects] is success.")
            for project in response.projects:
                if region == project.name:
                    return project.id

            self.log.error("Can not get project_id for %s", region)
            raise PolicyExecutionError("Can not get project_id for %s", region)
        except exceptions.ClientRequestException as ex:
            self.log.error(f"[actions]-remove-tag query the service:"
                           f"[/v3/projects] is failed."
                           f"cause: : {ex.error_msg}, "
                           f"status: {ex.status_code}, "
                           f"requestId: {ex.request_id}")
            raise


class RenameResourceTagAction(HuaweiCloudBaseAction):
    """Rename the specified tags from the specified resources.

    :example:

        . code-block :: yaml

            policies:
            - name: multiple-rename-tag-example
              resource: huaweicloud.evs-volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: rename-tag
                  old_key: owner-old
                  new_key: owner-new
    """

    log = logging.getLogger("custodian.actions.rename-tag")

    schema = type_schema("rename-tag",
                         value={'type': 'string'},
                         old_key={'type': 'string'},
                         new_key={'type': 'string'})

    def validate(self):
        """validate"""
        if not self.data.get('old_key'):
            raise PolicyValidationError("Can not perform rename tag without old_key")
        if not self.data.get('new_key'):
            raise PolicyValidationError("Can not perform rename tag without new_key")
        return self

    def process(self, resources):
        self.resources = []
        self.resources.extend(resources)
        self.project_id = self.get_project_id()
        self.tms_client = self.get_tag_client()

        value = self.data.get('value', None)
        old_key = self.data.get('old_key')
        new_key = self.data.get('new_key')
        self.process_resources_concurrently(resources, old_key, new_key, value)
        for success_resource_res in self.resources:
            self.log.info(
                f"[actions]-rename-tag The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{success_resource_res['id']}] rename tag is success. ")
        return self.process_result(resources=[resource["id"] for resource in self.resources])

    def process_resource(self, resource, old_key, new_key, value):
        try:
            if not value:
                value = self.get_value_by_key(resource, old_key)
            if not value:
                self.log.warning(
                    f"[actions]-rename-tag The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{resource['id']} rename tag is failed. "
                    f"cause: No value of key {old_key}")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return
            old_tags = [{"key": old_key, "value": value}]
            new_tags = [{"key": new_key, "value": value}]
            resources = [
                {"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}]

            request_body = ReqDeleteTag(project_id=self.project_id, resources=resources,
                                        tags=old_tags)
            request = DeleteResourceTagRequest(body=request_body)
            delete_response = self.tms_client.delete_resource_tag(request=request)
            if len(delete_response.failed_resources) > 0:
                self.log.warning(f"[actions]-rename-tag "
                                 f"The resource:{self.manager.ctx.policy.resource_type} "
                               f"with id:[{resource['id']} "
                               f"delete tag:{old_tags} is failed. "
                               f"cause: {delete_response.failed_resources[0].error_msg}")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return
            else:
                self.log.debug(f"[actions]-rename-tag "
                               f"The resource:{self.manager.ctx.policy.resource_type} "
                               f"with id:[{resource['id']} "
                               f"delete tag:{old_tags} is success. ")

            request_body = ReqCreateTag(project_id=self.project_id, resources=resources,
                                        tags=new_tags)
            request = CreateResourceTagRequest(body=request_body)
            create_response = self.tms_client.create_resource_tag(request=request)
            if len(create_response.failed_resources) > 0:
                self.log.warning(f"[actions]-rename-tag "
                                 f"The resource:{self.manager.ctx.policy.resource_type} "
                                 f"with id:[{resource['id']} "
                                 f"create tag:{new_tags} is failed. "
                                 f"cause: {create_response.failed_resources[0].error_msg}")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return
            else:
                self.log.debug(f"[actions]-rename-tag "
                               f"The resource:{self.manager.ctx.policy.resource_type} "
                               f"with id:[{resource['id']} "
                               f"create tag:{new_tags} is success.]")
        except exceptions.ClientRequestException as ex:
            self.log.warning(
                f"[actions]-rename-tag The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{resource['id']}] rename tag is failed. "
                f"cause: : {ex.error_msg}, "
                f"status: {ex.status_code}, "
                f"requestId: {ex.request_id}")
            self.handle_exception(failed_resources=[resource], resources=self.resources)
            return
        except Exception:
            self.handle_exception(failed_resources=[resource], resources=self.resources)
            raise

    def process_resources_concurrently(self, resources, old_key, new_key, value):
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self.process_resource, resource, old_key, new_key, value) for
                       resource in
                       resources]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.error(
                        f"process_resources_concurrently unexpected error occurred: {e}")

    def perform_action(self, resource):
        pass

    def get_value_by_key(self, resource, key):
        try:
            if isinstance(resource, dict) and 'tags' in resource:
                tags = resource['tags']
                if isinstance(tags, dict):
                    # 格式为 {k1: v1, k2: v2}
                    return tags.get(key)
                elif isinstance(tags, list):
                    if all(isinstance(item, dict) and len(item) == 1 for item in tags):
                        # 格式为 [{k1: v1}, {k2: v2}]
                        for item in tags:
                            if key in item:
                                return item[key]
                    elif all(isinstance(item, str) and '=' in item for item in tags):
                        # 格式为 ["k1=v1", "k2=v2"]
                        for item in tags:
                            k, v = item.split('=', 1)
                            if k == key:
                                return v
                    elif all(
                            isinstance(item, dict) and 'key' in item and 'value' in item for item in
                            tags):
                        # 格式为 [{"key": k1, "value": v1}, {"key": k2, "value": v2}]
                        for item in tags:
                            if item['key'] == key:
                                return item['value']
            return None
        except Exception:
            self.log.warning("Parse tags in resource %s failed", resource["id"])
            return None

    def handle_exception(self, failed_resources, resources):
        self.failed_resources.extend(failed_resources)
        for failed_resource in failed_resources:
            resources.remove(failed_resource)

    def get_project_id(self):
        try:
            iam_client = local_session(self.manager.session_factory).client("iam-v3")

            region = local_session(self.manager.session_factory).region
            request = KeystoneListProjectsRequest(name=region)
            response = iam_client.keystone_list_projects(request=request)
            self.log.debug("[actions]-rename-tag query the service:"
                           "[/v3/projects] is success.")
            for project in response.projects:
                if region == project.name:
                    return project.id

            self.log.error("Can not get project_id for %s", region)
            raise PolicyExecutionError("Can not get project_id for %s", region)
        except exceptions.ClientRequestException as ex:
            self.log.error(f"[actions]-rename-tag query the service:"
                           f"[/v3/projects] is failed."
                           f"cause: : {ex.error_msg}, "
                           f"status: {ex.status_code}, "
                           f"requestId: {ex.request_id}")
            raise


class NormalizeResourceTagAction(HuaweiCloudBaseAction):
    """Normalize the specified tags from the specified resources.
    Set the tag value to uppercase, title, lowercase, replace, or strip text
    from a tag key

    :example:

        . code-block :: yaml

            policies:
            - name: multiple-normalize-tag-example
              resource: huaweicloud.evs-volume
              filters:
                - "tag:test-key": present
              actions:
              - type: normalize-tag
                key: lower_key
                action: lower

            policies:
            - name: multiple-normalize-tag-example
              resource: huaweicloud.evs-volume
              filters:
                - "tag:test-key": present
              actions:
              - type: normalize-tag
                key: strip_key
                action: strip
                old_sub_str: a

            policies:
            - name: multiple-normalize-tag-example
              resource: huaweicloud.evs-volume
              filters:
                - "tag:test-key": present
              actions:
              - type: normalize-tag
                key: strip_key
                action: replace
                old_sub_str: a
                new_sub_str: b

    """

    log = logging.getLogger("custodian.actions.normalize-tag")

    action_list = ['upper', 'lower', 'title', 'strip', 'replace']
    schema = type_schema("normalize-tag",
                         key={'type': 'string'},
                         value={'type': 'string'},
                         action={'type': 'string',
                                 'items': {
                                     'enum': action_list
                                 }},
                         old_sub_str={'type': 'string'},
                         new_sub_str={'type': 'string'})

    def validate(self):
        """validate"""
        if not self.data.get('key'):
            raise PolicyValidationError("Can not perform normalize tag without key")
        if not self.data.get('action') and self.data.get('action') not in self.action_list:
            raise PolicyValidationError(
                "Can not perform normalize tag when "
                "action not in [upper, lower, title, strip, replace]")
        action = self.data.get('action')
        if action == 'strip' and not self.data.get('old_sub_str'):
            raise PolicyValidationError(
                "Can not perform normalize tag when action is strip without old_sub_str")
        if action == 'replace' and not (
                self.data.get('old_sub_str') and self.data.get('new_sub_str')):
            raise PolicyValidationError(
                "Can not perform normalize tag when "
                "action is strip without old_sub_str or new_sub_str")

        return self

    def process(self, resources):
        self.resources = []
        self.resources.extend(resources)
        self.project_id = self.get_project_id()
        self.tms_client = self.get_tag_client()

        self.key = self.data.get('key')
        self.action = self.data.get('action')
        self.old_value = self.data.get('value', None)
        self.old_sub_str = self.data.get('old_sub_str', "")
        self.new_sub_str = self.data.get('new_sub_str', "")

        self.process_resources_concurrently(resources)
        for success_resource_res in self.resources:
            self.log.info(
                f"[actions]-normalize-tag The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{success_resource_res['id']}] normalize tag is success. ")
        return self.process_result(resources=[resource["id"] for resource in self.resources])

    def process_resource(self, resource):
        try:
            if not self.old_value:
                old_value = self.get_value_by_key(resource, self.key)
            else:
                old_value = self.old_value
            if not self.old_value and not old_value:
                self.log.warning(
                    f"[actions]-normalize-tag The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{resource['id']} normalize tag is failed. "
                    f"cause: No value of key {self.key}.")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return

            new_value = self.get_new_value(old_value, self.action, self.old_sub_str,
                                                self.new_sub_str)
            if not new_value:
                self.log.warning(
                    f"[actions]-normalize-tag The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{resource['id']} normalize tag is failed. "
                    f"cause: Can not get new value of key {self.key}.")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return

            old_tags = [{"key": self.key, "value": old_value}]
            new_tags = [{"key": self.key, "value": new_value}]
            resources = [
                {"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}]

            request_body = ReqDeleteTag(project_id=self.project_id, resources=resources,
                                        tags=old_tags)
            request = DeleteResourceTagRequest(body=request_body)
            delete_response = self.tms_client.delete_resource_tag(request=request)
            if len(delete_response.failed_resources) > 0:
                self.log.warning(f"[actions]-normalize-tag "
                                 f"The resource:{self.manager.ctx.policy.resource_type} "
                                 f"with id:[{resource['id']} "
                                 f"delete tag:{old_tags} is failed. "
                                 f"cause: {delete_response.failed_resources[0].error_msg}")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return
            else:
                self.log.debug(f"[actions]-normalize-tag "
                               f"The resource:{self.manager.ctx.policy.resource_type} "
                               f"with id:[{resource['id']} "
                               f"delete tag:{old_tags} is success. ")

            request_body = ReqCreateTag(project_id=self.project_id, resources=resources,
                                        tags=new_tags)
            request = CreateResourceTagRequest(body=request_body)
            create_response = self.tms_client.create_resource_tag(request=request)
            if len(create_response.failed_resources) > 0:
                self.log.warning(f"[actions]-normalize-tag "
                                 f"The resource:{self.manager.ctx.policy.resource_type} "
                                 f"with id:[{resource['id']} "
                                 f"create tag:{new_tags} is failed. "
                                 f"cause: {create_response.failed_resources[0].error_msg}")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return
            else:
                self.log.debug(f"[actions]-normalize-tag "
                               f"The resource:{self.manager.ctx.policy.resource_type} "
                               f"with id:[{resource['id']} "
                               f"create tag:{new_tags} is success.]")
        except exceptions.ClientRequestException as ex:
            self.log.warning(
                f"[actions]-normalize-tag The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{resource['id']}] normalize tag is failed. "
                f"cause: : {ex.error_msg}, "
                f"status: {ex.status_code}, "
                f"requestId: {ex.request_id}")
            self.handle_exception(failed_resources=[resource], resources=self.resources)
            return
        except Exception:
            self.handle_exception(failed_resources=[resource], resources=self.resources)
            raise

    def process_resources_concurrently(self, resources):
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self.process_resource, resource) for resource in resources]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.error(
                        f"process_resources_concurrently unexpected error occurred: {e}")

    def perform_action(self, resource):
        pass

    def get_new_value(self, value, action, old_sub_str, new_sub_str):
        if action == 'lower' and not value.islower():
            return value.lower()
        elif action == 'upper' and not value.isupper():
            return value.upper()
        elif action == 'title' and not value.istitle():
            return value.title()
        elif action == 'strip' and old_sub_str and old_sub_str in value:
            return value.strip(old_sub_str)
        elif action == 'replace' and old_sub_str and new_sub_str and old_sub_str in value:
            return value.replace(old_sub_str, new_sub_str)
        else:
            return None

    def get_value_by_key(self, resource, key):
        try:
            if isinstance(resource, dict) and 'tags' in resource:
                tags = resource['tags']
                if isinstance(tags, dict):
                    # 格式为 {k1: v1, k2: v2}
                    return tags.get(key)
                elif isinstance(tags, list):
                    if all(isinstance(item, dict) and len(item) == 1 for item in tags):
                        # 格式为 [{k1: v1}, {k2: v2}]
                        for item in tags:
                            if key in item:
                                return item[key]
                    elif all(isinstance(item, str) and '=' in item for item in tags):
                        # 格式为 ["k1=v1", "k2=v2"]
                        for item in tags:
                            k, v = item.split('=', 1)
                            if k == key:
                                return v
                    elif all(
                            isinstance(item, dict) and 'key' in item and 'value' in item for item in
                            tags):
                        # 格式为 [{"key": k1, "value": v1}, {"key": k2, "value": v2}]
                        for item in tags:
                            if item['key'] == key:
                                return item['value']
            return None
        except Exception:
            self.log.warning("Parse tags in resource %s failed", resource["id"])
            return None

    def filter_resources(self, resources):
        key = self.data.get('key', None)
        return [resource for resource in resources if key in resource.get('tags')]

    def handle_exception(self, failed_resources, resources):
        self.failed_resources.extend(failed_resources)
        for failed_resource in failed_resources:
            resources.remove(failed_resource)

    def get_project_id(self):
        try:
            iam_client = local_session(self.manager.session_factory).client("iam-v3")

            region = local_session(self.manager.session_factory).region
            request = KeystoneListProjectsRequest(name=region)
            response = iam_client.keystone_list_projects(request=request)
            self.log.debug("[actions]-normalize-tag query the service:"
                           "[/v3/projects] is success.")
            for project in response.projects:
                if region == project.name:
                    return project.id

            self.log.error("Can not get project_id for %s", region)
            raise PolicyExecutionError("Can not get project_id for %s", region)
        except exceptions.ClientRequestException as ex:
            self.log.error(f"[actions]-normalize-tag query the service:"
                           f"[/v3/projects] is failed."
                           f"cause: : {ex.error_msg}, "
                           f"status: {ex.status_code}, "
                           f"requestId: {ex.request_id}")
            raise


class TrimResourceTagAction(HuaweiCloudBaseAction):
    """Trim the specified tags from the specified resources.

    :example:

        . code-block :: yaml

            policies:
            - name: multiple-tag-trim-example
              resource: huaweicloud.evs-volume
              filters:
                - type: value
                  key: "length(tags)"
                  op: ge
                  value: 8
              actions:
                - type: tag-trim
                  space: 3
                  preserve:
                    - owner1
                    - owner2
    """

    log = logging.getLogger("custodian.actions.tag-trim")

    schema = type_schema("tag-trim",
                         space={'type': 'integer'},
                         preserve={'type': 'array', 'items': {'type': 'string'}})

    def validate(self):
        """validate"""
        if not self.data.get('space'):
            raise PolicyValidationError("Can not perform tag-trim without space")
        if self.data.get('space') > MAX_TAGS_SIZE:
            raise PolicyValidationError(
                "Can not perform tag-trim when space more than %d" % MAX_TAGS_SIZE)
        if self.data.get('space') < 0:
            raise PolicyValidationError("Can not perform tag-trim when space less than zero")
        return self

    def process(self, resources):
        self.resources = []
        self.resources.extend(resources)
        self.project_id = self.get_project_id()
        self.tms_client = self.get_tag_client()

        space = self.data.get('space', 0)
        preserve = self.data.get('preserve', [])
        self.process_resources_concurrently(resources, space, preserve)
        for success_resource_res in self.resources:
            self.log.info(
                f"[actions]-tag-trim The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{success_resource_res['id']}] tag trim is success. ")
        return self.process_result(resources=[resource["id"] for resource in self.resources])

    def process_resource(self, resource, space, preserve):
        try:
            tags = self.get_tags_from_resource(resource)
            delete_keys = self.get_delete_keys(tags, space, preserve, resource["id"])
            if len(delete_keys) == 0:
                self.log.info("No need to tag-trim of %s", resource['id'])
                return

            old_tags = [{"key": key, "value": tags[key]} for key in delete_keys]
            resources = [
                {"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}]

            request_body = ReqDeleteTag(project_id=self.project_id, resources=resources,
                                        tags=old_tags)
            request = DeleteResourceTagRequest(body=request_body)
            delete_response = self.tms_client.delete_resource_tag(request=request)
            if len(delete_response.failed_resources) > 0:
                self.log.warning(f"[actions]-tag-trim "
                                 f"The resource:{self.manager.ctx.policy.resource_type} "
                                 f"with id:[{resource['id']} "
                                 f"delete tag:{old_tags} is failed. "
                                 f"cause: {delete_response.failed_resources[0].error_msg}")
                self.handle_exception(failed_resources=[resource], resources=self.resources)
                return
            else:
                self.log.debug(f"[actions]-tag-trim "
                               f"The resource:{self.manager.ctx.policy.resource_type} "
                               f"with id:[{resource['id']} "
                               f"delete tag:{old_tags} is success. ")
        except exceptions.ClientRequestException as ex:
            self.log.warning(
                f"[actions]-tag-trim The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{resource['id']}] tag trim is failed. "
                f"cause: : {ex.error_msg}, "
                f"status: {ex.status_code}, "
                f"requestId: {ex.request_id}")
            self.handle_exception(failed_resources=[resource], resources=self.resources)
            return
        except Exception:
            self.handle_exception(failed_resources=[resource], resources=self.resources)
            raise

    def process_resources_concurrently(self, resources, space, preserve):
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self.process_resource, resource, space, preserve) for
                       resource in resources]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.error(
                        f"process_resources_concurrently unexpected error occurred: {e}")

    def perform_action(self, resource):
        pass

    def get_delete_keys(self, tags, space, preserve, reosurce_id):
        if len(tags) > MAX_TAGS_SIZE:
            self.log.warning(
                f"[actions]-tag-trim The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{reosurce_id}] tag trim is failed. "
                f"cause: Can not perform tag-trim when tags "
                f"more than {MAX_TAGS_SIZE}, please reduce to {MAX_TAGS_SIZE}")
            raise PolicyExecutionError(
                "Can not perform tag-trim when tags more than %d, please reduce to %d" %
                                        (MAX_TAGS_SIZE, MAX_TAGS_SIZE))
        if MAX_TAGS_SIZE - len(tags) >= space:
            return []
        else:
            delete_keys_count = len(tags) - (MAX_TAGS_SIZE - space)
            delete_keys = [key for key in tags.keys() if key not in preserve]
            if delete_keys_count > len(delete_keys):
                self.log.warning(
                    f"[actions]-tag-trim The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{reosurce_id}] tag trim is failed. "
                    f"cause: Can not perform tag-trim with policy. ")
                raise PolicyValidationError("Can not remove tags with policy")
            index_to_delete = random.sample(range(len(delete_keys)), delete_keys_count)
            index_to_delete.sort()
            res = []
            for index in index_to_delete:
                res.append(delete_keys[index])

            return res

    def get_tags_from_resource(self, resource):
        try:
            tags = resource["tags"]
            if isinstance(tags, dict):
                return tags
            elif isinstance(tags, list):
                if all(isinstance(item, dict) and len(item) == 1 for item in tags):
                    # [{k1: v1}, {k2: v2}]
                    result = {}
                    for item in tags:
                        key, value = list(item.items())[0]
                        result[key] = value
                    return result
                elif all(isinstance(item, str) and '=' in item for item in tags):
                    # ["k1=v1", "k2=v2"]
                    result = {}
                    for item in tags:
                        key, value = item.split('=', 1)
                        result[key] = value
                    return result
                elif all(isinstance(item, dict) and 'key' in item and 'value' in item for item in
                         tags):
                    # [{"key": k1, "value": v1}, {"key": k2, "value": v2}]
                    return {item['key']: item['value'] for item in tags}
            return {}
        except Exception:
            self.log.warning("Parse tags in resource %s failed", resource["id"])
            return {}

    def handle_exception(self, failed_resources, resources):
        self.failed_resources.extend(failed_resources)
        for failed_resource in failed_resources:
            resources.remove(failed_resource)

    def get_project_id(self):
        try:
            iam_client = local_session(self.manager.session_factory).client("iam-v3")

            region = local_session(self.manager.session_factory).region
            request = KeystoneListProjectsRequest(name=region)
            response = iam_client.keystone_list_projects(request=request)
            self.log.debug("[actions]-tag-trim query the service:"
                           "[/v3/projects] is success.")
            for project in response.projects:
                if region == project.name:
                    return project.id

            self.log.error("Can not get project_id for %s", region)
            raise PolicyExecutionError("Can not get project_id for %s", region)
        except exceptions.ClientRequestException as ex:
            self.log.error(f"[actions]-tag-trim query the service:"
                           f"[/v3/projects] is failed."
                           f"cause: : {ex.error_msg}, "
                           f"status: {ex.status_code}, "
                           f"requestId: {ex.request_id}")
            raise


class CreateResourceTagDelayedAction(HuaweiCloudBaseAction):
    """Tag resources for future action.

        The optional 'tz' parameter can be used to adjust the clock to align
        with a given timezone. The default value is 'utc'.

        If neither 'days' nor 'hours' is specified, Cloud Custodian will default
        to marking the resource for action 4 days in the future.

        . code-block :: yaml

          policies:
            - name: multiple-tags-example
              resource: huaweicloud.evs-volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: mark-for-op
                  tag: test-key
                  op: stop
                  days: 4
    """
    log = logging.getLogger("custodian.actions.mark-for-op")

    schema = type_schema('mark-for-op',
                         tag={'type': 'string'},
                         msg={'type': 'string'},
                         days={'type': 'number', 'minimum': 0},
                         hours={'type': 'number', 'minimum': 0},
                         tz={'type': 'string'},
                         op={'type': 'string'})

    default_template = '{op}_{action_date}'

    def validate(self):
        op = self.data.get('op')
        if self.manager and op not in self.manager.action_registry.keys():
            raise PolicyValidationError(
                "mark-for-op specifies invalid op:%s in %s" % (
                    op, self.manager.data))

        self.tz = tzutil.gettz(
            Time.TZ_ALIASES.get(self.data.get('tz', 'utc')))
        if not self.tz:
            raise PolicyValidationError(
                "Invalid timezone specified %s in %s" % (
                    self.tz, self.manager.data))
        return self

    def get_config_values(self):
        cfg = {
            'op': self.data.get('op', 'stop'),
            'tag': self.data.get('tag', DEFAULT_TAG),
            'msg': self.data.get('msg', self.default_template),
            'tz': self.data.get('tz', 'utc'),
            'days': self.data.get('days', 0),
            'hours': self.data.get('hours', 0)}
        cfg['action_date'] = self.generate_timestamp(
            cfg['days'], cfg['hours'])
        return cfg

    def generate_timestamp(self, days, hours):
        n = datetime.now(tz=self.tz)
        if days is None or hours is None:
            # maintains default value of days being 4 if nothing is provided
            days = 4
        action_date = (n + timedelta(days=days, hours=hours))
        if hours > 0:
            action_date_string = action_date.strftime('%Y-%m-%d-%H-%M-%Z')
        else:
            action_date_string = action_date.strftime('%Y-%m-%d')

        return action_date_string

    def process(self, resources):
        project_id = self.get_project_id()
        cfg = self.get_config_values()
        self.tz = tzutil.gettz(Time.TZ_ALIASES.get(cfg['tz']))

        msg = cfg['msg'].format(
            op=cfg['op'], action_date=cfg['action_date'])

        self.log.info("Tagging %d resources for %s on %s" % (
            len(resources), cfg['op'], cfg['action_date']))

        tags = [{'key': cfg['tag'], 'value': msg}]

        tms_client = self.get_tag_client()
        resources = [{"resource_id": resource["id"], "resource_type": resource["tag_resource_type"]}
                     for resource in resources
                     if "tag_resource_type" in resource.keys() and len(
                resource['tag_resource_type']) > 0]
        self.log.debug("Start mark-for-op, tags:[%s], resources:[%s]", tags, resources)
        for resource_batch in chunks(resources, RESOURCE_MAX_SIZE):
            try:
                failed_resources = self.process_resource_set(tms_client, resource_batch, tags,
                                                             project_id)
                self.handle_exception(failed_resources=failed_resources, resources=resources)
            except exceptions.ClientRequestException as ex:
                for failed_resource_res in resource_batch:
                    self.log.warning(
                        f"[actions]-mark-for-op "
                        f"The resource:{self.manager.ctx.policy.resource_type} "
                        f"with id:[{failed_resource_res['resource_id']}] create tag is failed. "
                        f"cause: : {ex.error_msg}, "
                        f"status: {ex.status_code}, "
                        f"requestId: {ex.request_id}")
                self.handle_exception(failed_resources=resource_batch, resources=resources)
        for success_resource_res in resources:
            self.log.info(
                f"[actions]-mark-for-op The resource:{self.manager.ctx.policy.resource_type} "
                f"with id:[{success_resource_res['resource_id']}] create tag is success. ")
        return self.process_result(resources=[resource["resource_id"] for resource in resources])

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
        failed_resource_ids = [failed_resource.resource_id for failed_resource in
                               response.failed_resources]
        if len(failed_resource_ids) > 0:
            for failed_resource_res in response.failed_resources:
                self.log.warning(
                    f"[actions]-mark-for-op The resource:{self.manager.ctx.policy.resource_type} "
                    f"with id:[{failed_resource_res.resource_id}] create tag is failed. "
                    f"cause: {failed_resource_res.error_msg}")
        return [resource for resource in resource_batch if
                resource["resource_id"] in failed_resource_ids]

    def get_project_id(self):
        try:
            iam_client = local_session(self.manager.session_factory).client("iam-v3")

            region = local_session(self.manager.session_factory).region
            request = KeystoneListProjectsRequest(name=region)
            response = iam_client.keystone_list_projects(request=request)
            self.log.debug("[actions]-mark-for-op query the service:"
                           "[/v3/projects] is success.")
            for project in response.projects:
                if region == project.name:
                    return project.id

            self.log.error("Can not get project_id for %s", region)
            raise PolicyExecutionError("Can not get project_id for %s", region)
        except exceptions.ClientRequestException as ex:
            self.log.error(f"[actions]-mark-for-op query the service:"
                           f"[/v3/projects] is failed."
                           f"cause: : {ex.error_msg}, "
                           f"status: {ex.status_code}, "
                           f"requestId: {ex.request_id}")
            raise
