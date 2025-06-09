# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import os
import operator
import copy
import requests
from urllib import parse as urlparse

from c7n.registry import PluginRegistry
from c7n.provider import Provider, clouds

from c7n_huaweicloud.client import Session
from c7n_huaweicloud.resources.resource_map import ResourceMap
from c7n_huaweicloud.utils.signer import Signer, HttpRequest
from huaweicloudsdkcore.auth.credentials import Credentials
from huaweicloudsdkcore.utils import time_utils

log = logging.getLogger("custodian.huaweicloud.provider")

credential = Credentials()


def get_credentials():
    if (not credential.security_token or
            credential._expired_at - time_utils.get_timestamp_utc() < 60):
        credential.update_security_token_from_metadata()
    return credential.ak, credential.sk, credential.security_token


class HuaweiSessionFactory:

    def __init__(self, options):
        if not isinstance(options, dict):
            options = vars(options)
        self.options = options
        self._validate_credentials_config()

    def _validate_credentials_config(self):
        self.use_assume = hasattr(self.options, 'agency_urn') and self.options.agency_urn
        self.ak = getattr(self.options, 'access_key_id', os.getenv('HUAWEI_ACCESS_KEY_ID'))
        self.sk = getattr(self.options, 'secret_access_key', os.getenv('HUAWEI_SECRET_ACCESS_KEY'))
        self.token = getattr(self.options, 'security_token', os.getenv('HUAWEI_SECURITY_TOKEN'))

    def __call__(self):
        (self.options['access_key_id'],
         self.options['secret_access_key'],
         self.options['security_token']) = self.get_credential()

        return Session(self.options)

    def get_credential(self):
        if self.use_assume:
            log.info("get v5 assume credential.")
            return self._get_assumed_credentials()
        return self.ak, self.sk, self.token

    def _get_assumed_credentials(self):
        try:
            ecs_ak, ecs_sk, ecs_token = get_credentials()
            sig = Signer()
            sig.Key = ecs_ak
            sig.Secret = ecs_sk
            url = f"https://sts.{self.options.region}.myhuaweicloud.com/v5/agencies/assume"
            request = HttpRequest("POST", url)
            request.headers = {"Content-Type": "application/json", "X-Security-Token": ecs_token}
            request.body = json.dumps({
                "duration_seconds": getattr(self.options, 'duration_seconds', 3600),
                "agency_urn": self.options.agency_urn,
                "agency_session_name": "custodian_agency_session",
            })
            sig.Sign(request)
            resp = requests.post(url, headers=request.headers, data=request.body)
            resp.raise_for_status()
            json_resp = resp.json()
            if not json_resp.get("credentials"):
                raise ValueError("No credentials in assume role response")
            creds = json_resp["credentials"]
            return creds["access_key_id"], creds["secret_access_key"], creds["security_token"]

        except requests.exceptions.HTTPError as e:
            log.error(f"Assume role request failed with status:{e.response.status_code}, "
                      f"exception: {str(e)}")
            raise ValueError(f"Assume role failed: {str(e)}")
        except (KeyError, ValueError) as e:
            log.error(f"Invalid assume role response: {str(e)}")
            raise ValueError("Invalid assume role response format")
        except Exception as e:
            log.error(f"Unexpected error during assume role: {str(e)}")
            raise


@clouds.register("huaweicloud")
class HuaweiCloud(Provider):
    display_name = "Huawei Cloud"
    resource_prefix = "huaweicloud"
    resources = PluginRegistry("%s.resources" % resource_prefix)
    resource_map = ResourceMap

    def initialize(self, options):
        return options

    def initialize_policies(self, policy_collection, options):
        from c7n.policy import Policy, PolicyCollection
        policies = []
        regions = options.regions if len(options.regions) > 0 \
            else [os.environ.get("HUAWEI_DEFAULT_REGION", "sa-brazil-1")]
        for p in policy_collection:
            for region in regions:
                options_copy = copy.copy(options)
                options_copy.region = str(region)

                if len(options.regions) > 1 or 'all' in options.regions and getattr(
                        options, 'output_dir', None):
                    options_copy.output_dir = join_output(options.output_dir, region)
                policies.append(
                    Policy(p.data, options_copy,
                           session_factory=policy_collection.session_factory()))

        return PolicyCollection(
            sorted(policies, key=operator.attrgetter('options.region')),
            options)

    def get_session_factory(self, options):
        return HuaweiSessionFactory(options)


def join_output(output_dir, suffix):
    if '{region}' in output_dir:
        return output_dir.rstrip('/')
    if output_dir.endswith('://'):
        return output_dir + suffix
    output_url_parts = urlparse.urlparse(output_dir)
    # for output urls, the end of the url may be a
    # query string. make sure we add a suffix to
    # the path component.
    output_url_parts = output_url_parts._replace(
        path=output_url_parts.path.rstrip('/') + '/%s' % suffix
    )
    return urlparse.urlunparse(output_url_parts)


resources = HuaweiCloud.resources
