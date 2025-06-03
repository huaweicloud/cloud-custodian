# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from huaweicloudsdklts.v2 import UpdateLogStreamRequest, UpdateLogStreamParams

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.filters.stream import LtsStreamStorageEnabledFilter


log = logging.getLogger("custodian.huaweicloud.resources.lts-stream")


@resources.register('lts-stream')
class Stream(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'lts-stream'
        enum_spec = ("list_log_groups", 'log_groups', 'offset')
        id = 'log_group_id'
        tag = True
        tag_resource_type = 'lts-stream'


Stream.filter_registry.register('streams-storage-enabled', LtsStreamStorageEnabledFilter)


@Stream.action_registry.register("disable-stream-storage")
class LtsDisableStreamStorage(HuaweiCloudBaseAction):
    schema = type_schema("disable-stream-storage")

    def perform_action(self, resource):
        time.sleep(0.3)
        client = self.manager.get_client()
        request = UpdateLogStreamRequest()
        request.log_group_id = resource["log_group_id"]
        request.log_stream_id = resource["log_stream_id"]
        request.body = UpdateLogStreamParams(
            ttl_in_days=7
        )
        log.error("disable stream storage: " + resource["log_stream_id"])
        response = client.update_log_stream(request)
        return response
