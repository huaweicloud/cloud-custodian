# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json
import traceback
import time

from c7n.filters import Filter
from c7n.filters.core import ValueFilter, AgeFilter
from c7n.utils import local_session, type_schema

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager
from c7n_huaweicloud.query import TypeInfo

# Centralized imports for HuaweiCloud SDK modules
from huaweicloudsdkswr.v2.model.list_retentions_request import ListRetentionsRequest
from huaweicloudsdkswr.v2.model.list_repository_tags_request import ListRepositoryTagsRequest
from huaweicloudsdkswr.v2.model.create_retention_request import CreateRetentionRequest
from huaweicloudsdkswr.v2.model.create_retention_request_body import CreateRetentionRequestBody
from huaweicloudsdkswr.v2.model.rule import Rule
from huaweicloudsdkswr.v2.model.tag_selector import TagSelector

log = logging.getLogger('custodian.huaweicloud.swr')


@resources.register('swr')
class Swr(QueryResourceManager):
    """Huawei Cloud SWR (Software Repository) Resource Manager.

    """

    class resource_type(TypeInfo):
        """Define SWR resource metadata and type information"""
        service = 'swr'
        # Specify API operation, result list key, and pagination for enumerating resources
        # 'list_repos_details' is the API method name
        # 'body' is the field name in the response containing the instance list
        # 'offset' is the parameter name for pagination
        enum_spec = ('list_repos_details', 'body', 'offset')
        id = 'name'  # Specify resource unique identifier field name
        name = 'name'  # Specify resource name field name
        filter_name = 'name'  # Field name for filtering by name
        filter_type = 'scalar'  # Filter type (scalar for simple value comparison)
        taggable = False  # Indicate that this resource doesn't support tagging directly
        tag_resource_type = None
        date = 'created_at'  # Specify field name for resource creation time

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


@Swr.filter_registry.register('lifecycle-rule')
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
        params={'type': 'object'},
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
        # Lazily load lifecycle policies only when needed
        for resource in resources:
            # Skip if we've already loaded the lifecycle policy for this resource
            if self.policy_annotation in resource:
                continue

            # Get lifecycle policy for this repository
            try:
                self._get_lifecycle_policy(client, resource)
            except Exception as e:
                log.warning(
                    "Exception getting lifecycle policy for %s: %s",
                    resource['name'], e)
                resource[self.policy_annotation] = []

        state = self.data.get('state', True)
        results = []

        # Extract filter conditions
        params_filters = self.build_params_filters()
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

                # Check rule parameters
                if params_filters and not self.match_policy_params(policy, params_filters):
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

    def _get_lifecycle_policy(self, client, resource):
        """Get lifecycle policy for a specific repository.

        :param client: HuaweiCloud SWR client
        :param resource: SWR repository resource dictionary
        """
        repository = resource['name']
        namespace = resource['namespace']
        request = ListRetentionsRequest()
        request.repository = repository
        request.namespace = namespace
        response = client.list_retentions(request)
        retention_list = []
        if response and response.body:
            for retention in response.body:
                if hasattr(retention, 'to_dict'):
                    retention_list.append(retention.to_dict())
                else:
                    retention_list.append(retention)
        resource[self.policy_annotation] = retention_list

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

    def match_policy_params(self, policy, params_filters):
        """Check if policy parameters match filters.

        :param policy: Lifecycle policy to check
        :param params_filters: Parameter filters to apply
        :return: True if policy matches parameter filters, False otherwise
        """
        for rule in policy.get('rules', []):
            rule_params = rule.get('params', {})

            # Check if each parameter matches
            all_params_match = True
            for param_key, filter_instance in params_filters.items():
                # If parameter doesn't exist, no match
                if param_key not in rule_params:
                    all_params_match = False
                    break

                # Create temporary object for filter check
                param_value = rule_params[param_key]
                # Ensure numeric parameters are converted to numbers
                if isinstance(param_value, str) and param_value.isdigit():
                    param_value = int(param_value)
                temp_obj = {param_key: param_value}

                if not filter_instance(temp_obj):
                    all_params_match = False
                    break

            # If all parameters of current rule match, return True
            if all_params_match:
                return True

        return False

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


