# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import base64
import logging
import re
import functools
import time
import json
import copy

from huaweicloudsdkkms.v2 import ShowPublicKeyRequest, OperateKeyRequestBody, ShowPublicKeyResponse

from c7n.filters import Filter
from c7n_huaweicloud.actions.smn import NotifyMessageAction
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n.utils import local_session, type_schema
from huaweicloudsdkcore.exceptions import exceptions
from c7n_huaweicloud.filters.exempted import get_obs_name, get_obs_server, get_file_path

# Import Huawei Cloud CCE SDK related request and response classes
from huaweicloudsdkcce.v3 import (
    DeleteClusterRequest,
    HibernateClusterRequest, AwakeClusterRequest, UpdateClusterRequest,
    DeleteNodePoolRequest, UpdateNodePoolRequest,
    DeleteNodeRequest,
    ListAddonInstancesRequest, DeleteAddonInstanceRequest,
    DeleteChartRequest,
    DeleteReleaseRequest,
    NodePoolUpdate, NodePoolMetadataUpdate, NodePoolSpecUpdate,
    ClusterInformation, ClusterInformationSpec, ClusterMetadataForUpdate,
    ContainerNetworkUpdate, EniNetworkUpdate, ClusterInformationSpecHostNetwork,
    NodePoolNodeAutoscaling, UpdateClusterLogConfigRequest,
    ClusterLogConfig, ShowClusterConfigRequest, CceClient,
    ShowClusterConfigResponse, ClusterLogConfigLogConfigs,
    ListAddonTemplatesRequest, ListAddonTemplatesResponse,
    Versions, SupportVersions, CreateAddonInstanceRequest,
    InstanceRequest, AddonMetadata, InstanceRequestSpec, ShowClusterRequest
)

log = logging.getLogger("custodian.huaweicloud.cce")


@resources.register("cce-cluster")
class CceCluster(QueryResourceManager):
    """Huawei Cloud CCE Cluster Resource Manager

    Container clusters provide high-reliability, high-performance enterprise-level
    container application management services. Support standard Kubernetes API,
    integrated with Huawei Cloud computing, network, storage and other services.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-cce-clusters
            resource: huaweicloud.cce-cluster
            filters:
              - type: value
                key: status.phase
                value: Available
    """

    class resource_type(TypeInfo):
        service = "cce-cluster"
        enum_spec = ("list_clusters", "items", None)
        id = "metadata.uid"
        name = "metadata.name"
        taggable = True
        tag_resource_type = "cce-cluster"

    def augment(self, resources):
        """Augment CCE cluster resources with additional information including tags

        This method enhances the cluster resources by adding standardized tags and
        other necessary fields for Cloud Custodian operations.

        :param resources: List of CCE cluster resources
        :return: Enhanced list of resources
        """
        if not resources:
            return resources

        for resource in resources:
            # Extract clusterTags from spec and convert to tags dictionary format
            # According to CCE API documentation, clusterTags are located in spec.clusterTags
            cluster_tags = resource.get('spec', {}).get('clusterTags', [])
            if cluster_tags and isinstance(cluster_tags, list):
                # Convert clusterTags list format to dictionary format for Cloud Custodian filters
                tags_dict = {}
                for tag in cluster_tags:
                    if isinstance(tag, dict):
                        key = tag.get("key")
                        # Default to empty string if no value
                        value = tag.get("value", "")
                        if key:
                            tags_dict[key] = value

                # Store dictionary format for Cloud Custodian filters at metadata level
                resource['tags'] = tags_dict
            elif 'tags' not in resource:
                # If no clusterTags found, initialize empty tags dict
                resource['tags'] = {}

            resource['name'] = resource.get('metadata', {}).get('name', '')

        return resources


@CceCluster.action_registry.register("delete")
class DeleteCceCluster(HuaweiCloudBaseAction):
    """Delete CCE Cluster

    This operation will permanently delete the specified CCE cluster and all its related resources.
    Please use this operation with caution as deletion cannot be undone.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-old-cce-clusters
            resource: huaweicloud.cce-cluster
            filters:
              - type: value
                key: status.phase
                value: Available
            actions:
              - type: delete
                delete_evs: true
                delete_eni: true
    """

    schema = type_schema(
        "delete",
        # Whether to delete cluster-associated EVS disks
        delete_evs={"type": "boolean", "default": False},
        # Whether to delete cluster-associated ENI
        delete_eni={"type": "boolean", "default": True},
        # Whether to delete cluster-associated network resources
        delete_net={"type": "boolean", "default": True},
        # Whether to delete cluster-associated OBS storage
        delete_obs={"type": "boolean", "default": False},
        # Whether to delete cluster-associated sfs turbo storage
        delete_efs={"type": "boolean", "default": False},
        # Whether to delete cluster-associated sfs storage
        delete_sfs={"type": "boolean", "default": False},
        # Whether to delete cluster-associated sfs3.0 storage
        delete_sfs30={"type": "boolean", "default": False},
        # Whether to delete cluster-associated lts resources
        lts_reclaim_policy={"type": "string",
                            "default": 'Delete_Master_Log_Stream'},
        # Whether to delete cluster-associated evs resources
        ondemand_node_policy={"type": "string", "default": 'delete'},
        # Whether to delete cluster-associated evs resources
        periodic_node_policy={"type": "string", "default": 'retain'},
    )

    permissions = ('cce:deleteCluster',)

    def perform_action(self, resource):
        """Perform delete operation on a single CCE cluster"""
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')

        client = self.manager.get_client()

        try:
            if not cluster_id:
                raise Exception("empty cluster id")

            cluster_status = resource.get("status", {}).get("phase")
            if cluster_status == "Deleting":
                log.info(
                    f"[actions]- [delete] The resource:[huaweicloud.cce-cluster] with id:["
                    f"{cluster_name}/{cluster_id}] delete cluster skipped. cause: already "
                    f"Deleting.")
                return None
            elif (cluster_status != "Available" and cluster_status != "Error" and
                  cluster_status != "Unavailable"):
                wait_cluster_status_ready(client, cluster_id, "Available,Unavailable,Error", 20,
                                          30, 600)

            # Build delete cluster request
            request = DeleteClusterRequest()
            request.cluster_id = cluster_id

            # Set delete options
            request.delete_eni = self.data.get('delete_eni', True)
            request.delete_net = self.data.get('delete_net', True)
            request.delete_efs = self.data.get('delete_evs', False)
            request.delete_evs = self.data.get('delete_evs', False)
            request.delete_obs = self.data.get('delete_obs', False)
            request.delete_sfs = self.data.get('delete_evs', False)
            request.delete_sfs30 = self.data.get('delete_evs', False)
            request.lts_reclaim_policy = self.data.get('lts_reclaim_policy',
                                                       "Delete_Master_Log_Stream")
            request.ondemand_node_policy = self.data.get(
                'ondemand_node_policy', "delete")
            request.periodic_node_policy = self.data.get(
                'periodic_node_policy', "retain")

            # Execute delete operation
            response = client.delete_cluster(request)
            log.info(
                f"[actions]- [delete] The resource:[huaweicloud.cce-cluster] with id:["
                f"{cluster_name}/{cluster_id}] delete cluster succeeded.")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] delete cluster failed."
                f" cause: {e.error_msg} (status code: {e.status_code}).")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] delete cluster failed."
                f" cause: {str(e)}.")
            raise


