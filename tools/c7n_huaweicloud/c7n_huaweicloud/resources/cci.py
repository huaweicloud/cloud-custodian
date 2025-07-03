# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.filters import ValueFilter, AgeFilter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.cci")


# ===============================
# CCI Query Resource Manager Base Class
# ===============================
class CCIQueryResourceManager(QueryResourceManager):
    """CCI Resource Query Manager Base Class

    Provides special query logic for CCI resources, including namespace handling.
    Inherits from standard QueryResourceManager but optimized for CCI service.
    """

    def _normalize_resource(self, resource):
        """Normalize resource data structure

        For CCI resources (Kubernetes style), maintain their original structure.
        Ensure resources have basic metadata structure and add creationTimestamp at same level.
        """
        if not isinstance(resource, dict):
            return resource

        # Ensure resource has metadata structure
        if 'metadata' not in resource:
            resource['metadata'] = {}

        # Assign uid value to id, ensure metadata has id attribute
        metadata = resource['metadata']
        if 'uid' in metadata:
            metadata['id'] = metadata['uid']

        # Add creationTimestamp to same level as metadata
        creation_timestamp = metadata.get('creationTimestamp')
        if creation_timestamp:
            resource['creationTimestamp'] = creation_timestamp

        # For CCI resources, no need to promote metadata fields to top level
        # Because filters and other components expect standard Kubernetes resource structure
        return resource

    def _get_resource_id(self, resource):
        """Get resource ID

        Prioritize using UID, if no UID then use name as identifier
        """
        if isinstance(resource, dict):
            metadata = resource.get('metadata', {})
            # Prioritize using UID
            uid = metadata.get('uid')
            if uid:
                return uid
            # If no UID, use name as backup
            name = metadata.get('name')
            if name:
                namespace = metadata.get('namespace')
                if namespace:
                    return f"{namespace}/{name}"  # Namespaced resources use namespace/name format
                else:
                    return name  # Cluster-level resources use name directly
            # Finally try to get id field from top level
            return resource.get('id')
        return None

    def _get_namespaces(self):
        """Get list of all available namespaces

        Returns:
            list: List of namespace names
        """
        try:
            session = local_session(self.session_factory)
            client = session.client("cci")

            # Get namespace list
            namespaces_response = client.list_namespaces()
            if not namespaces_response or 'items' not in namespaces_response:
                log.warning("No namespaces found or invalid response format")
                return ['default']  # Return default namespace

            # Extract namespace names
            namespace_names = []
            for ns in namespaces_response['items']:
                if isinstance(ns, dict) and 'metadata' in ns and 'name' in ns['metadata']:
                    namespace_names.append(ns['metadata']['name'])

            if not namespace_names:
                log.warning("No valid namespace names found, using default")
                return ['default']

            log.debug(f"Found namespaces: {namespace_names}")
            return namespace_names

        except Exception as e:
            log.error(f"Failed to get namespaces: {e}")
            return ['default']  # Return default namespace on error

    def _get_namespaced_resources(self, enum_op):
        """Get resources from all namespaces

        Args:
            enum_op: Resource enumeration operation method name

        Returns:
            list: List of resources from all namespaces
        """
        all_resources = []
        namespaces = self._get_namespaces()

        session = local_session(self.session_factory)
        client = session.client("cci")

        for namespace in namespaces:
            response = None  # Initialize response variable
            try:
                log.debug(f"Querying {enum_op} in namespace: {namespace}")

                # Call corresponding client method based on operation method name
                if hasattr(client, enum_op):
                    method = getattr(client, enum_op)
                    response = method(namespace)

                    if response and 'items' in response:
                        # Add namespace info to each resource (if not already present)
                        for resource in response['items']:
                            if isinstance(resource, dict):
                                if 'metadata' not in resource:
                                    resource['metadata'] = {}
                                if 'namespace' not in resource['metadata']:
                                    resource['metadata']['namespace'] = namespace

                        all_resources.extend(response['items'])
                        log.debug(
                            f"Found {len(response['items'])} resources in namespace {namespace}")
                    else:
                        log.debug(f"No resources found in namespace {namespace}")

                else:
                    log.error(f"Client method {enum_op} not found")

            except Exception as e:
                log.error(f"Failed to get resources from namespace {namespace}: {e}")
                if response is not None:
                    log.debug(f"Response was: {response}")
                continue

        log.info(f"Total resources found across all namespaces: {len(all_resources)}")
        return all_resources

    def augment(self, resources):
        """Enhance resource data

        Standardize CCI resources
        """
        if not resources:
            return resources

        augmented = []
        for resource in resources:
            resource = self._normalize_resource(resource)
            augmented.append(resource)

        return augmented

    def get_resources(self, resource_ids=None):
        """Get resource list and properly handle nested ID structure

        Override parent class method to ensure correct resource ID setting
        """
        try:
            # Use parent class logic to get raw resources
            resources = super().get_resources(resource_ids)

            # Post-process each resource to ensure ID field is correctly set
            processed_resources = []
            for resource in resources:
                # Normalize resource structure
                resource = self._normalize_resource(resource)

                # Set top-level ID field to avoid KeyError in query.py
                resource_id = self._get_resource_id(resource)
                if resource_id:
                    resource['id'] = resource_id

                processed_resources.append(resource)

            return processed_resources

        except Exception as e:
            log.error(f"Failed to get CCI resources: {e}")
            return []


