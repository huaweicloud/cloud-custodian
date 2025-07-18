# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
import traceback

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



    def get_resources(self, resource_ids):
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
                        streams.append(streamDict)
                        should_break = True
                        break
            except Exception as e:
                log.error("[filters]-The filter:[streams-storage-enabled] query the service:[LTS:"
                          "list_log_stream] failed. cause: {}".format(e))
                raise
            if should_break:
                break
        log.info("[event/period]-The filtered resources has [{}]"
                 " in total. ".format(str(len(streams))))
        return streams

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
            request.body = UpdateLogStreamParamre(
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
