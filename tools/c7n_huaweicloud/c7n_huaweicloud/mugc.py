# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import itertools
import os
import re
import logging
import sys

from c7n.config import Config
from c7n.policy import load as policy_load, PolicyCollection

from c7n_huaweicloud import mu
from provider import HuaweiCloud

log = logging.getLogger('mugc')


def load_policies(options, policy_options):
    policies = PolicyCollection([], policy_options)
    for f in options.config_files:
        policies += policy_load(policy_options, f).filter(options.policy_filters)
    return policies


def region_gc(options, policy_options, region, policies):
    log.info("Region:%s Starting garbage collection", region)
    options.region = region
    session_factory = HuaweiCloud().get_session_factory(policy_options)
    manager = mu.FunctionGraphManager(session_factory)
    funcs = list(manager.list_functions(options.prefix))

    remove = []
    pattern = re.compile(options.policy_regex)
    for f in funcs:
        if not f['func_name'].startswith(options.prefix):
            continue
        policy_name_in_function = f['func_name'].replace(options.prefix, "")
        if not pattern.match(policy_name_in_function):
            continue
        match = False
        for p in policies:
            if f['func_name'].endswith(p.name):
                if 'region' not in p.data or p.data['region'] == region:
                    match = True
        if options.present:
            if match:
                remove.append(f)
        elif not match:
            remove.append(f)

    if len(remove) == 0:
        log.info('No function need to delete.')

    for function in remove:
        f = mu.FunctionGraph(
            {
                'func_urn': function['func_urn'],
                'func_name': function['func_name'],
                'package': function['package'],
                'runtime': function['runtime'],
                'timeout': function['timeout'],
                'handler': function['handler'],
                'memory_size': function['memory_size'],
                'xrole': function.get('xrole', ""),
            }, None
        )

        log.info("Region:%s Removing %s", region, function['func_name'])
        if options.dryrun:
            log.info("Dryrun skipping removal")
            continue
        manager.remove(f)
        log.info("Region:%s Removed %s", region, function['func_name'])


def resources_gc_prefix(options, policy_options, policy_collection):
    """Garbage collect old custodian policies based on prefix.

    We attempt to introspect to find the event sources for a policy
    but without the old configuration this is implicit.
    """

    # Classify policies by region
    policy_regions = {}
    for p in policy_collection:
        policy_regions.setdefault(p.options.region, []).append(p)

    regions = get_gc_regions(options.regions, policy_options)
    for r in regions:
        region_gc(options, policy_options, r, policy_regions.get(r, []))


def get_gc_regions(regions, policy_options):
    if 'all' in regions:
        # TODO: 当前只支持圣保罗一局点，后续实现all模式
        pass
    return regions


def setup_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs='*', help="Policy configuration file(s)")
    parser.add_argument(
        '-c', '--config', dest="config_files", nargs="*", action='append',
        help="Policy configuration files(s)", default=[])
    parser.add_argument(
        "--present", action="store_true", default=False,
        help='Target policies present in config files for removal instead of skipping them.')
    parser.add_argument(
        '-r', '--region', action='append', dest='regions', metavar='REGION',
        help="HuaweiCloud Region to target. Can be used multiple times, also supports `all`")
    parser.add_argument('--dryrun', action="store_true", default=False)
    parser.add_argument(
        "--profile", default=os.environ.get('HuaweiCloud_PROFILE'),
        help="HuaweiCloud Account Config File Profile to utilize")
    parser.add_argument(
        "--prefix", default="custodian-",
        help="The FunctionGraph name prefix to use for clean-up")
    parser.add_argument(
        "--policy-regex", default="",
        help="The policy must match the regex")
    parser.add_argument("-p", "--policies", default=[], dest='policy_filters',
                        action='append', help="Only use named/matched policies")
    parser.add_argument(
        "--assume", default=None, dest="assume_role",
        help="Role to assume")
    parser.add_argument(
        "-v", dest="verbose", action="store_true", default=False,
        help='toggle verbose logging')
    return parser


def main():
    parser = setup_parser()
    options = parser.parse_args()

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s: %(name)s:%(levelname)s %(message)s")
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('c7n.cache').setLevel(logging.WARNING)

    if not options.regions:
        options.regions = [os.environ.get('HUAWEICLOUD_REGION', 'sa-brazil-1')]

    files = []
    files.extend(itertools.chain(*options.config_files))
    files.extend(options.configs)
    options.config_files = files

    if not files:
        parser.print_help()
        sys.exit(1)

    policy_options = Config.empty(
        regions=options.regions,
        access_key_id=os.environ.get('HUAWEICLOUD_ACCESS_KEY_ID', None),
        secret_access_key=os.environ.get('HUAWEICLOUD_SECRET_ACCESS_KEY', None),
        security_token=os.environ.get('HUAWEICLOUD_SECURITY_TOKEN', None),
        region=os.environ.get('HUAWEICLOUD_REGION', None),
        domain_id=os.environ.get('HUAWEICLOUD_DOMAIN_ID', None),
        name=os.environ.get('HUAWEICLOUD_DOMAIN_NAME', None),
        status=os.environ.get('HUAWEICLOUD_DOMAIN_STATUS', None),
    )

    # use cloud provider to initialize policies to get region expansion
    policies = HuaweiCloud().initialize_policies(
        PolicyCollection([
            p for p in load_policies(
                options, policy_options)
            if p.provider_name == 'huaweicloud'],
            policy_options),
        policy_options)

    resources_gc_prefix(options, policy_options, policies)


if __name__ == '__main__':
    main()
