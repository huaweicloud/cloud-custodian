# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import os

import click
import yaml

POLICY_KEY = "policies"


@click.command()
@click.option(
    '-f', '--output',
    type=click.File('w'), default='merged_policy.yml',
    help="File to store the merged policy. default: ./merged_policy.yml")
@click.option(
    '-p', '--policy_files', required=True,
    help="The file path of the policy file, with multiple values separated by commas")
@click.option(
    '-d', '--policy_files_path', required=True,
    help="Path of the policy files to be merged.")
def main(output, policy_files, policy_files_path):
    policy_file_list = [x.strip() for x in policy_files.split(',') if x.strip()]
    if not policy_file_list:
        raise ValueError("Merge Policy files failed, No policy file specified.")

    result = {POLICY_KEY: []}
    for policy in policy_file_list:
        with open(os.path.join(policy_files_path, policy), 'r') as f:
            temp_policy_data = yaml.load(f, Loader=yaml.SafeLoader)
            if not temp_policy_data:
                continue

            result[POLICY_KEY].extend(temp_policy_data.get(POLICY_KEY, []))

    if not result.get(POLICY_KEY):
        raise ValueError("Merge policy files failed, The specified policy files has no valid "
                         "content.")

    print(yaml.dump(result, default_flow_style=False, Dumper=yaml.SafeDumper, sort_keys=False),
          file=output)


if __name__ == '__main__':
    main()
