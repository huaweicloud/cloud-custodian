# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import time
import logging
import sys

import click
from huaweicloudsdkcore.auth import endpoint
from huaweicloudsdkcore.auth.provider import MetadataCredentialProvider
from huaweicloudsdkorganizations.v1 import ListAccountsRequest, OrganizationsClient, \
    ListTagResourcesRequest
from huaweicloudsdkorganizations.v1.region.organizations_region import OrganizationsRegion
from c7n.utils import yaml_dump

logger = logging.getLogger('huaweicloud-accounts-generating')


def get_next_page_params(response=None):
    if not response:
        return None
    page_info = response.page_info
    if not page_info:
        return None
    next_marker = page_info.next_marker
    if not next_marker:
        return None
    return next_marker


@click.command()
@click.option(
    '-f', '--output',
    type=click.File('w'), default='accounts.yml',
    help="File to store the generated config. default: ./accounts.yml")
@click.option(
    '-a', '--agency_name',
    type=str, default='custodian_agency',
    help="trust agency name. default:custodian_agency")
@click.option(
    '-n', '--name',
    multiple=True, type=str,
    help="The account name specified for the query")
@click.option(
    '-e', '--exclude_name',
    multiple=True, type=str,
    help="The account name specified for the exclude query")
@click.option(
    '-o', '--ou_ids',
    multiple=True, type=str,
    help="The Organizational Unit id specified for the query")
@click.option(
    '-s', '--status',
    multiple=True, type=str,
    help="The account status specified for the query")
@click.option(
    '-d', '--duration_seconds',
    default=900, type=int,
    help="assume session duration second. default:900")
@click.option(
    '-r', '--regions',
    multiple=True, type=str, default=('cn-north-4',),
    help="huaweicloud region for executing policy. default:cn-north-4")
@click.option(
    '--domain_id',
    type=str, default=None,
    help="Account ID of the executing machine.")
@click.option(
    '-t', '--is_set_tags',
    type=bool, default=False,
    help="Set account tags or not.")
@click.option(
    '--debug',
    is_flag=True,
    help="Enable debug logging")
def main(output, agency_name, name, exclude_name, ou_ids, status, duration_seconds, regions,
         domain_id, is_set_tags, debug):
    """
    Generate a c7n-org huawei cloud accounts config file
    """

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    accounts = []
    marker = None
    index = 0
    ou_id_len = len(ou_ids)

    try:
        logger.info("Initializing HuaweiCloud Organizations client...")
        global_provider = (
            MetadataCredentialProvider.get_global_credential_metadata_provider()
        )
        globalCredentials = (global_provider.get_credentials()
                             .with_domain_id(domain_id)
                             .with_iam_endpoint(endpoint.get_iam_endpoint_by_id(regions[0])))

        client = (
            OrganizationsClient.new_builder()
            .with_credentials(globalCredentials)
            .with_region(OrganizationsRegion.CN_NORTH_4)
            .build()
        )
        logger.info("Successfully initialized Organizations client")
    except Exception as e:
        logger.error("Failed to initialize Organizations client: %s", str(e))
        raise

    try:
        logger.info("Starting to list accounts with parameters: "
                    "ou_ids=%s, name=%s, exclude_name=%s, status=%s",
                    ou_ids, name, exclude_name, status)

        while True:
            while True:
                parent_id = None if ou_id_len == 0 else ou_ids[index]
                logger.debug("Making ListAccounts request with parent_id=%s, marker=%s",
                             parent_id, marker)
                request = ListAccountsRequest(parent_id=parent_id, limit=500, marker=marker)

                try:
                    response = client.list_accounts(request)
                    logger.debug("Received ListAccounts response with %d accounts",
                                 len(response.accounts))
                except Exception as e:
                    logger.error("Failed to list accounts: %s", str(e))
                    raise

                marker = get_next_page_params(response)
                for account in response.accounts:
                    if name and account.name not in name:
                        continue
                    if exclude_name and account.name in exclude_name:
                        continue
                    if status and account.status not in status:
                        continue
                    accounts.append(account)

                if not marker:
                    logger.debug("No more pages for current OU")
                    break
                else:
                    logger.debug("More pages available, next marker: %s", marker)

            index += 1
            if ou_id_len - index <= 0:
                logger.debug("Processed all OUs")
                break

        logger.info("Successfully listed %d accounts", len(accounts))

        results = []
        logger.info("Processing account details (tags=%s)...", is_set_tags)

        for account in accounts:
            marker = None
            if is_set_tags:
                logger.debug("Processing tags for account %s (%s)", account.name, account.id)

                while True:
                    try:
                        request = ListTagResourcesRequest(
                            resource_type='organizations:accounts',
                            resource_id=account.id,
                            limit=200,
                            marker=marker
                        )
                        logger.debug("Making ListTagResources request for account %s", account.id)
                        response = client.list_tag_resources(request)
                        logger.debug("Received %d tags for account %s",
                                     len(response.tags), account.id)
                    except Exception as e:
                        logger.error("Failed to list tags for account %s: %s", account.id, str(e))
                        raise

                    marker = get_next_page_params(response)
                    if hasattr(account, 'tags'):
                        [account.tags.append(tag) for tag in response.tags]
                    else:
                        setattr(account, 'tags', response.tags)

                    if not marker:
                        break
                    else:
                        time.sleep(0.02)

            acc_info = {
                'name': account.name,
                'domain_id': account.id,
                'status': account.status,
                'agency_urn': f"iam::{account.id}:agency:{agency_name}",
                'duration_seconds': duration_seconds,
                'regions': regions
            }

            if hasattr(account, 'tags'):
                tags_dict = {tag.key: tag.value for tag in account.tags} if account.tags else {}
                acc_info['tags'] = tags_dict
                logger.debug("Account %s has %d tags", account.name, len(tags_dict))

            results.append(acc_info)

        logger.info("Successfully processed %d accounts", len(results))
        logger.info("Writing results to %s", output.name)
        print(yaml_dump({'domains': results}), file=output)
        logger.info("Configuration file generated successfully")

    except Exception as e:
        logger.error("Script failed with error: %s", str(e))
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical("Unhandled exception: %s", str(e))
        sys.exit(1)