@CceCluster.action_registry.register("hibernate")
class HibernateCceCluster(HuaweiCloudBaseAction):
    """Hibernate CCE Cluster

    Put the CCE cluster into hibernation state to save computing resource costs.
    Hibernated clusters can be restarted through the awaken operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: hibernate-idle-clusters
            resource: huaweicloud.cce-cluster
            filters:
              - type: value
                key: status.phase
                value: Available
            actions:
              - type: hibernate
    """

    schema = type_schema("hibernate")
    permissions = ('cce:hibernateCluster',)

    def perform_action(self, resource):
        """Perform hibernate operation on a single CCE cluster"""
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')

        client = self.manager.get_client()

        try:
            if not cluster_id:
                raise Exception("empty cluster id")

            cluster_status = resource.get("status", {}).get("phase", '')
            if (cluster_status == "Hibernating" or cluster_status == "Hibernation"):
                log.info(
                    f"[actions]- [hibernate] The resource:[huaweicloud.cce-cluster] with id:["
                    f"{cluster_name}/{cluster_id}] hibernate cluster skipped. "
                    f"cause: already Hibernating.")
                return None
            elif cluster_status == "Awaking":
                wait_cluster_status_ready(client, cluster_id, "Available", 20, 30, 600)
            elif cluster_status == "Creating":
                wait_cluster_status_ready(client, cluster_id, "Available", 20, 30, 600)
            elif cluster_status != "Available" and cluster_status != "Unavailable":
                raise Exception(f"invalid cluster status {cluster_status}")

            request = HibernateClusterRequest()
            request.cluster_id = cluster_id

            response = client.hibernate_cluster(request)
            log.info(
                f"[actions]- [hibernate] The resource:[huaweicloud.cce-cluster] with id:["
                f"{cluster_name}/{cluster_id}] hibernate cluster succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [hibernate]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] hibernate cluster failed."
                f" cause: {e.error_msg} (status code: {e.status_code}).")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [hibernate]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] hibernate cluster failed."
                f" cause: {str(e)}.")
            raise


@CceCluster.action_registry.register("awake")
class AwakeCceCluster(HuaweiCloudBaseAction):
    """Awake CCE Cluster

    Restart hibernated CCE cluster to resume normal operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: awake-hibernated-clusters
            resource: huaweicloud.cce-cluster
            filters:
              - type: value
                key: status.phase
                value: Hibernating
            actions:
              - type: awake
    """

    schema = type_schema("awake")
    permissions = ('cce:awakeCluster',)

    def perform_action(self, resource):
        """Perform awake operation on a single CCE cluster"""
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')

        client = self.manager.get_client()

        try:
            if not cluster_id:
                raise Exception("empty cluster id")

            request = AwakeClusterRequest()
            request.cluster_id = cluster_id

            response = client.awake_cluster(request)
            log.info(
                f"[actions]- [awake] The resource:[huaweicloud.cce-cluster] with id:["
                f"{cluster_name}/{cluster_id}] awake cluster succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [awake]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] awake cluster failed."
                f" cause: {e.error_msg} (status code: {e.status_code}).")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [awake]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] awake cluster failed."
                f" cause: {str(e)}.")
            raise


@CceCluster.action_registry.register("update")
class UpdateCceCluster(HuaweiCloudBaseAction):
    """Update CCE Cluster

    Update CCE cluster configuration information,
    such as cluster description, custom SAN, network configuration, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: update-cluster-description
            resource: huaweicloud.cce-cluster
            actions:
              - type: update
                spec:
                  description: "Updated cluster description"
                  custom_san:
                    - "example.com"
                    - "test.example.com"
                  deletion_protection: true
                metadata:
                  alias: "new-cluster-alias"
    """

    schema = type_schema(
        "update",
        spec={
            "type": "object",
            "properties": {
                "description": {"type": "string"},  # Cluster description
                "custom_san": {  # Custom SAN list
                    "type": "array",
                    "items": {"type": "string"}
                },
                "container_network": {  # Container network update configuration
                    "type": "object",
                    "properties": {
                        "cidrs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "cidr": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "eni_network": {  # ENI network update configuration
                    "type": "object",
                    "properties": {
                        "subnets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "subnet_id": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "host_network": {  # Host network configuration
                    "type": "object",
                    "properties": {
                        "subnet_id": {"type": "string"}
                    }
                },
                # Deletion protection
                "deletion_protection": {"type": "boolean"}
            }
        },
        metadata={
            "type": "object",
            "properties": {
                "alias": {"type": "string"}  # Cluster alias
            }
        }
    )
    permissions = ('cce:updateCluster',)

    def perform_action(self, resource):
        """Perform update operation on a single CCE cluster"""
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')

        client = self.manager.get_client()

        try:
            if not cluster_id:
                raise Exception("empty cluster id")

            # Build update cluster request
            request = UpdateClusterRequest()
            request.cluster_id = cluster_id

            # Create cluster information object
            cluster_info = ClusterInformation()

            # Set spec configuration
            spec_config = self.data.get('spec', {})
            if spec_config:
                cluster_spec = ClusterInformationSpec()

                # Set description
                if spec_config.get('description'):
                    cluster_spec.description = spec_config.get('description')

                # Set custom SAN
                if spec_config.get('custom_san'):
                    cluster_spec.custom_san = spec_config.get('custom_san')

                # Set container network configuration
                if spec_config.get('container_network'):
                    container_net = ContainerNetworkUpdate()
                    if spec_config['container_network'].get('cidrs'):
                        # Set CIDR according to actual SDK structure
                        container_net.cidrs = spec_config['container_network']['cidrs']
                    cluster_spec.container_network = container_net

                # Set ENI network configuration
                if spec_config.get('eni_network'):
                    eni_net = EniNetworkUpdate()
                    if spec_config['eni_network'].get('subnets'):
                        # Set subnets according to actual SDK structure
                        eni_net.subnets = spec_config['eni_network']['subnets']
                    cluster_spec.eni_network = eni_net

                # Set host network configuration
                if spec_config.get('host_network'):
                    host_net = ClusterInformationSpecHostNetwork()
                    if spec_config['host_network'].get('subnet_id'):
                        host_net.subnet_id = spec_config['host_network']['subnet_id']
                    cluster_spec.host_network = host_net

                # Set deletion protection
                if 'deletion_protection' in spec_config:
                    cluster_spec.deletion_protection = spec_config.get(
                        'deletion_protection')

                cluster_info.spec = cluster_spec

            # Set metadata configuration
            metadata_config = self.data.get('metadata', {})
            if metadata_config:
                cluster_metadata = ClusterMetadataForUpdate()

                # Set cluster alias
                if metadata_config.get('alias'):
                    cluster_metadata.alias = metadata_config.get('alias')

                cluster_info.metadata = cluster_metadata

            request.body = cluster_info

            response = client.update_cluster(request)
            log.info(
                f"[actions]- [update] The resource:[huaweicloud.cce-cluster] with id:["
                f"{cluster_name}/{cluster_id}] update cluster succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [update]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] update cluster failed."
                f" cause: {e.error_msg} (status code: {e.status_code}).")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [update]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] update cluster failed."
                f" cause: {str(e)}.")
            raise


