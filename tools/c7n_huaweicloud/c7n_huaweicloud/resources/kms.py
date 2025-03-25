# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import uuid

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkkms.v2 import EnableKeyRotationRequest, OperateKeyRequestBody, DisableKeyRotationRequest, \
    EnableKeyRequest, DisableKeyRequest

from c7n.filters import ValueFilter
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.kms")


@resources.register('kms')
class Kms(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'kms'
        enum_spec = ("list_keys", 'key_details', 'offset')
        id = 'key_id'
        tag = False


@Kms.action_registry.register("enable_key_rotation")
class rotationKey(HuaweiCloudBaseAction):
    """rotation kms key.

    :Example:

    .. code-block:: yaml

policies:
  - name: enable_key_rotation
    resource: huaweicloud.kms
    filters:
      - type: value
        key: key_state
        value: "17368998-bdca-4302-95ee-8925d139a29f"
    actions:
      - enable_key_rotation
    """

    schema = type_schema("enable_key_rotation")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = EnableKeyRotationRequest()

        request.body = OperateKeyRequestBody(
            key_id=resource["key_id"],
            sequence=uuid.uuid4().hex
        )
        try:
            response = client.enable_key_rotation(request)
        except Exception as e:
            raise e

        return response


@Kms.action_registry.register("disable_key_rotation")
class disableRotationKey(HuaweiCloudBaseAction):
    """rotation kms key.

    :Example:

    .. code-block:: yaml

policies:
  - name: disable_key_rotation
    resource: huaweicloud.kms
    filters:
      - type: value
        key: key_state
        value: "2"
    actions:
      - disable_key_rotation
    """

    schema = type_schema("disable_key_rotation")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DisableKeyRotationRequest()
        request.body = OperateKeyRequestBody(
            key_id=resource["key_id"],
            sequence=uuid.uuid4().hex
        )
        try:
            response = client.disable_key_rotation(request)
        except Exception as e:
            raise e

        return response

@Kms.action_registry.register("enable_key")
class enableKey(HuaweiCloudBaseAction):
    """rotation kms key.

    :Example:

    .. code-block:: yaml

policies:
  - name: enable_key
    resource: huaweicloud.kms
    filters:
      - type: value
        key: key_id
        value: "17368998-bdca-4302-95ee-8925d139a29f"
    actions:
      - enable_key
    """

    schema = type_schema("enable_key")

    def perform_action(self, resource):
        client = self.manager.get_client()

        request = EnableKeyRequest()
        request.body = OperateKeyRequestBody(
            key_id=resource["key_id"],
            sequence=uuid.uuid4().hex
        )
        try:
            response = client.enable_key(request)
        except Exception as e:
            raise e

        return response

@Kms.action_registry.register("disable_key")
class disableKey(HuaweiCloudBaseAction):
    """rotation kms key.

    :Example:

    .. code-block:: yaml

policies:
  - name: disable_key
    resource: huaweicloud.kms
    filters:
      - type: value
        key: key_id
        value: "17368998-bdca-4302-95ee-8925d139a29f"
    actions:
      - disable_key
    """

    schema = type_schema("disable_key")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DisableKeyRequest()
        request.body = OperateKeyRequestBody(
            key_id=resource["key_id"],
            sequence=uuid.uuid4().hex
        )
        try:
            response = client.disable_key(request)
        except Exception as e:
            raise e

        return response


@Kms.filter_registry.register("all_keys_disable")
class instanceDisable(ValueFilter):
    '''
    policies:
  - name: instance_disable
    resource: huaweicloud.kms
    filters:
      - type: instance_disable
        key: "key_state"
        value: "3"

    '''
    schema = type_schema("all_keys_disable", rinherit=ValueFilter.schema)






