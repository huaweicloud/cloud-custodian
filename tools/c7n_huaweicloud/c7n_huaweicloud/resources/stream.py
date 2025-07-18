# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from huaweicloudsdklts.v2 import UpdateLogStreamRequest, UpdateLogStreamParams

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.filters.stream import LtsStreamStorageEnabledFilter, \
    LtsStreamStorageEnabledFilterForSchedule

log = logging.getLogger("custodian.huaweicloud.resources.lts-stream")


@resources.register('lts-stream')
class Stream(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'lts-stream'
        enum_spec = ("list_log_groups", 'log_groups', 'offset')
        id = 'log_group_id'
        tags = "tag"
        tag_resource_type = 'lts-stream'


Stream.filter_registry.register('streams-storage-enabled', LtsStreamStorageEnabledFilter)
Stream.filter_registry.register('streams-storage-enabled-for-schedule',
                                LtsStreamStorageEnabledFilterForSchedule)


@Stream.action_registry.register("disable-stream-storage")
class LtsDisableStreamStorage(HuaweiCloudBaseAction):
    schema = type_schema("disable-stream-storage")

    def perform_action(self, resource):
        time.sleep(0.22)
        try:
            client = self.manager.get_client()
            request = UpdateLogStreamRequest()
            request.log_group_id = resource["log_group_id"]
            request.log_stream_id = resource["log_stream_id"]
            request.body = UpdateLogStreamParams(
                whether_log_storage=False
            )
            log.info("[actions]-[disable-stream-storage]: The resource:[stream] with"
                     "id:[{}] modify storage is success".format(resource["log_stream_id"]))
            response = client.update_log_stream(request)
            return response
        except Exception as e:
            log.error("[actions]-[disable-stream-storage]-The resource:[stream] with id:"
                      "[{}] modify sotrage failed. cause: {}".format(resource["log_stream_id"], e))
            raise