@CceCluster.action_registry.register("update-cluster-log-config")
class UpdateClusterLogConfig(HuaweiCloudBaseAction):
    """
    Update Cluster Log Config

    :example:

    .. code-block:: yaml

        policies:
          - name: update-cluster-log-config
            resource: huaweicloud.cce-cluster
            actions:
              - type: update-cluster-log-config
                ttl_in_days: 30
                enable: true
    """

    action_name = "update-cluster-log-config"
    schema = type_schema(
        "update-cluster-log-config",
        ttl_in_days={"type": "integer", "default": 30},
        enable={"type": "boolean", "default": False},

    )

    permissions = ('cce:updateClusterLogConfig',)
    components: set = {"audit", "kube-apiserver", "kube-controller-manager", "kube-scheduler"}

    def perform_action(self, resource):
        """Perform updateClusterLogConfig operation on a single CCE cluster"""
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')
        cluster_status = resource.get("status", {}).get("phase", '')

        client = self.manager.get_client()

        try:
            if not cluster_id:
                raise Exception("empty cluster id")

            if cluster_status == "Creating":
                wait_cluster_status_ready(client, cluster_id, "Available", 20, 30, 600)
            elif cluster_status == "Deleting" or cluster_status == "Error":
                return None
            elif cluster_status != "Available":
                raise Exception(f"invalid cluster status {cluster_status}")

            @retry(times=3, interval=30)
            def _retry():
                self.update_cluster_log_config(cluster_id, cluster_name)

            _retry()
            log.info(
                f"[actions]- [{self.action_name}] The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] update cluster log config succeeded.")
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] update cluster log config failed."
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] update cluster log config failed."
                f" cause: {str(e)}")
            raise

    def update_cluster_log_config(self, cluster_id: str, cluster_name: str):
        client = self.manager.get_client()
        body = ClusterLogConfig()
        body.ttl_in_days = self.data.get('ttl_in_days', 30)
        body.log_configs = self.generate_log_configs(self.data.get("enable", False))
        request = UpdateClusterLogConfigRequest(cluster_id, body)
        response = client.update_cluster_log_config(request)
        return response

    def generate_log_configs(self, enable: bool) -> list[ClusterLogConfigLogConfigs]:
        return list([ClusterLogConfigLogConfigs(d, enable) for d in self.components])


@CceCluster.filter_registry.register("cluster-log-enabled")
class ClusterLogEnabledFilter(Filter):
    """
    Filter the cce clusters which kubernetes logs enabled

    :example:

    . code-block:: YAML
        policies:
          - name: update-cluster-log-config
            resource: huaweicloud.cce-cluster
            filters:
              - type: cluster-log-enabled
                enabled: true

    """
    filter_name = 'cluster-log-enabled'
    schema = type_schema("cluster-log-enabled", enabled={"type": "boolean", "default": True})
    components: set = {"audit", "kube-apiserver", "kube-controller-manager", "kube-scheduler"}

    def __call__(self, resource):
        excepted = self.data.get("enabled", False)
        cluster_id = resource["id"] if "id" in resource else None
        cluster_status = resource.get("status", {}).get("phase", '')
        if cluster_status != "Available":
            return not excepted

        try:
            if not cluster_id:
                raise Exception("empty cluster_id")

            client: CceClient = self.manager.get_client()
            request = ShowClusterConfigRequest()
            request.cluster_id = cluster_id

            response = client.show_cluster_config(request)
            log.info(
                f"[filters]- The filter:[{self.filter_name}] query cluster logs-config succeeded.")
            return excepted == self.all_enabled(response)
        except exceptions.ClientRequestException as e:
            log.error(
                f"[filters]- the filter:[{self.filter_name}] query cluster logs-config failed."
                f" cause: request id:{e.request_id},"
                f" status code:{e.status_code}, msg:{e.error_msg}")
            raise
        except Exception as e:
            log.error(
                f"[filters]- the filter:[{self.filter_name}] query cluster logs-config failed."
                f" cause: {str(e)}.")
            raise

    def all_enabled(self, response: ShowClusterConfigResponse) -> bool:
        enabled_components = set(d.name for d in response.log_configs if d.enable)
        return enabled_components.issuperset(self.components)


@CceCluster.filter_registry.register("cluster-encrypted")
class ClusterEncryptedFilter(Filter):
    """
    Filter the cce clusters which secret encrypted

    :example:

    . code-block:: YAML
        policies:
          - name: cluster-encrypted
            resource: huaweicloud.cce-cluster
            filters:
              - type: cluster-encrypted
                encrypted: true

    """
    filter_name = 'cluster-encrypted'
    schema = type_schema("cluster-encrypted", encrypted={"type": "boolean", "default": True})

    def __call__(self, resource):
        encrypted = self.data.get("encrypted", False)
        actual = resource.get("spec", {}).get("encryptionConfig", {}).get("mode", "Default")
        return encrypted == (actual != "Default")


@CceCluster.filter_registry.register("cluster-signature-enabled")
class ClusterSignatureEnabledFilter(Filter):
    """
    Filter cluster enable the container image signature verification
    :example:

    . code-block:: YAML
        policies:
          - name: cluster-signature-enabled
            resource: huaweicloud.cce-cluster
            filters:
              - type: cluster-signature-enabled
                enabled: true
    """
    filter_name = "cluster-signature-enabled"
    plugin_name = "swr-cosign"
    schema = type_schema("cluster-signature-enabled", enabled={"type": "boolean", "default": True})

    def __call__(self, resource):
        excepted = self.data.get("enabled", False)
        cluster_id = resource["id"] if "id" in resource else None
        cluster_status = resource.get("status", {}).get("phase", '')
        if cluster_status != "Available":
            return not excepted

        if not cluster_id:
            return False

        try:
            client: CceClient = self.manager.get_client()
            plugin_status = get_plugin_status(client, cluster_id, self.plugin_name)
            installed = plugin_status not in ["deleting", "deleteFailed", "deleteSuccess"]
            log.error(
                f"[filters]- the filter:[{self.filter_name}] query cluster addon instances "
                f"succeeded")
            return excepted == installed
        except PluginNotInstalled:
            log.error(
                f"[filters]- the filter:[{self.filter_name}] query cluster addon instances "
                f"succeeded")
            return not excepted
        except exceptions.ClientRequestException as e:
            log.error(
                f"[filters]- the filter:[{self.filter_name}] query cluster addon instances failed."
                f" cause: request id:{e.request_id},"
                f" status code:{e.status_code}, msg:{e.error_msg}")
            raise
        except Exception as e:
            log.error(
                f"[filters]- the filter:[{self.filter_name}] query cluster addon instances failed."
                f" cause: {str(e)}.")
            raise


