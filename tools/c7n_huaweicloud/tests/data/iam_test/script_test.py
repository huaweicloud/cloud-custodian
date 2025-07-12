# !/usr/bin/env python3
import os
import sys
import json
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("c7n_org_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    try:
        # 获取环境变量
        env_vars = {
            "account region": os.getenv("HUAWEICLOUD_REGION"),
            "account name": os.getenv("HUAWEICLOUD_DOMAIN_NAME"),
            "account id": os.getenv("HUAWEICLOUD_DOMAIN_ID"),
            "account status": os.getenv("HUAWEICLOUD_DOMAIN_STATUS"),
            "account ak": os.getenv("HUAWEICLOUD_ACCESS_KEY_ID"),
            "account sk": os.getenv("HUAWEICLOUD_SECRET_ACCESS_KEY"),
            "account token": os.getenv("HUAWEICLOUD_SECURITY_TOKEN")
        }

        # 记录环境变量
        logger.info("env vars:")
        for key, value in env_vars.items():
            logger.info(f"  {key}: {value}")

        # 获取脚本参数（排除脚本名称本身）
        script_args = sys.argv[1:]
        logger.info(f"args: {script_args}")

        # 解析命名参数（例如 --option1 value1 --option2 value2）
        named_args = {}
        current_key = None
        for arg in script_args:
            if arg.startswith('--'):
                current_key = arg[2:]
                named_args[current_key] = None
            elif current_key is not None:
                named_args[current_key] = arg
                current_key = None

        logger.info(f"format args: {json.dumps(named_args, indent=2)}")

        # 创建输出文件
        output_dir = 'script_test'
        os.makedirs(output_dir, exist_ok=True)

        # 写入环境变量信息
        env_file = os.path.join(output_dir, 'environment.json')
        with open(env_file, 'w') as f:
            json.dump(env_vars, f, indent=2)

        # 写入参数信息
        args_file = os.path.join(output_dir, 'arguments.json')
        with open(args_file, 'w') as f:
            json.dump({
                'script_args': script_args,
                'named_args': named_args
            }, f, indent=2)

        logger.info(f"output: {output_dir}")

        logger.info("finish.")
        return 0

    except Exception as e:
        logger.error(f"script failed: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
