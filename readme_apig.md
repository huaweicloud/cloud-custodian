# Cloud Custodian Huawei Cloud APIG 支持计划

本文档旨在规划和说明在 Cloud Custodian 中添加对华为云 API 网关 (APIG) 服务的支持所需实现的功能。

## 1. 资源定义

- **资源类型:** `huaweicloud.apig`
- **主要查询 API:** `ListApisV2` (用于列出用户账户下的 API)
    - **SDK:** `huaweicloudsdkapig.v2.ListApisV2Request`
    - **API 链接:** [查询API列表 - https://support.huaweicloud.com/api-apig/ListApisV2.html](https://support.huaweicloud.com/api-apig/ListApisV2.html)
- **资源 ID:** `id` (API 返回结果中的 API ID)
- **资源名称:** `name` (API 返回结果中的 API 名称)

## 2. Filters (过滤器)

以下是计划支持的过滤器列表，包括通用过滤器和 APIG 特定过滤器：

### 2.1 通用 Filters

| Filter 类型         | 描述                                       | 可复用性      | 依赖/备注                                                                                                                                |
| :------------------ | :----------------------------------------- | :------------ | :--------------------------------------------------------------------------------------------------------------------------------------- |
| `value`             | 基于资源的任意属性值进行过滤 (如 `name`, `status`, `type`, `protocol` 等) | **可复用**    | 使用核心 `ValueFilter`，直接作用于 `ListApisV2` 返回的资源属性。                                                                            |
| `list-item`         | 过滤列表类型属性中的元素 (如 `publish` 信息, `backend_api` 信息等)       | **可复用**    | 使用核心 `ListItemFilter`，需要根据 APIG 资源的具体列表属性进行配置。                                                                       |
| `tag-count`         | 基于资源标签数量进行过滤                        | **可复用**    | 依赖于下面的标签支持。使用 `c7n_huaweicloud.filters.tms.TagCountFilter`。                                                                 |
| `marked-for-op`     | 基于特定标记标签过滤需要执行操作的资源               | **可复用**    | 依赖于下面的标签支持和 `mark-for-op` action。使用 `c7n_huaweicloud.filters.tms.TagActionFilter`。                                                 |
| `age`               | 基于资源的创建时间或更新时间进行过滤                | **可复用**    | 使用核心 `AgeFilter` 或 `ValueFilter` (`value_type: age`)，作用于 `create_time` 等时间戳字段。                                                   |
| `metrics`           | 基于云监控 (CES) 指标进行过滤                   | **可复用**    | 核心 `MetricsFilter` 可复用，但需确认 CES 是否支持 APIG 相关指标，并进行适配。涉及 `huaweicloudsdkces.v1`。                                |
| `config-compliance` | 基于云配置 (Config) 服务合规性进行过滤            | **可复用**    | 核心 `ConfigComplianceFilter` 可复用，但需确认 Config 服务是否支持 APIG 资源类型，并进行适配。涉及 `huaweicloudsdkconfig.v1`。                 |
| `tag` / `tags`      | 基于标签键/值进行过滤                          | **部分可复用**  | 可复用 `c7n_huaweicloud.filters.tms.FilterByTag`。**注意:** 需要确认 APIG API 资源本身是否直接使用 TMS 进行标签管理，还是仅 APIG 实例使用。若 API 本身不支持 TMS，则需要自定义实现。 |

### 2.2 APIG 特定 Filters

| Filter 类型         | 描述                                           | 可复用性      | 依赖/备注                                           |
| :------------------ | :--------------------------------------------- | :------------ | :-------------------------------------------------- |
| `environment-binding` | 过滤绑定了特定环境的 API                           | **需开发**    | 需要检查 `ListApisV2` 或其他 API 是否返回环境绑定信息，并实现相应过滤逻辑。 |
| `domain-association` | 过滤绑定了特定自定义域名的 API                      | **需开发**    | 需要检查相关 API 返回信息，实现过滤逻辑。                     |
| `backend-type`      | 过滤使用特定后端服务类型 (如 `HTTP`, `FUNCTION`) 的 API | **可复用**    | 可通过 `value` filter 实现，过滤 `backend_type` 字段。    |

*(可根据实际需求添加更多 APIG 特定过滤器)*

## 3. Actions (操作)

以下是计划支持的操作列表，包括通用操作和 APIG 特定操作：

### 3.1 通用 Actions

| Action 类型     | 描述                                       | 可复用性      | 依赖/备注                                                                                                                                                                                                                                      |
| :-------------- | :----------------------------------------- | :------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tag`           | 为资源添加标签                               | **部分可复用**  | 可复用 `c7n_huaweicloud.actions.tms.Tag`。**注意:** 同上，需确认 APIG API 是否使用 TMS。若否，则需自定义实现，可能涉及 `BatchCreateOrDeleteInstanceTags` (https://support.huaweicloud.com/api-apig/BatchCreateOrDeleteInstanceTags.html) 但这个是实例标签，API 本身的标签 API 需要确认。 |
| `remove-tag`    | 删除资源标签                               | **部分可复用**  | 可复用 `c7n_huaweicloud.actions.tms.RemoveTag`。**注意:** 同上。                                                                                                                                                                                   |
| `mark-for-op`   | 添加标记标签，用于延迟操作 (如稍后删除)            | **可复用**    | 使用 `c7n_huaweicloud.actions.autotag.TagDelayedAction`。依赖标签支持。                                                                                                                                                                     |
| `delete`        | 删除 API 资源                              | **需开发**    | 需要调用 APIG 删除 API 的接口 (如 `DeleteApiV2`) 并封装成 Action。SDK: `huaweicloudsdkapig.v2.DeleteApiV2Request` (需确认 API 是否存在)。                                                                                                              |

### 3.2 APIG 特定 Actions

| Action 类型           | 描述                       | 可复用性      | 依赖/备注                                                                                                                                                                    |
| :-------------------- | :------------------------- | :------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `publish`             | 发布 API 到指定环境          | **需开发**    | 需要调用 APIG 发布 API 的接口 (如 `PublishApiToEnvironmentV2`)。SDK: `huaweicloudsdkapig.v2.PublishApiToEnvironmentV2Request` (需确认 API)。                                       |
| `offline`             | 从指定环境下线 API           | **需开发**    | 需要调用 APIG 下线 API 的接口 (如 `OfflineApiFromEnvironmentV2`)。SDK: `huaweicloudsdkapig.v2.OfflineApiFromEnvironmentV2Request` (需确认 API)。                                     |
| `update-environment`  | 修改环境信息                 | **需开发**    | 调用 `UpdateEnvironmentV2`。SDK: `huaweicloudsdkapig.v2.UpdateEnvironmentV2Request`。API 链接: [修改环境](https://support.huaweicloud.com/api-apig/UpdateEnvironmentV2.html)          |
| `delete-environment`  | 删除环境                     | **需开发**    | 调用 `DeleteEnvironmentV2`。SDK: `huaweicloudsdkapig.v2.DeleteEnvironmentV2Request`。API 链接: [删除环境](https://support.huaweicloud.com/api-apig/DeleteEnvironmentV2.html)          |
| `update-domain`       | 修改自定义域名信息           | **需开发**    | 调用 `UpdateDomainV2`。SDK: `huaweicloudsdkapig.v2.UpdateDomainV2Request`。API 链接: [修改域名](https://support.huaweicloud.com/api-apig/UpdateDomainV2.html)                 |
| `modify-api`          | 修改 API 的部分属性 (如描述等) | **需开发**    | 需要调用 APIG 修改 API 的接口 (如 `ModifyApiV2`)。SDK: `huaweicloudsdkapig.v2.ModifyApiV2Request` (需确认 API)。                                                                 |

*(可根据实际需求添加更多 APIG 特定操作)*

## 4. 依赖服务

实现 APIG 资源管理主要依赖以下华为云服务：

1.  **API 网关 (APIG):** 核心服务，提供 API 的查询、管理接口。
2.  **标签管理服务 (TMS):** (可能) 用于管理 API 资源的标签。
3.  **云监控 (CES):** (可选) 用于基于监控指标进行过滤。
4.  **云配置 (Config):** (可选) 用于基于合规性进行过滤。
5.  **身份和访问管理 (IAM):** 用于认证和授权。

## 5. SDK 依赖

- **主要 SDK:** `huaweicloudsdkapig` (具体版本根据需要确定, 目前主要是 `v2`)
- **其他可能涉及的 SDK:**
    - `huaweicloudsdktms`
    - `huaweicloudsdkces`
    - `huaweicloudsdkconfig`
    - `huaweicloudsdkcore` (基础依赖)

## 6. 开发说明

- **资源管理器 (`apig.py`):** 需要在 `tools/c7n_huaweicloud/c7n_huaweicloud/resources/` 目录下创建 `apig.py` 文件，实现 `APIGResourceManager` 类，继承 `QueryResourceManager`，并实现 `resource_type` 和可能需要的 `augment` 方法。
- **过滤器实现:**
    - 可复用的过滤器直接在策略中使用。
    - 需要开发的过滤器在 `tools/c7n_huaweicloud/c7n_huaweicloud/filters/` 目录下实现，或直接在 `apig.py` 中注册。
- **操作实现:**
    - 可复用的操作直接在策略中使用。
    - 需要开发的操作在 `tools/c7n_huaweicloud/c7n_huaweicloud/actions/` 目录下实现，继承 `HuaweiCloudBaseAction`。
- **测试:** 需要在 `tools/c7n_huaweicloud/tests/` 目录下添加 `test_apig.py`，包含单元测试和 VCR 功能测试。