@CceCluster.action_registry.register("enable-cluster-signature")
class EnableClusterSignature(HuaweiCloudBaseAction):
    """
    Enable the container image signature verification


    :example:

    .. code-block:: yaml

        policies:
          - name: enable-cluster-signature
            resource: huaweicloud.cce-cluster
            actions:
              - type: enable-cluster-signature
                public_key: 'xxx'

    """

    action_name = "enable-cluster-signature"
    plugin_name = "swr-cosign"
    schema = type_schema("enable-cluster-signature",
                         rinherit={
                             'type': 'object',
                             'additionalProperties': False,
                             'required': ['type', 'message', 'topic_urn_list'],
                             'properties': {
                                 'type': {'enum': ['enable-cluster-signature']},
                                 "topic_urn_list": {
                                     "type": "array",
                                     "items": {"type": "string"}
                                 },
                                 'subject': {'type': 'string'},
                                 'public_key': {'type': 'string'},
                                 'kms_id': {'type': 'string'},
                                 'obs_url': {'type': 'string'}
                             }
                         })
    permissions = ('cce:enableClusterSignature',)

    def perform_action(self, resource):
        """Perform updateClusterLogConfig operation on a single CCE cluster"""
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')
        cluster_version = resource.get('spec', {}).get('version')
        cluster_type = resource.get('spec', {}).get('type')
        cluster_flavor = resource.get('spec', {}).get('flavor')
        cluster_status = resource.get("status", {}).get("phase", '')

        client = self.manager.get_client()

        try:

            if not cluster_id:
                raise Exception("empty cluster ID")

            if not cluster_version:
                raise Exception("unknown cluster version")

            if not cluster_type:
                raise Exception("unknown cluster type")

            if cluster_status == "Creating":
                wait_cluster_status_ready(client, cluster_id, "Available", 20, 30, 600)
            elif cluster_status == "Deleting" or cluster_status == "Error":
                log.info(
                    f"[actions]- [{self.action_name}] The resource:[huaweicloud.cce-cluster] with "
                    f"id:[{cluster_name}/{cluster_id}] enable cluster container image signature "
                    f"skipped. cause: invalid cluster status: {cluster_status}")
                return None
            elif cluster_status != "Available":
                raise Exception(f"invalid cluster status {cluster_status}")

            version = self.get_latest_plugin(cluster_version, cluster_type)
            spec = InstanceRequestSpec(version=version.version, cluster_id=cluster_id,
                                       addon_template_name=self.plugin_name)
            basic = version.input.get('basic', {})
            basic["rbac_enabled"] = True
            basic["cluster_version"] = cluster_version
            custom = version.input.get('parameters', {}).get('custom')
            custom["cosignPub"] = self.get_base64_decode_public_key()
            custom["globs"] = ["**"]

            spec.values = {
                "basic": basic,
                "flavor": get_matched_flavor(cluster_flavor, version.input.get('parameters', {})),
                "custom": custom,
            }
            metadata = AddonMetadata(annotations={"addon.install/type": "install"})
            body = InstanceRequest("Addon", "v3", metadata, spec)
            request = CreateAddonInstanceRequest(body)
            response = client.create_addon_instance(request)
            log.debug(f"[actions]-{self.action_name} query the service:[/api/v3/addons] succeeded.")
            self.wait_plugin_installing_ready(cluster_id, cluster_name)
            log.info(
                f"[actions]- [{self.action_name}] The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] enable cluster container image signature "
                f"succeeded. ")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] enable cluster container image signature failed."
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except PluginInstallFailed as e:
            self.notify_install_failed_message(resource, str(e))
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] enable cluster container image signature failed."
                f" cause: {str(e)}")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] enable cluster container image signature failed."
                f" cause: {str(e)}")
            raise

    def get_base64_decode_public_key(self) -> str:
        if self.data.get("public_key"):
            return self.data.get('public_key')
        public_id = self.data.get('kms_id', '')

        obs_url = self.data.get('obs_url', '')
        if obs_url != '':
            context = self.get_file_content(obs_url)
            if 'signature_key' in context:
                public_id = context['signature_key']

        if public_id is None or len(public_id) == 0:
            raise Exception("public_id empty")

        session = local_session(self.manager.session_factory)
        client = session.client("kms")

        request = ShowPublicKeyRequest(OperateKeyRequestBody(public_id))
        response: ShowPublicKeyResponse = client.show_public_key(request)
        log.debug(
            f"[actions]-{self.action_name} query the service:["
            f"/v1.0/project_id/kms/get-publickey] succeeded.")
        public_key = response.public_key
        return base64.b64encode(public_key.encode()).decode()

    def get_latest_plugin(self, cluster_version: str, cluster_type: str):
        client = self.manager.get_client()
        request = ListAddonTemplatesRequest(self.plugin_name)
        response: ListAddonTemplatesResponse = client.list_addon_templates(request)
        log.debug(
            f"[actions]-{self.action_name} query the service:[/api/v3/addontemplates] succeeded.")
        versions: list[Versions] = []

        for _, plugin in enumerate(response.items):
            if plugin.metadata.name != self.plugin_name:
                continue
            for _, version in enumerate(plugin.spec.versions):
                if if_version_support(cluster_version, cluster_type, version.support_versions):
                    versions.append(version)

        if len(versions) == 0:
            raise Exception("no available plugin version")

        versions = sorted(versions, key=lambda v: version_key(v.version))

        return versions[-1]

    def get_file_content(self, obs_url):
        if not obs_url:
            raise Exception("empty obs_url")
        obs_client = local_session(self.manager.session_factory).client("obs")
        protocol_end = len("https://")
        path_without_protocol = obs_url[protocol_end:]
        obs_bucket_name = get_obs_name(path_without_protocol)
        obs_server = get_obs_server(path_without_protocol)
        obs_file = get_file_path(path_without_protocol)
        obs_client.server = obs_server
        resp = obs_client.getObject(bucketName=obs_bucket_name,
                                    objectKey=obs_file,
                                    loadStreamInMemory=True)
        log.debug(f"[actions]-{self.action_name} query the service:[{obs_url}] succeeded.")
        content = json.loads(resp.body.buffer)
        return content

    def wait_plugin_installing_ready(self, cluster_id: str, cluster_name: str):
        try:
            @retry(times=5, interval=60, timeout=300)
            def _wait():
                client: CceClient = self.manager.get_client()
                plugin_status = get_plugin_status(client, cluster_id, self.plugin_name)
                log.debug(
                    f"[actions]- the action:[{self.action_name}] query the service:["
                    f"GET:/api/v3/addons] succeeded.")
                assert plugin_status not in ["installing",
                                             "installFailed"], f"invalid status {plugin_status}"

            _wait()
        except Exception as e:
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] install plugin failed."
                f" cause: {str(e)}")
            raise PluginInstallFailed(self.plugin_name)

    def notify_install_failed_message(self, resource, msg):
        cluster_id = resource.get('metadata', {}).get('uid')
        cluster_name = resource.get('metadata', {}).get('name', 'Unknown')
        try:
            new_data = copy.deepcopy(self.data)
            new_data.pop('type', None)
            message = (f"[actions]-[{self.action_name}]-"
                       f"The resource:[huaweicloud.cce-cluster] with id:[{cluster_name}/"
                       f"{cluster_id}] enable cluster container image signature failed."
                       f"cause: {msg}")
            new_data['message'] = message
            log.warning(f"[actions]-[{self.action_name}]-"
                        f"The resource:[huaweicloud.cce-cluster] with id:[{cluster_name}/"
                        f"{cluster_id}] enable cluster container image signature failed."
                        f"cause: {msg}")
            notify_msg_action = NotifyMessageAction(new_data, self.manager)
            notify_msg_action.process([resource])
        except Exception as e:
            log.error(
                f"[actions]- [{self.action_name}]- The resource:[huaweicloud.cce-cluster] with "
                f"id:[{cluster_name}/{cluster_id}] notify plugin install error failed."
                f" cause: {str(e)}")


