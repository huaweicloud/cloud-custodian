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
    """HMAC-SHA256 计算"""
    return hmac.new(key.encode('utf-8'),
                    msg.encode('utf-8'),
                    digestmod=hashlib.sha256).digest()


def urlencode_path(path):
    """URL编码路径"""
    return quote(path, safe='~')


def hex_encode_sha256_hash(data):
    """SHA256哈希并转换为十六进制"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    sha = hashlib.sha256()
    sha.update(data)
    return sha.hexdigest()


def find_header(headers, header_name):
    """查找请求头"""
    for key, value in headers.items():
        if key.lower() == header_name.lower():
            return value
    return None


class HttpRequest:
    """HTTP请求包装类"""

    def __init__(self, method="", url="", headers=None, body=""):
        self.method = method

        # 解析URL
        sp = url.split("://", 1)
        self.scheme = 'https'
        if len(sp) > 1:
            self.scheme = sp[0]
            url = sp[1]

        # 解析查询参数
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

        # 解析主机和路径
        sp = url.split('/', 1)
        self.host = sp[0]
        if len(sp) > 1:
            self.uri = '/' + sp[1]
        else:
            self.uri = '/'

        self.headers = headers if headers else {}
        self.body = body.encode("utf-8") if isinstance(body, str) else body


class HuaweiCloudSigner:
    """华为云V4签名器"""

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
        """签名请求"""
        if isinstance(request.body, str):
            request.body = request.body.encode('utf-8')

        # 添加时间戳头
        header_time = find_header(request.headers, self.HeaderXDate)
        if header_time is None:
            time = datetime.utcnow()
            request.headers[self.HeaderXDate] = datetime.strftime(time, self.DateFormat)
        else:
            time = datetime.strptime(header_time, self.DateFormat)

        # 添加Host头
        have_host = False
        for key in request.headers:
            if key.lower() == 'host':
                have_host = True
                break
        if not have_host:
            request.headers["host"] = request.host

        # 添加Content-Length头
        request.headers["content-length"] = str(len(request.body))

        # 构造查询字符串
        query_string = self._canonical_query_string(request)
        if query_string != "":
            request.uri = request.uri + "?" + query_string

        # 获取签名头列表
        signed_headers = self._signed_headers(request)

        # 构造规范请求
        canonical_request = self._canonical_request(request, signed_headers)

        # 构造待签名字符串
        string_to_sign = self._string_to_sign(canonical_request, time)

        # 计算签名
        signature = self._sign_string_to_sign(string_to_sign, self.secret_key)

        # 构造授权头
        auth_value = self._auth_header_value(signature, self.access_key, signed_headers)
        request.headers[self.HeaderAuthorization] = auth_value

    def _canonical_request(self, request, signed_headers):
        """构造规范请求"""
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
        """构造规范URI"""
        patterns = unquote(request.uri).split('/')
        uri = []
        for value in patterns:
            uri.append(urlencode_path(value))
        url_path = "/".join(uri)
        if url_path[-1] != '/':
            url_path = url_path + "/"
        return url_path

    def _canonical_query_string(self, request):
        """构造规范查询字符串"""
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
        """构造规范头"""
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
        """获取签名头列表"""
        arr = []
        for k in request.headers:
            arr.append(k.lower())
        arr.sort()
        return arr

    def _string_to_sign(self, canonical_request, time):
        """构造待签名字符串"""
        hashed_canonical_request = hex_encode_sha256_hash(canonical_request.encode('utf-8'))
        return "%s\n%s\n%s" % (
            self.Algorithm,
            datetime.strftime(time, self.DateFormat),
            hashed_canonical_request
        )

    def _sign_string_to_sign(self, string_to_sign, secret_key):
        """签名待签名字符串"""
        hmac_digest = hmacsha256(secret_key, string_to_sign)
        return binascii.hexlify(hmac_digest).decode()

    def _auth_header_value(self, signature, access_key, signed_headers):
        """构造授权头值"""
        return "%s Access=%s, SignedHeaders=%s, Signature=%s" % (
            self.Algorithm,
            access_key,
            ";".join(signed_headers),
            signature
        )


class CCIClient:
    """华为云CCI（容器实例）服务客户端
    CCI服务使用Kubernetes API格式但需要华为云认证。
    此客户端封装对CCI服务的API调用。
    """

    def __init__(self, region, credentials):
        """初始化CCI客户端
        Args:
            region: 华为云区域
            credentials: 华为云认证凭据
        """
        self.region = region
        self.credentials = credentials
        self.base_url = f"https://cci.{region}.myhuaweicloud.com"
        self.api_version = "v1"

        # 初始化签名器
        if hasattr(credentials, 'ak') and hasattr(credentials, 'sk'):
            self.signer = HuaweiCloudSigner(credentials.ak, credentials.sk)
        else:
            self.signer = None
            log.warning("CCI客户端初始化时没有有效凭据")

    def _make_request(self, method, endpoint, **kwargs):
        """发起API请求
        Args:
            method: HTTP方法
            endpoint: API端点
            **kwargs: 其他请求参数
        Returns:
            响应数据
        """
        response = None  # 初始化响应变量
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'cloud-custodian-huaweicloud/1.0'
            }

            # 合并用户提供的头
            if 'headers' in kwargs:
                headers.update(kwargs.pop('headers'))

            # 获取请求体
            body = ""
            if 'json' in kwargs:
                body = json.dumps(kwargs.pop('json'))
                headers['Content-Type'] = 'application/merge-patch+json'
            elif 'data' in kwargs:
                body = kwargs.pop('data')
                if isinstance(body, dict):
                    body = json.dumps(body)
                    headers['Content-Type'] = 'application/merge-patch+json'

            # 添加华为云认证头
            if self.signer:
                # 创建HTTP请求对象
                request = HttpRequest(method, url, headers, body)

                # 签名请求
                self.signer.sign(request)

                # 更新头
                headers = request.headers

                log.debug(f"CCI API请求签名成功 {method} {url}")
            else:
                log.warning(f"向{method} {url}发起未签名请求")

            # 发送请求
            response = requests.request(method, url, headers=headers, data=body, **kwargs)
            response.raise_for_status()

            # 解析响应
            if response.content:
                try:
                    response_data = response.json()
                    # 处理响应数据，为每个资源的metadata添加id属性
                    self._process_response_data(response_data)
                    return response_data
                except json.JSONDecodeError:
                    log.warning(f"CCI API返回非JSON响应：{response.text}")
                    return response.text
            return None

        except requests.exceptions.RequestException as e:
            log.error(f"CCI API请求失败：{e}")
            if hasattr(e, 'response') and e.response is not None:
                log.error(f"响应状态：{e.response.status_code}")
                log.error(f"响应内容：{e.response.text}")
            elif response is not None:
                log.debug(f"本地响应为：{response}")
            raise

    def _process_response_data(self, data):
        """处理响应数据，为metadata添加id属性
        Args:
            data: 响应数据
        """
        if isinstance(data, dict):
            # 处理单个资源
            if 'metadata' in data:
                self._add_id_to_metadata(data['metadata'])
                # 将metadata.creationTimestamp提升到与metadata同级
                self._add_creation_timestamp(data)

            # 处理资源列表（items字段）
            if 'items' in data and isinstance(data['items'], list):
                for item in data['items']:
                    if isinstance(item, dict) and 'metadata' in item:
                        item["id"] = item["metadata"]["uid"]
                        # 将metadata.creationTimestamp提升到与metadata同级
                        self._add_creation_timestamp(item)
        elif isinstance(data, list):
            # 处理资源列表
            for item in data:
                if isinstance(item, dict) and 'metadata' in item:
                    item["id"] = item["metadata"]["uid"]
                    # 将metadata.creationTimestamp提升到与metadata同级
                    self._add_creation_timestamp(item)

    def _add_id_to_metadata(self, metadata):
        """为metadata添加id属性
        Args:
            metadata: 资源metadata字典
        """
        if isinstance(metadata, dict) and 'uid' in metadata:
            metadata['id'] = metadata['uid']

    def _add_creation_timestamp(self, resource):
        """将metadata.creationTimestamp提升到与metadata同级
        Args:
            resource: 资源字典
        """
        if isinstance(resource, dict) and 'metadata' in resource:
            metadata = resource['metadata']
            if isinstance(metadata, dict) and 'creationTimestamp' in metadata:
                # 将metadata.creationTimestamp的值赋给同级的creationTimestamp
                resource['creationTimestamp'] = metadata['creationTimestamp']

    def list_namespaces(self, request=None):
        """列出所有命名空间
        Args:
            request: 请求参数（可选，用于兼容性）
        Returns:
            dict: 包含命名空间列表的响应数据
        """
        endpoint = f"api/{self.api_version}/namespaces"
        return self._make_request("GET", endpoint)

    def list_namespaced_pods(self, request=None):
        """列出所有命名空间中的Pod
        Args:
            namespace: 命名空间名称（此参数将被忽略，获取所有命名空间的pod）
            request: 请求参数（可选，用于兼容性）
        Returns:
            dict: 包含所有命名空间Pod列表的响应数据
        """
        # 首先获取所有命名空间
        namespaces_response = self.list_namespaces()

        # 初始化合并响应结构
        combined_response = {
            "apiVersion": "v1",
            "kind": "PodList",
            "items": []
        }

        # 从命名空间响应中提取命名空间名称
        if namespaces_response and "items" in namespaces_response:
            for namespace_item in namespaces_response["items"]:
                if "metadata" in namespace_item and "name" in namespace_item["metadata"]:
                    namespace_name = namespace_item["metadata"]["name"]

                    try:
                        # 获取该命名空间中的所有pod
                        endpoint = f"api/{self.api_version}/namespaces/{namespace_name}/pods"
                        pods_response = self._make_request("GET", endpoint)

                        # 将该命名空间的pod添加到合并响应中
                        if pods_response and "items" in pods_response:
                            combined_response["items"].extend(pods_response["items"])

                    except Exception as e:
                        log.warning(f"无法从命名空间{namespace_name}获取pod：{e}")
                        continue

        # 处理最终合并的响应
        self._process_response_data(combined_response)
        return combined_response

    def list_namespaced_configmaps(self, request=None):
        """列出所有命名空间中的ConfigMap
        Args:
            namespace: 命名空间名称（此参数将被忽略，获取所有命名空间的configmap）
            request: 请求参数（可选，用于兼容性）
        Returns:
            dict: 包含所有命名空间ConfigMap列表的响应数据
        """
        # 首先获取所有命名空间
        namespaces_response = self.list_namespaces()

        # 初始化合并响应结构
        combined_response = {
            "apiVersion": "v1",
            "kind": "ConfigMapList",
            "items": []
        }

        # 从命名空间响应中提取命名空间名称
        if namespaces_response and "items" in namespaces_response:
            for namespace_item in namespaces_response["items"]:
                if "metadata" in namespace_item and "name" in namespace_item["metadata"]:
                    namespace_name = namespace_item["metadata"]["name"]

                    try:
                        # 获取该命名空间中的所有configmap
                        endpoint = f"api/{self.api_version}/namespaces/{namespace_name}/configmaps"
                        configmaps_response = self._make_request("GET", endpoint)

                        # 将该命名空间的configmap添加到合并响应中
                        if configmaps_response and "items" in configmaps_response:
                            combined_response["items"].extend(configmaps_response["items"])

                    except Exception as e:
                        log.warning(
                            f"无法从命名空间{namespace_name}获取configmap：{e}")
                        continue

        # 处理最终合并的响应
        self._process_response_data(combined_response)
        return combined_response

    def list_namespaced_secrets(self, request=None):
        """列出所有命名空间中的Secret
        Args:
            namespace: 命名空间名称（此参数将被忽略，获取所有命名空间的secret）
            request: 请求参数（可选，用于兼容性）
        Returns:
            dict: 包含所有命名空间Secret列表的响应数据
        """
        # 首先获取所有命名空间
        namespaces_response = self.list_namespaces()

        # 初始化合并响应结构
        combined_response = {
            "apiVersion": "v1",
            "kind": "SecretList",
            "items": []
        }

        # 从命名空间响应中提取命名空间名称
        if namespaces_response and "items" in namespaces_response:
            for namespace_item in namespaces_response["items"]:
                if "metadata" in namespace_item and "name" in namespace_item["metadata"]:
                    namespace_name = namespace_item["metadata"]["name"]

                    try:
                        # 获取该命名空间中的所有secret
                        endpoint = f"api/{self.api_version}/namespaces/{namespace_name}/secrets"
                        secrets_response = self._make_request("GET", endpoint)

                        # 将该命名空间的secret添加到合并响应中
                        if secrets_response and "items" in secrets_response:
                            combined_response["items"].extend(secrets_response["items"])

                    except Exception as e:
                        log.warning(f"无法从命名空间{namespace_name}获取secret：{e}")
                        continue

        # 处理最终合并的响应
        self._process_response_data(combined_response)
        return combined_response

    def patch_namespaced_pod(self, name, namespace, body):
        """修改Pod
        Args:
            name: Pod名称
            namespace: 命名空间名称
            body: 修改数据体
        Returns:
            dict: 修改操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/pods/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_pod(self, name, namespace):
        """删除Pod
        Args:
            name: Pod名称
            namespace: 命名空间名称
        Returns:
            dict: 删除操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/pods/{name}"
        return self._make_request("DELETE", endpoint)

    def patch_namespaced_configmap(self, name, namespace, body):
        """修改ConfigMap
        Args:
            name: ConfigMap名称
            namespace: 命名空间名称
            body: 修改数据体
        Returns:
            dict: 修改操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/configmaps/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_configmap(self, name, namespace):
        """删除ConfigMap
        Args:
            name: ConfigMap名称
            namespace: 命名空间名称
        Returns:
            dict: 删除操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/configmaps/{name}"
        return self._make_request("DELETE", endpoint)

    def patch_namespaced_secret(self, name, namespace, body):
        """修改Secret
        Args:
            name: Secret名称
            namespace: 命名空间名称
            body: 修改数据体
        Returns:
            dict: 修改操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/secrets/{name}"
        return self._make_request("PATCH", endpoint, json=body)

    def delete_namespaced_secret(self, name, namespace):
        """删除Secret
        Args:
            name: Secret名称
            namespace: 命名空间名称
        Returns:
            dict: 删除操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{namespace}/secrets/{name}"
        return self._make_request("DELETE", endpoint)

    def delete_namespace(self, name):
        """删除命名空间
        Args:
            name: 命名空间名称
        Returns:
            dict: 删除操作的响应结果
        """
        endpoint = f"api/{self.api_version}/namespaces/{name}"
        return self._make_request("DELETE", endpoint) 