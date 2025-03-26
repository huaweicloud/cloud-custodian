# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys

from huaweicloudsdkconfig.v1 import ConfigClient, ShowTrackerConfigRequest
from huaweicloudsdkconfig.v1.region.config_region import ConfigRegion
from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkecs.v2 import EcsClient, ListServersDetailsRequest
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion
from huaweicloudsdkevs.v2 import EvsClient, ListVolumesRequest
from huaweicloudsdkevs.v2.region.evs_region import EvsRegion
from huaweicloudsdkiam.v3 import IamClient
from huaweicloudsdkiam.v3.region.iam_region import IamRegion
from huaweicloudsdkvpc.v2 import ListSecurityGroupsRequest
from huaweicloudsdkvpc.v2.vpc_client import VpcClient as VpcClientV2
from huaweicloudsdkvpc.v3.region.vpc_region import VpcRegion
from huaweicloudsdkvpc.v3.vpc_client import VpcClient as VpcClientV3
from huaweicloudsdkfunctiongraph.v2 import FunctionGraphClient, ListFunctionsRequest
from huaweicloudsdkfunctiongraph.v2.region.functiongraph_region import FunctionGraphRegion
from huaweicloudsdktms.v1 import TmsClient
from huaweicloudsdktms.v1.region.tms_region import TmsRegion
from huaweicloudsdkdeh.v1 import DeHClient, ListDedicatedHostsRequest
from huaweicloudsdkdeh.v1.region.deh_region import DeHRegion
from huaweicloudsdkces.v2 import CesClient, ListAlarmRulesRequest
from huaweicloudsdkces.v2.region.ces_region import CesRegion
from huaweicloudsdkkms.v2 import KmsClient, ListKeysRequest, ListKeysRequestBody
from huaweicloudsdkkms.v2.region.kms_region import KmsRegion
from huaweicloudsdkeg.v1 import EgClient
from huaweicloudsdkeg.v1.region.eg_region import EgRegion
from huaweicloudsdkelb.v3.region.elb_region import ElbRegion
from huaweicloudsdkelb.v3 import ElbClient, ListLoadBalancersRequest, ListListenersRequest
from huaweicloudsdkeip.v3.region.eip_region import EipRegion
from huaweicloudsdkeip.v3 import EipClient
from huaweicloudsdkgeip.v3.region.geip_region import GeipRegion
from huaweicloudsdkgeip.v3 import GeipClient
from huaweicloudsdkims.v2.region.ims_region import ImsRegion
from huaweicloudsdkims.v2 import ImsClient, ListImagesRequest
from huaweicloudsdkcbr.v1.region.cbr_region import CbrRegion
from huaweicloudsdkcbr.v1 import CbrClient
from huaweicloudsdksmn.v2.region.smn_region import SmnRegion
from huaweicloudsdksmn.v2 import SmnClient, ListTopicsRequest
from huaweicloudsdknat.v2.region.nat_region import NatRegion
from huaweicloudsdknat.v2 import ListNatGatewaysRequest, NatClient, \
    ListNatGatewaySnatRulesRequest, ListNatGatewayDnatRulesRequest

log = logging.getLogger('custodian.huaweicloud.client')