@resources.register("cce-nodepool")
class CceNodePool(QueryResourceManager):
    """Huawei Cloud CCE Node Pool Resource Manager

    A node pool is a group of nodes with the same configuration in a cluster.
    Node pools make it easy to manage nodes in a cluster and support elastic scaling.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-cce-nodepools
            resource: huaweicloud.cce-nodepool
            filters:
              - type: value
                key: status.phase
                value: Active
    """

    class resource_type(TypeInfo):
        service = "cce-nodepool"  # Use cluster service
        enum_spec = ("list_clusters", "items", None)  # Query clusters first
        id = "metadata.uid"
        name = "metadata.name"

    def get_resources(self, resource_ids):
        # Get all node pools
        all_nodepools = self._fetch_resources({})
        result = []
        for nodepool in all_nodepools:
            if nodepool["metadata"]["uid"] in resource_ids:
                result.append(nodepool)
        return result

    def augment(self, clusters):
        """Get node pools for all clusters"""
        client = self.get_client()
        session = local_session(self.session_factory)

        # Get node pools for each cluster
        result = []
        for cluster in clusters:
            cluster_id = cluster['metadata']['uid']
            try:
                # Create node pool request object
                nodepool_request = session.request('cce-nodepool')
                nodepool_request.cluster_id = cluster_id
                node_pools_response = client.list_node_pools(nodepool_request)
                node_pools = node_pools_response.items
                for node_pool in node_pools:
                    # Convert to dictionary format
                    node_pool_dict = node_pool.to_dict() if hasattr(
                        node_pool, 'to_dict') else node_pool
                    # Add cluster information to node resource
                    node_pool_dict['clusterId'] = cluster_id
                    node_pool_dict['clusterName'] = cluster['metadata']['name']
                    result.append(node_pool_dict)
            except Exception as e:
                log.warning(
                    f"Failed to get node pools for cluster {cluster_id}: {e}")

        return result


@CceNodePool.action_registry.register("delete")
class DeleteCceNodePool(HuaweiCloudBaseAction):
    """Delete CCE Node Pool

    Delete the specified CCE node pool, including all nodes in the pool.
    Please note that this operation is irreversible.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-empty-nodepools
            resource: huaweicloud.cce-nodepool
            filters:
              - type: value
                key: metadata.uid
                value: test-nodepool-uid
            actions:
              - type: delete
    """

    schema = type_schema("delete")
    permissions = ('cce:deleteNodePool',)

    def perform_action(self, resource):
        """Perform delete operation on a single node pool"""
        nodepool_id = resource.get('metadata', {}).get('uid')
        nodepool_name = resource.get('metadata', {}).get('name', 'Unknown')
        cluster_id = resource.get('clusterId')

        client = self.manager.get_client()

        try:

            if not cluster_id:
                raise Exception("empty cluster id")

            if not nodepool_id:
                raise Exception("empty nodepool id")

            request = DeleteNodePoolRequest()
            request.cluster_id = cluster_id
            request.nodepool_id = nodepool_id

            response = client.delete_node_pool(request)
            log.info(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-nodepool] with "
                f"id:[{nodepool_name}/{nodepool_id}] delete nodepool succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-nodepool] with "
                f"id:[{nodepool_name}/{nodepool_id}] delete nodepool failed. "
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-nodepool] with "
                f"id:[{nodepool_name}/{nodepool_id}] delete nodepool failed. "
                f" cause: {str(e)}")
            raise


