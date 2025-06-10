# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import hashlib
import hmac
import binascii
from urllib.parse import quote, unquote

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
from huaweicloudsdklts.v2 import LtsClient, ListTransfersRequest, ListLogGroupsRequest
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
from huaweicloudsdkcbr.v1 import ListBackupsRequest, ListVaultRequest, ListProtectableRequest
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

# CCI related imports - for Huawei Cloud Container Instance Service
try:
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

import requests
import json
from datetime import datetime

log = logging.getLogger("custodian.huaweicloud.client")


# Huawei Cloud V4 signature algorithm implementation
def hmacsha256(key, msg):
    """HMAC-SHA256 calculation"""
    return hmac.new(key.encode('utf-8'),
                    msg.encode('utf-8'),
                    digestmod=hashlib.sha256).digest()


def urlencode_path(path):
    """URL encode path"""
    return quote(path, safe='~')


def hex_encode_sha256_hash(data):
    """SHA256 hash and convert to hexadecimal"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    sha = hashlib.sha256()
    sha.update(data)
    return sha.hexdigest()


def find_header(headers, header_name):
    """Find request header"""
    for key, value in headers.items():
        if key.lower() == header_name.lower():
            return value
    return None


class HttpRequest:
    """HTTP request wrapper class"""

    def __init__(self, method="", url="", headers=None, body=""):
        self.method = method

        # Parse URL
        sp = url.split("://", 1)
        self.scheme = 'https'
        if len(sp) > 1:
            self.scheme = sp[0]
            url = sp[1]

        # Parse query parameters
        self.query = {}
        sp = url.split('?', 1)
        url = sp[0]
        if len(sp) > 1:
            for kv in sp[1].split("&"):
                sp_kv = kv.split("=", 1)
                k = sp_kv[0]
                v = ""
                if len(sp_kv) > 1:
                    v = sp_kv[1]
                if k != '':
                    k = unquote(k)
                    v = unquote(v)
                    if k in self.query:
                        self.query[k].append(v)
                    else:
                        self.query[k] = [v]

        # Parse host and path
        sp = url.split('/', 1)
        self.host = sp[0]
        if len(sp) > 1:
            self.uri = '/' + sp[1]
        else:
            self.uri = '/'

        self.headers = headers if headers else {}
        self.body = body.encode("utf-8") if isinstance(body, str) else body


class HuaweiCloudSigner:
    """Huawei Cloud V4 signer"""

    DateFormat = "%Y%m%dT%H%M%SZ"
    Algorithm = "SDK-HMAC-SHA256"
    HeaderXDate = "X-Sdk-Date"
    HeaderHost = "host"
    HeaderAuthorization = "Authorization"
    HeaderContentSHA256 = "x-sdk-content-sha256"

    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key

    def sign(self, request):
        """Sign the request"""
        if isinstance(request.body, str):
            request.body = request.body.encode('utf-8')

        # Add timestamp header
        header_time = find_header(request.headers, self.HeaderXDate)
        if header_time is None:
            time = datetime.utcnow()
            request.headers[self.HeaderXDate] = datetime.strftime(time, self.DateFormat)
        else:
            time = datetime.strptime(header_time, self.DateFormat)

        # Add Host header
        have_host = False
        for key in request.headers:
            if key.lower() == 'host':
                have_host = True
                break
        if not have_host:
            request.headers["host"] = request.host

        # Add Content-Length header
        request.headers["content-length"] = str(len(request.body))

        # Construct query string
        query_string = self._canonical_query_string(request)
        if query_string != "":
            request.uri = request.uri + "?" + query_string

        # Get signed headers list
        signed_headers = self._signed_headers(request)

        # Construct canonical request
        canonical_request = self._canonical_request(request, signed_headers)

        # Construct string to sign
        string_to_sign = self._string_to_sign(canonical_request, time)

        # Calculate signature
        signature = self._sign_string_to_sign(string_to_sign, self.secret_key)

        # Construct authorization header
        auth_value = self._auth_header_value(signature, self.access_key, signed_headers)
        request.headers[self.HeaderAuthorization] = auth_value

    def _canonical_request(self, request, signed_headers):
        """Construct canonical request"""
        canonical_headers = self._canonical_headers(request, signed_headers)
        content_hash = find_header(request.headers, self.HeaderContentSHA256)
        if content_hash is None:
            content_hash = hex_encode_sha256_hash(request.body)

        return "%s\n%s\n%s\n%s\n%s\n%s" % (
            request.method.upper(),
            self._canonical_uri(request),
            self._canonical_query_string(request),
            canonical_headers,
            ";".join(signed_headers),
            content_hash
        )

    def _canonical_uri(self, request):
        """Construct canonical URI"""
        patterns = unquote(request.uri).split('/')
        uri = []
        for value in patterns:
            uri.append(urlencode_path(value))
        url_path = "/".join(uri)
        if url_path[-1] != '/':
            url_path = url_path + "/"
        return url_path

    def _canonical_query_string(self, request):
        """Construct canonical query string"""
        keys = []
        for key in request.query:
            keys.append(key)
        keys.sort()

        arr = []
        for key in keys:
            ke = urlencode_path(key)
            value = request.query[key]
            if isinstance(value, list):
                value.sort()
                for v in value:
                    kv = ke + "=" + urlencode_path(str(v))
                    arr.append(kv)
            else:
                kv = ke + "=" + urlencode_path(str(value))
                arr.append(kv)
        return '&'.join(arr)

    def _canonical_headers(self, request, signed_headers):
        """Construct canonical headers"""
        arr = []
        _headers = {}
        for k in request.headers:
            key_encoded = k.lower()
            value = request.headers[k]
            value_encoded = value.strip()
            _headers[key_encoded] = value_encoded
            request.headers[k] = value_encoded.encode("utf-8").decode('iso-8859-1')

        for k in signed_headers:
            arr.append(k + ":" + _headers[k])
        return '\n'.join(arr) + "\n"

    def _signed_headers(self, request):
        """Get signed headers list"""
        arr = []
        for k in request.headers:
            arr.append(k.lower())
        arr.sort()
        return arr

    def _string_to_sign(self, canonical_request, time):
        """Construct string to sign"""
        hashed_canonical_request = hex_encode_sha256_hash(canonical_request.encode('utf-8'))
        return "%s\n%s\n%s" % (
            self.Algorithm,
            datetime.strftime(time, self.DateFormat),
            hashed_canonical_request
        )

    def _sign_string_to_sign(self, string_to_sign, secret_key):
        """Sign string to sign"""
        hmac_digest = hmacsha256(secret_key, string_to_sign)
        return binascii.hexlify(hmac_digest).decode()

    def _auth_header_value(self, signature, access_key, signed_headers):
        """Construct authorization header value"""
        return "%s Access=%s, SignedHeaders=%s, Signature=%s" % (
            self.Algorithm,
            access_key,
            ";".join(signed_headers),
            signature
        )


class CCIClient:
    """Huawei Cloud CCI (Container Instance) Service Client
    CCI service uses Kubernetes API format but requires Huawei Cloud authentication.
    This client wraps API calls to CCI service.
    """

    def __init__(self, region, credentials):
        """Initialize CCI client
        Args:
            region: Huawei Cloud region
            credentials: Huawei Cloud authentication credentials
        """
        self.region = region
        self.credentials = credentials
        self.base_url = f"https://cci.{region}.myhuaweicloud.com"
        self.api_version = "v1"

        # Initialize signer
        if hasattr(credentials, 'ak') and hasattr(credentials, 'sk'):
            self.signer = HuaweiCloudSigner(credentials.ak, credentials.sk)
        else:
            self.signer = None
            log.warning("CCI client initialized without valid credentials")

    def _make_request(self, method, endpoint, **kwargs):
        """Make API request
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Other request parameters
        Returns:
            Response data
        """
        response = None  # Initialize response variable
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'cloud-custodian-huaweicloud/1.0'
            }

            # Merge user-provided headers
            if 'headers' in kwargs:
                headers.update(kwargs.pop('headers'))

            # Get request body
            body = ""
            if 'json' in kwargs:
                body = json.dumps(kwargs.pop('json'))
                headers['Content-Type'] = 'application/json'
            elif 'data' in kwargs:
                body = kwargs.pop('data')
                if isinstance(body, dict):
                    body = json.dumps(body)
                    headers['Content-Type'] = 'application/json'

            # Add Huawei Cloud authentication header
            if self.signer:
                # Create HTTP request object
                request = HttpRequest(method, url, headers, body)

                # Sign the request
                self.signer.sign(request)

                # Update headers
                headers = request.headers

                log.debug(f"CCI API request signed successfully for {method} {url}")
            else:
                log.warning(f"Making unsigned request to {method} {url}")

            # Send request
            response = requests.request(method, url, headers=headers, data=body, **kwargs)
            response.raise_for_status()

            # Parse response
            if response.content:
                try:
                    response_data = response.json()
                    # Process response data, add id attribute to each resource's metadata
                    self._process_response_data(response_data)
                    return response_data
                except json.JSONDecodeError:
                    log.warning(f"Non-JSON response from CCI API: {response.text}")
                    return response.text
            return None

        except requests.exceptions.RequestException as e:
            log.error(f"CCI API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                log.error(f"Response status: {e.response.status_code}")
                log.error(f"Response content: {e.response.text}")
            elif response is not None:
                log.debug(f"Local response was: {response}")
            raise

    def _process_response_data(self, data):
        """Process response data, add id attribute to metadata
        Args:
            data: Response data
        """
        if isinstance(data, dict):
            # Process single resource
            if 'metadata' in data:
                self._add_id_to_metadata(data['metadata'])
                # Promote metadata.creationTimestamp to same level as metadata
                self._add_creation_timestamp(data)

            # Process resource list (items field)
            if 'items' in data and isinstance(data['items'], list):
                for item in data['items']:
                    if isinstance(item, dict) and 'metadata' in item:
                        item["id"] = item["metadata"]["uid"]
                        # Promote metadata.creationTimestamp to same level as metadata
                        self._add_creation_timestamp(item)
        elif isinstance(data, list):
            # Process resource list
            for item in data:
                if isinstance(item, dict) and 'metadata' in item:
                    item["id"] = item["metadata"]["uid"]
                    # Promote metadata.creationTimestamp to same level as metadata
                    self._add_creation_timestamp(item)

    def _add_id_to_metadata(self, metadata):
        """Add id attribute to metadata
        Args:
            metadata: Resource metadata dictionary
        """
        if isinstance(metadata, dict) and 'uid' in metadata:
            metadata['id'] = metadata['uid']

    def _add_creation_timestamp(self, resource):
        """Promote metadata.creationTimestamp to same level as metadata
        Args:
            resource: Resource dictionary
        """
        if isinstance(resource, dict) and 'metadata' in resource:
            metadata = resource['metadata']
            if isinstance(metadata, dict) and 'creationTimestamp' in metadata:
                # Assign metadata.creationTimestamp value to same-level creationTimestamp
                resource['creationTimestamp'] = metadata['creationTimestamp']

    def list_namespaces(self, request=None):
        """List all namespaces
        Args:
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing namespace list
        """
        endpoint = f"api/{self.api_version}/namespaces"
        return self._make_request("GET", endpoint)

    def list_namespaced_pods(self, namespace="default", request=None):
        """List Pods in all namespaces
        Args:
            namespace: Namespace name (this parameter will
            be ignored, gets pods from all namespaces)
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing Pod list from all namespaces
        """
        # First get all namespaces
        namespaces_response = self.list_namespaces()

        # Initialize merged response structure
        combined_response = {
            "apiVersion": "v1",
            "kind": "PodList",
            "items": []
        }

        # Extract namespace names from namespace response
        if namespaces_response and "items" in namespaces_response:
            for namespace_item in namespaces_response["items"]:
                if "metadata" in namespace_item and "name" in namespace_item["metadata"]:
                    namespace_name = namespace_item["metadata"]["name"]

                    try:
                        # Get all pods in this namespace
                        endpoint = f"api/{self.api_version}/namespaces/{namespace_name}/pods"
                        pods_response = self._make_request("GET", endpoint)

                        # Add pods from this namespace to merged response
                        if pods_response and "items" in pods_response:
                            combined_response["items"].extend(pods_response["items"])

                    except Exception as e:
                        log.warning(f"Failed to get pods from namespace {namespace_name}: {e}")
                        continue

        # Process final merged response
        self._process_response_data(combined_response)
        return combined_response

    def list_namespaced_configmaps(self, namespace="default", request=None):

        """List ConfigMaps in all namespaces
        Args:
            namespace: Namespace name (this parameter will
            be ignored, gets configmaps from all namespaces)
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing ConfigMap list from all namespaces
        """
        # First get all namespaces
        namespaces_response = self.list_namespaces()

        # Initialize merged response structure
        combined_response = {
            "apiVersion": "v1",
            "kind": "ConfigMapList",
            "items": []
        }

        # Extract namespace names from namespace response
        if namespaces_response and "items" in namespaces_response:
            for namespace_item in namespaces_response["items"]:
                if "metadata" in namespace_item and "name" in namespace_item["metadata"]:
                    namespace_name = namespace_item["metadata"]["name"]

                    try:
                        # Get all configmaps in this namespace
                        endpoint = f"api/{self.api_version}/namespaces/{namespace_name}/configmaps"
                        configmaps_response = self._make_request("GET", endpoint)

                        # Add configmaps from this namespace to merged response
                        if configmaps_response and "items" in configmaps_response:
                            combined_response["items"].extend(configmaps_response["items"])

                    except Exception as e:
                        log.warning(
                            f"Failed to get configmaps from namespace {namespace_name}: {e}")
                        continue

        # Process final merged response
        self._process_response_data(combined_response)
        return combined_response

    def list_namespaced_secrets(self, namespace="default", request=None):
        """List Secrets in all namespaces
        Args:
            namespace: Namespace name (this parameter will be ignored,
            gets secrets from all namespaces)
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing Secret list from all namespaces
        """
        # First get all namespaces
        namespaces_response = self.list_namespaces()

        # Initialize merged response structure
        combined_response = {
            "apiVersion": "v1",
            "kind": "SecretList",
            "items": []
        }

        # Extract namespace names from namespace response
        if namespaces_response and "items" in namespaces_response:
            for namespace_item in namespaces_response["items"]:
                if "metadata" in namespace_item and "name" in namespace_item["metadata"]:
                    namespace_name = namespace_item["metadata"]["name"]

                    try:
                        # Get all secrets in this namespace
                        endpoint = f"api/{self.api_version}/namespaces/{namespace_name}/secrets"
                        secrets_response = self._make_request("GET", endpoint)

                        # Add secrets from this namespace to merged response
                        if secrets_response and "items" in secrets_response:
                            combined_response["items"].extend(secrets_response["items"])

                    except Exception as e:
                        log.warning(f"Failed to get secrets from namespace {namespace_name}: {e}")
                        continue

        # Process final merged response
        self._process_response_data(combined_response)
        return combined_response

    def patch_namespaced_pod(self, name, namespace, body):
        """Modify Pod
        Args:
            name: Pod name
            namespace: Namespace name
            body: Modification data body
        Returns:
            dict: Response result of modification operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/pods/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_pod(self, name, namespace):
        """Delete Pod
        Args:
            name: Pod name
            namespace: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/pods/{name}"
        return self._make_request("DELETE", endpoint)

    def patch_namespaced_configmap(self, name, namespace, body):
        """Modify ConfigMap
        Args:
            name: ConfigMap name
            namespace: Namespace name
            body: Modification data body
        Returns:
            dict: Response result of modification operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/configmaps/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_configmap(self, name, namespace):
        """Delete ConfigMap
        Args:
            name: ConfigMap name
            namespace: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/configmaps/{name}"
        return self._make_request("DELETE", endpoint)

    def patch_namespaced_secret(self, name, namespace, body):
        """Modify Secret
        Args:
            name: Secret name
            namespace: Namespace name
            body: Modification data body
        Returns:
            dict: Response result of modification operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/secrets/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_secret(self, name, namespace):
        """Delete Secret
        Args:
            name: Secret name
            namespace: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/secrets/{name}"
        return self._make_request("DELETE", endpoint)

    def delete_namespace(self, name):
        """Delete namespace
        Args:
            name: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"api/{self.api_version}/namespaces/{name}"
        return self._make_request("DELETE", endpoint)


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
        elif service in ["lts-transfer", "lts-stream"]:
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
                service == "cbr-backup" or service == "cbr-vault" or service == "cbr-protectable"
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
        elif service == "cci":
            # CCI service uses special client
            if not K8S_AVAILABLE:
                log.warning("Kubernetes client not available, CCI functionality may be limited")
            client = CCIClient(self.region, credentials)
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
        elif service == "lts-stream":
            request = ListLogGroupsRequest()
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
        elif service == "cbr-protectable":
            request = ListProtectableRequest()
            request.protectable_type = "server"
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
            request = ListDomainsRequest(show_tags=True)
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
        elif service == "cci":
            # CCI service uses special processing,
            # returns True indicating no need to preconstruct request object
            request = True
        return request
