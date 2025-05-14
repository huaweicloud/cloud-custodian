# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json
import traceback

from c7n.filters import Filter
from c7n.filters.core import ValueFilter, AgeFilter
from c7n.utils import type_schema

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
from huaweicloudsdkswr.v2.model.list_repos_details_request import ListReposDetailsRequest

log = logging.getLogger('custodian.huaweicloud.swr')


@resources.register('swr')
class Swr(QueryResourceManager):
    """Huawei Cloud SWR (Software Repository) Resource Manager.

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-repository-filter
            resource: huaweicloud.swr
            filters:
              - type: age
                days: 90
                op: gt
              - type: value
                key: is_public
                value: true
    """

    class resource_type(TypeInfo):
        service = 'swr'
        enum_spec = ('list_repos_details', 'body', None)
        id = 'name'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False
        tag_resource_type = 'swr'
        date = 'created_at'

    def augment(self, resources):
        """Augment resource information with lifecycle policies."""
        client = self.get_client()
        for resource in resources:
            resource['tag_resource_type'] = 'swr-repository'
            self.get_lifecycle_policy(client, resource)
        return resources

    def get_lifecycle_policy(self, client, resource):
        """Get lifecycle policy for a specific repository."""
        try:
            repository = resource['name']
            namespace = resource['namespace']
            request = ListRetentionsRequest()
            request.repository = repository
            request.namespace = namespace
            response = client.list_retentions(request)
            retention_list = []
            if not response or not response.body:
                resource['c7n:lifecycle-policy'] = []
                return resource
            for retention in response.body:
                if hasattr(retention, 'to_dict'):
                    retention_list.append(retention.to_dict())
                else:
                    retention_list.append(retention)
            resource['c7n:lifecycle-policy'] = retention_list
        except Exception as e:
            log.warning(
                "Exception getting lifecycle policy for %s: %s",
                resource['name'], e)
        return resource