@CceNodePool.action_registry.register("update")
class UpdateCceNodePool(HuaweiCloudBaseAction):
    """Update CCE Node Pool

    Update CCE node pool configuration, such as node count, labels, node template, etc.
    Supports updating node pool metadata and spec configuration.

    :example:

    .. code-block:: yaml

        policies:
          - name: update-nodepool-config
            resource: huaweicloud.cce-nodepool
            actions:
              - type: update
                metadata:
                  name: updated-nodepool-name
                spec:
                  initial_node_count: 3
                  ignore_initial_node_count: false
                  autoscaling:
                    enable: true
                    min_node_count: 1
                    max_node_count: 10
                  node_template:
                    flavor: s6.large.2
                    az: cn-north-4a
                    os: EulerOS 2.5
                    login:
                      ssh_key: my-keypair
                    rootVolume:
                      size: 40
                      volumetype: SAS
                    dataVolumes:
                      - size: 100
                        volumetype: SAS
                    k8s_tags:
                      environment: production
                      team: dev
                    user_tags:
                      - key: owner
                        value: admin
                  taint_policy_on_existing_nodes: ignore
                  label_policy_on_existing_nodes: ignore
    """

    schema = type_schema(
        "update",
        metadata={
            "type": "object",
            "properties": {
                "name": {"type": "string"}  # Node pool name
            }
        },
        spec={
            "type": "object",
            "properties": {
                # Expected node count of node pool
                "initial_node_count": {"type": "integer"},
                # Whether to ignore initial_node_count
                "ignore_initial_node_count": {"type": "boolean"},
                "autoscaling": {  # Auto-scaling configuration
                    "type": "object",
                    "properties": {
                        "enable": {"type": "boolean"},
                        "min_node_count": {"type": "integer"},
                        "max_node_count": {"type": "integer"},
                        "scale_down_cooldown_time": {"type": "integer"},
                        "priority": {"type": "integer"}
                    }
                },
                "node_template": {  # Node template configuration
                    "type": "object",
                    "properties": {
                        "flavor": {"type": "string"},
                        "az": {"type": "string"},
                        "os": {"type": "string"},
                        "login": {
                            "type": "object",
                            "properties": {
                                "ssh_key": {"type": "string"},
                                "user_password": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {"type": "string"}
                                    }
                                }
                            }
                        },
                        "rootVolume": {
                            "type": "object",
                            "properties": {
                                "size": {"type": "integer"},
                                "volumetype": {"type": "string"}
                            }
                        },
                        "dataVolumes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "size": {"type": "integer"},
                                    "volumetype": {"type": "string"}
                                }
                            }
                        },
                        "k8s_tags": {"type": "object"},
                        "user_tags": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "value": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "taint_policy_on_existing_nodes": {  # Taint policy
                    "type": "string",
                    "enum": ["refresh", "ignore"]
                },
                "label_policy_on_existing_nodes": {  # Label policy
                    "type": "string",
                    "enum": ["refresh", "ignore"]
                },
                "user_tags_policy_on_existing_nodes": {  # User tag policy
                    "type": "string",
                    "enum": ["refresh", "ignore"]
                }
            }
        }
    )
    permissions = ('cce:updateNodePool',)

    def perform_action(self, resource):
        """Perform update operation on a single node pool"""
        nodepool_id = resource.get('metadata', {}).get('uid')
        nodepool_name = resource.get('metadata', {}).get('name', 'Unknown')
        cluster_id = resource.get('clusterId')

        client = self.manager.get_client()

        try:

            if not cluster_id:
                raise Exception("empty cluster id")

            if not nodepool_id:
                raise Exception("empty nodepool id")

            request = UpdateNodePoolRequest()
            request.cluster_id = cluster_id
            request.nodepool_id = nodepool_id

            # Build request body
            node_pool_update = NodePoolUpdate()

            # Set metadata
            metadata_config = self.data.get('metadata', {})
            if metadata_config:
                metadata_update = NodePoolMetadataUpdate()
                if 'name' in metadata_config:
                    metadata_update.name = metadata_config['name']
                node_pool_update.metadata = metadata_update

            # Set spec
            spec_config = self.data.get('spec', {})
            if spec_config:
                spec_update = NodePoolSpecUpdate()

                # Set node count related configuration
                if 'initial_node_count' in spec_config:
                    spec_update.initial_node_count = spec_config['initial_node_count']

                if 'ignore_initial_node_count' in spec_config:
                    spec_update.ignore_initial_node_count = spec_config['ignore_initial_node_count']

                # Set auto-scaling configuration
                if 'autoscaling' in spec_config:
                    autoscaling_config = spec_config['autoscaling']
                    autoscaling = NodePoolNodeAutoscaling()
                    if 'enable' in autoscaling_config:
                        autoscaling.enable = autoscaling_config['enable']
                    if 'min_node_count' in autoscaling_config:
                        autoscaling.min_node_count = autoscaling_config['min_node_count']
                    if 'max_node_count' in autoscaling_config:
                        autoscaling.max_node_count = autoscaling_config['max_node_count']
                    if 'scale_down_cooldown_time' in autoscaling_config:
                        autoscaling.scale_down_cooldown_time = autoscaling_config[
                            'scale_down_cooldown_time']
                    if 'priority' in autoscaling_config:
                        autoscaling.priority = autoscaling_config['priority']
                    spec_update.autoscaling = autoscaling

                # Set node template configuration
                if 'node_template' in spec_config:
                    from huaweicloudsdkcce.v3.model.node_spec_update import NodeSpecUpdate
                    node_template_config = spec_config['node_template']
                    node_template = NodeSpecUpdate()

                    if 'flavor' in node_template_config:
                        node_template.flavor = node_template_config['flavor']
                    if 'az' in node_template_config:
                        node_template.az = node_template_config['az']
                    if 'os' in node_template_config:
                        node_template.os = node_template_config['os']

                    # Set login method
                    if 'login' in node_template_config:
                        from huaweicloudsdkcce.v3.model.login import Login
                        login_config = node_template_config['login']
                        login = Login()
                        if 'ssh_key' in login_config:
                            login.ssh_key = login_config['ssh_key']
                        if 'user_password' in login_config:
                            from huaweicloudsdkcce.v3.model.user_password import UserPassword
                            password_config = login_config['user_password']
                            user_password = UserPassword()
                            if 'username' in password_config:
                                user_password.username = password_config['username']
                            if 'password' in password_config:
                                user_password.password = password_config['password']
                            login.user_password = user_password
                        node_template.login = login

                    # Set system disk
                    if 'rootVolume' in node_template_config:
                        from huaweicloudsdkcce.v3.model.volume import Volume
                        root_volume_config = node_template_config['rootVolume']
                        root_volume = Volume()
                        if 'size' in root_volume_config:
                            root_volume.size = root_volume_config['size']
                        if 'volumetype' in root_volume_config:
                            root_volume.volumetype = root_volume_config['volumetype']
                        node_template.root_volume = root_volume

                    # Set data disks
                    if 'dataVolumes' in node_template_config:
                        from huaweicloudsdkcce.v3.model.volume import Volume
                        data_volumes_config = node_template_config['dataVolumes']
                        data_volumes = []
                        for dv_config in data_volumes_config:
                            data_volume = Volume()
                            if 'size' in dv_config:
                                data_volume.size = dv_config['size']
                            if 'volumetype' in dv_config:
                                data_volume.volumetype = dv_config['volumetype']
                            data_volumes.append(data_volume)
                        node_template.data_volumes = data_volumes

                    # Set K8S labels
                    if 'k8s_tags' in node_template_config:
                        node_template.k8s_tags = node_template_config['k8s_tags']

                    # Set user tags
                    if 'user_tags' in node_template_config:
                        from huaweicloudsdkcce.v3.model.user_tag import UserTag
                        user_tags_config = node_template_config['user_tags']
                        user_tags = []
                        for tag_config in user_tags_config:
                            user_tag = UserTag()
                            if 'key' in tag_config:
                                user_tag.key = tag_config['key']
                            if 'value' in tag_config:
                                user_tag.value = tag_config['value']
                            user_tags.append(user_tag)
                        node_template.user_tags = user_tags

                    spec_update.node_template = node_template

                # Set policy configuration
                if 'taint_policy_on_existing_nodes' in spec_config:
                    spec_update.taint_policy_on_existing_nodes = spec_config[
                        'taint_policy_on_existing_nodes']

                if 'label_policy_on_existing_nodes' in spec_config:
                    spec_update.label_policy_on_existing_nodes = spec_config[
                        'label_policy_on_existing_nodes']

                if 'user_tags_policy_on_existing_nodes' in spec_config:
                    spec_update.user_tags_policy_on_existing_nodes = spec_config[
                        'user_tags_policy_on_existing_nodes']

                node_pool_update.spec = spec_update

            # Set request body
            request.body = node_pool_update
            response = client.update_node_pool(request)
            log.info(
                f"[actions]- [update]- The resource:[huaweicloud.cce-nodepool] with "
                f"id:[{nodepool_name}/{nodepool_id}] update nodepool succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [update]- The resource:[huaweicloud.cce-nodepool] with "
                f"id:[{nodepool_name}/{nodepool_id}] update nodepool failed. "
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [update]- The resource:[huaweicloud.cce-nodepool] with "
                f"id:[{nodepool_name}/{nodepool_id}] update nodepool failed. "
                f" cause: {str(e)}")
            raise


@resources.register("cce-node")
class CceNode(QueryResourceManager):
    """Huawei Cloud CCE Node Resource Manager

    Worker nodes in the cluster for running container applications.
    Nodes can be virtual machines or physical machines that host Pod operations.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-cce-nodes
            resource: huaweicloud.cce-node
            filters:
              - type: value
                key: status.phase
                value: Active
    """

    class resource_type(TypeInfo):
        service = "cce-node"  # Use cluster service
        enum_spec = ("list_clusters", "items", None)  # Query clusters first
        id = "metadata.uid"
        name = "metadata.name"

    def get_resources(self, resource_ids):
        # Get all nodes
        all_nodes = self._fetch_resources({})
        result = []
        for node in all_nodes:
            if node["metadata"]["uid"] in resource_ids:
                result.append(node)
        return result

    def augment(self, clusters):
        """Get nodes for all clusters"""
        client = self.get_client()
        session = local_session(self.session_factory)

        # Get nodes for each cluster
        result = []
        for cluster in clusters:
            cluster_id = cluster['metadata']['uid']
            try:
                # Create node request object
                nodes_request = session.request('cce-node')
                nodes_request.cluster_id = cluster_id
                nodes_response = client.list_nodes(nodes_request)
                nodes = nodes_response.items
                for node in nodes:
                    # Convert to dictionary format
                    node_dict = node.to_dict() if hasattr(node, 'to_dict') else node
                    # Add cluster information to node resource
                    node_dict['clusterId'] = cluster_id
                    node_dict['clusterName'] = cluster['metadata']['name']
                    result.append(node_dict)
            except Exception as e:
                log.warning(
                    f"Failed to get nodes for cluster {cluster_id}: {e}")

        return result


