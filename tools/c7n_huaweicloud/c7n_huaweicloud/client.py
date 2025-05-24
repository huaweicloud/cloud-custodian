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
from huaweicloudsdkbms.v1 import BmsClient, ListBareMetalServerDetailsRequest
from huaweicloudsdkbms.v1.region.bms_region import BmsRegion
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
from huaweicloudsdkeg.v1 import ListSubscriptionsRequest
from huaweicloudsdkeip.v3.region.eip_region import EipRegion
from huaweicloudsdkeip.v3 import EipClient, ListPublicipsRequest
from huaweicloudsdkeip.v2 import EipClient as EipClientV2
from huaweicloudsdkeip.v2.region.eip_region import EipRegion as EipRegionV2
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
from huaweicloudsdkhss.v5 import ListHostStatusRequest, HssClient
from huaweicloudsdkhss.v5.region.hss_region import HssRegion
from huaweicloudsdkram.v1 import (
    RamClient,
    SearchResourceShareAssociationsRequest,
    SearchResourceShareAssociationsReqBody,
)
from huaweicloudsdkrds.v3 import RdsClient, ListInstancesRequest as RdsListInstancesRequest
from huaweicloudsdkrds.v3.region.rds_region import RdsRegion
from huaweicloudsdkram.v1.region.ram_region import RamRegion
from huaweicloudsdkrocketmq.v2 import (
    RocketMQClient, ListInstancesRequest as RocketMQListInstancesRequest
)
from huaweicloudsdkrocketmq.v2.region.rocketmq_region import RocketMQRegion
from huaweicloudsdkapig.v2 import (
    ApigClient,
    ListApisV2Request,
    ListEnvironmentsV2Request,
    ListApiGroupsV2Request,
    ListInstancesV2Request,
)
from huaweicloudsdkapig.v2.region.apig_region import ApigRegion
from huaweicloudsdkswr.v2 import SwrClient, ListReposDetailsRequest, ListRepositoryTagsRequest
from huaweicloudsdkswr.v2.region.swr_region import SwrRegion
from huaweicloudsdkscm.v3 import ScmClient, ListCertificatesRequest
from huaweicloudsdkscm.v3.region.scm_region import ScmRegion
from huaweicloudsdkaom.v2 import (
    AomClient,
    ListMetricOrEventAlarmRuleRequest
)
from huaweicloudsdkaom.v2.region.aom_region import AomRegion
from huaweicloudsdkdc.v3 import DcClient, ListDirectConnectsRequest
from huaweicloudsdkdc.v3.region.dc_region import DcRegion
from huaweicloudsdkcc.v3 import CcClient, ListCentralNetworksRequest
from huaweicloudsdkcc.v3.region.cc_region import CcRegion
from huaweicloudsdkcdn.v2 import CdnClient, ListDomainsRequest
from huaweicloudsdkcdn.v2.region.cdn_region import CdnRegion
from huaweicloudsdkworkspace.v2 import WorkspaceClient, ListDesktopsDetailRequest
from huaweicloudsdkworkspace.v2.region.workspace_region import WorkspaceRegion
from huaweicloudsdkccm.v1 import CcmClient, ListCertificateAuthorityRequest, ListCertificateRequest
from huaweicloudsdkccm.v1.region.ccm_region import CcmRegion

log = logging.getLogger("custodian.huaweicloud.client")


