# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys

from huaweicloudsdkconfig.v1 import ConfigClient, ShowTrackerConfigRequest
from huaweicloudsdkconfig.v1.region.config_region import ConfigRegion
from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkcore.auth.provider import MetadataCredentialProvider
from huaweicloudsdkecs.v2 import EcsClient, ListServersDetailsRequest
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion
from huaweicloudsdkevs.v2 import EvsClient, ListVolumesRequest
from huaweicloudsdkevs.v2.region.evs_region import EvsRegion
from huaweicloudsdkiam.v5 import (
    IamClient as IamClientV5,
    ListUsersV5Request,
    ListPoliciesV5Request,
)
from huaweicloudsdkiam.v5.region import iam_region as iam_region_v5
from huaweicloudsdkiam.v3 import IamClient as IamClientV3
from huaweicloudsdkiam.v3.region.iam_region import IamRegion as iam_region_v3
from huaweicloudsdkvpc.v2 import ListSecurityGroupsRequest
from huaweicloudsdkvpc.v2.vpc_client import VpcClient as VpcClientV2
from huaweicloudsdkvpc.v3.region.vpc_region import VpcRegion
from huaweicloudsdkvpc.v3.vpc_client import VpcClient as VpcClientV3
from huaweicloudsdkfunctiongraph.v2 import FunctionGraphClient, ListFunctionsRequest
from huaweicloudsdkfunctiongraph.v2.region.functiongraph_region import (
    FunctionGraphRegion,
)
from huaweicloudsdktms.v1 import TmsClient
from huaweicloudsdktms.v1.region.tms_region import TmsRegion
from huaweicloudsdklts.v2 import LtsClient, ListTransfersRequest
from huaweicloudsdklts.v2.region.lts_region import LtsRegion
from huaweicloudsdkdeh.v1 import DeHClient, ListDedicatedHostsRequest
from huaweicloudsdkdeh.v1.region.deh_region import DeHRegion
from huaweicloudsdker.v3 import ErClient, ListEnterpriseRoutersRequest
from huaweicloudsdker.v3.region.er_region import ErRegion
from obs import ObsClient
from huaweicloudsdkces.v2 import CesClient, ListAlarmRulesRequest
from huaweicloudsdkces.v2.region.ces_region import CesRegion
from huaweicloudsdkkafka.v2 import KafkaClient, ListInstancesRequest
from huaweicloudsdkkafka.v2.region.kafka_region import KafkaRegion
from huaweicloudsdkkms.v2 import KmsClient, ListKeysRequest, ListKeysRequestBody
from huaweicloudsdkkms.v2.region.kms_region import KmsRegion
from huaweicloudsdkeg.v1 import EgClient
from huaweicloudsdkeg.v1.region.eg_region import EgRegion
from huaweicloudsdkelb.v3.region.elb_region import ElbRegion
from huaweicloudsdkelb.v3 import (
    ElbClient,
    ListLoadBalancersRequest,
    ListListenersRequest,
)
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
from huaweicloudsdknat.v2 import (
    ListNatGatewaysRequest,
    NatClient,
    ListNatGatewaySnatRulesRequest,
    ListNatGatewayDnatRulesRequest,
)
from huaweicloudsdkcts.v3 import (
    CtsClient,
    ListTrackersRequest,
    ListNotificationsRequest,
)
from huaweicloudsdkcts.v3.region.cts_region import CtsRegion
from huaweicloudsdkcbr.v1 import ListBackupsRequest, ListVaultRequest
from huaweicloudsdksfsturbo.v1 import SFSTurboClient, ListSharesRequest
from huaweicloudsdksfsturbo.v1.region.sfsturbo_region import SFSTurboRegion
from huaweicloudsdkcoc.v1 import CocClient, ListInstanceCompliantRequest
from huaweicloudsdkcoc.v1.region.coc_region import CocRegion
from huaweicloudsdkorganizations.v1 import (
    OrganizationsClient,
    ListAccountsRequest,
    ListOrganizationalUnitsRequest,
    ListPoliciesRequest,
)
from huaweicloudsdkorganizations.v1.region.organizations_region import (
    OrganizationsRegion,
)
from huaweicloudsdkantiddos.v1 import AntiDDoSClient, ListDDosStatusRequest
from huaweicloudsdkantiddos.v1.region.antiddos_region import AntiDDoSRegion
from huaweicloudsdksecmaster.v2 import ListWorkspacesRequest, SecMasterClient
from huaweicloudsdksecmaster.v2.region.secmaster_region import SecMasterRegion
from huaweicloudsdkram.v1 import (
    RamClient,
    SearchResourceShareAssociationsRequest,
    SearchResourceShareAssociationsReqBody,
)
from huaweicloudsdkram.v1.region.ram_region import RamRegion


