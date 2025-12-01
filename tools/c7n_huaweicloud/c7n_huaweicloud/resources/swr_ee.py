# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging
import jmespath
import json

from urllib.parse import quote_plus
from retrying import retry

from c7n.filters import Filter
from c7n.filters.core import ValueFilter, AgeFilter
from c7n.utils import local_session, type_schema
from c7n.exceptions import PolicyValidationError

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.actions.base import is_retryable_exception
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

# Centralized imports for HuaweiCloud SDK modules
from huaweicloudsdkswr.v2.model.list_instance_request import ListInstanceRequest
from huaweicloudsdkswr.v2.model.list_instance_repositories_request import \
    ListInstanceRepositoriesRequest
from huaweicloudsdkswr.v2.model.create_retention_policy_request_body import \
    CreateRetentionPolicyRequestBody
from huaweicloudsdkswr.v2.model.create_instance_retention_policy_request import \
    CreateInstanceRetentionPolicyRequest
from huaweicloudsdkswr.v2.model.update_retention_policy_request_body import \
    UpdateRetentionPolicyRequestBody
from huaweicloudsdkswr.v2.model.update_instance_retention_policy_request import \
    UpdateInstanceRetentionPolicyRequest
from huaweicloudsdkswr.v2.model.list_instance_retention_policies_request import \
    ListInstanceRetentionPoliciesRequest
from huaweicloudsdkswr.v2.model.retention_rule import RetentionRule
from huaweicloudsdkswr.v2.model.retention_selector import RetentionSelector
from huaweicloudsdkswr.v2.model.trigger_setting import TriggerSetting
from huaweicloudsdkswr.v2.model.trigger_config import TriggerConfig
from huaweicloudsdkswr.v2.model.list_instance_artifacts_request import ListInstanceArtifactsRequest
from huaweicloudsdkswr.v2.model.list_instance_all_artifacts_request import \
    ListInstanceAllArtifactsRequest
from huaweicloudsdkswr.v2.model.list_immutable_rules_request import ListImmutableRulesRequest
from huaweicloudsdkswr.v2.model.rule_selector import RuleSelector
from huaweicloudsdkswr.v2.model.create_immutable_rule_request import CreateImmutableRuleRequest
from huaweicloudsdkswr.v2.model.update_immutable_rule_request import UpdateImmutableRuleRequest
from huaweicloudsdkswr.v2.model.create_immutable_rule_body import CreateImmutableRuleBody
from huaweicloudsdkswr.v2.model.update_immutable_rule_body import UpdateImmutableRuleBody
from huaweicloudsdkswr.v2.model.list_instance_namespaces_request import \
    ListInstanceNamespacesRequest

log = logging.getLogger('custodian.huaweicloud.swr-ee')


@resources.register('swr-ee')
class SwrEe(QueryResourceManager):
    """Huawei Cloud SWR Enterprise Edition Resource Manager.

    This class manages SWR Enterprise Edition repositories on HuaweiCloud.
    It provides functionality for discovering, filtering, and managing SWR repositories.
    """

    class resource_type(TypeInfo):
        """Define SWR resource metadata and type information.

        Attributes:
            service (str): Service name for SWR
            enum_spec (tuple): API operation, result list key, and pagination info
            id (str): Resource unique identifier field name
            name (str): Resource name field name
            filter_name (str): Field name for filtering by name
            filter_type (str): Filter type for simple value comparison
            taggable (bool): Whether resource supports tagging
            tag_resource_type (None): Tag resource type
            date (str): Field name for resource creation time
        """
        service = 'swr'
        # Specify API operation, result list key, and pagination for enumerating resources
        # 'list_instance_repositories' is the API method name
        # 'body' is the field name in the response containing the instance list
        # 'offset' is the parameter name for pagination
        enum_spec = ('list_instance_repositories', 'body', 'offset')
        id = 'uid'  # Specify resource unique identifier field name
        name = 'name'  # Specify resource name field name
        filter_name = 'name'  # Field name for filtering by name
        filter_type = 'scalar'  # Filter type (scalar for simple value comparison)
        taggable = False  # Indicate that this resource doesn't support tagging directly
        tag_resource_type = None
        date = 'created_at'  # Specify field name for resource creation time

    def _fetch_resources(self, query):
        """Fetch all SWR Enterprise Edition repositories.

        This method implements a two-level query:
        1. Query all SWR EE instances
        2. For each instance, query its repositories

        :param query: Query parameters
        :return: List of all SWR EE repositories
        """
        all_repositories = []
        limit = 100

        try:
            client = self.get_client()
            if query and 'instance_id' in query:
                instances = [{"id": query['instance_id']}]
            else:
                instances = _pagination_limit_offset(
                    client,
                    "list_instance",
                    "instances",
                    ListInstanceRequest(limit=limit)
                )

            for instance_index, instance in enumerate(instances):
                repositories = _pagination_limit_offset(
                    client,
                    "list_instance_repositories",
                    "repositories",
                    ListInstanceRepositoriesRequest(
                        instance_id=instance["id"],
                        limit=limit
                    )
                )

                namespaces = _pagination_limit_offset(
                    client,
                    "list_instance_namespaces",
                    "namespaces",
                    ListInstanceNamespacesRequest(
                        instance_id=instance["id"],
                        limit=limit
                    )
                )

                namespaces_public_mapping = {}
                for namespace in namespaces:
                    is_public = namespace["metadata"]["public"].lower() == "true"
                    namespaces_public_mapping[namespace["namespace_id"]] = is_public

                for repository in repositories:
                    repository['instance_id'] = instance['id']
                    repository['uid'] = f"{instance['id']}/{repository['name']}"
                    repository['is_public'] = namespaces_public_mapping.get(
                        repository['namespace_id'], False
                    )
                    all_repositories.append(repository)

                log.debug(
                    f"The resource:[swr-ee] retrieved {len(repositories)} repositories: "
                    f"{instance['id']} ({instance_index + 1}/{len(instances)})")

        except Exception as e:
            log.error(f"The resource:[swr-ee] failed to fetch SWR repositories: {e}")
            raise e

        log.debug(
            f"The resource:[swr-ee] retrieved a total of {len(all_repositories)} SWR repositories")
        return all_repositories

    def get_resources(self, resource_ids):

        resources = []
        for resource_id in resource_ids:
            # resource_id: {instance_id}/{namespace_name}/{repo_name}
            resource_id_list = resource_id.split("/")
            if len(resource_id_list) < 3:
                continue

            temp_resources = self._fetch_resources({
                "instance_id": resource_id_list[0]
            })

            repository = "/".join(resource_id_list[2:])
            for temp_resource in temp_resources:
                if temp_resource["namespace_name"] == resource_id_list[1] and temp_resource[
                    "name"] == repository:
                    resources.append(temp_resource)

        return self.filter_resources(resources)


