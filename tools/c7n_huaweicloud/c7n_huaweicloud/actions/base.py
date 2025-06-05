# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import abc
import http.client
import logging
import requests
import socket
from abc import ABC
from retrying import retry

from c7n.actions import BaseAction
from huaweicloudsdkcore.exceptions import exceptions

from c7n.utils import local_session

log = logging.getLogger("custodian.huaweicloud.actions.base")


RETRYABLE_EXCEPTIONS = (
    http.client.ResponseNotReady,
    http.client.IncompleteRead,
    socket.error,
    exceptions.ConnectionException,
    requests.exceptions.RetryError,
)


def is_retryable_exception(e):
    if isinstance(e, RETRYABLE_EXCEPTIONS):
        return True
    # 429 too many requests
    if isinstance(e, exceptions.ClientRequestException) and e.status_code == 429:
        return True

    return False


class HuaweiCloudBaseAction(BaseAction, ABC):
    failed_resources = []
    result = {"succeeded_resources": [], "failed_resources": failed_resources}

    def get_tag_client(self):
        return local_session(self.manager.session_factory).client("tms")

    def process_result(self, resources):
        self.result.get("succeeded_resources").extend(resources)
        return self.result

    @retry(retry_on_exception=is_retryable_exception,
           wait_exponential_multiplier=1000,
           wait_exponential_max=10000,
           stop_max_attempt_number=5)
    def process_action(self, resource):
        self.perform_action(resource)

    def process(self, resources):
        for resource in resources:
            self.process_action(resource)
        return self.process_result(resources)

    # All the HuaweiCloud actions that extends the HuaweiCloudBaseAction should implement
    # the below method to have the logic for invoking the respective client
    @abc.abstractmethod
    def perform_action(self, resource):
        raise NotImplementedError("Base action class does not implement this behavior")
