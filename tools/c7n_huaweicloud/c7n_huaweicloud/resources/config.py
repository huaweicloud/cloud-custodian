# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

from huaweicloudsdkconfig.v1 import DeleteTrackerConfigRequest, CreateTrackerConfigRequest, \
    TrackerConfigBody, \
    ChannelConfigBody, TrackerSMNChannelConfigBody, TrackerOBSChannelConfigBody, SelectorConfigBody

from c7n.exceptions import PolicyValidationError
from c7n.filters import ValueFilter
from c7n.utils import type_schema
from c7n_huaweicloud.actions import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


@resources.register('config-tracker')
class ConfigTracker(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'config'
        enum_spec = ("show_tracker_config", '*', 'offset')
        id = 'domain_id'
        config_resource_support = True


@ConfigTracker.action_registry.register("delete-tracker")
class DeleteTrackerAction(HuaweiCloudBaseAction):
    """Delete Config Tracker.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-config-tracker
            resource: huaweicloud.config-tracker
            actions:
              - type: delete-tracker
    """
    log = logging.getLogger("custodian.huaweicloud.resources.config.DeleteTrackerAction")

    schema = type_schema("delete-tracker")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteTrackerConfigRequest()
        client.delete_tracker_config(request=request)
        self.log.info("Successfully delete config-tracker")


class CreateTrackerAction(HuaweiCloudBaseAction):
    """Create Config Tracker.

    :Example:

    .. code-block:: yaml

        policies:
          - name: create-config-tracker
            resource: huaweicloud.config-tracker
            actions:
              - type: create-tracker
                smn: true
                region_id: cn-north-4
                project_id: 123456****789789456
                topic_urn: ********
                obs: true
                bucket_name: test_obs
                bucket_prefix:
                all_supported: true
                resource_type:
                  - vpc
                retention_period_in_days: 30
                agency_name: rms_tracker_agency
    """
    log = logging.getLogger("custodian.huaweicloud.resources.config.CreateTrackerAction")

    schema = type_schema("create-tracker",
                         smn={'type': 'boolean'},
                         region_id={'type': 'string'},
                         project_id={'type': 'string'},
                         topic_urn={'type': 'string'},
                         obs={'type': 'boolean'},
                         bucket_name={'type': 'string'},
                         bucket_prefix={'type': 'string'},
                         all_supported={'type': 'boolean'},
                         resource_types={'type': 'array', 'items': {'type': 'string'}},
                         retention_period_in_days={'type': 'integer'},
                         agency_name={'type': 'string'}
                         )

    def validate(self):
        smn = self.data.get('smn')
        if smn and not (
                self.data.get('region_id') and self.data.get('project_id') and self.data.get(
                'topic_urn')):
            raise PolicyValidationError("Can not create or update tracke when parameter is error")

        obs = self.data.get('obs')
        if obs and not (self.data.get('region_id') and self.data.get('bucket_name')):
            raise PolicyValidationError("Can not create or update tracke when parameter is error")

        return self

    def perform_action(self, resource):
        smn = self.data.get('smn', False)
        obs = self.data.get('obs', False)
        if not (smn or obs):
            raise PolicyValidationError(
                "Can not create or update tracke when smn and obs both false")

        region_id = self.data.get('region_id')
        project_id = self.data.get('project_id')
        topic_urn = self.data.get('topic_urn')
        bucket_name = self.data.get('bucket_name')
        bucket_prefix = self.data.get('bucket_prefix')
        all_supported = self.data.get('all_supported', True)
        resource_types = self.data.get('resource_types', [])
        retention_period_in_days = self.data.get('retnetion_period_in_days', None)
        agency_name = self.data.get('agency_name', "rms_tracker_agency")

        client = self.manager.get_client()

        channel = None
        if smn:
            channel = ChannelConfigBody(smn=TrackerSMNChannelConfigBody(
                region_id=region_id,
                topic_urn=topic_urn,
                project_id=project_id,
            ))
        if obs:
            channel = ChannelConfigBody(obs=TrackerOBSChannelConfigBody(
                region_id=region_id,
                bucket_name=bucket_name,
                bucket_prefix=bucket_prefix,
            ))

        selector = SelectorConfigBody(
            all_supported=all_supported,
            resource_types=resource_types
        )

        request_body = TrackerConfigBody(
            channel=channel,
            selector=selector,
            retention_period_in_days=retention_period_in_days,
            agency_name=agency_name
        )
        request = CreateTrackerConfigRequest(body=request_body)
        client.create_tracker_config(request=request)
        self.log.info("Successfully create config-tracker")


@ConfigTracker.filter_registry.register("retention")
class ConfigRetentionConfigurations(ValueFilter):
    """
    Filter to look for config retention configurations

    Huawei Config supports only one retention configuration in a particular account.

    retention_period_in_days value should be an integer ranging from 30 to 2557

    :example:

    .. code-block:: yaml

        policies:
        - name: config-recorder-verify-retention
          resource: config-recorder
          filters:
            - type: retention
              key: retention_period_in_days
              value: 30

    """

    schema = type_schema(
        "retention",
        rinherit=ValueFilter.schema,

    )
    annotation_key = "huawei:ConfigRetentionConfigs"

    def process(self, resources, event=None):
        for resource in resources:
            resource[self.annotation_key] = {
                "retention_period_in_days": resource.get("retention_period_in_days", None)}
        return super().process(resources, event)

    def __call__(self, resource):
        return super().__call__(resource[self.annotation_key])