@SwrEe.filter_registry.register('age')
class SwrEeAgeFilter(AgeFilter):
    """SWR Repository creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-old-repos
            resource: huaweicloud.swr-ee
            filters:
              - type: age
                days: 90
                op: gt  # Creation time greater than 90 days
    """

    schema = type_schema(
        'age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )

    date_attribute = "created_at"


@resources.register('swr-ee-image')
class SwrEeImage(QueryResourceManager):
    """Huawei Cloud SWR Image Resource Manager.

    This class manages SWR image resources on HuaweiCloud. It implements a two-level query approach:
    1. First retrieving all SWR repositories
    2. Then querying images for each repository.
    """

    class resource_type(TypeInfo):
        """Define SWR Image resource metadata and type information.

        Attributes:
            service (str): Service name for SWR
            enum_spec (tuple): API operation, result list key, and pagination info
            id (str): Resource unique identifier field name
            name (str): Tag field corresponds to image version name
            filter_name (str): Field name for filtering by tag
            filter_type (str): Filter type for simple value comparison
            taggable (bool): Whether resource supports tagging
            date (str): Field name for resource creation time
        """
        service = 'swr'
        enum_spec = ('list_instance_all_artifacts', 'body', 'offset')
        id = 'uid'
        name = 'tag'
        filter_name = 'tag'
        filter_type = 'scalar'
        taggable = False
        date = 'push_time'

    # Delay time between API requests (seconds)
    api_request_delay = 0.5

    def _fetch_resources(self, query):
        """Fetch all SWR images.

        This method implements a two-level query:
        1. Query all SWR repositories
        2. For each repository, query its images

        Args:
            query (dict): Query parameters (not used in this implementation)

        Returns:
            list: List of all SWR images
        """
        all_images = []
        instances = []

        limit = 100
        client = self.get_client()

        if query and 'instance_id' in query:
            instances.append({"id": query['instance_id']})
        else:
            instances = _pagination_limit_offset(
                client,
                "list_instance",
                "instances",
                ListInstanceRequest(limit=limit)
            )

        all_images = []
        for instance in instances:
            try:
                temp_images = self._get_artifacts(instance)
                log.debug(
                    "The resource:[swr-ee-image] instance: %s, Retrieved a total of %d SWR images",
                    instance['id'],
                    len(temp_images))

                all_images.extend(temp_images)
            except Exception as artifact_err:
                log.warning("The resource:[swr-ee-image] failed to get artifacts: %s", artifact_err)
                temp_images = self._get_artifacts_by_traverse_repos(instance)
                all_images.extend(temp_images)

        log.debug("The resource:[swr-ee-image] retrieved a total of %d SWR images", len(all_images))
        return all_images

    def _get_artifacts(self, instance):
        """Get artifacts using list_instance_all_artifacts API.

        Returns:
            list: List of artifacts
        """
        limit = 100
        client = self.get_client()

        artifacts = _pagination_limit_marker(
            client,
            "list_instance_all_artifacts",
            "artifacts",
            ListInstanceAllArtifactsRequest(
                instance_id=instance['id'],
                limit=limit
            )
        )

        for artifact in artifacts:
            artifact['instance_id'] = instance['id']
            artifact['uid'] = f"{instance['id']}/{artifact['id']}"

        return artifacts

    def _get_artifacts_by_traverse_repos(self, instance):
        """Get artifacts by traversing repositories.

        Returns:
            list: List of artifacts
        """
        from c7n_huaweicloud.provider import resources as huaweicloud_resources
        swr_manager = huaweicloud_resources.get('swr-ee')(self.ctx, {})
        repositories = swr_manager.resources(query={"instance_id": instance['id']})

        limit = 100
        client = self.get_client()

        all_artifacts = []
        for repo_index, repo in enumerate(repositories):
            artifacts = _pagination_limit_offset(
                client,
                "list_instance_artifacts",
                "artifacts",
                ListInstanceArtifactsRequest(
                    instance_id=repo['instance_id'],
                    namespace_name=repo['namespace_name'],
                    repository_name=quote_plus(repo['name']),
                    limit=limit
                )
            )
            for artifact in artifacts:
                artifact['instance_id'] = repo['instance_id']
                artifact['uid'] = f"{repo['instance_id']}/{artifact['id']}"

            all_artifacts.extend(artifacts)
            log.debug(
                f"The resource:[swr-ee-image] retrieved {len(artifacts)} images for repository "
                f"{repo['instance_id']}/{repo['namespace_name']}/{repo['name']} "
                f"({repo_index + 1}/{len(repositories)})")

            # Add delay between repository queries to avoid API rate limiting
            # if repo_index < len(repositories) - 1:
            #     time.sleep(self.api_request_delay)

        return all_artifacts

    def get_resources(self, resource_ids):
        """Get resources by their IDs.

        Args:
            resource_ids (list): List of resource IDs to fetch

        Returns:
            list: List of matching resources
        """
        resources = []
        for resource_id in resource_ids:
            # resource_id: {instance_id}/{namespace_name}/{repo_name}/{digest}
            resource_id_list = resource_id.split("/")
            if len(resource_id_list) < 3:
                continue

            temp_resources = self._fetch_resources({
                "instance_id": resource_id_list[0]
            })

            art_urn = "/".join(resource_id_list[1:])

            for temp_resource in temp_resources:
                if 'repository_name' not in temp_resource:
                    continue

                art = f"{temp_resource['repository_name']}/{temp_resource['digest']}"
                if art == art_urn:
                    resources.append(temp_resource)

        return self.filter_resources(resources)


@SwrEeImage.filter_registry.register('age')
class SwrEeImageAgeFilter(AgeFilter):
    """SWR Image creation time filter.

    This filter allows filtering images based on their creation time.

    Example:
        .. code-block:: yaml

            policies:
              - name: swr-image-old
                resource: huaweicloud.swr-ee-image
                filters:
                  - type: age
                    days: 90
                    op: gt  # Creation time greater than 90 days
    """

    schema = type_schema(
        'age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )

    date_attribute = "push_time"


@resources.register('swr-ee-namespace')
class SwrEeNamespace(QueryResourceManager):
    """Huawei Cloud SWR Enterprise Edition Resource Manager.

    This class manages SWR Enterprise Edition repositories on HuaweiCloud.
    It provides functionality for discovering, filtering, and managing SWR namespaces.
    """

    class resource_type(TypeInfo):
        """Define SWR resource metadata and type information.

        Attributes:
            service (str): Service name for SWR
            enum_spec (tuple): API operation, result list key, and pagination info
            id (str): Resource unique identifier field name
            name (str): Resource name field name
            filter_name (str): Field name for filtering by name
            filter_type (str): Filter type for simple value comparison
            taggable (bool): Whether resource supports tagging
            tag_resource_type (None): Tag resource type
            date (str): Field name for resource creation time
        """
        service = 'swr'
        # Specify API operation, result list key, and pagination for enumerating resources
        # 'list_instance_repositories' is the API method name
        # 'body' is the field name in the response containing the instance list
        # 'offset' is the parameter name for pagination
        enum_spec = ('list_instance_namespaces', 'namespaces', 'offset')
        id = 'uid'  # Specify resource unique identifier field name
        name = 'name'  # Specify resource name field name
        filter_name = 'name'  # Field name for filtering by name
        filter_type = 'scalar'  # Filter type (scalar for simple value comparison)
        taggable = False  # Indicate that this resource doesn't support tagging directly
        tag_resource_type = None
        date = 'created_at'  # Specify field name for resource creation time

    def _fetch_resources(self, query):
        """Fetch all SWR Enterprise Edition repositories.

        This method implements a two-level query:
        1. Query all SWR EE instances
        2. For each instance, query its repositories

        :param query: Query parameters
        :return: List of all SWR EE repositories
        """
        all_namespaces = []
        limit = 100

        try:
            client = self.get_client()
            if query and 'instance_id' in query:
                instances = [{"id": query['instance_id']}]
            else:
                instances = _pagination_limit_offset(
                    client,
                    "list_instance",
                    "instances",
                    ListInstanceRequest(limit=limit)
                )

            for instance_index, instance in enumerate(instances):
                namespaces = _pagination_limit_offset(
                    client,
                    "list_instance_namespaces",
                    "namespaces",
                    ListInstanceNamespacesRequest(
                        instance_id=instance["id"],
                        limit=limit
                    )
                )

                for namespace in namespaces:
                    namespace['instance_id'] = instance['id']
                    namespace['uid'] = f"{instance['id']}/{namespace['name']}"
                    namespace['is_public'] = namespace["metadata"]["public"].lower() == "true"
                    all_namespaces.append(namespace)

                log.debug(
                    f"The resource:[swr-ee-namespace] retrieved {len(namespaces)} namespaces:"
                    f" {instance['id']} ({instance_index + 1}/{len(instances)})")

        except Exception as e:
            log.error(f"The resource:[swr-ee-namespace] failed to fetch SWR namespaces: {e}")
            raise e

        log.debug(
            f"The resource:[swr-ee-namespace] retrieved a total of {len(all_namespaces)} "
            f"namespaces")
        return all_namespaces

    def get_resources(self, resource_ids):

        resources = []
        for resource_id in resource_ids:
            # resource_id: {instance_id}/{namespace_name}
            resource_id_list = resource_id.split("/")
            if len(resource_id_list) < 2:
                continue

            temp_resources = self._fetch_resources({
                "instance_id": resource_id_list[0]
            })

            for temp_resource in temp_resources:
                if temp_resource["name"] == resource_id_list[1]:
                    resources.append(temp_resource)

        return self.filter_resources(resources)


@SwrEeNamespace.filter_registry.register('age')
class SwrEeNamespaceAgeFilter(AgeFilter):
    """SWR Namespace creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-old-namespaces
            resource: huaweicloud.swr-ee-namespace
            filters:
              - type: age
                days: 90
                op: gt  # Creation time greater than 90 days
    """

    schema = type_schema(
        'age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )

    date_attribute = "created_at"


@SwrEeNamespace.filter_registry.register('lifecycle-rule')
class LifecycleRule(Filter):
    """SWR repository lifecycle rule filter.

    This filter allows filtering repositories based on their lifecycle rules.
    It supports filtering by:
    - Presence/absence of lifecycle rules
    - Specific rule properties
    - Tag selectors
    - Retention periods

    The filter lazily loads lifecycle policies only for repositories that need to be
    processed, improving efficiency when dealing with many repositories.

    :example:

    .. code-block:: yaml

       policies:
        # Filter repositories without lifecycle rules
        - name: swr-no-lifecycle-rules
          resource: huaweicloud.swr-ee-namespace
          filters:
            - type: lifecycle-rule
              state: False  # Repositories without lifecycle rules

    .. code-block:: yaml

       policies:
        # Filter repositories with specific lifecycle rules (path matching specific properties)
        - name: swr-with-specific-rule
          resource: huaweicloud.swr-ee-namespace
          filters:
            - type: lifecycle-rule
              state: True  # Repositories with lifecycle rules
              match:
                - type: value
                  key: rules[0].template
                  value: latestPushedK   # latestPushedK, latestPulledN,
                                        # nDaysSinceLastPush, nDaysSinceLastPull

    .. code-block:: yaml

       policies:
        # Filter repositories with retention period greater than 30 days
        - name: swr-with-long-retention
          resource: huaweicloud.swr-ee-namespace
          filters:
            - type: lifecycle-rule
              state: True  # Repositories with lifecycle rules
              match:
                - type: value
                  key: rules[0].params.nDaysSinceLastPull
                  value_type: integer
                  op: gte
                  value: 30

    .. code-block:: yaml

       policies:
        # Filter repositories using specific tag selector
        - name: swr-with-specific-tag-selector
          resource: huaweicloud.swr-ee-namespace
          filters:
            - type: lifecycle-rule
              tag_selector:
                kind: doublestar
                pattern: v5

    .. code-block:: yaml

       policies:
        # Combined filter conditions: match both parameters and tag selector
        - name: swr-with-combined-filters
          resource: huaweicloud.swr-ee-namespace
          filters:
              tag_selector:
                kind: doublestar
                pattern: v5
              match:
                - type: value
                  key: algorithm
                  value: or
    """

    schema = type_schema(
        'lifecycle-rule',
        state={'type': 'boolean'},
        match={'type': 'array', 'items': {
            'oneOf': [
                {'$ref': '#/definitions/filters/value'},
                {'type': 'object', 'minProperties': 1, 'maxProperties': 1},
            ]}},
        tag_selector={'type': 'object'}
    )
    policy_annotation = 'c7n:lifecycle-policy'

    def process(self, resources, event=None):
        """Process resources based on lifecycle rule criteria.

        This method lazily loads lifecycle policies for each namespace
        only when needed, improving efficiency.

        Args:
            resources (list): List of resources to filter
            event (dict, optional): Event context

        Returns:
            list: Filtered resource list
        """
        client = local_session(self.manager.session_factory).client('swr')
        limit = 100

        instance_retentions = {}

        for resource in resources:
            if self.policy_annotation in resource:
                continue

            retentions = []
            if resource["instance_id"] in instance_retentions:
                retentions = instance_retentions[resource["instance_id"]]
            else:
                retentions = _pagination_limit_offset(
                    client,
                    "list_instance_retention_policies",
                    "retentions",
                    ListInstanceRetentionPoliciesRequest(
                        instance_id=resource["instance_id"],
                        limit=limit
                    )
                )
                instance_retentions[resource["instance_id"]] = retentions

            retention_list = []
            for retention in retentions:
                if resource["namespace_id"] != retention["namespace_id"]:
                    continue
                retention_list.append(retention)

            resource[self.policy_annotation] = retention_list

        state = self.data.get('state', True)
        results = []

        tag_selector = self.data.get('tag_selector')
        matchers = self.build_matchers()

        for resource in resources:
            policies = resource.get(self.policy_annotation, [])

            if not policies and not state:
                results.append(resource)
                continue

            if not policies and state:
                continue

            rule_matches = False
            for policy in policies:
                if not self.match_policy_with_matchers(policy, matchers):
                    continue

                if tag_selector and not self.match_tag_selector(policy, tag_selector):
                    continue

                rule_matches = True
                break

            if rule_matches == state:
                results.append(resource)

        return results

    def build_params_filters(self):
        """Build parameter filters.

        Returns:
            dict: Dictionary of parameter filters
        """
        params_filters = {}
        if 'params' in self.data:
            for param_key, param_config in self.data.get('params', {}).items():
                if isinstance(param_config, dict):
                    filter_data = param_config.copy()
                    if 'key' not in filter_data:
                        filter_data['key'] = param_key
                    if 'value_type' not in filter_data:
                        filter_data['value_type'] = 'integer'
                    params_filters[param_key] = ValueFilter(filter_data)
                else:
                    params_filters[param_key] = ValueFilter({
                        'type': 'value',
                        'key': param_key,
                        'value': param_config,
                        'value_type': 'integer'
                    })
        return params_filters

    def build_matchers(self):
        """Build generic matchers.

        Returns:
            list: List of value filter matchers
        """
        matchers = []
        for matcher in self.data.get('match', []):
            vf = ValueFilter(matcher)
            vf.annotate = False
            matchers.append(vf)
        return matchers

    def match_policy_with_matchers(self, policy, matchers):
        """Check if policy matches using generic matchers.

        Args:
            policy (dict): Lifecycle policy to check
            matchers (list): List of matchers to apply

        Returns:
            bool: True if policy matches all matchers, False otherwise
        """
        if not matchers:
            return True

        for matcher in matchers:
            if not matcher(policy):
                return False
        return True

    def match_tag_selector(self, policy, tag_selector):
        """Check if policy tag selector matches the filter.

        Args:
            policy (dict): Lifecycle policy to check
            tag_selector (dict): Tag selector criteria

        Returns:
            bool: True if policy matches tag selector, False otherwise
        """
        for rule in policy.get('rules', []):
            for selector in rule.get('tag_selectors', []):
                match = True
                # Check if all specified selector fields match
                for key, expected_value in tag_selector.items():
                    if key not in selector:
                        match = False
                        break
                    if expected_value is not None and selector[key] != expected_value:
                        match = False
                        break
                if match:
                    return True
        return False


@SwrEeNamespace.action_registry.register('set-lifecycle')
class SetLifecycle(HuaweiCloudBaseAction):
    """Set lifecycle rules for SWR repositories.

    :example:

    .. code-block:: yaml

        policies:
        # 配置老化规则
          - name: swr-set-lifecycle
            resource: huaweicloud.swr-ee-namespace
            filters:
              - type: lifecycle-rule
                state: False
            actions:
              - type: set-lifecycle
                rules:
                  - template: nDaysSinceLastPush
                    params:
                      nDaysSinceLastPush: 30
                    scope_selectors:
                      repository:
                        - kind: doublestar
                          pattern: '{repo1, repo2}'
                    tag_selectors:
                      - kind: doublestar
                        pattern: ^release-.*$

    .. code-block:: yaml

        policies:
        # 配置老化规则
          - name: swr-set-lifecycle
            resource: huaweicloud.swr-ee-namespace
            filters:
              - type: lifecycle-rule
                state: False
            actions:
              - type: set-lifecycle
                rules:
                  - template: nDaysSinceLastPush
                    params:
                      nDaysSinceLastPush: 30
                    scope_selectors:
                      repository:
                        - kind: doublestar
                          pattern: '**'
                    tag_selectors:
                      - kind: doublestar
                        pattern: '**'

    .. code-block:: yaml

        policies:
        # 取消老化规则
          - name: swr-set-lifecycle
            resource: huaweicloud.swr-ee-namespace
            filters:
              - type: lifecycle-rule
                state: True
            actions:
              - type: set-lifecycle
                state: False
    """

    schema = type_schema(
        'set-lifecycle',
        state={'type': 'boolean', 'default': True},
        algorithm={'type': 'string', 'enum': ['or'], 'default': 'or'},
        rules={
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['template', 'params', 'tag_selectors'],
                'properties': {
                    'template': {
                        'type': 'string',
                        'enum': [
                            'latestPushedK',
                            'latestPulledN',
                            'nDaysSinceLastPush',
                            'nDaysSinceLastPull'
                        ]
                    },
                    'params': {'type': 'object'},
                    'scope_selectors': {
                        'type': 'object',
                        'required': ['repository'],
                        'properties': {
                            'repository': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'required': ['kind', 'pattern'],
                                    'properties': {
                                        'kind': {'type': 'string', 'enum': ['doublestar']},
                                        'pattern': {'type': 'string'},
                                    }
                                }
                            }
                        }
                    },
                    'tag_selectors': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'required': ['kind', 'pattern'],
                            'properties': {
                                'kind': {'type': 'string', 'enum': ['doublestar']},
                                'pattern': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        }
    )

    permissions = ('swr:repository:createRetentionPolicy', 'swr:repository:updateRetentionPolicy')

    def validate(self):
        """Validate action configuration.

        Returns:
            self: The action instance

        Raises:
            PolicyValidationError: If configuration is invalid
        """
        if self.data.get('state') is False and 'rules' in self.data:
            raise PolicyValidationError(
                "set-lifecycle can't use statements and state: false")
        elif self.data.get('state', True) and not self.data.get('rules'):
            raise PolicyValidationError(
                "set-lifecycle requires rules with state: true")
        return self

    def process(self, resources):
        """Process resources list, create lifecycle rules for each repository.

        Args:
            resources: List of resources to process

        Returns:
            Processed resources
        """
        is_set = self.data.get('state', True)

        for resource in resources:
            self._create_or_update_retention_policy(
                resource['instance_id'],
                resource['name'],
                resource['namespace_id'],
                is_set
            )

    def perform_action(self, resource):
        pass

    def _create_or_update_retention_policy(self, instance_id, namespace_name, namespace_id,
                                           is_set):

        client = self.manager.get_client()
        policy_name = f"custodian-retention-{namespace_name}"

        try:

            # Query if the retention policy already exists
            retentions = _pagination_limit_offset(
                client,
                "list_instance_retention_policies",
                "retentions",
                ListInstanceRetentionPoliciesRequest(
                    instance_id=instance_id,
                    namespace_id=int(namespace_id),
                    limit=100
                )
            )

            # If the policy does not exist and is_set is False (cancel), return directly
            if not retentions and not is_set:
                return

            # If the namespace has already been manually configured with a policy,
            # skip and do not create a new one
            if retentions and retentions[0]['name'] != policy_name:
                log.warning(
                    f"[actions]-[set-lifecycle] instance: {instance_id}, "
                    f"namespace: {namespace_name}, "
                    f"policy has been manually created")
                return

            # Create rule objects
            rules = []
            config_rules = self.data.get('rules', [])
            if not is_set:
                config_rules = retentions[0]['rules']

            for rule_data in config_rules:
                # Create tag selectors
                tag_selectors = []
                for selector_data in rule_data.get('tag_selectors', []):
                    # Ensure kind and pattern are string type
                    kind = selector_data.get('kind')
                    pattern = selector_data.get('pattern')

                    if not kind or not pattern:
                        log.warning(
                            f"[actions]-[set-lifecycle] Skipping invalid tag_selector: "
                            f"{selector_data}"
                        )
                        continue

                    selector = RetentionSelector(
                        kind=kind,
                        decoration="matches",
                        pattern=pattern
                    )
                    tag_selectors.append(selector)

                # Ensure there are tag selectors
                if not tag_selectors:
                    log.warning(
                        "[actions]-[set-lifecycle] No valid tag_selectors,"
                        " will use default empty tag selector")
                    # Add a default tag selector to avoid API error
                    tag_selectors.append(RetentionSelector(
                        kind="doublestar",
                        decoration="matches",
                        pattern="**"
                    ))

                # Create scope selectors
                repository_selectors = []
                for scope_data in rule_data.get('scope_selectors', {}).get('repository', []):
                    # Ensure kind and pattern are string type
                    kind = scope_data.get('kind')
                    pattern = scope_data.get('pattern')

                    if not kind or not pattern:
                        log.warning(
                            f"[actions]-[set-lifecycle] Skipping invalid scope_selectors: "
                            f"{scope_data}"
                        )
                        continue

                    fin_pattern = pattern

                    # 如果取消老化策略，则repo pattern清空
                    if not is_set:
                        fin_pattern = '{}'

                    selector = RetentionSelector(
                        kind=kind,
                        decoration="repoMatches",
                        pattern=fin_pattern
                    )
                    repository_selectors.append(selector)

                # Ensure there are scope selectors
                if not repository_selectors:
                    log.warning(
                        "[actions]-[set-lifecycle] No valid repository_selectors, "
                        "will use default empty repository selector")
                    # Add a default scope selector to avoid API error
                    repository_selectors.append(RetentionSelector(
                        kind="doublestar",
                        decoration="repoMatches",
                        pattern="{}"
                    ))

                scope_selectors = {"repository": repository_selectors}

                rule = RetentionRule(
                    priority=0,
                    disabled=False,
                    action='retain',
                    template=rule_data.get('template'),
                    params=rule_data.get('params', {}),
                    tag_selectors=tag_selectors,
                    scope_selectors=scope_selectors,
                    repo_scope_mode='regular'
                )
                rules.append(rule)

            # Log final generated rules
            log.debug(f"[actions]-[set-lifecycle] Final generated rules: {rules}")

            trigger_setting = TriggerSetting(cron="0 59 23 * * ?")
            trigger_config = TriggerConfig(type="scheduled", trigger_settings=trigger_setting)

            if not retentions:
                # Create request body
                body = CreateRetentionPolicyRequestBody(
                    algorithm=self.data.get('algorithm', 'or'),
                    enabled=True,
                    rules=rules,
                    trigger=trigger_config,
                    name=policy_name
                )

                request = CreateInstanceRetentionPolicyRequest(
                    instance_id=instance_id,
                    namespace_name=namespace_name,
                    body=body
                )

                # Output complete request content for debugging
                if hasattr(request, 'to_dict'):
                    log.debug(f"[actions]-[set-lifecycle] Complete request: {request.to_dict()}")

                # Send request
                log.debug(
                    f"[actions]-[set-lifecycle] Sending create lifecycle rule request: "
                    f"instance_id={instance_id}, namespace_name={namespace_name}"
                )
                response = client.create_instance_retention_policy(request)

                # Process response
                retention_id = response.id

                log.info(
                    f"[actions]-[set-lifecycle] Successfully created lifecycle rule: "
                    f"{instance_id}/{namespace_name}, ID: {retention_id}"
                )
            else:
                # Create request body
                body = UpdateRetentionPolicyRequestBody(
                    enabled=True,
                    algorithm=self.data.get('algorithm', 'or'),
                    rules=rules,
                    trigger=trigger_config,
                    name=policy_name
                )

                request = UpdateInstanceRetentionPolicyRequest(
                    instance_id=instance_id,
                    namespace_name=namespace_name,
                    policy_id=retentions[0]['id'],
                    body=body
                )

                # Output complete request content for debugging
                if hasattr(request, 'to_dict'):
                    log.debug(f"[actions]-[set-lifecycle] Complete request: {request.to_dict()}")

                # Send request
                log.info(
                    f"[actions]-[set-lifecycle] Sending update lifecycle rule request: "
                    f"instance_id={instance_id}, namespace_name={namespace_name}"
                )
                response = client.update_instance_retention_policy(request)

                log.info(
                    f"[actions]-[set-lifecycle] Successfully updated lifecycle rule: "
                    f"{instance_id}/{namespace_name}, ID: {retentions[0]['id']}"
                )

        except Exception as e:
            # Record detailed exception information
            error_msg = str(e)
            log.error(
                f"[actions]-[set-lifecycle] Failed to create lifecycle rule: "
                f"{instance_id}/{namespace_name}: {error_msg}"
            )


@SwrEeNamespace.action_registry.register('set-immutability')
class SwrEeSetImmutability(HuaweiCloudBaseAction):
    """Set immutability rules for SWR repositories."""

    permissions = ('swr:repository:createImmutableRule', 'swr:repository:updateImmutableRule')
    schema = type_schema(
        'set-immutability',
        state={'type': 'boolean', 'default': True},
        scope_selectors={
            'type': 'object',
            'required': ['repository'],
            'properties': {
                'repository': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['kind', 'pattern'],
                        'properties': {
                            'kind': {'type': 'string', 'enum': ['doublestar']},
                            'pattern': {'type': 'string'},
                        }
                    }
                }
            }
        },
        tag_selectors={
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['kind', 'pattern'],
                'properties': {
                    'kind': {'type': 'string', 'enum': ['doublestar']},
                    'pattern': {'type': 'string'}
                }
            }
        }
    )

    def process(self, resources):
        s = True if self.data.get('state', True) else False

        for resource in resources:
            self._create_or_update_immutablerule_policy(resource['instance_id'],
                                                        resource['name'],
                                                        resource['namespace_id'], s)

    def perform_action(self, resource):
        pass

    def _create_or_update_immutablerule_policy(self, instance_id, namespace_name, namespace_id,
                                               enable_immutability):
        """Create or update immutability rule policy.

        Args:
            instance_id: Instance ID
            namespace_name: Namespace name
            namespace_id: Namespace ID
            enable_immutability: Whether to enable or disable immutability
        """
        client = self.manager.get_client()
        priority = 101

        # Query immutablerule policy by namespace
        imutable_rules = _pagination_limit_offset(
            client,
            'list_immutable_rules',
            'immutable_rules',
            ListImmutableRulesRequest(
                instance_id=instance_id,
                namespace_id=int(namespace_id),
                limit=100
            )
        )

        tag_selectors = []

        for tag_selector in self.data.get('tag_selectors', []):
            kind = tag_selector.get('kind')
            pattern = tag_selector.get('pattern')

            if not kind or not pattern:
                log.warning(
                    f"[actions]-[set-immutability] Skipping invalid tag_selector: {tag_selector}"
                )
                continue

            selector = RetentionSelector(
                kind=kind,
                decoration="matches",
                pattern=pattern
            )
            tag_selectors.append(selector)

        if not tag_selectors:
            tag_selectors.append(RuleSelector(
                kind="doublestar",
                decoration="matches",
                pattern="**"
            ))

            # Create scope selectors
        repository_selectors = []
        for scope_data in self.data.get('scope_selectors', {}).get('repository', []):
            # Ensure kind and pattern are string type
            kind = scope_data.get('kind')
            pattern = scope_data.get('pattern')

            if not kind or not pattern:
                log.warning(
                    f"[actions]-[set-immutability] Skipping invalid scope_selectors: {scope_data}"
                )
                continue

            fin_pattern = pattern

            # 如果取消不可变策略，则repo pattern清空
            if not enable_immutability:
                fin_pattern = '{}'

            selector = RetentionSelector(
                kind=kind,
                decoration="repoMatches",
                pattern=fin_pattern
            )
            repository_selectors.append(selector)

        # Ensure there are scope selectors
        if not repository_selectors:
            log.warning(
                "[actions]-[set-immutability] No valid repository_selectors, "
                "will use default empty repository selector")
            # Add a default scope selector to avoid API error
            repository_selectors.append(RetentionSelector(
                kind="doublestar",
                decoration="repoMatches",
                pattern="{}"
            ))

        scope_selectors = {"repository": repository_selectors}

        # If the immutability rule does not exist and you want to remove the immutability policy,
        # return directly
        if not imutable_rules:
            if enable_immutability:
                rule = CreateImmutableRuleBody(
                    disabled=False,
                    action='immutable',
                    template='immutable_template',
                    tag_selectors=tag_selectors,
                    scope_selectors=scope_selectors,
                    priority=priority
                )
                response = client.create_immutable_rule(
                    CreateImmutableRuleRequest(
                        instance_id=instance_id,
                        namespace_name=namespace_name,
                        body=rule
                    )
                )

                log.info(
                    f"[actions]-[set-immutability] Successfully created immutable rule: "
                    f"{instance_id}/{namespace_name}, ID: {response.id}"
                )

            return

        imutable_dict = imutable_rules[0]
        # 101 is the unique priority configured by custodian
        if imutable_dict['priority'] != priority:
            log.warning(
                f"[actions]-[set-immutability] instance_id: {instance_id}, "
                f"namespace_name: {namespace_name}, "
                f"has been manually set")
            return

        rule = UpdateImmutableRuleBody(disabled=False, action='immutable',
                                       template='immutable_template',
                                       tag_selectors=tag_selectors,
                                       scope_selectors=scope_selectors,
                                       priority=priority)
        response = client.update_immutable_rule(UpdateImmutableRuleRequest(
            instance_id=instance_id,
            namespace_name=namespace_name,
            immutable_rule_id=imutable_dict['id'],
            body=rule))
        log.info(
            f"[actions]-[set-immutability] Successfully updated immutable rule: "
            f"{instance_id}/{namespace_name}, ID: {imutable_dict['id']}"
        )