class Session:
    """Session"""

    def __init__(self, options=None):
        self.region = os.getenv('HUAWEI_DEFAULT_REGION')
        self.token = None
        if not self.region:
            log.error('No default region set. Specify a default via HUAWEI_DEFAULT_REGION')
            sys.exit(1)

        if options is not None:
            self.ak = options.get('SecurityAccessKey')
            self.sk = options.get('SecuritySecretKey')
            self.token = options.get('SecurityToken')
        self.ak = os.getenv('HUAWEI_ACCESS_KEY_ID') or self.ak
        if self.ak is None:
            log.error('No access key id set. '
                      'Specify a default via HUAWEI_ACCESS_KEY_ID or context')
            sys.exit(1)

        self.sk = os.getenv('HUAWEI_SECRET_ACCESS_KEY') or self.sk
        if self.sk is None:
            log.error('No secret access key set. '
                      'Specify a default via HUAWEI_SECRET_ACCESS_KEY or context')
            sys.exit(1)

        self.tms_region = os.getenv('HUAWEI_DEFAULT_TMS_REGION')
        if not self.tms_region:
            self.tms_region = 'cn-north-4'

    def client(self, service):
        credentials = BasicCredentials(self.ak, self.sk, os.getenv('HUAWEI_PROJECT_ID')) \
            .with_security_token(self.token)
        if service == 'vpc':
            client = VpcClientV3.new_builder() \
                .with_credentials(credentials) \
                .with_region(VpcRegion.value_of(self.region)) \
                .build()
        elif service == 'vpc_v2':
            client = VpcClientV2.new_builder() \
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
                .with_region(TmsRegion.value_of(self.tms_region)) \
                .build()
        elif service == 'cbr':
            client = CbrClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(CbrRegion.value_of(self.region)) \
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
        elif service == 'deh':
            client = DeHClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(DeHRegion.value_of(self.region)) \
                .build()
        elif service == 'ces':
            client = CesClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(CesRegion.value_of(self.region)) \
                .build()
        elif service == 'smn':
            client = SmnClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(SmnRegion.value_of(self.region)) \
                .build()
        elif service == 'kms':
            client = KmsClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(KmsRegion.value_of(self.region)) \
                .build()
        elif service == 'functiongraph':
            client = FunctionGraphClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(FunctionGraphRegion.value_of(self.region)) \
                .build()
        elif service == 'eg':
            client = EgClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(EgRegion.value_of(self.region)) \
                .build()
        elif service in ['elb_loadbalancer', 'elb_listener']:
            client = ElbClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(ElbRegion.value_of(self.region)) \
                .build()
        elif service == 'eip':
            client = EipClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(EipRegion.value_of(self.region)) \
                .build()
        elif service == 'geip':
            client = GeipClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(GeipRegion.value_of(self.region)) \
                .build()
        elif service == 'ims':
            client = ImsClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(ImsRegion.value_of(self.region)) \
                .build()
        elif service == 'cbr-backup' or service == 'cbr-vault' or service == 'cbr-policy':
            client = CbrClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(CbrRegion.value_of(self.region)) \
                .build()
        elif service == 'smn':
            client = SmnClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(SmnRegion.value_of(self.region)) \
                .build()
        elif service in ['nat_gateway', 'nat_snat_rule', 'nat_dnat_rule']:
            client = NatClient.new_builder() \
                .with_credentials(credentials) \
                .with_region(NatRegion.value_of(self.region)) \
                .build()

        return client

    def request(self, service):
        if service == 'vpc' or service == 'vpc_v2':
            request = ListSecurityGroupsRequest()
        elif service == 'evs':
            request = ListVolumesRequest()
        elif service == 'config':
            request = ShowTrackerConfigRequest()
        elif service == 'ecs':
            request = ListServersDetailsRequest()
        elif service == 'deh':
            request = ListDedicatedHostsRequest()
        elif service == 'ces':
            request = ListAlarmRulesRequest()
        elif service == 'kms':
            request = ListKeysRequest()
            request.body = ListKeysRequestBody(
                key_spec="ALL"
            )
        elif service == 'functiongraph':
            request = ListFunctionsRequest()
        elif service == 'elb_loadbalancer':
            request = ListLoadBalancersRequest()
        elif service == 'elb_listener':
            request = ListListenersRequest()
        elif service == 'ims':
            request = ListImagesRequest()
        elif service == 'smn':
            request = ListTopicsRequest()
        elif service == 'nat_gateway':
            request = ListNatGatewaysRequest()
        elif service == 'nat_snat_rule':
            request = ListNatGatewaySnatRulesRequest()
        elif service == 'nat_dnat_rule':
            request = ListNatGatewayDnatRulesRequest()

        return request