@Swr.filter_registry.register('lifecycle-rule')
class LifecycleRule(Filter):
    """SWR repository lifecycle rule filter.

    Filter repositories with or without specific lifecycle rules based on parameters
    such as days, tag selectors (kind, pattern), etc.

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

    def build_params_filters(self):
        """Build parameter filters."""
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
        """Build generic matchers."""
        matchers = []
        for matcher in self.data.get('match', []):
            vf = ValueFilter(matcher)
            vf.annotate = False
            matchers.append(vf)
        return matchers

    def match_policy_with_matchers(self, policy, matchers):
        """Check if policy matches using generic matchers."""
        if not matchers:
            return True

        for matcher in matchers:
            if not matcher(policy):
                return False
        return True

    def match_policy_params(self, policy, params_filters):
        """Check if policy parameters match filters."""
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
        """Check if policy tag selector matches the filter."""
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

    :example:

    .. code-block:: yaml

        policies:
          - name: swr-image-filter
            resource: huaweicloud.swr-image
            filters:
              - type: value
                key: Tag
                value: latest
    """

    class resource_type(TypeInfo):
        service = 'swr'
        enum_spec = ('list_repository_tags', 'body', None)
        id = 'id'
        name = 'Tag'  # Tag field corresponds to image version name
        filter_name = 'Tag'
        filter_type = 'scalar'
        taggable = False  # SWR images don't support tagging
        date = 'created'  # Creation time field

    def augment(self, resources):
        """Enhance resource information."""
        result = []
        for resource in resources:
            try:
                # Ensure Tag field exists and provide compatibility for lowercase tag field
                if 'Tag' in resource and 'tag' not in resource:
                    resource['tag'] = resource['Tag']
                elif 'tag' in resource and 'Tag' not in resource:
                    resource['Tag'] = resource['tag']

                # Build complete ID
                if 'namespace' in resource and 'repository' in resource:
                    tag_val = resource.get('Tag') or resource.get('tag')
                    if tag_val:
                        # Use Tag value to build ID
                        resource['id'] = (f"{resource['namespace']}/"
                                          f"{resource['repository']}/{tag_val}")

                result.append(resource)
            except Exception as e:
                self.log.warning(
                    f"Failed to enhance resource information: {e}")

        return result

    def get_resources(self, resource_ids):
        """Get specific resources by ID."""
        resources = []

        if not resource_ids:
            return resources

        client = self.get_client()

        # Parse resource ID format: namespace/repository/tag
        for resource_id in resource_ids:
            try:
                namespace, repository, tag = resource_id.split('/')

                request = ListRepositoryTagsRequest(
                    namespace=namespace,
                    repository=repository,
                    tag=tag  # Directly filter the specified tag
                )

                # Send request
                response = client.list_repository_tags(request)

                # Process response
                if response.body:
                    for image in response.body:
                        image_dict = {}
                        if hasattr(image, 'to_dict'):
                            image_dict = image.to_dict()
                        else:
                            image_dict = image

                        # Add namespace and repository information
                        image_dict['namespace'] = namespace
                        image_dict['repository'] = repository

                        resources.append(image_dict)
            except Exception as e:
                self.log.warning(f"Failed to get resource {resource_id}: {e}")

        return self.augment(resources)

    def resources(self, query=None):
        """Get resource list by querying all repositories first."""
        resources = []
        client = self.get_client()

        # First get all repository list
        try:
            # Query SWR repository list
            repos_request = ListReposDetailsRequest()
            repos_response = client.list_repos_details(repos_request)

            if repos_response.body:
                for repo in repos_response.body:
                    repo_dict = repo
                    if hasattr(repo, 'to_dict'):
                        repo_dict = repo.to_dict()
                    else:
                        repo_dict = repo

                    # Get repository's namespace and name
                    namespace = repo_dict.get('namespace')
                    repository = repo_dict.get('name')

                    if namespace and repository:
                        # Get all image tags for this repository
                        repo_tags = self._get_repository_tags(
                            client, namespace, repository)
                        resources.extend(repo_tags)
        except Exception as e:
            self.log.error(
                f"Failed to query SWR repository list: {e}")

        with self.ctx.tracer.subsegment('filter'):
            resources = self.filter_resources(resources)

        return self.augment(resources)

    def _get_repository_tags(self, client, namespace, repository):
        """Get all image tags for the specified repository.

        Fetches tag information for a SWR repository.
        """
        tags = []
        try:
            # Build request parameters
            request_kwargs = {
                'namespace': namespace,
                'repository': repository
            }

            # Create and send request
            request = ListRepositoryTagsRequest(**request_kwargs)
            response = client.list_repository_tags(request)

            # Process response
            if response.body:
                for image in response.body:
                    image_dict = {}
                    if hasattr(image, 'to_dict'):
                        image_dict = image.to_dict()
                    else:
                        image_dict = image

                    # Ensure image tag has namespace and repository information
                    image_dict['namespace'] = namespace
                    image_dict['repository'] = repository

                    # Process Tag field - ensure Tag field exists
                    # HuaweiCloud API returns Tag field in uppercase
                    if 'Tag' in image_dict and not image_dict.get('tag'):
                        image_dict['tag'] = image_dict['Tag']
                    elif 'tag' in image_dict and not image_dict.get('Tag'):
                        image_dict['Tag'] = image_dict['tag']
                    elif 'Tag' not in image_dict and 'tag' not in image_dict:
                        # If no Tag field, but path field exists, try to extract from path
                        if 'path' in image_dict and ':' in image_dict['path']:
                            tag_value = image_dict['path'].split(':')[-1]
                            # Set both uppercase and lowercase tag fields
                            image_dict['Tag'] = tag_value
                            image_dict['tag'] = tag_value

                    tags.append(image_dict)

        except Exception as e:
            self.log.error(
                f"Failed to query repository "
                f"{namespace}/{repository} tags: {e}")

        return tags


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
        """Process resources list, create lifecycle rules for each repository."""
        # Validate rule configuration
        if 'rules' not in self.data or not self.data['rules']:
            self.log.error("Missing required lifecycle rule configuration")
            return []

        # Call parent's process method to process resources
        return super(SetLifecycle, self).process(resources)

    def perform_action(self, resource):
        """Implement abstract method, perform action for a single resource."""
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