class Session:
    """Session"""

    def __init__(self, options=None):
        self.token = None
        self.domain_id = None
        self.region = None
        self.ak = None
        self.sk = None

        if options is not None:
            self.ak = options.get("access_key_id")
            self.sk = options.get("secret_access_key")
            self.token = options.get("security_token")
            self.domain_id = options.get("domain_id")
            self.region = options.get("region")

        self.ak = self.ak or os.getenv("HUAWEI_ACCESS_KEY_ID")
        self.sk = self.sk or os.getenv("HUAWEI_SECRET_ACCESS_KEY")
        self.region = self.region or os.getenv("HUAWEI_DEFAULT_REGION")

        if not self.region:
            log.error(
                "No default region set. Specify a default via HUAWEI_DEFAULT_REGION."
            )
            sys.exit(1)

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
            globalCredentials = (GlobalCredentials(self.ak, self.sk, self.domain_id)
                                 .with_security_token(self.token))
        client = None
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
        elif service == "eip_v2":
            client = (
                EipClientV2.new_builder()
                .with_credentials(credentials)
                .with_region(EipRegionV2.value_of(self.region))
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
        elif service == "workspace":
            client = (
                WorkspaceClient.new_builder()
                .with_credentials(credentials)
                .with_region(WorkspaceRegion.value_of(self.region))
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
        elif service == "hss":
            client = (
                HssClient.new_builder()
                .with_credentials(credentials)
                .with_region(HssRegion.value_of(self.region))
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
        elif service == 'reliability':
            client = (
                RocketMQClient.new_builder()
                .with_credentials(credentials)
                .with_region(RocketMQRegion.value_of(self.region))
                .build()
            )
        elif service == 'apig' or service in ['apig-api', 'apig-stage', 'apig-api-groups',
                                              'apig-instance']:
            client = (
                ApigClient.new_builder()
                .with_credentials(credentials)
                .with_region(ApigRegion.value_of(self.region))
                .build()
            )
        elif service in ['swr', 'swr-image']:
            client = (
                SwrClient.new_builder()
                .with_credentials(credentials)
                .with_region(SwrRegion.value_of(self.region))
                .build()
            )
        elif service == 'ccm-ssl-certificate':
            client = (
                ScmClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(ScmRegion.value_of("ap-southeast-1"))
                .build()
            )
        elif service == 'dc':
            client = (
                DcClient.new_builder()
                .with_credentials(credentials)
                .with_region(DcRegion.value_of(self.region))
                .build()
            )
        elif service == "cc":
            client = (
                CcClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(CcRegion.CN_NORTH_4)
                .build()
            )
        elif service == "cdn":
            client = (
                CdnClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(CdnRegion.CN_NORTH_1)
                .build()
            )
        elif service == "bms":
            client = (
                BmsClient.new_builder()
                .with_credentials(credentials)
                .with_region(BmsRegion.value_of(self.region))
                .build()
            )
        elif service == "rds":
            client = (
                RdsClient.new_builder()
                .with_credentials(credentials)
                .with_region(RdsRegion.value_of(self.region))
                .build()
            )
        elif service == 'aom':
            client = (
                AomClient.new_builder()
                .with_credentials(credentials)
                .with_region(AomRegion.value_of(self.region))
                .build()
            )
        elif service in ['ccm-private-ca', 'ccm-private-certificate']:
            client = (
                CcmClient.new_builder()
                .with_credentials(globalCredentials)
                .with_region(CcmRegion.value_of("ap-southeast-3"))
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
        elif service == "cc":
            request = ListCentralNetworksRequest()
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
        elif service == "workspace":
            request = ListDesktopsDetailRequest()
        elif service == "kms":
            request = ListKeysRequest()
            request.body = ListKeysRequestBody(key_spec="ALL")
        elif service == "functiongraph":
            request = ListFunctionsRequest()
        elif service == "elb_loadbalancer":
            request = ListLoadBalancersRequest()
        elif service == "elb_listener":
            request = ListListenersRequest()
        elif service == "eip":
            request = ListPublicipsRequest()
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
        elif service == "hss":
            request = ListHostStatusRequest()
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
        elif service == "cdn":
            request = ListDomainsRequest()
        elif service == 'reliability':
            request = RocketMQListInstancesRequest()
        elif service == 'apig-api':
            request = ListApisV2Request()
        elif service == 'apig-stage':
            request = ListEnvironmentsV2Request()
        elif service == 'apig-api-groups':
            request = ListApiGroupsV2Request()
        elif service == 'apig-instance':
            request = ListInstancesV2Request()
        elif service == 'swr':
            request = ListReposDetailsRequest()
        elif service == 'swr-image':
            request = ListRepositoryTagsRequest()
        elif service == 'ccm-ssl-certificate':
            request = ListCertificatesRequest()
            request.expired_days_since = 1095
        elif service == 'dc':
            request = ListDirectConnectsRequest()
        elif service == "bms":
            request = ListBareMetalServerDetailsRequest()
        elif service == 'rds':
            request = RdsListInstancesRequest()
        elif service == 'eg':
            request = ListSubscriptionsRequest()
        elif service == 'aom':
            request = ListMetricOrEventAlarmRuleRequest(enterprise_project_id="all_granted_eps")
        elif service == 'ccm-private-ca':
            request = ListCertificateAuthorityRequest()
        elif service == 'ccm-private-certificate':
            request = ListCertificateRequest()
        return request
