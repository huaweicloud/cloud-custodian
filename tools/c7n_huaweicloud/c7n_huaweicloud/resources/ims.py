# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkims.v2 import (
    GlanceDeleteImageRequest,
    GlanceDeleteImageRequestBody,
    BatchAddMembersRequest,
    BatchAddMembersRequestBody,
    BatchDeleteMembersRequest,
    BatchUpdateMembersRequest,
    BatchUpdateMembersRequestBody,
    CopyImageInRegionRequest,
    CopyImageInRegionRequestBody,
    ShowJobRequest,
)

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import AgeFilter, ValueFilter

log = logging.getLogger("custodian.huaweicloud.resources.ims")


@resources.register("ims")
class Ims(QueryResourceManager):
    class resource_type(TypeInfo):
        service = "ims"
        enum_spec = ("list_images", "images", "ims")
        id = "id"
        tag_resource_type = "private_image"


@Ims.action_registry.register("deregister")
class Deregister(HuaweiCloudBaseAction):
    """Deregister IMS Images.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ims-deregister-test
            resource: huaweicloud.ims
            filters:
              - type: value
                key: name
                value: "test"
            actions:
              - deregister
    """

    schema = type_schema("deregister")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = GlanceDeleteImageRequest()
        request.image_id = resource["id"]
        request.body = GlanceDeleteImageRequestBody()
        try:
            response = client.glance_delete_image(request)
        except exceptions.ClientRequestException as e:
            log.error(e)
            raise
        return json.dumps(response.to_dict())


@Ims.action_registry.register("set-permissions")
class SetPermissions(HuaweiCloudBaseAction):
    """Share IMS Images.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ims-share-image
            resource: huaweicloud.ims
            filters:
              - type: value
                key: name
                value: "test"
            actions:
              - type: set-permissions
                projects: ["project_id"]
                op: add
    """

    op_arr = ("add", "remove")
    schema = type_schema(
        "set-permissions", projects={"type": "array"}, op={"enum": op_arr}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        op = self.data.get("op", None)
        projects = self.data.get("projects", None)
        source_image_ids = [resource["id"]]
        response = {}
        if not projects:
            return
        if op == "add":
            request = BatchAddMembersRequest()
            request.body = BatchAddMembersRequestBody(
                projects=projects, images=source_image_ids
            )
            try:
                response = client.batch_add_members(request)
            except exceptions.ClientRequestException as e:
                log.error(e)
                raise
        elif op == "remove":
            request = BatchDeleteMembersRequest()
            request.body = BatchAddMembersRequestBody(
                projects=projects, images=source_image_ids
            )
            try:
                response = client.batch_delete_members(request)
            except exceptions.ClientRequestException as e:
                log.error(e)
                raise
        else:
            raise ValueError("invalid add_projects or remove_projects")
        log.info("response: %s" % json.dumps(response.to_dict()))
        return json.dumps(response.to_dict())


@Ims.action_registry.register("cancel-launch-permission")
class CancelLaunchPermissions(HuaweiCloudBaseAction):
    """Accepted Or Rejected IMS Images.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ims-cancel-launch-permission
            resource: huaweicloud.ims
            actions:
              - type: cancel-launch-permission
                status: rejected
                project_id: $project_id
                image_ids: ['image_id']

    """

    schema = type_schema(
        "cancel-launch-permission",
        status={"type": "string", "enum": ["accepted", "rejected"]},
        project_id={"type": "string"},
        vault_id={"type": "string"},
        image_ids={"type": "array", "items": {"type": "string"}},
        required=(
            "status",
            "project_id",
            "image_ids",
        ),
    )

    def process(self, resources):
        client = self.manager.get_client()
        request = BatchUpdateMembersRequest()
        request.body = BatchUpdateMembersRequestBody(
            vault_id=self.data.get("vault_id", None),
            status=self.data.get("status", None),
            project_id=self.data.get("project_id", None),
            images=self.data.get("image_ids", None),
        )
        try:
            response = client.batch_update_members(request)
        except exceptions.ClientRequestException as e:
            log.error(e)
            raise
        # log.info("response: %s" % json.dumps(response.to_dict()))
        return json.dumps(response.to_dict())

    def perform_action(self, resource):
        return super().perform_action(resource)


@Ims.action_registry.register("copy")
class Copy(HuaweiCloudBaseAction):
    """Copy IMS Images.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ims-copy-image
            resource: huaweicloud.ims
            filters:
              - type: value
                key: name
                value: "test"
            actions:
              - type: copy
                name: itau-copy
                description: test
    """

    schema = type_schema(
        "copy",
        name={"type": "string"},
        enterprise_project_id={"type": "string"},
        description={"type": "string"},
        cmk_id={"type": "string"},
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = CopyImageInRegionRequest()
        request.image_id = resource["id"]
        request.body = CopyImageInRegionRequestBody(
            name=self.data.get("name", None),
            enterprise_project_id=self.data.get("enterprise_project_id", None),
            description=self.data.get("description", None),
            cmk_id=self.data.get("cmk_id", None),
        )
        try:
            response = client.copy_image_in_region(request)
        except exceptions.ClientRequestException as e:
            log.error(e)
            raise
        log.info("response: %s" % json.dumps(response.to_dict()))
        return json.dumps(response.to_dict())


@Ims.action_registry.register("job")
class Job(HuaweiCloudBaseAction):
    """Query IMS Job.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ims-job-query
            resource: huaweicloud.ims
            actions:
              - type: copy
                job_id: 123
    """

    schema = type_schema("job", job_id={"type": "string"})

    def process(self, resources):
        client = self.manager.get_client()
        request = ShowJobRequest()
        try:
            request.job_id = self.data.get("job_id", None)
            response = client.show_job(request)
        except exceptions.ClientRequestException as e:
            log.error(e)
            raise
        return json.dumps(response.to_dict())

    def perform_action(self, resource):
        return super().perform_action(resource)


@Ims.filter_registry.register("image-age")
class ImageAge(AgeFilter):
    """Filters images based on the age (in days)

    :example:

    .. code-block:: yaml

            policies:
              - name: ims-image-age-filter
                resource: ims
                filters:
                  - type: image-age
                    days: 30
    """

    date_attribute = "created_at"
    schema = type_schema(
        "image-age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number", "minimum": 0},
    )


@Ims.filter_registry.register("image-attribute")
class ImageAttribute(ValueFilter):
    """IMS Image Value Filter on a given image attribute.

    :example:

    .. code-block:: yaml

            policies:
              - name: ims-image-windows
                resource: huaweicloud.ims
                filters:
                  - type: image-attribute
                    attribute: __os_type
                    key: "Value"
                    value: Windows
    """

    valid_attrs = ("virtual_env_type", "status", "disk_format", "__os_type")

    schema = type_schema(
        "image-attribute",
        rinherit=ValueFilter.schema,
        attribute={"enum": valid_attrs},
        required=("attribute",),
    )
    schema_alias = False

    def process(self, resources, event=None):
        attribute = self.data["attribute"]
        self.get_image_attribute(resources, attribute)
        return [
            resource
            for resource in resources
            if self.match(resource["image:attribute-%s" % attribute])
        ]

    def get_image_attribute(self, resources, attribute):
        for resource in resources:
            resource["image:attribute-%s" % attribute] = {"Value": resource[attribute]}