@retry(retry_on_exception=is_retryable_exception,
       wait_exponential_multiplier=1000,
       wait_exponential_max=10000,
       stop_max_attempt_number=5)
def _invoke_client_enum(client, enum_op, request):
    _invoker = getattr(client, enum_op)
    return _invoker(request)


def _safe_json_parse(response):
    if isinstance(response, (dict, list)):
        return response
    try:
        return json.loads(str(response))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")


def _pagination_limit_offset(client, enum_op, path, request):
    """Handle pagination for API requests with limit and offset.

    Args:
        client: API client instance
        enum_op: API operation name
        path: JMESPath expression to extract data
        request: Request object with limit parameter

    Returns:
        List of resources from all pages
    """
    offset = 0
    limit = 100
    resources = []
    while True:
        request.limit = request.limit or limit
        request.offset = offset
        response = _invoke_client_enum(client, enum_op, request)
        res = jmespath.search(path, _safe_json_parse(response))

        resources.extend(res)
        if len(res) == limit:
            offset += limit
        else:
            return resources
    return resources


def _pagination_limit_marker(client, enum_op, path, request):
    """Handle pagination for API requests with limit and marker.

    Args:
        client: API client instance
        enum_op: API operation name
        path: JMESPath expression to extract data
        request: Request object with limit parameter

    Returns:
        List of resources from all pages
    """
    marker = 1
    limit = 100
    resources = []
    while True:
        request.limit = request.limit or limit
        request.marker = marker
        response = _invoke_client_enum(client, enum_op, request)
        res = jmespath.search(path, _safe_json_parse(response))

        resources.extend(res)

        data_json = json.loads(str(response))
        if "next_marker" not in data_json or not data_json["next_marker"]:
            return resources
        marker = data_json["next_marker"]

    return resources
