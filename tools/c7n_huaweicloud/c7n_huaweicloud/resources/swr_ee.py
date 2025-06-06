# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import traceback
import time
import jmespath

import glob, re
from idlelib.rpc import response_queue
from urllib.parse import quote_plus

from c7n.filters import Filter
from c7n.filters.core import ValueFilter, AgeFilter
from c7n.utils import local_session, type_schema
from c7n.exceptions import PolicyValidationError

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, DescribeSource
from c7n_huaweicloud.query import TypeInfo

# Centralized imports for HuaweiCloud SDK modules
from huaweicloudsdkswr.v2.model.list_instance_request import ListInstanceRequest
from huaweicloudsdkswr.v2.model.list_instance_repositories_request import \
    ListInstanceRepositoriesRequest
from huaweicloudsdkswr.v2.model.create_retention_policy_req import CreateRetentionPolicyReq
from huaweicloudsdkswr.v2.model.create_instance_retention_policy_request import \
    CreateInstanceRetentionPolicyRequest
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

log = logging.getLogger('custodian.huaweicloud.swr-ee')
log.setLevel(logging.DEBUG)


@resources.register('swr-ee')
class SwrEe(QueryResourceManager):
    """Huawei Cloud SWR Enterprise Edition Resource Manager.

    """

    class resource_type(TypeInfo):
        """Define SWR resource metadata and type information"""
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
        """Fetch all SWR Enterprise Edition repositories by first getting instances then repositories.

        This method overrides parent's _fetch_resources to implement the two-level query:
        1. Query all SWR EE instances
        2. For each instance, query its repositories

        :param query: Query parameters
        :return: List of all SWR EE repositories
        """
        all_repositories = []
        limit = 100

        # First get all SWR repositories
        try:
            client = self.get_client()
            if query and 'instance_id' in query:
                instances = [{"id": query['instance_id']}]
            else:
                instances = _pagination_limit_offset(client, "list_instance",
                                                     "instances",
                                                     ListInstanceRequest(
                                                         limit=limit
                                                     ))

            # For each instances, get its repositories
            for instance_index, instance in enumerate(instances):
                # Get all repositories for this instance
                repositories = _pagination_limit_offset(client,
                                                        "list_instance_repositories",
                                                        "repositories",
                                                        ListInstanceRepositoriesRequest(
                                                            instance_id=instance["id"],
                                                            limit=limit))

                for repository in repositories:
                    repository['instance_id'] = instance['id']
                    repository['instance_name'] = instance['name']
                    repository['uid'] = f"{instance['id']}/{repository['name']}"
                    all_repositories.append(repository)

                self.log.debug(
                    f"Retrieved {len(repositories)} repositories for instance: {instance['id']} "
                    f"({instance_index + 1}/{len(instances)})")

        except Exception as e:
            self.log.error(f"Failed to fetch SWR repositories: {e}")

        self.log.info(f"Retrieved a total of {len(all_repositories)} SWR repositories")
        return all_repositories

    def get_resources(self, resource_ids):
        resources = (
                self.augment(self.source.get_resources(self.get_resource_query())) or []
        )
        result = []
        for resource in resources:
            resource_id = resource["namespace"] + "/" + resource["id"]
            if resource_id in resource_ids:
                result.append(resource)
        return result


