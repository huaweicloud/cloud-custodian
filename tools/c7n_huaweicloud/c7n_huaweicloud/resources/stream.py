# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from huaweicloudsdklts.v2 import UpdateLogStreamRequest, UpdateLogStreamParams, \
    ListLogGroupsRequest, ListLogStreamRequest

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
        tag = True
        tag_resource_type = 'lts-stream'

    def get_resources(self, resource_ids):
        log.info("after listen get all groups")
        client = self.get_client()
        streams = []
        request = ListLogGroupsRequest()
        stream_request = ListLogStreamRequest()
        response = client.list_log_groups(request)
        should_break = False
        for group in response.log_groups:
            if group.log_group_name.startswith("functiongraph.log.group"):
                continue
            time.sleep(0.22)
            stream_request.log_group_id = group.log_group_id
            try:
                stream_response = client.list_log_stream(stream_request)
                for stream in stream_response.log_streams:
                    if stream.log_stream_id == resource_ids[0] and stream.whether_log_storage:
                        streamDict = {}
                        streamDict["log_group_id"] = group.log_group_id
                        streamDict["log_stream_id"] = stream.log_stream_id
                        streamDict["log_stream_name"] = stream.log_stream_name
                        streamDict["id"] = stream.log_stream_id
                        streams.append(streamDict)
                        should_break = True
                        break
            except Exception as e:
                log.error(e)
                raise
            if should_break:
                break
        log.info("The number of streams to disable storage is " + str(len(streams)))
        return streams


Stream.filter_registry.register('streams-storage-enabled', LtsStreamStorageEnabledFilter)
Stream.filter_registry.register('streams-storage-enabled-for-schedule',
                                LtsStreamStorageEnabledFilterForSchedule)


@Stream.action_registry.register("disable-stream-storage")
class LtsDisableStreamStorage(HuaweiCloudBaseAction):
    schema = type_schema("disable-stream-storage")

    def perform_action(self, resource):
        time.sleep(0.22)
        client = self.manager.get_client()
        request = UpdateLogStreamRequest()
        request.log_group_id = resource["log_group_id"]
        request.log_stream_id = resource["log_stream_id"]
        request.body = UpdateLogStreamParams(
            whether_log_storage=False
        )
        log.info("disable storage: " + resource["log_stream_id"])
        response = client.update_log_stream(request)
        return response
