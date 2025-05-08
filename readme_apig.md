# 华为云 APIG 服务适配 Cloud Custodian

本文档描述了基于 Cloud Custodian 适配华为云 APIG (API 网关) 服务的实现方案。华为云 APIG 服务功能对应 AWS 的 API Gateway 服务，我们需要实现类似的资源类型、过滤器和操作。

## 资源类型

我们需要实现以下三种资源类型:

1. `rest-api` - API 网关中的 API
2. `rest-stage` - API 网关中的环境
3. `apigw-domain-name` - API 网关中的域名

## 通用 Filters

以下是所有资源类型都应支持的通用过滤器:

| Filter 名称 | 描述 | 可复用性 | 涉及 SDK |
|------------|------|---------|---------|
| `value` | 值过滤器，基本过滤功能 | 可复用现有实现 | - |
| `event` | 事件过滤器 | 可复用现有实现 | - |
| `marked-for-op` | 标记为操作的资源过滤 | 可复用华为云已有实现 | - |
| `list-item` | 列表项过滤器 | 可复用华为云已有实现 | - |
| `reduce` | 聚合过滤器 | 可复用现有实现 | - |
| `tag-count` | 标签数量过滤器 | 可复用华为云已有实现 | - |
| `finding` | 查找过滤器 | 需要新开发 | - |
| `ops-item` | 运维项过滤器 | 需要新开发 | - |
| `config-compliance` | 配置合规性过滤器 | 需要新开发 | - |

## 通用 Actions

以下是所有资源类型都应支持的通用操作:

| Action 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| `tag` | 添加标签 | 可复用华为云已有实现 | huaweicloudsdkapig.v2.ApiGatewayClient.batch_create_or_delete_instance_tags |
| `remove-tag` | 移除标签 | 可复用华为云已有实现 | huaweicloudsdkapig.v2.ApiGatewayClient.batch_create_or_delete_instance_tags |
| `mark-for-op` | 标记为将来操作 | 可复用华为云已有实现 | 与标签相关 |
| `auto-tag-user` | 自动标记用户 | 可复用华为云已有实现 | 与标签相关 |
| `rename-tag` | 重命名标签 | 可复用华为云已有实现 | 与标签相关 |
| `copy-related-tag` | 复制相关标签 | 需要新开发 | 与标签相关 |
| `notify` | 通知 | 可复用华为云已有实现 | - |
| `webhook` | 网络钩子 | 可复用现有实现 | - |
| `put-metric` | 放置指标 | 需要新开发 | - |
| `invoke-lambda` | 调用函数 | 可替换为华为云 FunctionGraph 服务 | 需要华为云 FunctionGraph SDK |
| `invoke-sfn` | 调用状态机 | 需要新开发或映射到类似服务 | - |
| `post-finding` | 发布发现结果 | 需要新开发 | - |
| `post-item` | 发布项目 | 需要新开发 | - |

## 资源特定功能

### 1. rest-api

#### Filters

| Filter 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| `rest-method` | REST 方法过滤器 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.list_apis_v2 |
| `rest-integration` | REST 集成过滤器 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.list_apis_v2 |
| `rest-resource` | REST 资源过滤器 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.list_apis_v2 |

#### Actions

| Action 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| `update-method` | 更新方法 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient |
| `delete-integration` | 删除集成 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient |
| `delete` | 删除 API | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient |

### 2. rest-stage

#### Filters

| Filter 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| `metrics` | 指标过滤器 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.list_environments_v2 |
| `client-certificate` | 客户端证书过滤器 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.list_environments_v2 |
| `waf-enabled` | WAF 启用过滤器 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.list_environments_v2 |

#### Actions

| Action 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| `update` | 更新环境 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.update_environment_v2 |
| `delete` | 删除环境 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.delete_environment_v2 |

### 3. apigw-domain-name

#### Filters

| Filter 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| 通用过滤器 | 使用上述通用过滤器 | - | huaweicloudsdkapig.v2.ApiGatewayClient |

#### Actions

| Action 名称 | 描述 | 可复用性 | 涉及 SDK/API |
|------------|------|---------|-------------|
| `update-security` | 更新安全策略 | 需要新开发 | huaweicloudsdkapig.v2.ApiGatewayClient.update_domain_v2 |

## 开发建议

1. 首先复用现有的通用过滤器和操作，这些在华为云其他服务中已经实现
2. 对于特定的 APIG 功能，需要基于华为云 SDK 开发新的过滤器和操作
3. 针对华为云 APIG 特有的功能，可能需要开发额外的过滤器和操作
4. 部分 AWS 特有功能可能在华为云没有直接对应，需要寻找替代方案或跳过

## SDK 依赖

主要依赖:
- huaweicloudsdkapig.v2.ApiGatewayClient
- 华为云通用标签管理服务 (TMS)

## API 参考

- 查询 API 列表: https://support.huaweicloud.com/api-apig/ListApisV2.html
- 查询环境列表: https://support.huaweicloud.com/api-apig/ListEnvironmentsV2.html
- 修改环境: https://support.huaweicloud.com/api-apig/UpdateEnvironmentV2.html
- 删除环境: https://support.huaweicloud.com/api-apig/DeleteEnvironmentV2.html
- 修改域名: https://support.huaweicloud.com/api-apig/UpdateDomainV2.html
- 查询项目下所有实例标签: https://support.huaweicloud.com/api-apig/ListProjectInstanceTags.html
- 批量添加或删除单个实例的标签: https://support.huaweicloud.com/api-apig/BatchCreateOrDeleteInstanceTags.html