@SwrEe.filter_registry.register('age')
class SwrEeAgeFilter(AgeFilter):
    """SWR Repository creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-old-repos
            resource: huaweicloud.swr
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


@SwrEe.filter_registry.register('lifecycle-rule')
class LifecycleRule(Filter):
    """SWR repository lifecycle rule filter.

    Filter repositories with or without specific lifecycle rules based on parameters
    such as days, tag selectors (kind, pattern), etc.

    This filter lazily loads lifecycle policies only for repositories that need to be
    processed, improving efficiency when dealing with many repositories.

    :example:

    .. code-block:: yaml

       policies:
        # Filter repositories without lifecycle rules
        - name: swr-no-lifecycle-rules
          resource: huaweicloud.swr
          filters:
            - type: lifecycle-rule
              state: False  # Repositories without lifecycle rules

    .. code-block:: yaml

       policies:
        # Filter repositories with specific lifecycle rules (path matching specific properties)
        - name: swr-with-specific-rule
          resource: huaweicloud.swr
          filters:
            - type: lifecycle-rule
              state: True  # Repositories with lifecycle rules
              match:
                - type: value
                  key: rules[0].template
                  value: date_rule

    .. code-block:: yaml

       policies:
        # Filter repositories with retention period greater than 30 days
        - name: swr-with-long-retention
          resource: huaweicloud.swr
          filters:
            - type: lifecycle-rule
              params:
                days:
                  type: value
                  value_type: integer
                  op: gte
                  value: 30

    .. code-block:: yaml

       policies:
        # Filter repositories using specific tag selector
        - name: swr-with-specific-tag-selector
          resource: huaweicloud.swr
          filters:
            - type: lifecycle-rule
              tag_selector:
                kind: label
                pattern: v5

    .. code-block:: yaml

       policies:
        # Combined filter conditions: match both parameters and tag selector
        - name: swr-with-combined-filters
          resource: huaweicloud.swr
          filters:
            - type: lifecycle-rule
              params:
                days:
                  type: value
                  value_type: integer
                  op: gte
                  value: 30
              tag_selector:
                kind: label
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

        This method now lazily loads lifecycle policies for each repository
        only when needed, improving efficiency.

        :param resources: List of resources to filter
        :param event: Optional event context
        :return: Filtered resource list
        """
        client = local_session(self.manager.session_factory).client('swr')

        # list retention
        retentions = _pagination_limit_offset(client,
                                              "list_instance_retention_policies",
                                              "retentions",
                                              ListInstanceRetentionPoliciesRequest(
                                                  instance_id=instance["id"],
                                                  limit=limit))

        # Lazily load lifecycle policies only when needed
        for resource in resources:
            # Skip if we've already loaded the lifecycle policy for this resource
            if self.policy_annotation in resource:
                continue

            retention_list = []
            for retention in retentions:
                if repository["namespace_name"] != retention["namespace_name"]:
                    continue

                for rule in policy.get('rules', []):
                    repository_selectors = rule.get('scope_selectors', {}).get('repository', [])
                    for repository_selector in repository_selectors:
                        regex = re.compile(
                            glob.translate(repository_selector['pattern'], recursive=True,
                                           include_hidden=True))
                        if regex.match(resource['name']):
                            retention_list.append(retention)
                            break
            resource[self.policy_annotation] = retention_list

        state = self.data.get('state', True)
        results = []

        # Extract filter conditions
        tag_selector = self.data.get('tag_selector')
        matchers = self.build_matchers()

        for resource in resources:
            policies = resource.get(self.policy_annotation, [])

            # If there are no lifecycle rules but state is False, add the resource
            if not policies and not state:
                results.append(resource)
                continue

            # If there are no lifecycle rules but state is True, skip the resource
            if not policies and state:
                continue

            # Check if each lifecycle rule matches all conditions
            rule_matches = False
            for policy in policies:
                # Check with generic matchers
                if not self.match_policy_with_matchers(policy, matchers):
                    continue

                # Check tag selector
                if tag_selector and not self.match_tag_selector(policy, tag_selector):
                    continue

                # If passed all filters, mark as a match
                rule_matches = True
                break

            # If the rule match status matches the required state, add the resource
            if rule_matches == state:
                results.append(resource)

        return results

    def build_params_filters(self):
        """Build parameter filters.

        :return: Dictionary of parameter filters
        """
        params_filters = {}
        if 'params' in self.data:
            for param_key, param_config in self.data.get('params', {}).items():
                if isinstance(param_config, dict):
                    # Copy configuration to avoid modifying original data
                    filter_data = param_config.copy()
                    # Ensure filter has a key parameter
                    if 'key' not in filter_data:
                        filter_data['key'] = param_key
                    # Set value type, default to integer
                    if 'value_type' not in filter_data:
                        filter_data['value_type'] = 'integer'
                    params_filters[param_key] = ValueFilter(filter_data)
                else:
                    # Simple value matching
                    params_filters[param_key] = ValueFilter({
                        'type': 'value',
                        'key': param_key,
                        'value': param_config,
                        'value_type': 'integer'
                    })
        return params_filters

    def build_matchers(self):
        """Build generic matchers.

        :return: List of value filter matchers
        """
        matchers = []
        for matcher in self.data.get('match', []):
            vf = ValueFilter(matcher)
            vf.annotate = False
            matchers.append(vf)
        return matchers

    def match_policy_with_matchers(self, policy, matchers):
        """Check if policy matches using generic matchers.

        :param policy: Lifecycle policy to check
        :param matchers: List of matchers to apply
        :return: True if policy matches all matchers, False otherwise
        """
        if not matchers:
            return True

        for matcher in matchers:
            if not matcher(policy):
                return False
        return True

    def match_tag_selector(self, policy, tag_selector):
        """Check if policy tag selector matches the filter.

        :param policy: Lifecycle policy to check
        :param tag_selector: Tag selector criteria
        :return: True if policy matches tag selector, False otherwise
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


