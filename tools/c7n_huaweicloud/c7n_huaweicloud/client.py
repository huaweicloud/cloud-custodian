# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkconfig.v1 import ConfigClient, ShowTrackerConfigRequest
from huaweicloudsdkconfig.v1.region.config_region import ConfigRegion
from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkecs.v2 import *
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkevs.v2.region.evs_region import EvsRegion
from huaweicloudsdkiam.v3 import IamClient
from huaweicloudsdkiam.v3.region.iam_region import IamRegion
from huaweicloudsdkvpc.v2 import *
from huaweicloudsdkvpc.v2.region.vpc_region import VpcRegion
from huaweicloudsdktms.v1 import *
from huaweicloudsdktms.v1.region.tms_region import TmsRegion
from huaweicloudsdksmn.v2 import *
from huaweicloudsdksmn.v2.region.smn_region import SmnRegion
from huaweicloudsdkcoc.v1 import *
from huaweicloudsdkcoc.v1.region.coc_region import CocRegion

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
        credentials = BasicCredentials(self.ak, self.sk, os.getenv('HUAWEI_PROJECT_ID'))
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
            global_credentials = GlobalCredentials(self.ak, self.sk)
            client = TmsClient.new_builder() \
                .with_credentials(global_credentials) \
                .with_region(TmsRegion.value_of(self.region)) \
                .build()
        elif service == 'iam':
            globalCredentials = GlobalCredentials(self.ak, self.sk)
            client = IamClient.new_builder() \
                .with_credentials(globalCredentials) \
                .with_region(IamRegion.value_of(self.region)) \
                .build()
        elif service == 'config':
            globalCredentials = GlobalCredentials(self.ak, self.sk)
            client = ConfigClient.new_builder() \
                .with_credentials(globalCredentials) \
                .with_region(ConfigRegion.value_of(self.region)) \
                .build()
        elif service == 'coc':
            global_credentials = GlobalCredentials(self.ak, self.sk)
            client = CocClient.new_builder() \
                .with_credentials(global_credentials) \
                .with_region(CocRegion.value_of(self.region)) \
                .build()
        elif service == 'smn':
            client = SmnClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(SmnRegion.value_of(self.region)) \
                .build()

        return client

    def request(self, service):
        if service == 'vpc':
            request = ListVpcsRequest()
        elif service == 'evs':
            request = ListVolumesRequest()
        elif service == 'config':
            request = ShowTrackerConfigRequest()
        elif service == 'coc':
            request = ListInstanceCompliantRequest()

        return request
