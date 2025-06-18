# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.provider import resources
from c7n.utils import local_session

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
        tag_resource_type = "cce"


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
        service = "cce-cluster"  # Use cluster service
        enum_spec = ("list_clusters", "items", None)  # Query clusters first
        id = "metadata.uid"
        name = "metadata.name"
        tag_resource_type = "cce"

    def get_resources(self, resource_ids):
        # Get all node pools
        all_nodepools = self._fetch_resources({})
        result = []
        for nodepool in all_nodepools:
            if nodepool["id"] in resource_ids:
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
                    result.append(node_pool_dict)
            except Exception as e:
                log.warning(
                    f"Failed to get node pools for cluster {cluster_id}: {e}")

        return result


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
        service = "cce-cluster"  # Use cluster service
        enum_spec = ("list_clusters", "items", None)  # Query clusters first
        id = "metadata.uid"
        name = "metadata.name"
        tag_resource_type = "cce"

    def get_resources(self, resource_ids):
        # Get all nodes
        all_nodes = self._fetch_resources({})
        result = []
        for node in all_nodes:
            if node["id"] in resource_ids:
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
                    result.append(node_dict)
            except Exception as e:
                log.warning(
                    f"Failed to get nodes for cluster {cluster_id}: {e}")

        return result


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

    :example:

    .. code-block:: yaml

        policies:
          - name: list-addon-instances
            resource: huaweicloud.cce-addoninstance
            filters:
              - type: value
                key: status.status
                value: running
    """

    class resource_type(TypeInfo):
        service = "cce-addoninstance"
        enum_spec = ("list_addon_instances", "items", None)
        id = "metadata.uid"
        name = "metadata.name"
        # Addon instances usually do not support tagging


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
            filters:
              - type: value
                key: spec.chart_type
                value: helm
    """

    class resource_type(TypeInfo):
        service = "cce-chart"
        enum_spec = ("list_charts", "body", None)
        id = "name"
        name = "name"
        # Chart resources usually do not support tagging


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
        service = "cce-cluster"  # Use cluster service
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