@SwrEe.action_registry.register('set-lifecycle')
class SetLifecycle(HuaweiCloudBaseAction):
    """Set lifecycle rules for SWR repositories.

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-set-lifecycle
            resource: huaweicloud.swr
            filters:
              - type: value
                key: name
                value: test-repo
            actions:
              - type: set-lifecycle
                algorithm: or
                rules:
                  # Date Rule
                  - template: nDaysSinceLastPush
                    params:
                      nDaysSinceLastPush: 30
                    tag_selectors:
                      - kind: doublestar
                        pattern: ^release-.*$
    """

    schema = type_schema(
        'set-lifecycle',
        algorithm={'type': 'string', 'enum': ['or'], 'default': 'or'},
        rules={
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['template', 'params', 'tag_selectors'],
                'properties': {
                    'template': {'type': 'string',
                                 'enum': ['latestPushedK', 'latestPulledN', 'nDaysSinceLastPush',
                                          'nDaysSinceLastPull']},
                    'params': {'type': 'object'},
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

    permissions = ('swr:*:*:*',)  # SWR related permissions

    def validate(self):
        if self.data.get('state') is False and 'rules' in self.data:
            raise PolicyValidationError(
                "set-lifecycle can't use statements and state: false")
        elif self.data.get('state', True) and not self.data.get('rules'):
            raise PolicyValidationError(
                "set-lifecycle requires rules with state: true")
        return self

    def process(self, resources):
        """Process resources list, create lifecycle rules for each repository.

        :param resources: List of resources to process
        :return: Processed resources
        """

        namespace_repos = {}
        # 根据instance, namespace进行分类
        for resource in resources:
            key = resource["instance_id"] + "-" + resource["namespace_name"]
            namespace_repo = []
            if key in namespace_repos:
                namespace_repo = namespace_repos[key]

            namespace_repo.append(resource["name"])
            namespace_repos[key] = namespace_repo

        repo_names = []
        for key, value in namespace_repos.items():
            key_list = key.split("-")
            repo_pattern = ",".join(value)
            repo_pattern = "{" + repo_pattern + "}"

            self._create_or_update_retention_policy(key_list[0], key_list[1], repo_pattern)

    def _create_or_update_retention_policy(self, instance_id, namespace_name, repo_pattern):
        """Implement abstract method, perform action for a single resource.

        :param resource: Single resource to process
        :return: Updated resource with action results
        """
        client = self.manager.get_client()

        try:
            # Log original configuration for debugging
            self.log.debug(
                f"Original rule configuration: {self.data.get('rules')}")

            # Create rule objects
            rules = []
            for rule_data in self.data.get('rules', []):

                # Create tag selectors
                tag_selectors = []
                for selector_data in rule_data.get('tag_selectors', []):
                    # Ensure kind and pattern are string type
                    kind = selector_data.get('kind')
                    pattern = selector_data.get('pattern')

                    if not kind or not pattern:
                        self.log.warning(
                            f"Skipping invalid tag_selector: {selector_data}"
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
                    self.log.warning(
                        "No valid tag_selectors, will use default empty tag selector")
                    # Add a default tag selector to avoid API error
                    tag_selectors.append(RetentionSelector(
                        kind="doublestar",
                        decoration="matches",
                        pattern="**"
                    ))

                repository_rule = RetentionSelector(
                    kind="doublestar",
                    decoration="repoMatches",
                    pattern=repo_pattern
                )
                scope_selectors = {"repository": [repository_rule]}

                rule = RetentionRule(priority=0, disabled=False, action='retain',
                                     template=rule_data.get('template'),
                                     params=rule_data.get('params', {}),
                                     tag_selectors=tag_selectors,
                                     scope_selectors=scope_selectors)
                rules.append(rule)

            # Ensure there is at least one rule
            if not rules:
                self.log.error("No valid rule configuration")
                resource['status'] = 'error'
                resource['error'] = 'No valid rules configured'
                return resource

            # Log final generated rules
            self.log.debug(f"Final generated rules: {rules}")

            trigger_setting = TriggerSetting(cron="* * * * * ?")
            trigger_config = TriggerConfig(type="scheduled", trigger_setting=trigger_setting)
            # Create request body
            body = CreateRetentionPolicyReq(
                algorithm=self.data.get('algorithm', 'or'),
                rules=rules,
                trigger=trigger_config,
                enabled=True,
                name="cloud-custodian-" + namespace_name
            )

            request = CreateInstanceRetentionPolicyRequest(instance_id=instance_id,
                                                           namespace_name=namespace_name,
                                                           body=body)

            # Output complete request content for debugging
            if hasattr(request, 'to_dict'):
                self.log.debug(f"Complete request: {request.to_dict()}")

            # Send request
            self.log.info(
                f"Sending create lifecycle rule request: "
                f"instance_id={instance_id}, namespace_name={namespace_name}"
            )
            response = client.create_instance_retention_policy(request)

            # Process response
            retention_id = response.id

            self.log.info(
                f"Successfully created lifecycle rule: "
                f"{instance_id}/{namespace_name}, ID: {retention_id}"
            )

            return resource
        except Exception as e:
            # Record detailed exception information
            error_msg = str(e)
            error_detail = traceback.format_exc()
            self.log.error(
                f"Failed to create lifecycle rule: "
                f"{instance_id}/{namespace_name}: {error_msg}"
            )
            self.log.debug(f"Exception details: {error_detail}")

            resource['status'] = 'error'
            resource['error'] = error_msg
            return resource


@SwrEe.action_registry.register('set-immutability')
class SwrEeSetImmutability(HuaweiCloudBaseAction):
    permissions = ('swr:PutImageTagMutability',)
    schema = type_schema(
        'set-immutability',
        state={'type': 'boolean', 'default': True})

    def process(self, resources):
        client = local_session(self.manager.session_factory).client('ecr')
        s = 'IMMUTABLE' if self.data.get('state', True) else 'MUTABLE'
        for r in resources:
            try:
                client.put_image_tag_mutability(
                    registryId=r['registryId'],
                    repositoryName=r['repositoryName'],
                    imageTagMutability=s)
            except client.exceptions.RepositoryNotFoundException:
                continue

            namespace_repos = {}
            # 根据instance, namespace进行分类
            for resource in resources:
                key = resource["instance_id"] + "-" + resource["namespace_name"] + "-" + resource[
                    "namespace_id"]
                namespace_repo = []
                if key in namespace_repos:
                    namespace_repo = namespace_repos[key]

                namespace_repo.append(resource["name"])
                namespace_repos[key] = namespace_repo

            repo_names = []
            for key, value in namespace_repos.items():
                key_list = key.split("-")

                self._create_or_update_immutablerule_policy(key_list[0], key_list[1], key_list[2],
                                                            value)

    def parse_pattern(self, input_str):
        # 去除首尾空格和花括号
        content = input_str.strip().strip('{}')
        # 分割并清理每个元素
        items = [item.strip() for item in content.split(',')]
        return items

    def bulid_pattern(self, repos):
        repo_pattern = ",".join(repos)
        repo_pattern = "{" + repo_pattern + "}"
        return repo_pattern

    def merge_repos(self, old_repos, new_repos):
        merged_set = set(array1) | set(array2)
        result = list(merged_set)

    def sub_repos(self, old_repos, new_repos):
        return list(set(old_repos) - set(new_repos))

    def _create_or_update_immutablerule_policy(self, instance_id, namespace_name, namespace_id,
                                               repos, enable_immutability):
        """Implement abstract method, perform action for a single resource.

        :param resource: Single resource to process
        :return: Updated resource with action results
        """
        client = self.manager.get_client()

        extra = f"custodian-immutability-{namespace_name}"

        # 根据namespace查询immutablerule policy
        imutable_rules = _pagination_limit_offset(client, 'list_imutable_rules', 'imutable_rule',
                                                  ListImmutableRulesRequest(
                                                      instance_id=instance_id,
                                                      namespace_id=namespace_id,
                                                      limit=100))
        tag_selectors = []
        tag_selectors.append(RuleSelector(
            kind="doublestar",
            decoration="matches",
            pattern="**"
        ))

        # 不可变规则不存在，以及去掉不可变策略,则直接返回
        if len(imutable_rules) <= 0:
            if enable_immutability:
                # 创建immutablerule policy

                repo_pattern = self.bulid_pattern(repos)

                repository_rule = RuleSelector(
                    kind="doublestar",
                    decoration="repoMatches",
                    pattern=repo_pattern,
                    extra=extra
                )
                scope_selectors = {"repository": [repository_rule]}

                rule = CreateImmutableRuleBody(namespace_id=namespace_id,
                                               namespace_name=namespace_name,
                                               disabled=False, action='immutable',
                                               template='immutable_template',
                                               tag_selectors=tag_selectors,
                                               scope_selectors=scope_selectors)
                response = client.create_immutable_rule(CreateImmutableRuleRequest(body=rule))

            return

        imutableDict = imutable_rules[0].to_dict()
        if len(imutableDict['scope_selectors']['repository']) > 0 and \
                imutableDict['scope_selectors']['repository'][0]['extra'] != extra:
            self.log.warning(
                f"instance_id: {instance_id}, namespace_name: {namespace_name}, has been manually set")
            return

        repo_pattern = self.bulid_pattern(repos)
        if len(imutableDict['scope_selectors']['repository']) > 0:
            old_repo_pattern = imutableDict['scope_selectors']['repository'][0]['pattern']
            old_repos = self.parse_pattern(old_repo_pattern)
            fin_repos = []
            if enable_immutability:
                fin_repos = self.merge_repos(old_repos, new_repos)
            else:
                fin_repos = self.sub_repos(old_repos, new_repos)

            repo_pattern = self.bulid_pattern(fin_repos)

        repository_rule = RuleSelector(
            kind="doublestar",
            decoration="repoMatches",
            pattern=repo_pattern,
            extra=extra
        )
        scope_selectors = {"repository": [repository_rule]}

        rule = UpdateImmutableRuleBody(namespace_id=namespace_id,
                                       namespace_name=namespace_name,
                                       disabled=False, action='immutable',
                                       template='immutable_template',
                                       tag_selectors=tag_selectors,
                                       scope_selectors=scope_selectors)
        response = client.update_immutable_rule(CreateImmutableRuleRequest(body=rule))


@resources.register('swr-ee-image')
class SwrEeImage(QueryResourceManager):
    """Huawei Cloud SWR Image Resource Manager.

    This class is responsible for discovering, filtering, and managing SWR image resources
    on HuaweiCloud. It implements a two-level query approach, first retrieving all SWR repositories,
    then querying images for each repository.

    """

    class resource_type(TypeInfo):
        """Define SWR Image resource metadata and type information"""
        service = 'swr'  # Specify corresponding HuaweiCloud service name
        # Specify API operation, result list key, and pagination for enumerating resources
        # 'list_repository_tags' is the API method name
        # 'body' is the field name in the response containing the tag list
        # 'offset' is the parameter name for pagination
        enum_spec = ('list_instance_all_artifacts', 'body', 'offset')
        id = 'uid'  # Specify resource unique identifier field name
        name = 'tag'  # Tag field corresponds to image version name
        filter_name = 'tag'  # Field name for filtering by tag
        filter_type = 'scalar'  # Filter type (scalar for simple value comparison)
        taggable = False  # SWR images don't support tagging
        date = 'push_time'  # Creation time field

    # Delay time between API requests (seconds)
    api_request_delay = 0.5

    def _fetch_resources(self, query):
        """Fetch all SWR images by first getting repositories then images.

        This method overrides parent's _fetch_resources to implement the two-level query:
        1. Query all SWR repositories
        2. For each repository, query its images

        :param query: Query parameters (not used in this implementation)
        :return: List of all SWR images
        """
        all_images = []

        try:
            all_images = self._get_artifacts()
        except Exception as artifact_err:
            self.log.error(f"Failed to get artifacts: {artifact_err}")
            all_images = self._get_artifacts_by_traverse_repos()

        self.log.info(f"Retrieved a total of {len(all_images)} SWR images")
        return all_images

    def _get_artifacts(self):
        limit = 100
        client = self.get_client()

        instances = _pagination_limit_offset(client, "list_instance",
                                             "instances",
                                             ListInstanceRequest(
                                                 limit=limit
                                             ))

        all_artifacts = []
        for instance in instances:
            artifacts = _pagination_limit_offset(client, "list_instance_all_artifacts",
                                                 "artifacts",
                                                 ListInstanceAllArtifactsRequest(
                                                     instance_id=instance['id'],
                                                     limit=limit
                                                 ))
            for artifact in artifacts:
                artifact['instance_id'] = instance['id']
                artifact['instance_name'] = instance['name']
                artifact['uid'] = f"{instance['id']}/{artifact['id']}"
            all_artifacts.extend(artifacts)

        return all_artifacts

    def _get_artifacts_by_traverse_repos(self):

        # Use SWR resource manager to get all repositories with pagination handled
        from c7n_huaweicloud.provider import resources as huaweicloud_resources
        swr_manager = huaweicloud_resources.get('swr-ee')(self.ctx, {})
        repositories = swr_manager.resources()

        limit = 100
        client = self.get_client()

        all_artifacts = []
        # For each repository, get its images
        for repo_index, repo in enumerate(repositories):

            # Get all images for this repository
            artifacts = _pagination_limit_offset(client, "list_instance_artifacts",
                                                 "artifacts",
                                                 ListInstanceArtifactsRequest(
                                                     instance_id=repo['instance_id'],
                                                     namespace_name=repo['namespace_name'],
                                                     repository_name=quote_plus(repo['name']),
                                                     limit=limit
                                                 ))
            for artifact in artifacts:
                artifact['instance_id'] = repo['instance_id']
                artifact['instance_name'] = repo['instance_name']
                artifact['uid'] = f"{repo['instance_id']}/{artifact['id']}"

            all_artifacts.extend(artifacts)
            self.log.debug(
                f"Retrieved {len(artifacts)} images for repository {repo['instance_id']}/{repo['namespace_name']}/{repo['name']} "
                f"({repo_index + 1}/{len(repositories)})")

            # Add delay between repository queries to avoid API rate limiting
            if repo_index < len(repositories) - 1:
                time.sleep(self.api_request_delay)

        return all_artifacts

    def get_resources(self, resource_ids):

        resources = []
        for resource_id in resource_ids:
            namespace_repo = resource_id.split(':')[0]
            namespace = namespace_repo.split('/')[0]
            repository = "/".join(namespace_repo.split('/')[1:])
            temp_resources = self._fetch_resources({"namespace": namespace, "name": repository})
            resources.append(temp_resources)

        return self.filter_resources(resources)


@SwrEeImage.filter_registry.register('age')
class SwrEeImageAgeFilter(AgeFilter):
    """SWR Image creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-image-old
            resource: huaweicloud.swr-image
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


def _pagination_limit_offset(client, enum_op, path, request):
    offset = 0
    limit = 100
    resources = []
    while 1:
        request.limit = request.limit or limit
        request.offset = offset
        response = getattr(client, enum_op)(request)
        res = jmespath.search(
            path,
            eval(
                str(response)
                .replace("null", "None")
                .replace("false", "False")
                .replace("true", "True")
            ),
        )

        resources = resources + res
        if len(res) == limit:
            offset += limit
        else:
            return resources
    return resources
