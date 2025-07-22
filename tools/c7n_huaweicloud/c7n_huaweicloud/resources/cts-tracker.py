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
            log.info(
                f"[actions]-[delete_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"delete tracker is success"
            )
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]-[delete_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"delete tracker is failed"
            )
            log.error(f"cause: {e.status_code}, {e.request_id},"
                      f" {e.error_code}, {e.error_msg}")
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
            log.info(
                f"[actions]-[update_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"toggle tracker is success"
            )
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]-[update_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"toggle tracker is failed"
            )
            log.error(f"cause: {e.status_code}, {e.request_id},"
                      f" {e.error_code}, {e.error_msg}")
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
              agency_name: "your_agency_name"
              status: "enabled"
              is_organization_tracker: false
              management_event_selector:
                exclude_service:
                  - "service1"
                  - "service2"
              is_lts_enabled: true
              obs_info:
                bucket_name: "your bucketname"
                file_prefix_name: "your_prefix"
                is_obs_created: true
                bucket_lifecycle: 30
                compress_type: "gzip"
                is_sort_by_service: true
              data_bucket:
                data_bucket_name: "your_data_bucket"
                data_event:
                  - "event1"
                  - "event2"
    """

    schema = type_schema(
        "set-trace-file-validation",
        tracker_name={"type": "string"},
        tracker_type={"type": "string"},
        agency_name={"type": "string"},
        status={"type": "string", "enum": ["enabled", "disabled"]},
        is_organization_tracker={"type": "boolean"},
        management_event_selector={"type": "object", "properties": {
            "exclude_service": {"type": "array", "items": {"type": "string"}}
        }},
        is_lts_enabled={"type": "boolean"},
        is_support_validate={"type": "boolean"},
        kms_id={"type": "string"},
        is_support_trace_files_encryption={"type": "boolean"},
        obs_info={"type": "object", "properties": {
            "bucket_name": {"type": "string"},
            "file_prefix_name": {"type": "string"},
            "is_obs_created": {"type": "boolean"},
            "bucket_lifecycle": {"type": "number"},
            "compress_type": {"type": "string", "enum": ["gzip", "json", "none"]},
            "is_sort_by_service": {"type": "boolean"}
        }},
        data_bucket={"type": "object", "properties": {
            "data_bucket_name": {"type": "string"},
            "data_event": {"type": "array", "items": {"type": "string"}}
        }}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        properties = {
            "tracker_name": self.data.get("tracker_name", ""),
            "tracker_type": self.data.get("tracker_type", ""),
            "agency_name": self.data.get("agency_name", ""),
            "status": self.data.get("status", ""),
            "is_organization_tracker": self.data.get("is_organization_tracker", False),
            "management_event_selector": self.data.get("management_event_selector", {}),
            "is_lts_enabled": self.data.get("is_lts_enabled", False),
            "is_support_validate": self.data.get("is_support_validate"),
            "kms_id": self.data.get("kms_id"),
            "is_support_trace_files_encryption":
                self.data.get("is_support_trace_files_encryption", False),
            "obs_info": self.data.get("obs_info", {}),
            "data_bucket": self.data.get("data_bucket", {})
        }

        request = UpdateTrackerRequest()
        request.body = UpdateTrackerRequestBody(
            tracker_name=properties["tracker_name"],
            tracker_type=properties["tracker_type"],
            agency_name=properties["agency_name"],
            status=properties["status"],
            is_organization_tracker=properties["is_organization_tracker"],
            management_event_selector=properties["management_event_selector"],
            is_lts_enabled=properties["is_lts_enabled"],
            is_support_validate=properties["is_support_validate"],
            kms_id=properties["kms_id"],
            is_support_trace_files_encryption=properties["is_support_trace_files_encryption"],
            obs_info=TrackerObsInfo(
                bucket_name=properties["obs_info"].get("bucket_name"),
                file_prefix_name=properties["obs_info"].get("file_prefix_name"),
                is_obs_created=properties["obs_info"].get("is_obs_created"),
                bucket_lifecycle=properties["obs_info"].get("bucket_lifecycle"),
                compress_type=properties["obs_info"].get("compress_type", ""),
                is_sort_by_service=properties["obs_info"].get("is_sort_by_service", False)
            ) if properties["obs_info"] else None,
            data_bucket=properties["data_bucket"] if properties["data_bucket"] else None
        )

        try:
            response = client.update_tracker(request)
            log.info(
                f"[actions]-[update_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"set file validation/encryption/obs tranfer/lts transfer is success "
                f"is_support_validate={properties['is_support_validate']} "
                f"for tracker {properties['tracker_name']}."
            )
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]-[update_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"set file validation/encryption/obs tranfer/lts transfer is failed."
            )
            log.error(f"cause: {e.status_code}, {e.request_id},"
                      f" {e.error_code}, {e.error_msg}")
            raise
        return response


@Tracker.action_registry.register("set-trace-file-validation-with-lts-preservation")
class CtsSetTraceFileValidationWithLtsPreservation(HuaweiCloudBaseAction):
    """Set Trace File Validation. this action is used to configure the log file integrity
     verification and encryption storage settings for the CTS tracker.
    :Example:
    .. code-block:: yaml
    policies:
        - name: set-trace-file-validation-with-lts-preservation
          resource: huaweicloud.cts-tracker
          actions:
            - type: set-trace-file-validation
              tracker_name: "system"
              tracker_type: "system"
              is_support_validate: true
              kms_id: "kms id"
              is_support_trace_files_encryption: true
              agency_name: "your_agency_name"
              status: "enabled"
              is_organization_tracker: false
              management_event_selector:
                exclude_service:
                  - "service1"
                  - "service2"
              is_lts_enabled: true
              obs_info:
                bucket_name: "your bucketname"
                file_prefix_name: "your_prefix"
                is_obs_created: true
                bucket_lifecycle: 30
                compress_type: "gzip"
                is_sort_by_service: true
              data_bucket:
                data_bucket_name: "your_data_bucket"
                data_event:
                  - "event1"
                  - "event2"
    """

    schema = type_schema(
        "set-trace-file-validation-with-lts-preservation",
        tracker_name={"type": "string"},
        tracker_type={"type": "string"},
        agency_name={"type": "string"},
        status={"type": "string", "enum": ["enabled", "disabled"]},
        is_organization_tracker={"type": "boolean"},
        management_event_selector={"type": "object", "properties": {
            "exclude_service": {"type": "array", "items": {"type": "string"}}
        }},
        is_lts_enabled={"type": "boolean"},
        is_support_validate={"type": "boolean"},
        kms_id={"type": "string"},
        is_support_trace_files_encryption={"type": "boolean"},
        obs_info={"type": "object", "properties": {
            "bucket_name": {"type": "string"},
            "file_prefix_name": {"type": "string"},
            "is_obs_created": {"type": "boolean"},
            "bucket_lifecycle": {"type": "number"},
            "compress_type": {"type": "string", "enum": ["gzip", "json", "none"]},
            "is_sort_by_service": {"type": "boolean"}
        }},
        data_bucket={"type": "object", "properties": {
            "data_bucket_name": {"type": "string"},
            "data_event": {"type": "array", "items": {"type": "string"}}
        }}
    )

    def perform_action(self, resource):
        # 从 resource 对象中获取 lts.is_lts_enabled 的值
        is_lts_enabled = resource.get("lts", {}).get("is_lts_enabled", False)
        log.info(f"is_lts_enabled: {is_lts_enabled}")

        client = self.manager.get_client()
        properties = {
            "tracker_name": self.data.get("tracker_name", ""),
            "tracker_type": self.data.get("tracker_type", ""),
            "agency_name": self.data.get("agency_name", ""),
            "status": self.data.get("status", ""),
            "is_organization_tracker": self.data.get("is_organization_tracker", False),
            "management_event_selector": self.data.get("management_event_selector", {}),
            "is_lts_enabled": is_lts_enabled,
            "is_support_validate": self.data.get("is_support_validate"),
            "kms_id": self.data.get("kms_id"),
            "is_support_trace_files_encryption":
                self.data.get("is_support_trace_files_encryption", False),
            "obs_info": self.data.get("obs_info", {}),
            "data_bucket": self.data.get("data_bucket", {})
        }

        request = UpdateTrackerRequest()
        request.body = UpdateTrackerRequestBody(
            tracker_name=properties["tracker_name"],
            tracker_type=properties["tracker_type"],
            agency_name=properties["agency_name"],
            status=properties["status"],
            is_organization_tracker=properties["is_organization_tracker"],
            management_event_selector=properties["management_event_selector"],
            is_lts_enabled=properties["is_lts_enabled"],
            is_support_validate=properties["is_support_validate"],
            kms_id=properties["kms_id"],
            is_support_trace_files_encryption=properties["is_support_trace_files_encryption"],
            obs_info=TrackerObsInfo(
                bucket_name=properties["obs_info"].get("bucket_name"),
                file_prefix_name=properties["obs_info"].get("file_prefix_name"),
                is_obs_created=properties["obs_info"].get("is_obs_created"),
                bucket_lifecycle=properties["obs_info"].get("bucket_lifecycle"),
                compress_type=properties["obs_info"].get("compress_type", ""),
                is_sort_by_service=properties["obs_info"].get("is_sort_by_service", False)
            ) if properties["obs_info"] else None,
            data_bucket=properties["data_bucket"] if properties["data_bucket"] else None
        )

        try:
            # 打印 request 关键信息
            log.info(f"Request body: {request.body}")
            response = client.update_tracker(request)
            log.info(
                f"[actions]-[update_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"set file validation/encryption/obs tranfer with lts preservation is success "
                f"is_support_validate={properties['is_support_validate']} "
                f"for tracker {properties['tracker_name']}."
            )
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]-[update_tracker] The resource: [system tracker] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"set file validation/encryption/obs tranfer with lts preservation is failed."
            )
            log.error(f"cause: {e.status_code}, {e.request_id},"
                      f" {e.error_code}, {e.error_msg}")
            raise
        return response