class CCINamespacedResourceManager(CCIQueryResourceManager):
    """CCI Namespaced Resource Manager Base Class

    Specifically for managing CCI resources that require namespaces (like Pod, ConfigMap, Secret)
    """

    def get_resources(self, resource_ids=None):
        """Get resource list

        For namespaced resources, need to traverse all namespaces to get resources
        """
        try:
            # Get resource type information
            enum_spec = self.resource_type.enum_spec
            if not enum_spec or len(enum_spec) < 1:
                log.error(f"Invalid enum_spec for resource type: {self.resource_type}")
                return []

            enum_op = enum_spec[0]  # Get enumeration operation method name

            # Get resources from all namespaces
            resources = self._get_namespaced_resources(enum_op)

            # Filter by resource IDs if specified
            if resource_ids:
                filtered_resources = []
                for resource in resources:
                    resource_id = self._get_resource_id(resource)
                    if resource_id in resource_ids:
                        filtered_resources.append(resource)
                resources = filtered_resources

            # Enhance resource data, including correct ID field setting
            resources = self.augment(resources)

            # Ensure ID field is correctly set for each resource
            processed_resources = []
            for resource in resources:
                # Normalize resource structure
                resource = self._normalize_resource(resource)

                # Set top-level ID field to avoid KeyError in query.py
                resource_id = self._get_resource_id(resource)
                if resource_id:
                    resource['id'] = resource_id

                processed_resources.append(resource)

            return processed_resources

        except Exception as e:
            log.error(f"Failed to get resources: {e}")
            return []


# ===============================
# CCI Namespace Resource Type
# ===============================
@resources.register("cci_namespace")
class CCINamespace(CCIQueryResourceManager):
    """Huawei Cloud CCI Namespace Resource Manager

    CCI namespace is a logical isolation unit for container instances, used to organize and
    manage container instances, configurations, secrets and other resources.

    """

    class resource_type(TypeInfo):
        service = "cci"
        enum_spec = ("list_namespaces", "items", None)
        id = "metadata.uid"  # In Kubernetes, metadata.uid is used as unique identifier
        name = "metadata.name"  # metadata.name
        date = "metadata.creationTimestamp"  # metadata.creationTimestamp


# ===============================
# CCI Pod Resource Type
# ===============================
@resources.register("cci_pod")
class CCIPod(CCINamespacedResourceManager):
    """Huawei Cloud CCI Container Instance (Pod) Resource Manager

    CCI Pod is the basic unit for running container applications, containing one or more
    tightly coupled containers.

    """

    class resource_type(TypeInfo):
        service = "cci"
        enum_spec = ("list_namespaced_pods", "items", None)
        id = "metadata.uid"
        name = "metadata.name"
        date = "metadata.creationTimestamp"
        namespaced = True  # Pod is a namespaced resource


# ===============================
# CCI ConfigMap Resource Type
# ===============================
@resources.register("cci_configmap")
class CCIConfigMap(CCINamespacedResourceManager):
    """Huawei Cloud CCI ConfigMap Resource Manager

    CCI ConfigMap is used to store configuration data, providing configuration information
    to Pods.

    """

    class resource_type(TypeInfo):
        service = "cci"
        enum_spec = ("list_namespaced_configmaps", "items", None)
        id = "metadata.uid"
        name = "metadata.name"
        date = "metadata.creationTimestamp"
        namespaced = True


