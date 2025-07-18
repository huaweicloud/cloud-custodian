# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from c7n.filters import Filter
from c7n.utils import type_schema

from huaweicloudsdklts.v2 import ListLogStreamRequest

log = logging.getLogger("custodian.huaweicloud.filters.stream")


class LtsStreamStorageEnabledFilter(Filter):
    schema = type_schema(
        'streams-storage-enabled'
    )

    def process(self, resources, event=None):
        return resources


class LtsStreamStorageEnabledFilterForSchedule(Filter):
    schema = type_schema(
        'streams-storage-enabled-for-schedule'
    )

    def process(self, resources, event=None):
        client = self.manager.get_client()
        request = ListLogStreamRequest()
        log.info("enter lts filter for schedule")
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
                        streams.append(streamDict)
            except Exception as e:
                log.error(e)
                raise
        log.info("The number of streams to disable storage is " + str(len(streams)))
        return streams