log = logging.getLogger("custodian.huaweicloud.client")


class Session:
    """Session"""

    def __init__(self, options=None):
        self.region = os.getenv("HUAWEI_DEFAULT_REGION")
        self.token = None
        if not self.region:
            log.error(
                "No default region set. Specify a default via HUAWEI_DEFAULT_REGION"
            )
            sys.exit(1)

        if options is not None:
            self.ak = options.get("SecurityAccessKey")
            self.sk = options.get("SecuritySecretKey")
            self.token = options.get("SecurityToken")

        self.ak = os.getenv("HUAWEI_ACCESS_KEY_ID") or self.ak
        self.sk = os.getenv("HUAWEI_SECRET_ACCESS_KEY") or self.sk

    def client(self, service):
        if self.ak is None or self.sk is None:
            # basic
            basic_provider = (
                MetadataCredentialProvider.get_basic_credential_metadata_provider()
            )
            credentials = basic_provider.get_credentials()

            # global
            global_provider = (
                MetadataCredentialProvider.get_global_credential_metadata_provider()
            )
            globalCredentials = global_provider.get_credentials()
        else:
            credentials = BasicCredentials(
                self.ak, self.sk, os.getenv("HUAWEI_PROJECT_ID")
            ).with_security_token(self.token)
            globalCredentials = GlobalCredentials(self.ak, self.sk).with_security_token(
                self.token
            )

        if service == "vpc":
            client = (
                VpcClientV3.new_builder()
                .with_credentials(credentials)
                .with_region(VpcRegion.value_of(self.region))
                .build()
            )
        elif service == "vpc_v2":
            client = (
                VpcClientV2.new_builder()
                .with_credentials(credentials)
                .with_region(VpcRegion.value_of(self.region))
                .build()
            )
        elif service == "ecs":
            client = (
                EcsClient.new_builder()
                .with_credentials(credentials)
                .with_region(EcsRegion.value_of(self.region))
                .build()
            )
        elif service == "er":
            client = (
                ErClient.new_builder()
                .with_credentials(credentials)
                .with_region(ErRegion.value_of(self.region))
                .build()
            )
        elif service == "evs":
            client = (
                EvsClient.new_builder()
                .with_credentials(credentials)
                .with_region(EvsRegion.value_of(self.region))
                .build()
            )
        elif service == "lts-transfer":
            client = (
                LtsClient.new_builder()
                .with_credentials(credentials)
                .with_region(LtsRegion.value_of(self.region))
                .build()
            )
        elif service == "tms":
            client = (
                TmsClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(TmsRegion.value_of("ap-southeast-1"))
                .build()
            )
        elif service == "cbr":
            client = (
                CbrClient.new_builder()
                .with_credentials(credentials)
                .with_region(CbrRegion.value_of(self.region))
                .build()
            )
        elif service in ["iam-user", "iam-policy"]:
            client = (
                IamClientV5.new_builder()
                .with_credentials(globalCredentials)
                .with_region(iam_region_v5.IamRegion.value_of(self.region))
                .build()
            )
        elif service == "iam-v3":
            client = (
                IamClientV3.new_builder()
                .with_credentials(globalCredentials)
                .with_region(iam_region_v3.value_of(self.region))
                .build()
            )
        elif service == "config":
            client = (
                ConfigClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(ConfigRegion.value_of("cn-north-4"))
                .build()
            )
        elif service == "deh":
            client = (
                DeHClient.new_builder()
                .with_credentials(credentials)
                .with_region(DeHRegion.value_of(self.region))
                .build()
            )
        elif service == "obs":
            client = self.region_client(service, self.region)
        elif service == "ces":
            client = (
                CesClient.new_builder()
                .with_credentials(credentials)
                .with_region(CesRegion.value_of(self.region))
                .build()
            )
        elif service == "smn":
            client = (
                SmnClient.new_builder()
                .with_credentials(credentials)
                .with_region(SmnRegion.value_of(self.region))
                .build()
            )
        elif service == "kms":
            client = (
                KmsClient.new_builder()
                .with_credentials(credentials)
                .with_region(KmsRegion.value_of(self.region))
                .build()
            )
        elif service == "functiongraph":
            client = (
                FunctionGraphClient.new_builder()
                .with_credentials(credentials)
                .with_region(FunctionGraphRegion.value_of(self.region))
                .build()
            )
        elif service == "eg":
            client = (
                EgClient.new_builder()
                .with_credentials(credentials)
                .with_region(EgRegion.value_of(self.region))
                .build()
            )
        elif service in ["elb_loadbalancer", "elb_listener"]:
            client = (
                ElbClient.new_builder()
                .with_credentials(credentials)
                .with_region(ElbRegion.value_of(self.region))
                .build()
            )
        elif service == "eip":
            client = (
                EipClient.new_builder()
                .with_credentials(credentials)
                .with_region(EipRegion.value_of(self.region))
                .build()
            )
        elif service == "geip":
            client = (
                GeipClient.new_builder()
                .with_credentials(credentials)
                .with_region(GeipRegion.value_of(self.region))
                .build()
            )
        elif service == "ims":
            client = (
                ImsClient.new_builder()
                .with_credentials(credentials)
                .with_region(ImsRegion.value_of(self.region))
                .build()
            )
        elif (
            service == "cbr-backup" or service == "cbr-vault" or service == "cbr-policy"
        ):
            client = (
                CbrClient.new_builder()
                .with_credentials(credentials)
                .with_region(CbrRegion.value_of(self.region))
                .build()
            )
        elif service == "smn":
            client = (
                SmnClient.new_builder()
                .with_credentials(credentials)
                .with_region(SmnRegion.value_of(self.region))
                .build()
            )
        elif service in ["nat_gateway", "nat_snat_rule", "nat_dnat_rule"]:
            client = (
                NatClient.new_builder()
                .with_credentials(credentials)
                .with_region(NatRegion.value_of(self.region))
                .build()
            )
        elif service == "secmaster":
            client = (
                SecMasterClient.new_builder()
                .with_credentials(credentials)
                .with_region(SecMasterRegion.value_of(self.region))
                .build()
            )
        elif service == "cts-tracker":
            client = (
                CtsClient.new_builder()
                .with_credentials(credentials)
                .with_region(CtsRegion.value_of(self.region))
                .build()
            )
        elif service == "cts-notification-smn":
            client = (
                CtsClient.new_builder()
                .with_credentials(credentials)
                .with_region(CtsRegion.value_of(self.region))
                .build()
            )
        elif service == "cts-notification-func":
            client = (
                CtsClient.new_builder()
                .with_credentials(credentials)
                .with_region(CtsRegion.value_of(self.region))
                .build()
            )
        elif service == "sfsturbo":
            client = (
                SFSTurboClient.new_builder()
                .with_credentials(credentials)
                .with_region(SFSTurboRegion.value_of(self.region))
                .build()
            )
        elif service == "cbr":
            client = (
                CbrClient.new_builder()
                .with_credentials(credentials)
                .with_region(CbrRegion.value_of(self.region))
                .build()
            )
        elif service == "coc":
            client = (
                CocClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(CocRegion.value_of("cn-north-4"))
                .build()
            )
        elif service in ["org-policy", "org-unit", "org-account"]:
            client = (
                OrganizationsClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(OrganizationsRegion.CN_NORTH_4)
                .build()
            )
        elif service == "ram":
            client = (
                RamClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(RamRegion.CN_NORTH_4)
                .build()
            )
        elif service == "antiddos":
            client = (
                AntiDDoSClient.new_builder()
                .with_credentials(credentials)
                .with_region(AntiDDoSRegion.value_of(self.region))
                .build()
            )
        elif service == 'kafka':
            client = (
                KafkaClient.new_builder()
                .with_credentials(credentials)
                .with_region(KafkaRegion.value_of(self.region))
                .build()
            )

        return client

    def region_client(self, service, region):
        ak = self.ak
        sk = self.sk
        token = self.token

        if self.ak is None or self.sk is None:
            basic_provider = (
                MetadataCredentialProvider.get_basic_credential_metadata_provider()
            )
            credentials = basic_provider.get_credentials()
            ak = credentials.ak
            sk = credentials.sk
            token = credentials.security_token

        if service == "obs":
            server = "https://obs." + region + ".myhuaweicloud.com"
            client = ObsClient(
                access_key_id=ak,
                secret_access_key=sk,
                server=server,
                security_token=token,
            )
        return client

    def request(self, service):
        if service == "vpc" or service == "vpc_v2":
            request = ListSecurityGroupsRequest()
        elif service == "evs":
            request = ListVolumesRequest()
        elif service == "er":
            request = ListEnterpriseRoutersRequest()
        elif service == "lts-transfer":
            request = ListTransfersRequest()
        elif service == "config":
            request = ShowTrackerConfigRequest()
        elif service == "ecs":
            request = ListServersDetailsRequest(
                not_tags="__type_baremetal"
            )
        elif service == "deh":
            request = ListDedicatedHostsRequest()
        elif service == "obs":
            request = True
        elif service == "iam-user":
            request = ListUsersV5Request()
        elif service == "iam-policy":
            request = ListPoliciesV5Request()
        elif service == "ces":
            request = ListAlarmRulesRequest()
        elif service == "org-policy":
            request = ListPoliciesRequest()
        elif service == "org-unit":
            request = ListOrganizationalUnitsRequest()
        elif service == "org-account":
            request = ListAccountsRequest()

        elif service == "kms":
            request = ListKeysRequest()
            request.body = ListKeysRequestBody(key_spec="ALL")
        elif service == "functiongraph":
            request = ListFunctionsRequest()
        elif service == "elb_loadbalancer":
            request = ListLoadBalancersRequest()
        elif service == "elb_listener":
            request = ListListenersRequest()
        elif service == "ims":
            request = ListImagesRequest()
        elif service == "smn":
            request = ListTopicsRequest()
        elif service == "nat_gateway":
            request = ListNatGatewaysRequest()
        elif service == "nat_snat_rule":
            request = ListNatGatewaySnatRulesRequest()
        elif service == "nat_dnat_rule":
            request = ListNatGatewayDnatRulesRequest()
        elif service == "secmaster":
            request = ListWorkspacesRequest()
        elif service == "cts-tracker":
            request = ListTrackersRequest()
        elif service == "cts-notification-smn":
            request = ListNotificationsRequest()
            request.notification_type = "smn"
        elif service == "cts-notification-func":
            request = ListNotificationsRequest()
            request.notification_type = "fun"
        elif service == "cbr-backup":
            request = ListBackupsRequest()
            request.show_replication = True
        elif service == "cbr-vault":
            request = ListVaultRequest()
        elif service == "sfsturbo":
            request = ListSharesRequest()
        elif service == "coc":
            request = ListInstanceCompliantRequest()
        elif service == "ram":
            request = SearchResourceShareAssociationsRequest()
            request.body = SearchResourceShareAssociationsReqBody(
                association_type="principal", association_status="associated"
            )
        elif service == "antiddos":
            request = ListDDosStatusRequest()
        elif service == 'kafka':
            request = ListInstancesRequest()

        return request