# ===============================
# CCI Secret Resource Type
# ===============================
@resources.register("cci_secret")
class CCISecret(CCINamespacedResourceManager):
    """Huawei Cloud CCI Secret Resource Manager

    CCI Secret is used to store sensitive data such as passwords, OAuth tokens, SSH keys, etc.

    """

    class resource_type(TypeInfo):
        service = "cci"
        enum_spec = ("list_namespaced_secrets", "items", None)
        id = "metadata.uid"
        name = "metadata.name"
        date = "metadata.creationTimestamp"
        namespaced = True


# ===============================
# Common Filters - For All CCI Resources
# ===============================

class CCINameFilter(ValueFilter):
    """CCI Resource Name Filter

    Filter by resource name, supports exact match, regex match and other operators.

    :example:

    .. code-block:: yaml

        policies:
          - name: cci-pods-by-name
            resource: huaweicloud.cci_pod
            filters:
              - type: name
                value: "my-pod"
                op: eq
    """

    schema = type_schema("name", rinherit=ValueFilter.schema)
    schema_alias = False

    def __init__(self, data, manager=None):
        super(CCINameFilter, self).__init__(data, manager)
        self.data['key'] = 'metadata.name'


class CCICreationAgeFilter(AgeFilter):
    """CCI Resource Creation Time Filter

    Filter by resource creation time, supports greater than, less than, equal operations.

    :example:

    .. code-block:: yaml

        policies:
          - name: old-cci-pods
            resource: huaweicloud.cci_pod
            filters:
              - type: creation-age
                days: 7
                op: ge
    """

    date_attribute = "metadata.creationTimestamp"
    schema = type_schema(
        "creation-age",
        days={"type": "number", "minimum": 0},
        hours={"type": "number", "minimum": 0},
        minutes={"type": "number", "minimum": 0},
        op={"type": "string", "enum": ["eq", "equal", "ne", "not-equal",
                                       "gt", "greater-than", "ge", "gte",
                                       "le", "lte", "lt", "less-than"]},
        required=["op"]
    )

    def get_resource_date(self, resource):
        """Get resource creation time

        Support multiple formats of date attribute access:
        1. First try to access top-level creationTimestamp (already promoted by client)
        2. Then try to access metadata.creationTimestamp (original Kubernetes format)
        3. Finally try to get creationTimestamp from metadata

        Args:
            resource: Resource dictionary

        Returns:
            datetime: Parsed datetime object, returns None if unable to get
        """
        from dateutil.parser import parse
        from dateutil.tz import tzutc
        import datetime as dt

        # 1. Prioritize using creationTimestamp promoted to top level
        creation_timestamp = resource.get('creationTimestamp')
        if creation_timestamp:
            try:
                if not isinstance(creation_timestamp, dt.datetime):
                    creation_timestamp = parse(creation_timestamp)
                if not creation_timestamp.tzinfo:
                    creation_timestamp = creation_timestamp.replace(tzinfo=tzutc())
                return creation_timestamp
            except Exception as e:
                log.debug(f"Failed to parse top-level creationTimestamp: {e}")

        # 2. Try to get creationTimestamp from metadata
        metadata = resource.get('metadata', {})
        if isinstance(metadata, dict):
            creation_timestamp = metadata.get('creationTimestamp')
            if creation_timestamp:
                try:
                    if not isinstance(creation_timestamp, dt.datetime):
                        creation_timestamp = parse(creation_timestamp)
                    if not creation_timestamp.tzinfo:
                        creation_timestamp = creation_timestamp.replace(tzinfo=tzutc())
                    return creation_timestamp
                except Exception as e:
                    log.debug(f"Failed to parse metadata.creationTimestamp: {e}")

        # 3. If unable to get, log warning and return None
        resource_name = ""
        if isinstance(metadata, dict):
            resource_name = metadata.get('name', 'unknown')
        log.warning(f"Could not get creation timestamp for CCI resource {resource_name}")
        return None