@resources.register('swr-image')
class SwrImage(QueryResourceManager):
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
        enum_spec = ('list_repository_tags', 'body', 'offset')
        id = 'id'  # Specify resource unique identifier field name
        name = 'tag'  # Tag field corresponds to image version name
        filter_name = 'tag'  # Field name for filtering by tag
        filter_type = 'scalar'  # Filter type (scalar for simple value comparison)
        taggable = False  # SWR images don't support tagging
        date = 'created'  # Creation time field

    # Delay time between API requests (seconds)
    api_request_delay = 0.2

    def _fetch_resources(self, query):
        """Fetch all SWR images by first getting repositories then images.

        This method overrides parent's _fetch_resources to implement the two-level query:
        1. Query all SWR repositories
        2. For each repository, query its images

        :param query: Query parameters (not used in this implementation)
        :return: List of all SWR images
        """
        all_images = []

        # First get all SWR repositories
        try:
            if query and 'namespace' in query and 'name' in query:
                repositories = [{"namespace": query['namespace'], "name": query['name']}]
            else:
                # Use SWR resource manager to get all repositories with pagination handled
                from c7n_huaweicloud.provider import resources as huaweicloud_resources
                swr_manager = huaweicloud_resources.get('swr')(self.ctx, {})
                repositories = swr_manager.resources()

            client = self.get_client()

            # For each repository, get its images
            for repo_index, repo in enumerate(repositories):
                namespace = repo.get('namespace')
                repository = repo.get('name')

                if not namespace or not repository:
                    continue

                # Get all images for this repository
                images = self._get_repository_tags_paginated(client, namespace, repository)
                all_images.extend(images)
                self.log.debug(
                    f"Retrieved {len(images)} images for repository {namespace}/{repository} "
                    f"({repo_index + 1}/{len(repositories)})")

                # Add delay between repository queries to avoid API rate limiting
                if repo_index < len(repositories) - 1:
                    time.sleep(self.api_request_delay)

        except Exception as e:
            self.log.error(f"Failed to fetch SWR images: {e}")

        self.log.info(f"Retrieved a total of {len(all_images)} SWR images")
        return all_images

    def _get_repository_tags_paginated(self, client, namespace, repository):
        """Get all image tags for a repository with pagination.

        This uses the offset pagination mechanism that matches the SWR API.
        A delay is added between API calls to avoid triggering rate limits.

        :param client: HuaweiCloud SWR client
        :param namespace: Repository namespace
        :param repository: Repository name
        :return: List of image tags
        """
        tags = []
        offset = 0
        limit = 100  # Default page size
        page_num = 0

        try:
            while True:
                # Add page counter for logging purposes
                page_num += 1

                # Build request with pagination parameters
                request = ListRepositoryTagsRequest(
                    namespace=namespace,
                    repository=repository,
                    limit=limit,
                    offset=offset
                )

                # Execute request
                response = client.list_repository_tags(request)

                # Break if no results
                if not response.body or len(response.body) == 0:
                    break

                # Process results
                batch = []
                for image in response.body:
                    if hasattr(image, 'to_dict'):
                        image_dict = image.to_dict()
                    else:
                        image_dict = image

                    # Add repository context
                    image_dict['namespace'] = namespace
                    image_dict['repository'] = repository

                    batch.append(image_dict)

                # Add batch to results
                tags.extend(batch)

                # Check if we need to fetch more
                if len(batch) < limit:
                    break

                # Move to next page
                offset += limit

                self.log.debug(
                    f"Retrieved {len(batch)} tags for {namespace}/{repository}, "
                    f"page {page_num}, total so far: {len(tags)}")

                # Add delay between pagination requests to avoid API rate limiting
                time.sleep(self.api_request_delay)

        except Exception as e:
            self.log.error(
                f"Failed to get tags for repository {namespace}/{repository}: {e}")

        return tags

    def get_resources(self, resource_ids):

        resources = []
        for resource_id in resource_ids:
            namespace_repo = resource_id.split(':')[0]
            namespace = namespace_repo.split('/')[0]
            repository = "/".join(namespace_repo.split('/')[1:])
            temp_resources = self._fetch_resources({"namespace": namespace, "name": repository})
            resources.append(temp_resources)

        return self.filter_resources(resources)


@SwrImage.filter_registry.register('age')
class SwrImageAgeFilter(AgeFilter):
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

    date_attribute = "created"


@Swr.filter_registry.register('age')
class SwrAgeFilter(AgeFilter):
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


