# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions

from c7n.utils import type_schema
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