@CceNode.action_registry.register("delete")
class DeleteCceNode(HuaweiCloudBaseAction):
    """Delete CCE Node

    Delete the specified CCE node from the cluster.
    Note: Please ensure workloads on the node are migrated or backed up before deleting the node.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-failed-nodes
            resource: huaweicloud.cce-node
            filters:
              - type: value
                key: status.phase
                value: Error
            actions:
              - type: delete
    """

    schema = type_schema("delete")
    permissions = ('cce:deleteNode',)

    def perform_action(self, resource):
        """Perform delete operation on a single node"""
        node_id = resource.get('metadata', {}).get('uid')
        node_name = resource.get('metadata', {}).get('name', 'Unknown')
        cluster_id = resource.get('clusterId')

        client = self.manager.get_client()

        try:

            if not cluster_id:
                raise Exception("empty cluster id")

            if not node_id:
                raise Exception("empty node id")

            request = DeleteNodeRequest()
            request.cluster_id = cluster_id
            request.node_id = node_id

            response = client.delete_node(request)
            log.info(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-node] with "
                f"id:[{node_name}/{node_id}] delete node succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-node] with "
                f"id:[{node_name}/{node_id}] delete node failed. "
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-node] with "
                f"id:[{node_name}/{node_id}] delete node failed. "
                f" cause: {str(e)}")
            raise


@resources.register("cce-addontemplate")
class CceAddonTemplate(QueryResourceManager):
    """Huawei Cloud CCE Addon Template Resource Manager

    Addon templates define the specifications and configuration of addons.
    Huawei Cloud CCE provides various addon templates such as network addons,
    storage addons, monitoring addons, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-addon-templates
            resource: huaweicloud.cce-addontemplate
            filters:
              - type: value
                key: spec.type
                value: helm
    """

    class resource_type(TypeInfo):
        service = "cce-addontemplate"
        enum_spec = ("list_addon_templates", "items", None)
        id = "metadata.uid"
        name = "metadata.name"
        # Addon templates usually do not support tagging


@resources.register("cce-addoninstance")
class CceAddonInstance(QueryResourceManager):
    """Huawei Cloud CCE Addon Instance Resource Manager

    Specific addon instances created based on addon templates.
    Addon instances run in clusters and provide additional functionality for clusters.
    Note: This resource requires cluster_id parameter and queries addon instances
    across all clusters in the account.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-addon-instances
            resource: huaweicloud.cce-addoninstance
    """

    class resource_type(TypeInfo):
        service = "cce-addoninstance"  # Use cluster service
        enum_spec = ("list_clusters", "items", None)  # Query clusters first
        id = "metadata.uid"
        name = "metadata.name"
        # Addon instances usually do not support tagging

    def get_resources(self, resource_ids):
        # Get all addon instances
        all_addon_instances = self._fetch_resources({})
        result = []
        for addon_instance in all_addon_instances:
            if addon_instance["metadata"]["uid"] in resource_ids:
                result.append(addon_instance)
        return result

    def _convert_to_dict(self, obj):
        """Recursively convert SDK objects to dictionaries for JSON serialization"""
        if obj is None:
            return None
        elif hasattr(obj, 'to_dict'):
            # SDK object with to_dict method
            try:
                dict_obj = obj.to_dict()
                return self._convert_to_dict(dict_obj)
            except Exception:
                return str(obj)
        elif isinstance(obj, dict):
            # Dictionary - recursively convert values
            return {key: self._convert_to_dict(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            # List or tuple - recursively convert elements
            return [self._convert_to_dict(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Object with attributes - convert to dict
            try:
                return {key: self._convert_to_dict(value) for key, value in obj.__dict__.items()}
            except Exception:
                return str(obj)
        else:
            # Basic types (str, int, float, bool) or convert to string
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                # For other types like datetime, convert to string
                return str(obj)

    def augment(self, clusters):
        """Get addon instances for all clusters"""
        client = self.get_client()

        # Get addon instances for each cluster
        result = []
        for cluster in clusters:
            cluster_id = cluster['metadata']['uid']
            try:
                # Create addon instance request object
                request = ListAddonInstancesRequest()
                request.cluster_id = cluster_id
                response = client.list_addon_instances(request)
                addon_instances = response.items if response.items else []
                for addon_instance in addon_instances:
                    # Convert to dictionary format recursively
                    addon_instance_dict = self._convert_to_dict(addon_instance)

                    # Ensure we have at least basic structure
                    if not isinstance(addon_instance_dict, dict):
                        addon_instance_dict = {}

                    # Add cluster information to addon instance resource
                    addon_instance_dict['clusterId'] = cluster_id
                    addon_instance_dict['clusterName'] = cluster['metadata']['name']
                    result.append(addon_instance_dict)
            except Exception as e:
                log.warning(
                    f"Failed to get addon instances for cluster {cluster_id}: {e}")

        return result


@CceAddonInstance.action_registry.register("delete")
class DeleteCceAddonInstance(HuaweiCloudBaseAction):
    """Delete CCE Addon Instance

    Delete the specified CCE addon instance.
    Deleting addon instances may affect cluster functionality, please operate with caution.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-unused-addons
            resource: huaweicloud.cce-addoninstance
            filters:
              - type: value
                key: metadata.uid
                value: test-addon
            actions:
              - type: delete
    """

    schema = type_schema("delete")
    permissions = ('cce:deleteAddonInstance',)

    def perform_action(self, resource):
        """Perform delete operation on a single addon instance"""
        addon_id = resource.get('metadata', {}).get('uid')
        addon_name = resource.get('metadata', {}).get('name', 'Unknown')
        cluster_id = resource.get('clusterId')

        client = self.manager.get_client()

        try:
            if not addon_id:
                raise Exception("empty addon id")

            request = DeleteAddonInstanceRequest()
            request.id = addon_id
            # Set cluster_id if available (optional parameter for delete operation)
            if cluster_id:
                request.cluster_id = cluster_id

            response = client.delete_addon_instance(request)
            log.info(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-addoninstance] with "
                f"id:[{addon_name}/{addon_id}] delete addoninstance succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-addoninstance] with "
                f"id:[{addon_name}/{addon_id}] delete addoninstance failed. "
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-addoninstance] with "
                f"id:[{addon_name}/{addon_id}] delete addoninstance failed. "
                f" cause: {str(e)}")
            raise


@resources.register("cce-chart")
class CceChart(QueryResourceManager):
    """Huawei Cloud CCE Chart Resource Manager

    Helm chart resources for defining Kubernetes application deployment configurations.
    Charts contain all resource definitions and configuration information for applications.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-cce-charts
            resource: huaweicloud.cce-chart
    """

    class resource_type(TypeInfo):
        service = "cce-chart"
        enum_spec = ("list_charts", "body", None)
        id = "id"
        name = "name"
        # Chart resources usually do not support tagging


@CceChart.action_registry.register("delete")
class DeleteCceChart(HuaweiCloudBaseAction):
    """Delete CCE Chart

    Deleting charts will not affect Release instances created based on the chart.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-unused-charts
            resource: huaweicloud.cce-chart
            filters:
              - type: value
                key: name
                value: unused-chart
            actions:
              - type: delete
    """

    schema = type_schema("delete")
    permissions = ('cce:deleteChart',)

    def perform_action(self, resource):
        """Perform delete operation on a single chart"""
        chart_id = resource.get('id')
        chart_name = resource.get('name', 'Unknown')

        client = self.manager.get_client()

        try:
            if not chart_id:
                raise Exception("empty chart id")
            request = DeleteChartRequest()
            request.chart_id = chart_id

            response = client.delete_chart(request)
            log.info(
                f"[actions]- [update]- The resource:[huaweicloud.cce-chart] with "
                f"id:[{chart_name}/{chart_id}] delete chart succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [update]- The resource:[huaweicloud.cce-chart] with "
                f"id:[{chart_name}/{chart_id}] delete chart failed. "
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [update]- The resource:[huaweicloud.cce-chart] with "
                f"id:[{chart_name}/{chart_id}] delete chart failed. "
                f" cause: {str(e)}")
            raise


@resources.register("cce-release")
class CceRelease(QueryResourceManager):
    """Huawei Cloud CCE Release Resource Manager

    Application releases created based on Helm charts.
    Releases represent specific application instances deployed in clusters.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-cce-releases
            resource: huaweicloud.cce-release
    """

    class resource_type(TypeInfo):
        service = "cce-release"  # Use cluster service
        enum_spec = ("list_clusters", "items", None)  # Query clusters first
        id = "metadata.uid"
        name = "metadata.name"
        # Release resources usually do not support tagging

    def get_resources(self, resource_ids):
        # Get all releases
        all_releases = self._fetch_resources({})
        result = []
        for release in all_releases:
            if release["id"] in resource_ids:
                result.append(release)
        return result

    def augment(self, clusters):
        """Get releases for all clusters"""
        client = self.get_client()
        session = local_session(self.session_factory)

        # Get releases for each cluster
        result = []
        for cluster in clusters:
            cluster_id = cluster['metadata']['uid']
            try:
                # Create release request object
                releases_request = session.request('cce-release')
                releases_request.cluster_id = cluster_id
                releases_response = client.list_releases(releases_request)
                releases = releases_response.body
                for release in releases:
                    # Convert to dictionary format
                    release_dict = release.to_dict() if hasattr(release, 'to_dict') else release
                    result.append(release_dict)
            except Exception as e:
                log.warning(
                    f"Failed to get releases for cluster {cluster_id}: {e}")

        return result


@CceRelease.action_registry.register("delete")
class DeleteCceRelease(HuaweiCloudBaseAction):
    """Delete CCE Release

    Delete the specified Helm Release instance.
    Deleting releases will uninstall applications deployed in the cluster.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-failed-releases
            resource: huaweicloud.cce-release
            filters:
              - type: value
                key: status.phase
                value: failed
            actions:
              - type: delete
    """

    schema = type_schema("delete")
    permissions = ('cce:deleteRelease',)

    def perform_action(self, resource):
        """Perform delete operation on a single release"""
        release_name = resource.get('name')
        cluster_id = resource.get('cluster_id')
        namespace = resource.get('namespace', 'default')

        if not release_name or not cluster_id:
            log.error(
                f"Cannot delete release, missing required information: {release_name}")
            return None

        client = self.manager.get_client()

        try:
            request = DeleteReleaseRequest()
            request.cluster_id = cluster_id
            request.name = release_name
            request.namespace = namespace

            response = client.delete_release(request)
            log.info(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-release] with "
                f"id:[{release_name}] delete release succeeded.")
            return response

        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-release] with "
                f"id:[{release_name}] delete release failed. "
                f" cause: {e.error_msg} (status code: {e.status_code})")
            raise
        except Exception as e:
            log.error(
                f"[actions]- [delete]- The resource:[huaweicloud.cce-release] with "
                f"id:[{release_name}] delete release failed. "
                f" cause: {str(e)}")
            raise


