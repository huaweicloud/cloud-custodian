# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcts.v3 import (DeleteTrackerRequest, UpdateTrackerRequest,
                                  UpdateTrackerRequestBody, TrackerObsInfo)
from huaweicloudsdkcore.exceptions import exceptions

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.cts")


@resources.register('cts-tracker')
class Tracker(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cts-tracker'
        enum_spec = ("list_trackers", "trackers", "offset")
        id = 'id'
        tag = True
        tag_resource_type = 'cts-tracker'


@Tracker.action_registry.register("delete-tracker")
class CtsDeleteTracker(HuaweiCloudBaseAction):
    """Delete Tracker.
    :Example:
    .. code-block:: yaml
    policies:
        - name: delete-tracker
          resource: huaweicloud.cts-tracker
          actions:
            - type: delete-tracker
              tracker_name: "system"
              tracker_type: "system"
    """

    schema = type_schema(
        "delete-tracker",
        tracker_name={"type": "string"},
        tracker_type={"type": "string"}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        properties = {
            "tracker_name": self.data.get("tracker_name", ""),
            "tracker_type": self.data.get("tracker_type", "")
        }

        request = DeleteTrackerRequest()
        request.tracker_name = properties["tracker_name"]
        request.tracker_type = properties["tracker_type"]
        try:
            response = client.delete_tracker(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Tracker.action_registry.register("toggle-tracker")
class CtsToggleTracker(HuaweiCloudBaseAction):
    """Enable or Disable Tracker.
    :Example:
    .. code-block:: yaml
    policies:
        - name: toggle-tracker
          resource: huaweicloud.cts-tracker
          actions:
            - type: toggle-tracker
              tracker_name: "system"
              tracker_type: "system"
              status: "enabled"  # or "disabled"
    """

    schema = type_schema(
        "toggle-tracker",
        tracker_name={"type": "string"},
        tracker_type={"type": "string"},
        status={"type": "string", "enum": ["enabled", "disabled"]}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        properties = {
            "tracker_name": self.data.get("tracker_name", ""),
            "tracker_type": self.data.get("tracker_type", ""),
            "status": self.data.get("status", "")
        }

        request = UpdateTrackerRequest()
        request.body = UpdateTrackerRequestBody(
            status=properties["status"],
            tracker_name=properties["tracker_name"],
            tracker_type=properties["tracker_type"]
        )

        try:
            response = client.update_tracker(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Tracker.action_registry.register("set-trace-file-validation")
class CtsSetTraceFileValidation(HuaweiCloudBaseAction):
    """Set Trace File Validation. this action is used to configure the log file integrity
     verification and encryption storage settings for the CTS tracker.
    :Example:
    .. code-block:: yaml
    policies:
        - name: set-trace-file-validation
          resource: huaweicloud.cts-tracker
          actions:
            - type: set-trace-file-validation
              tracker_name: "system"
              tracker_type: "system"
              is_support_validate: true
              kms_id: "kms id"
              is_support_trace_files_encryption: true
              obs_info:
                bucket_name: "your bucketname"
                compress_type: "gzip"
                is_sort_by_service: true
    """

    schema = type_schema(
        "set-trace-file-validation",
        tracker_name={"type": "string"},
        tracker_type={"type": "string"},
        is_support_validate={"type": "boolean"},
        kms_id={"type": "string"},
        is_support_trace_files_encryption={"type": "boolean"},
        obs_info={"type": "object", "properties": {
            "bucket_name": {"type": "string"},
            "compress_type": {"type": "string", "enum": ["gzip", "json", "none"]},
            "is_sort_by_service": {"type": "boolean"}
        }}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        properties = {
            "tracker_name": self.data.get("tracker_name", ""),
            "tracker_type": self.data.get("tracker_type", ""),
            "is_support_validate": self.data.get("is_support_validate"),
            "kms_id": self.data.get("kms_id"),
            "is_support_trace_files_encryption":
                self.data.get("is_support_trace_files_encryption", True),
            "obs_info": self.data.get("obs_info", {})
        }

        request = UpdateTrackerRequest()
        request.body = UpdateTrackerRequestBody(
            is_support_validate=properties["is_support_validate"],
            kms_id=properties["kms_id"],
            is_support_trace_files_encryption=properties["is_support_trace_files_encryption"],
            obs_info=TrackerObsInfo(
                bucket_name=properties["obs_info"].get("bucket_name"),
                compress_type=properties["obs_info"].get("compress_type", ""),
                is_sort_by_service=properties["obs_info"].get("is_sort_by_service", True)
            ),
            tracker_name=properties["tracker_name"],
            tracker_type=properties["tracker_type"]
        )

        try:
            response = client.update_tracker(request)
            log.info(f"Successfully updated trace file validation ("
                     f"is_support_validate={properties['is_support_validate']}) "
                     f"for tracker {properties['tracker_name']}.")
        except exceptions.ClientRequestException as e:
            log.error(f"Error updating trace file validation: {e.status_code}, {e.request_id},"
                      f" {e.error_code}, {e.error_msg}")
            raise
        return response