class CCIUidFilter(ValueFilter):
    """CCI Resource UID Filter

    Filter by Kubernetes resource UID.

    :example:

    .. code-block:: yaml

        policies:
          - name: cci-resource-by-uid
            resource: huaweicloud.cci_pod
            filters:
              - type: uid
                value: "123e4567-e89b-12d3-a456-426614174000"
    """

    schema = type_schema("uid", rinherit=ValueFilter.schema)
    schema_alias = False

    def __init__(self, data, manager=None):
        super(CCIUidFilter, self).__init__(data, manager)
        self.data['key'] = 'metadata.uid'


class CCINamespaceFilter(ValueFilter):
    """CCI Resource Namespace Filter

    Filter by resource namespace, supports exact match, regex match and other operators.

    :example:

    .. code-block:: yaml

        policies:
          - name: cci-pods-by-namespace
            resource: huaweicloud.cci_pod
            filters:
              - type: namespace
                value: "default"
                op: eq
    """

    schema = type_schema("namespace", rinherit=ValueFilter.schema)
    schema_alias = False

    def __init__(self, data, manager=None):
        super(CCINamespaceFilter, self).__init__(data, manager)
        self.data['key'] = 'metadata.namespace'


# ===============================
# Pod Specific Filters
# ===============================

@CCIPod.filter_registry.register("name")
class PodNameFilter(CCINameFilter):
    """Pod Name Filter"""
    pass


@CCIPod.filter_registry.register("creation-age")
class PodCreationAgeFilter(CCICreationAgeFilter):
    """Pod Creation Time Filter"""
    pass


@CCIPod.filter_registry.register("uid")
class PodUidFilter(CCIUidFilter):
    """Pod UID Filter"""
    pass


@CCIPod.filter_registry.register("namespace")
class PodNamespaceFilter(CCINamespaceFilter):
    """Pod Namespace Filter"""
    pass


@CCIPod.filter_registry.register("image-name")
class PodImageNameFilter(ValueFilter):
    """Pod Image Name Filter

    Filter by image names used by containers in Pod.

    :example:

    .. code-block:: yaml

        policies:
          - name: pods-with-nginx
            resource: huaweicloud.cci_pod
            filters:
              - type: image-name
                value: "nginx"
                op: contains
    """

    schema = type_schema("image-name", rinherit=ValueFilter.schema)
    schema_alias = False

    def __init__(self, data, manager=None):
        super(PodImageNameFilter, self).__init__(data, manager)
        # Set a virtual key because we need custom matching logic
        self.data['key'] = 'spec.containers'

    def process(self, resources, event=None):
        """Process resource list, check container images in each Pod"""
        matched = []
        for resource in resources:
            if self.match_pod_images(resource):
                matched.append(resource)
        return matched

    def match_pod_images(self, resource):
        """Check if container images in Pod match filter conditions"""
        try:
            containers = resource.get('spec', {}).get('containers', [])
            for container in containers:
                image = container.get('image', '')
                # Create temporary data for matching, using image as key
                temp_data = {'image': image}
                # Temporarily modify key to match image field
                original_key = self.data.get('key')
                self.data['key'] = 'image'
                try:
                    result = self.match(temp_data)
                    if result:
                        return True
                finally:
                    # Restore original key
                    self.data['key'] = original_key
            return False
        except Exception as e:
            log.warning(f"Error processing Pod image filter: {e}")
            return False


# ===============================
# ConfigMap Specific Filters
# ===============================

@CCIConfigMap.filter_registry.register("name")
class ConfigMapNameFilter(CCINameFilter):
    """ConfigMap Name Filter"""
    pass


@CCIConfigMap.filter_registry.register("creation-age")
class ConfigMapCreationAgeFilter(CCICreationAgeFilter):
    """ConfigMap Creation Time Filter"""
    pass


@CCIConfigMap.filter_registry.register("uid")
class ConfigMapUidFilter(CCIUidFilter):
    """ConfigMap UID Filter"""
    pass


@CCIConfigMap.filter_registry.register("namespace")
class ConfigMapNamespaceFilter(CCINamespaceFilter):
    """ConfigMap Namespace Filter"""
    pass


# ===============================
# Secret Specific Filters
# ===============================

@CCISecret.filter_registry.register("name")
class SecretNameFilter(CCINameFilter):
    """Secret Name Filter"""
    pass


@CCISecret.filter_registry.register("creation-age")
class SecretCreationAgeFilter(CCICreationAgeFilter):
    """Secret Creation Time Filter"""
    pass


