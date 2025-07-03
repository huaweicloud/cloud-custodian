# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import hashlib
import hmac
import binascii
from urllib.parse import quote, unquote
import requests
import json
from datetime import datetime

log = logging.getLogger("custodian.huaweicloud.utils.cci_client")


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
    HeaderSecurityToken = "X-Security-Token"

    def __init__(self, access_key, secret_key, security_token):
        self.access_key = access_key
        self.secret_key = secret_key
        self.security_token = security_token

    def sign(self, request):
        """Sign request"""
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

        # Build query string
        query_string = self._canonical_query_string(request)
        if query_string != "":
            request.uri = request.uri + "?" + query_string

        # Get signed headers list
        signed_headers = self._signed_headers(request)

        # Build canonical request
        canonical_request = self._canonical_request(request, signed_headers)

        # Build string to sign
        string_to_sign = self._string_to_sign(canonical_request, time)

        # Calculate signature
        signature = self._sign_string_to_sign(string_to_sign, self.secret_key)

        # Build authorization header
        auth_value = self._auth_header_value(signature, self.access_key, signed_headers)
        request.headers[self.HeaderAuthorization] = auth_value
        if self.security_token is not None:
            request.headers[self.HeaderSecurityToken] = self.security_token

    def _canonical_request(self, request, signed_headers):
        """Build canonical request"""
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
        """Build canonical URI"""
        patterns = unquote(request.uri).split('/')
        uri = []
        for value in patterns:
            uri.append(urlencode_path(value))
        url_path = "/".join(uri)
        if url_path[-1] != '/':
            url_path = url_path + "/"
        return url_path

    def _canonical_query_string(self, request):
        """Build canonical query string"""
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
        """Build canonical headers"""
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
        """Build string to sign"""
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
        """Build authorization header value"""
        return "%s Access=%s, SignedHeaders=%s, Signature=%s" % (
            self.Algorithm,
            access_key,
            ";".join(signed_headers),
            signature
        )


class CCIClient:
    """Huawei Cloud CCI (Container Instance) service client
    CCI service uses Kubernetes API format but requires Huawei Cloud authentication.
    This client encapsulates API calls to CCI service.
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
        self.api_version = "v2"

        # Initialize signer
        if (hasattr(credentials, 'ak') and hasattr(credentials, 'sk')
                and hasattr(credentials, 'security_token')):
            self.signer = HuaweiCloudSigner(credentials.ak, credentials.sk,
                                            credentials.security_token)
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

            # Merge user provided headers
            if 'headers' in kwargs:
                headers.update(kwargs.pop('headers'))

            # Get request body
            body = ""
            if 'json' in kwargs:
                body = json.dumps(kwargs.pop('json'))
                headers['Content-Type'] = 'application/merge-patch+json'
            elif 'data' in kwargs:
                body = kwargs.pop('data')
                if isinstance(body, dict):
                    body = json.dumps(body)
                    headers['Content-Type'] = 'application/merge-patch+json'

            # Add Huawei Cloud authentication headers
            if self.signer:
                # Create HTTP request object
                request = HttpRequest(method, url, headers, body)

                # Sign request
                self.signer.sign(request)

                # Update headers
                headers = request.headers

                log.debug(f"CCI API request signed successfully {method} {url}")
            else:
                log.warning(f"Making unsigned request to {method} {url}")

            # Send request
            response = requests.request(method, url, headers=headers, data=body, **kwargs)
            response.raise_for_status()

            # Parse response
            if response.content:
                try:
                    response_data = response.json()
                    # Process response data, add id attribute to metadata of each resource
                    self._process_response_data(response_data)
                    return response_data
                except json.JSONDecodeError:
                    log.warning(f"CCI API returned non-JSON response: {response.text}")
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
                # Assign metadata.creationTimestamp value to creationTimestamp at same level
                resource['creationTimestamp'] = metadata['creationTimestamp']

    def list_namespaces(self, request=None):
        """List all namespaces
        Args:
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing namespace list
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces"
        return self._make_request("GET", endpoint)

    def list_namespaced_pods(self, request=None):
        """List pods in all namespaces
        Args:
            namespace: Namespace name (this parameter will be ignored, get pods from all namespaces)
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing pod list from all namespaces
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
                        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace_name}/pods"
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

    def list_namespaced_configmaps(self, request=None):
        """List configmaps in all namespaces
        Args:
            namespace: Namespace name (this parameter
             will be ignored, get configmaps from all namespaces)
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing configmap list from all namespaces
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
                        endpoint = (f"apis/cci/{self.api_version}/"
                                    f"namespaces/{namespace_name}/configmaps")
                        configmaps_response = self._make_request("GET", endpoint)

                        # Add configmaps from this namespace to merged response
                        if configmaps_response and "items" in configmaps_response:
                            combined_response["items"].extend(configmaps_response["items"])

                    except Exception as e:
                        log.warning(f"Failed to get configmaps from namespace"
                                    f" {namespace_name}: {e}")
                        continue

        # Process final merged response
        self._process_response_data(combined_response)
        return combined_response

    def list_namespaced_secrets(self, request=None):
        """List secrets in all namespaces
        Args:
            namespace: Namespace name (this parameter
             will be ignored, get secrets from all namespaces)
            request: Request parameters (optional, for compatibility)
        Returns:
            dict: Response data containing secret list from all namespaces
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
                        endpoint = (f"apis/cci/{self.api_version}"
                                    f"/namespaces/{namespace_name}/secrets")
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
        """Modify pod
        Args:
            name: Pod name
            namespace: Namespace name
            body: Modification data body
        Returns:
            dict: Response result of modification operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace}/pods/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_pod(self, name, namespace):
        """Delete pod
        Args:
            name: Pod name
            namespace: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace}/pods/{name}"
        return self._make_request("DELETE", endpoint)

    def patch_namespaced_configmap(self, name, namespace, body):
        """Modify configmap
        Args:
            name: ConfigMap name
            namespace: Namespace name
            body: Modification data body
        Returns:
            dict: Response result of modification operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace}/configmaps/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_configmap(self, name, namespace):
        """Delete configmap
        Args:
            name: ConfigMap name
            namespace: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace}/configmaps/{name}"
        return self._make_request("DELETE", endpoint)

    def patch_namespaced_secret(self, name, namespace, body):
        """Modify secret
        Args:
            name: Secret name
            namespace: Namespace name
            body: Modification data body
        Returns:
            dict: Response result of modification operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace}/secrets/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_secret(self, name, namespace):
        """Delete secret
        Args:
            name: Secret name
            namespace: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{namespace}/secrets/{name}"
        return self._make_request("DELETE", endpoint)

    def delete_namespace(self, name):
        """Delete namespace
        Args:
            name: Namespace name
        Returns:
            dict: Response result of deletion operation
        """
        endpoint = f"apis/cci/{self.api_version}/namespaces/{name}"
        return self._make_request("DELETE", endpoint)
