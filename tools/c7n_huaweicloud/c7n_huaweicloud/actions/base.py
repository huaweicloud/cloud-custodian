# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import abc
import logging
from abc import ABC

from c7n.actions import BaseAction
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcore.retry.backoff_strategy import BackoffStrategies

from c7n.utils import local_session

log = logging.getLogger("custodian.huaweicloud.actions.base")


class HuaweiCloudBaseAction(BaseAction, ABC):
    failed_resources = []
    result = {"succeeded_resources": [], "failed_resources": failed_resources}

    def get_tag_client(self):
        return local_session(self.manager.session_factory).client("tms")

    def handle_exception(self, resource, resources):
        self.failed_resources.append(resource)
        resources.remove(resource)

    def process_result(self, resources):
        self.result.get("succeeded_resources").extend(resources)
        return self.result

    def process(self, resources):
        for resource in resources:
            try:
                self.perform_action(resource)
            except exceptions.ClientRequestException as ex:
                res = resource.get("id", resource.get("name"))
                log.exception(
                    f"Unable to submit action against the resource - {res}"
                    f" RequestId: {ex.request_id}, Reason: {ex.error_msg}"
                )
                self.handle_exception(resource, resources)
                raise
        return self.process_result(resources)

    # All the HuaweiCloud actions that extends the HuaweiCloudBaseAction should implement
    # the below method to have the logic for invoking the respective client
    @abc.abstractmethod
    def perform_action(self, resource):
        raise NotImplementedError("Base action class does not implement this behavior")

    def _invoke_client_request(self, client, op, request):
        _invoker = getattr(client, op)
        if not op.endswith("_invoker"):
            return _invoker(request)

        def should_retry(resp, exc):
            # network connection exception
            if isinstance(exc, exceptions.ConnectionException):
                return True
            # 429 too many requests
            if isinstance(exc, exceptions.ClientRequestException) and exc.status_code == 429:
                return True

            return False

        try:
            return _invoker(request).with_retry(
                retry_condition=should_retry,
                max_retries=3,
                backoff_strategy=BackoffStrategies.EQUAL_JITTER
            ).invoke()
        except Exception as e:
            log.exception(f"Failed after max retries: {str(e)}")
            raise