@CCISecret.filter_registry.register("uid")
class SecretUidFilter(CCIUidFilter):
    """Secret UID Filter"""
    pass


@CCISecret.filter_registry.register("namespace")
class SecretNamespaceFilter(CCINamespaceFilter):
    """Secret Namespace Filter"""
    pass


# ===============================
# Namespace Specific Filters
# ===============================

@CCINamespace.filter_registry.register("name")
class NamespaceNameFilter(CCINameFilter):
    """Namespace Name Filter"""
    pass


@CCINamespace.filter_registry.register("creation-age")
class NamespaceCreationAgeFilter(CCICreationAgeFilter):
    """Namespace Creation Time Filter"""
    pass


@CCINamespace.filter_registry.register("uid")
class NamespaceUidFilter(CCIUidFilter):
    """Namespace UID Filter"""
    pass


# ===============================
# CCI Base Action Class
# ===============================


class CCIBaseAction(HuaweiCloudBaseAction):
    """CCI Service Base Action Class

    Provides common operation methods and error handling for CCI service.
    """

    def get_cci_client(self):
        """Get CCI client

        Returns:
            CCI client instance
        """
        session = local_session(self.manager.session_factory)
        return session.client("cci")

    def get_namespaces(self):
        """Get all available namespaces

        Returns:
            list: List of namespaces
        """
        namespaces = None
        try:
            client = self.get_cci_client()
            namespaces_response = client.list_namespaces()
            namespaces = namespaces_response.get('items', []) if namespaces_response else []
            return namespaces
        except Exception as e:
            log.error(f"Failed to get namespaces: {e}")
            return []


# ===============================
# Pod Actions
# ===============================

