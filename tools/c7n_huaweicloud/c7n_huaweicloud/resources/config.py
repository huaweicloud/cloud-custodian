# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

from huaweicloudsdkconfig.v1 import DeleteTrackerConfigRequest, ShowTrackerConfigRequest

from c7n.filters import ValueFilter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


@resources.register('config-tracker')
class ConfigTracker(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'config'
        enum_spec = ("show_tracker_config", '*', 'offset')
        id = 'domain_id'

@ConfigTracker.action_registry.register("delete-tracker")
class DeleteTrackerAction(HuaweiCloudBaseAction):
    """Delete Config Tracker.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-config-tracker
            resource: huaweicloud.config-tracker
            actions:
              - delete-tracker
    """
    log = logging.getLogger("custodian.huaweicloud.resources.config.DeleteTrackerAction")

    schema = type_schema("delete-tracker")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteTrackerConfigRequest()
        client.delete_tracker_config(request=request)
        self.log.info("Successfully delete config-tracker of %s", resource.get("id", resource.get("name")))


# @ConfigTracker.action_registry.register("create-tracker")
# class CreateTrackerAction(HuaweiCloudBaseAction):
#     """Create Config Tracker.
#
#     :Example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: create-config-tracker
#             resource: huaweicloud.config-tracker
#             actions:
#               - create-tracker
#     """
#     log = logging.getLogger("custodian.huaweicloud.resources.config.CreateTrackerAction")
#
#     schema = type_schema("create-tracker")
#
#     def perform_action(self, resource):
#         client = self.manager.get_client()
#         request = CreateTrackerConfigRequest()
#         client.delete_tracker_config(request=request)
#         self.log.info("Successfully delete config-tracker of %s", resource.get("id", resource.get("name")))


@ConfigTracker.filter_registry.register("retention")
class ConfigRetentionConfigurations(ValueFilter):
    """
    Filter to look for config retention configurations

    Huawei Config supports only one retention configuration in a particular account.

    RetentionPeriodInDays value should be an integer ranging from 30 to 2557

    :example:

    .. code-block:: yaml

        policies:
        - name: config-recorder-verify-retention
          resource: config-recorder
          filters:
            - type: retention
              key: RetentionPeriodInDays
              value: 30

    Also retrieves the retention configuration if no key/value is provided:

    :example:

    .. code-block:: yaml

        policies:
        - name: config-recorder
          resource: config-recorder
          filters:
            - type: retention
    """

    schema = type_schema(
        "retention",
        rinherit=ValueFilter.schema,

    )
    annotation_key = "huawei:ConfigRetentionConfigs"

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("config")

        request = ShowTrackerConfigRequest()
        response = client.show_tracker_config(request)
        retention_config = response.retention_period_in_days
        for resource in resources:
            resource[self.annotation_key] = retention_config
        return super().process(resources, event)

    def __call__(self, resource):
        return super().__call__(resource[self.annotation_key])