@Swr.action_registry.register('set-lifecycle')
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
                  - template: date_rule
                    params:
                      days: 90
                    tag_selectors:
                      - kind: label
                        pattern: v1.0
                      - kind: regexp
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
                    'template': {'type': 'string', 'enum': ['date_rule', 'tag_rule']},
                    'params': {'type': 'object'},
                    'tag_selectors': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'required': ['kind', 'pattern'],
                            'properties': {
                                'kind': {'type': 'string', 'enum': ['label', 'regexp']},
                                'pattern': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        }
    )

    permissions = ('swr:*:*:*',)  # SWR related permissions

    def process(self, resources):
        """Process resources list, create lifecycle rules for each repository.

        :param resources: List of resources to process
        :return: Processed resources
        """
        # Validate rule configuration
        if 'rules' not in self.data or not self.data['rules']:
            self.log.error("Missing required lifecycle rule configuration")
            return []

        # Call parent's process method to process resources
        return super(SetLifecycle, self).process(resources)

    def perform_action(self, resource):
        """Implement abstract method, perform action for a single resource.

        :param resource: Single resource to process
        :return: Updated resource with action results
        """
        client = self.manager.get_client()

        # Get repository information
        namespace = resource.get('namespace')
        repository = resource.get('name')

        if not namespace or not repository:
            self.log.error(
                f"Incomplete repository information: {resource.get('name', 'unknown')}")
            resource['status'] = 'error'
            resource['error'] = 'Missing namespace or repository information'
            return resource

        try:
            # Log original configuration for debugging
            self.log.debug(
                f"Original rule configuration: {self.data.get('rules')}")

            # Create rule objects
            rules = []
            for rule_data in self.data.get('rules', []):
                # Get template type and validate
                template = rule_data.get('template')
                if template not in ['date_rule', 'tag_rule']:
                    self.log.warning(
                        f"Unsupported template type: {template}, will use date_rule instead")
                    template = 'date_rule'

                # Special handling for params parameter, ensure correct data format
                param_obj = {}
                if template == 'date_rule':
                    # Get days value from rule configuration and ensure it's a string
                    days_value = rule_data.get('params', {}).get('days', '30')
                    param_obj['days'] = str(days_value)
                elif template == 'tag_rule':
                    # Get number value from rule configuration and ensure it's a string
                    num_value = rule_data.get('params', {}).get('num', '10')
                    param_obj['num'] = str(num_value)

                # Log processed parameters
                self.log.debug(f"Processed params parameter: {param_obj}")

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

                    selector = TagSelector(
                        kind=kind,
                        pattern=pattern
                    )
                    tag_selectors.append(selector)

                # Ensure there are tag selectors
                if not tag_selectors:
                    self.log.warning(
                        "No valid tag_selectors, will use default empty tag selector")
                    # Add a default tag selector to avoid API error
                    tag_selectors.append(TagSelector(
                        kind="label",
                        pattern="latest"
                    ))

                # Create rule object
                try:
                    # Create rule directly using dictionary
                    rule = Rule(
                        template=template,
                        params=param_obj,
                        tag_selectors=tag_selectors
                    )
                    rules.append(rule)
                    self.log.debug(
                        f"Successfully created rule: template={template}, params={param_obj}")
                except Exception as rule_err:
                    self.log.error(f"Failed to create rule object: {rule_err}")
                    # Try using serialized parameters
                    try:
                        rule = Rule(
                            template=template,
                            params=json.dumps(param_obj),
                            tag_selectors=tag_selectors
                        )
                        rules.append(rule)
                        self.log.debug(
                            f"Successfully created rule with serialized params: "
                            f"{json.dumps(param_obj)}"
                        )
                    except Exception as json_err:
                        self.log.error(
                            f"Failed to create rule with serialized params: {json_err}")

            # Ensure there is at least one rule
            if not rules:
                self.log.error("No valid rule configuration")
                resource['status'] = 'error'
                resource['error'] = 'No valid rules configured'
                return resource

            # Log final generated rules
            self.log.debug(f"Final generated rules: {rules}")

            # Create request body
            body = CreateRetentionRequestBody(
                algorithm=self.data.get('algorithm', 'or'),
                rules=rules
            )

            # Log request body
            if hasattr(body, 'to_dict'):
                self.log.debug(f"Request body: {body.to_dict()}")
            else:
                self.log.debug(f"Request body: {body}")

            # Create request
            request = CreateRetentionRequest(
                namespace=namespace,
                repository=repository,
                body=body
            )

            # Output complete request content for debugging
            if hasattr(request, 'to_dict'):
                self.log.debug(f"Complete request: {request.to_dict()}")

            # Send request
            self.log.info(
                f"Sending create lifecycle rule request: "
                f"namespace={namespace}, repository={repository}"
            )
            response = client.create_retention(request)

            # Process response
            retention_id = response.id

            self.log.info(
                f"Successfully created lifecycle rule: "
                f"{namespace}/{repository}, ID: {retention_id}"
            )

            # Add processing result information to resource
            resource['retention_id'] = retention_id
            resource['retention_status'] = 'created'

            return resource
        except Exception as e:
            # Record detailed exception information
            error_msg = str(e)
            error_detail = traceback.format_exc()
            self.log.error(
                f"Failed to create lifecycle rule: "
                f"{namespace}/{repository}: {error_msg}"
            )
            self.log.debug(f"Exception details: {error_detail}")

            resource['status'] = 'error'
            resource['error'] = error_msg
            return resource
