# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from c7n.filters import Filter
from c7n.utils import type_schema

from huaweicloudsdklts.v2 import ListLogStreamRequest, ListLogGroupsRequest

log = logging.getLogger("custodian.huaweicloud.filters.stream")


class LtsStreamStorageEnabledFilter(Filter):
    schema = type_schema(
        'streams-storage-enabled'
    )

    def process(self, resources, event=None):
        client = self.manager.get_client()
        streams = []
        request = ListLogGroupsRequest()
        stream_request = ListLogStreamRequest()
        response = client.list_log_groups(request)
        for group in response.log_groups:
            if group.log_group_name.startswith("functiongraph.log.group"):
                continue
            time.sleep(0.22)
            stream_request.log_group_id = group.log_group_id
            try:
                stream_response = client.list_log_stream(stream_request)
                for stream in stream_response.log_streams:
                    if stream.whether_log_storage:
                        streamDict = {}
                        streamDict["log_group_id"] = group.log_group_id
                        streamDict["log_stream_id"] = stream.log_stream_id
                        streamDict["log_stream_name"] = stream.log_stream_name
                        streamDict["id"] = stream.log_stream_id
                        streamDict["tags"] = stream.tag
                        streams.append(streamDict)
            except Exception as e:
                log.error("[filters]-The filter:[streams-storage-enabled] query the service:[LTS:"
                          "list_log_stream] failed. cause: {}".format(e))
                raise
        log.info("[event/period]-The filtered resources has [{}]"
                 " in total. ".format(str(len(streams))))
        return streams


class LtsStreamStorageEnabledFilterForSchedule(Filter):
    schema = type_schema(
        'streams-storage-enabled-for-schedule'
    )

    def process(self, resources, event=None):
        client = self.manager.get_client()
        request = ListLogStreamRequest()
        streams = []
        for group in resources:
            if group["log_group_name"].startswith("functiongraph.log.group"):
                continue
            request.log_group_id = group["log_group_id"]
            try:
                time.sleep(0.22)
                response = client.list_log_stream(request)
                for stream in response.log_streams:
                    if stream.whether_log_storage:
                        streamDict = {}
                        streamDict["log_group_id"] = group["log_group_id"]
                        streamDict["log_stream_id"] = stream.log_stream_id
                        streamDict["log_stream_name"] = stream.log_stream_name
                        streamDict["id"] = stream.log_stream_id
                        streamDict["tags"] = stream.tag
                        streams.append(streamDict)
            except Exception as e:
                log.error("[filters]-The filter:[streams-storage-enabled-for-schedule] query the"
                          " service:[LTS:lts_log_stream] failed. cause: {}".format(e))
                raise
        log.info("[event/period]-The filtered resources has [{}]"
                 " in total. ".format(str(len(streams))))
        return streams
