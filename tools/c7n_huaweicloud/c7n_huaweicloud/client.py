# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkecs.v2 import *
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkevs.v2.region.evs_region import EvsRegion
from huaweicloudsdkvpc.v2 import *
from huaweicloudsdktms.v1 import *
from huaweicloudsdktms.v1.region.tms_region import TmsRegion

from huaweicloudsdkiam.v5 import IamClient as IamClientV5, ListUsersV5Request, ListPoliciesV5Request

LIST_POLICIES_V_REQUEST = ListPoliciesV5Request

REQUEST = ListPoliciesV5Request

V_REQUEST = ListPoliciesV5Request
from huaweicloudsdkiam.v5.region import iam_region as iam_region_v5

log = logging.getLogger('custodian.huaweicloud.client')


class Session:
    """Session"""

    def __init__(self, options=None):
        self.region = os.getenv('HUAWEI_DEFAULT_REGION')
        if not self.region:
            log.error('No default region set. Specify a default via HUAWEI_DEFAULT_REGION')
            sys.exit(1)

        self.ak = os.getenv('HUAWEI_ACCESS_KEY_ID')
        if self.ak is None:
            log.error('No access key id set. Specify a default via HUAWEI_ACCESS_KEY_ID')
            sys.exit(1)

        self.sk = os.getenv('HUAWEI_SECRET_ACCESS_KEY')
        if self.sk is None:
            log.error('No secret access key set. Specify a default via HUAWEI_SECRET_ACCESS_KEY')
            sys.exit(1)

    def client(self, service):
        credentials = BasicCredentials(self.ak, self.sk)
        if service == 'vpc':
            client = VpcClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(VpcRegion.value_of(self.region)) \
                .build()
        elif service == 'ecs':
            client = EcsClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(EcsRegion.value_of(self.region)) \
                .build()
        elif service == 'evs':
            client = EvsClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(EvsRegion.value_of(self.region)) \
                .build()
        elif service == 'tms':
            globalCredentials = GlobalCredentials(self.ak, self.sk)
            client = TmsClient.new_builder() \
                .with_credentials(globalCredentials) \
                .with_region(TmsRegion.value_of(self.region)) \
                .build()
        elif service == 'iam':
            globalCredentials = GlobalCredentials(self.ak, self.sk)
            client = IamClientV5.new_builder() \
                .with_credentials(globalCredentials) \
                .with_region(iam_region_v5.IamRegion.value_of(self.region)) \
                .build()
        elif service == 'iam-policy':
            globalCredentials = GlobalCredentials(self.ak, self.sk)
            client = IamClientV5.new_builder() \
                .with_credentials(globalCredentials) \
                .with_region(iam_region_v5.IamRegion.value_of(self.region)) \
                .build()

        return client

    def request(self, service):
        if service == 'vpc':
            request = ListVpcsRequest()
        elif service == 'evs':
            request = ListVolumesRequest()
        elif service == 'iam':
            request = ListUsersV5Request()
        elif service == 'iam-policy':
            request = ListPoliciesV5Request()

        return request
