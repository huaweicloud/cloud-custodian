# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n.utils import local_session, type_schema
from huaweicloudsdkcore.exceptions import exceptions

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
    NodePoolNodeAutoscaling
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

        if not cluster_id:
            log.error(
                f"Cannot delete CCE cluster, missing cluster ID: {cluster_name}")
            return None

        client = self.manager.get_client()

        try:
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
                f"Started deleting CCE cluster {cluster_name} ({cluster_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to delete CCE cluster {cluster_name} ({cluster_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error("Error occurred while deleting"
                      f" CCE cluster {cluster_name} ({cluster_id}): {str(e)}")
            return None


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

        if not cluster_id:
            log.error(
                f"Cannot hibernate CCE cluster, missing cluster ID: {cluster_name}")
            return None

        client = self.manager.get_client()

        try:
            request = HibernateClusterRequest()
            request.cluster_id = cluster_id

            response = client.hibernate_cluster(request)
            log.info(
                f"Started hibernating CCE cluster {cluster_name} ({cluster_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to hibernate CCE cluster {cluster_name} ({cluster_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                "Error occurred while hibernating"
                f" CCE cluster {cluster_name} ({cluster_id}): {str(e)}")
            return None


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

        if not cluster_id:
            log.error(
                f"Cannot awake CCE cluster, missing cluster ID: {cluster_name}")
            return None

        client = self.manager.get_client()

        try:
            request = AwakeClusterRequest()
            request.cluster_id = cluster_id

            response = client.awake_cluster(request)
            log.info(
                f"Started awakening CCE cluster {cluster_name} ({cluster_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to awake CCE cluster {cluster_name} ({cluster_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                "Error occurred while awaking"
                f" CCE cluster {cluster_name} ({cluster_id}): {str(e)}")
            return None


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

        if not cluster_id:
            log.error(
                f"Cannot update CCE cluster, missing cluster ID: {cluster_name}")
            return None

        client = self.manager.get_client()

        try:
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
                f"Started updating CCE cluster {cluster_name} ({cluster_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to update CCE cluster {cluster_name} ({cluster_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                "Error occurred while updating"
                f" CCE cluster {cluster_name} ({cluster_id}): {str(e)}")
            return None


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

        if not nodepool_id or not cluster_id:
            log.error(
                f"Cannot delete node pool, missing required ID: {nodepool_name}")
            return None

        client = self.manager.get_client()

        try:
            request = DeleteNodePoolRequest()
            request.cluster_id = cluster_id
            request.nodepool_id = nodepool_id

            response = client.delete_node_pool(request)
            log.info(
                f"Started deleting CCE node pool {nodepool_name} ({nodepool_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to delete CCE node pool {nodepool_name} ({nodepool_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                "Error occurred while deleting"
                f" CCE node pool {nodepool_name} ({nodepool_id}): {str(e)}")
            return None


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

        if not nodepool_id or not cluster_id:
            log.error(
                f"Cannot update node pool, missing required ID: {nodepool_name}")
            return None

        client = self.manager.get_client()

        try:
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

            log.info(
                f"Started updating CCE node pool {nodepool_name} ({nodepool_id})")
            response = client.update_node_pool(request)
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to update CCE node pool {nodepool_name} ({nodepool_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                "Error occurred while updating"
                f" CCE node pool {nodepool_name} ({nodepool_id}): {str(e)}")
            return None


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

        if not node_id or not cluster_id:
            log.error(f"Cannot delete node, missing required ID: {node_name}")
            return None

        client = self.manager.get_client()

        try:
            request = DeleteNodeRequest()
            request.cluster_id = cluster_id
            request.node_id = node_id

            response = client.delete_node(request)
            log.info(f"Started deleting CCE node {node_name} ({node_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to delete CCE node {node_name} ({node_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                f"Error occurred while deleting CCE node {node_name} ({node_id}): {str(e)}")
            return None


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

        if not addon_id:
            log.error(
                f"Cannot delete addon instance, missing required ID: {addon_name}")
            return None

        client = self.manager.get_client()

        try:
            request = DeleteAddonInstanceRequest()
            request.id = addon_id
            # Set cluster_id if available (optional parameter for delete operation)
            if cluster_id:
                request.cluster_id = cluster_id

            response = client.delete_addon_instance(request)
            log.info(
                f"Started deleting CCE addon instance {addon_name} ({addon_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to delete CCE addon instance {addon_name} ({addon_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                "Error occurred while deleting"
                f"CCE addon instance {addon_name} ({addon_id}): {str(e)}")
            return None


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

        if not chart_id:
            log.error(f"Cannot delete chart, missing chart ID: {chart_name}")
            return None

        client = self.manager.get_client()

        try:
            request = DeleteChartRequest()
            request.chart_id = chart_id

            response = client.delete_chart(request)
            log.info(f"Started deleting CCE chart {chart_name} ({chart_id})")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to delete CCE chart {chart_name} ({chart_id}): "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                f"Error occurred while deleting CCE chart {chart_name} ({chart_id}): {str(e)}")
            return None


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
                f"Started deleting CCE release {release_name} in cluster {cluster_id}")
            return response

        except exceptions.ClientRequestException as e:
            log.error(f"Failed to delete CCE release {release_name}: "
                      f"{e.error_msg} (status code: {e.status_code})")
            return None
        except Exception as e:
            log.error(
                f"Error occurred while deleting CCE release {release_name}: {str(e)}")
            return None
