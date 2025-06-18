# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.provider import resources

log = logging.getLogger("custodian.huaweicloud.cce")


@resources.register("cce-cluster")
class CceCluster(QueryResourceManager):
    """华为云CCE集群资源管理器
    
    容器集群提供高可靠、高性能的企业级容器应用管理服务。
    支持标准Kubernetes API，集成了华为云的计算、网络、存储等服务。
    
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
        enum_spec = ("list_clusters", "items", "marker")
        id = "metadata.uid"
        name = "metadata.name"
        tag_resource_type = "cce"


@resources.register("cce-autopilot-cluster") 
class CceAutopilotCluster(QueryResourceManager):
    """华为云CCE Autopilot集群资源管理器
    
    CCE Autopilot是华为云推出的免运维Kubernetes容器集群，
    提供serverless的容器运行环境，用户无需关心节点管理。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: list-autopilot-clusters
            resource: huaweicloud.cce-autopilot-cluster
            filters:
              - type: value
                key: status.phase
                value: Available
    """
    
    class resource_type(TypeInfo):
        service = "cce-autopilot-cluster"
        enum_spec = ("list_autopilot_clusters", "items", "marker")
        id = "metadata.uid"
        name = "metadata.name" 
        tag_resource_type = "cce"


@resources.register("cce-nodepool")
class CceNodePool(QueryResourceManager):
    """华为云CCE节点池资源管理器
    
    节点池是集群中一组具有相同配置的节点。
    通过节点池可以方便地管理集群中的节点，支持弹性伸缩。
    
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
        service = "cce-nodepool"
        enum_spec = ("list_node_pools", "items", "marker")
        id = "metadata.uid"
        name = "metadata.name"
        tag_resource_type = "cce"


@resources.register("cce-node")
class CceNode(QueryResourceManager):
    """华为云CCE节点资源管理器
    
    集群中的工作节点，用于运行容器应用。
    节点可以是虚拟机或物理机，承载Pod的运行。
    
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
        service = "cce-node"
        enum_spec = ("list_nodes", "items", "marker")
        id = "metadata.uid"
        name = "metadata.name"
        tag_resource_type = "cce"


@resources.register("cce-addontemplate")
class CceAddonTemplate(QueryResourceManager):
    """华为云CCE插件模板资源管理器
    
    插件模板定义了插件的规格和配置。
    华为云CCE提供多种插件模板，如网络插件、存储插件、监控插件等。
    
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
        enum_spec = ("list_addon_templates", "items", "marker")
        id = "metadata.uid"
        name = "metadata.name"
        # 插件模板通常不支持标签功能


@resources.register("cce-addoninstance")
class CceAddonInstance(QueryResourceManager):
    """华为云CCE插件实例资源管理器
    
    基于插件模板创建的具体插件实例。
    插件实例运行在集群中，为集群提供额外的功能。
    
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
        enum_spec = ("list_addon_instances", "items", "marker")
        id = "metadata.uid"
        name = "metadata.name"
        # 插件实例通常不支持标签功能


@resources.register("cce-chart")
class CceChart(QueryResourceManager):
    """华为云CCE图表资源管理器
    
    Helm图表资源，用于定义Kubernetes应用的部署配置。
    图表包含应用的所有资源定义和配置信息。
    
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
        # 图表资源通常不支持标签功能


@resources.register("cce-release")
class CceRelease(QueryResourceManager):
    """华为云CCE发布资源管理器
    
    基于Helm图表创建的应用发布。
    发布表示在集群中部署的具体应用实例。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: list-cce-releases
            resource: huaweicloud.cce-release
            filters:
              - type: value
                key: status
                value: deployed
    """
    
    class resource_type(TypeInfo):
        service = "cce-release"
        enum_spec = ("list_releases", "body", None)
        id = "name"
        name = "name"
        # 发布资源通常不支持标签功能
