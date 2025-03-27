# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdklts.v2 import CreateTransferRequestBodyLogTransferInfo, TransferDetail, \
            CreateTransferRequestBodyLogStreams, CreateTransferRequestBody, CreateTransferRequest

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.filters.transfer import LtsTransferLogGroupStreamFilter

log = logging.getLogger("custodian.huaweicloud.resources.lts-transfer")


@resources.register('lts-transfer')
class Transfer(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'lts-transfer'
        enum_spec = ("list_transfers", 'log_transfers', 'offset')
        id = 'log_transfer_id'
        tag = True
        tag_resource_type = 'lts-transfer'


Transfer.filter_registry.register('transfer-logGroupStream-id', LtsTransferLogGroupStreamFilter)


@Transfer.action_registry.register("create-transfer")
class LtsCreateTransferLog(HuaweiCloudBaseAction):
    schema = type_schema(
        "create-transfer",
        log_group_id={"type": "string"},
        log_streams={"type": "array"},
        log_transfer_type={"type": "string"},
        log_transfer_mode={"type": "string"},
        log_storage_format={"type": "string"},
        log_transfer_status={"type": "string"},
        obs_period={'type': 'integer'},
        obs_period_unit={"type": "string"},
        obs_bucket_name={"type": "string"}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        try:
            request = CreateTransferRequest()
            logTransferDetailLogTransferInfo = TransferDetail(
                obs_period=self.data.get('obs_period'),
                obs_period_unit=self.data.get('obs_period_unit'),
                obs_bucket_name=self.data.get('obs_bucket_name')
            )
            logTransferInfobody = CreateTransferRequestBodyLogTransferInfo(
                log_transfer_type=self.data.get('log_transfer_type'),
                log_transfer_mode=self.data.get('log_transfer_mode'),
                log_storage_format=self.data.get('log_storage_format'),
                log_transfer_status=self.data.get('log_transfer_status'),
                log_transfer_detail=logTransferDetailLogTransferInfo
            )
            listLogStreamsbody = []
            for stream in self.data.get("log_streams"):
                listLogStreamsbody.append(CreateTransferRequestBodyLogStreams(
                    log_stream_id=stream["log_stream_id"]
                ))
            request.body = CreateTransferRequestBody(
                log_transfer_info=logTransferInfobody,
                log_streams=listLogStreamsbody,
                log_group_id=self.data.get("log_group_id"),
            )
            log.warning(request.body)
            response = client.create_transfer(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response
