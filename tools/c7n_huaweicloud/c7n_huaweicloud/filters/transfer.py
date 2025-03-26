# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from c7n.filters import Filter
from c7n.utils import type_schema


class LtsTransferLogGroupStreamFilter(Filter):
    schema = type_schema(
        'transfer-logGroupStream-id',
        metadata={'type': "object"}
    )

    def process(self, resources, event=None):
        matched = []
        params = self.data.get('metadata')
        for transfer in resources:
            if (transfer.get("log_transfer_info").get("log_transfer_type") != "OBS"):
                continue
            logGroup_match = transfer.get('log_group_id') == params.get('log_group_id')
            if not logGroup_match:
                continue

            log_streams = transfer.get('log_streams', [])
            for logStream in log_streams:
                if (logStream.get("log_stream_id") == params.get('log_stream_id')):
                    matched.append(transfer)
        return matched