class NoRetry(Exception):
    def __init__(self, reason):
        super(NoRetry, self).__init__(reason)
        self.reason = reason

    def __str__(self):
        return "NoRetry(reason=%s)" % self.reason


class PluginNotInstalled(Exception):
    def __init__(self, name):
        super(PluginNotInstalled, self).__init__(name)
        self.name = name

    def __str__(self):
        return "Plugin (name=%s) Not Installed" % self.name


class PluginInstallFailed(Exception):
    def __init__(self, name):
        super(PluginInstallFailed, self).__init__(name)
        self.name = name

    def __str__(self):
        return "Plugin (name=%s) Install Failed" % self.name


def retry(times=-1, interval=5, timeout=-1):
    """
    :param times: 重试次数，times = 0，表示不重试；times < 0，表示无限重试
    :param interval: 间隔多久时间重试，单位秒
    :param timeout: timout < 0 无超时设置；
                    timeout = 0，表示不重试；
                    timeout > 0，表示超时上限（单位秒），如果发生错误时，用时超过timeout，不再重试
    :return:: deco 实现重试功能的装饰器
    """

    # 防止无限重试
    assert times >= 0 or timeout >= 0, 'times and timeout should be given'

    def deco(func):

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            n = 0
            st = time.perf_counter()
            while True:
                n += 1
                try:
                    ret = func(*args, **kwargs)
                    return ret
                except Exception as e:
                    if isinstance(e, NoRetry):
                        raise
                    if 0 <= times <= n - 1:
                        raise
                    if timeout == 0:
                        raise
                    if 0 < timeout <= time.perf_counter() - st:
                        raise
                    if interval > 0:
                        time.sleep(interval)

        return wrapped

    return deco


def if_version_support(cluster_version: str, cluster_type: str,
                       support_versions: list[SupportVersions]) -> bool:
    for _, support_version in enumerate(support_versions):
        if support_version.cluster_type != cluster_type:
            continue
        for _, ver in enumerate(support_version.cluster_version):
            p = re.compile(ver)
            if p.match(cluster_version):
                return True
    return False


def version_key(version: str) -> list[int]:
    return [int(v) for v in version.split('.')]


def get_matched_flavor(cluster_flavor, flavors):
    custom = {}
    for k, v in flavors.items():
        if "flavor" not in k:
            continue
        if v["size"] in cluster_flavor:
            return v
        if v["size"] == "custom":
            custom = v
    return custom


def get_cluster_status(client: CceClient, cluster_id: str) -> str:
    request = ShowClusterRequest(cluster_id)
    response = client.show_cluster(request)
    return response.status.phase


def wait_cluster_status_ready(client: CceClient, cluster_id: str, cluster_status: str, times: int,
                              interval: int, timeout: int):
    @retry(times=times, interval=interval, timeout=timeout)
    def _wait():
        curr_status = get_cluster_status(client, cluster_id)
        assert curr_status in cluster_status, "invalid status %s" % curr_status

    _wait()


def get_plugin_status(client: CceClient, cluster_id: str, plugin_name: str) -> str:
    request = ListAddonInstancesRequest()
    request.cluster_id = cluster_id

    response = client.list_addon_instances(request)
    for _, item in enumerate(response.items):
        if plugin_name == item.metadata.name:
            return item.status.status
    raise PluginNotInstalled(plugin_name)