@CCIPod.action_registry.register("modify")
class ModifyPod(CCIBaseAction):
    """Modify Pod Operation

    Modify CCI Pod operation, supports updating Pod labels, annotations and other
    mutable fields.

    :example:

    .. code-block:: yaml

        policies:
          - name: modify-pod-labels
            resource: huaweicloud.cci_pod
            filters:
              - type: name
                value: "my-pod"
            actions:
              - type: modify
                patch:
                  metadata:
                    labels:
                      env: "production"
    """

    schema = type_schema(
        "modify",
        patch={"type": "object", "description": "Patch data to apply"}
    )

    def perform_action(self, resource):
        """Execute Pod modify operation

        Args:
            resource: Pod resource to modify

        Returns:
            Response result of modify operation
        """
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            namespace = resource.get('metadata', {}).get('namespace')
            name = resource.get('metadata', {}).get('name')
            patch_data = self.data.get('patch', {})

            if not namespace or not name:
                log.error(f"Pod resource missing namespace or name: {resource}")
                return None

            response = client.patch_namespaced_pod(
                name=name,
                namespace=namespace,
                body=patch_data
            )

            log.info(f"Successfully modified Pod {name} in namespace {namespace}")
            return response

        except Exception as e:
            log.error(
                f"Failed to modify Pod {resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None


@CCIPod.action_registry.register("delete")
class DeletePod(CCIBaseAction):
    """Delete Pod Operation

    Delete specified CCI Pod instance.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-old-pods
            resource: huaweicloud.cci_pod
            filters:
              - type: creation-age
                days: 30
                op: ge
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        """Execute Pod delete operation

        Args:
            resource: Pod resource to delete

        Returns:
            Response result of delete operation
        """
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            namespace = resource.get('metadata', {}).get('namespace')
            name = resource.get('metadata', {}).get('name')

            if not namespace or not name:
                log.error(f"Pod resource missing namespace or name: {resource}")
                return None

            response = client.delete_namespaced_pod(name=name, namespace=namespace)

            log.info(f"Successfully deleted Pod {name} in namespace {namespace}")
            return response

        except Exception as e:
            log.error(
                f"Failed to delete Pod {resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None


# ===============================
# ConfigMap Actions
# ===============================


@CCIConfigMap.action_registry.register("modify")
class ModifyConfigMap(CCIBaseAction):
    """Modify ConfigMap Operation

    Modify CCI ConfigMap operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: modify-configmap
            resource: huaweicloud.cci_configmap
            filters:
              - type: name
                value: "my-config"
            actions:
              - type: modify
                patch:
                  data:
                    key1: "new-value"
    """

    schema = type_schema(
        "modify",
        patch={"type": "object", "description": "Patch data to apply"}
    )

    def perform_action(self, resource):
        """Execute ConfigMap modify operation"""
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            namespace = resource.get('metadata', {}).get('namespace')
            name = resource.get('metadata', {}).get('name')
            patch_data = self.data.get('patch', {})

            if not namespace or not name:
                log.error(f"ConfigMap resource missing namespace or name: {resource}")
                return None

            response = client.patch_namespaced_configmap(
                name=name,
                namespace=namespace,
                body=patch_data
            )

            log.info(f"Successfully modified ConfigMap {name} in namespace {namespace}")
            return response

        except Exception as e:
            log.error(
                f"Failed to modify ConfigMap "
                f"{resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None


@CCIConfigMap.action_registry.register("delete")
class DeleteConfigMap(CCIBaseAction):
    """Delete ConfigMap Operation"""

    schema = type_schema("delete")

    def perform_action(self, resource):
        """Execute ConfigMap delete operation"""
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            namespace = resource.get('metadata', {}).get('namespace')
            name = resource.get('metadata', {}).get('name')

            if not namespace or not name:
                log.error(f"ConfigMap resource missing namespace or name: {resource}")
                return None

            response = client.delete_namespaced_configmap(name=name, namespace=namespace)

            log.info(f"Successfully deleted ConfigMap {name} in namespace {namespace}")
            return response

        except Exception as e:
            log.error(
                f"Failed to delete ConfigMap "
                f"{resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None


# ===============================
# Secret Actions
# ===============================

@CCISecret.action_registry.register("modify")
class ModifySecret(CCIBaseAction):
    """Modify Secret Operation"""

    schema = type_schema(
        "modify",
        patch={"type": "object", "description": "Patch data to apply"}
    )

    def perform_action(self, resource):
        """Execute Secret modify operation"""
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            namespace = resource.get('metadata', {}).get('namespace')
            name = resource.get('metadata', {}).get('name')
            patch_data = self.data.get('patch', {})

            if not namespace or not name:
                log.error(f"Secret resource missing namespace or name: {resource}")
                return None

            response = client.patch_namespaced_secret(
                name=name,
                namespace=namespace,
                body=patch_data
            )

            log.info(f"Successfully modified Secret {name} in namespace {namespace}")
            return response

        except Exception as e:
            log.error(
                f"Failed to modify Secret "
                f"{resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None


@CCISecret.action_registry.register("delete")
class DeleteSecret(CCIBaseAction):
    """Delete Secret Operation"""

    schema = type_schema("delete")

    def perform_action(self, resource):
        """Execute Secret delete operation"""
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            namespace = resource.get('metadata', {}).get('namespace')
            name = resource.get('metadata', {}).get('name')

            if not namespace or not name:
                log.error(f"Secret resource missing namespace or name: {resource}")
                return None

            response = client.delete_namespaced_secret(name=name, namespace=namespace)

            log.info(f"Successfully deleted Secret {name} in namespace {namespace}")
            return response

        except Exception as e:
            log.error(
                f"Failed to delete Secret "
                f"{resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None


# ===============================
# Namespace Actions
# ===============================

@CCINamespace.action_registry.register("delete")
class DeleteNamespace(CCIBaseAction):
    """Delete Namespace Operation

    Delete specified CCI namespace.
    Note: Deleting namespace will cascade delete all resources within it.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-empty-namespaces
            resource: huaweicloud.cci_namespace
            filters:
              - type: name
                value: "test-namespace"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        """Execute Namespace delete operation

        Args:
            resource: Namespace resource to delete

        Returns:
            Response result of delete operation
        """
        response = None  # Initialize response variable
        try:
            client = self.get_cci_client()
            name = resource.get('metadata', {}).get('name')

            if not name:
                log.error(f"Namespace resource missing name: {resource}")
                return None

            response = client.delete_namespace(name=name)

            log.info(f"Successfully deleted Namespace {name}")
            return response

        except Exception as e:
            log.error(
                f"Failed to delete Namespace "
                f"{resource.get('metadata', {}).get('name', 'unknown')}: {e}")
            if response is not None:
                log.debug(f"Response was: {response}")
            return None
