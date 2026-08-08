# mimotion

[![ 刷步数](https://github.com/TonyJiangWJ/mimotion/actions/workflows/run.yml/badge.svg)](https://github.com/TonyJiangWJ/mimotion/actions/workflows/run.yml)
[![GitHub stars](https://img.shields.io/github/stars/TonyJiangWJ/mimotion?style=flat-square)](https://github.com/TonyJiangWJ/mimotion/stargazers)

## 小米运动 / Zepp Life 自动刷步数（优雅版）

精简重写版，只保留核心功能：

- 每天在配置的小时列表里**随机挑一个时刻**，刷一次**随机步数**（不做线性增长，每天恰好一次）
- 仅 **Telegram** 推送刷步结果
- 多账号支持（`#` 分隔）
- token 加密缓存，减少重复登录

> 小米运动 APP 现已改名 **Zepp Life**。注册登录请搜索 `Zepp Life`，用的是**小米运动/ZeppLife 账号**，不是小米账号。

## 工作原理（一句话）

利用 Zepp Life 云端接受"未经验证的手环同步数据"这一特性：脚本复刻 App 的加密登录拿到 `app_token`，把一个预制的步数数据模板替换成今天的日期和你想要的步数，POST 到华米 `band_data.json` 接口，步数即写入云端，关联的支付宝/微信等第三方会自动同步。

## 随机时刻机制（无状态，恰好一次）

不用任何状态文件，也不用改写 cron：

- 每账号每天的目标时刻 = `sha256("日期:账号")`，从 `BRUSH_HOURS` 里确定性选出小时和分钟。
- GitHub Actions 每 30 分钟检查一次；目标时刻必然只落在唯一一个 30 分钟槽里，因此**只有那次运行真正刷步**，其余检查运行立即静默退出（几乎零成本）。
- 同一天同一账号只刷一次；每天的目标时刻不同，更接近真实作息。

## 部署指南

### 一、Fork 并创建 token

1. Fork 此仓库。
2. 前往 [Fine-grained tokens](https://github.com/settings/tokens?type=beta) 创建个人 token（建议用最小权限）：
   - `Repository access` → `Only select repositories` → 勾选你的 fork
   - `Repository permissions`：勾选 `Actions`(Read/write)、`Contents`(Read/write)、`Metadata`(Read-only)、`Workflows`(Read/write)
3. 生成后复制保存。

### 二、配置 Secrets

进入你的 fork：`Settings → Secrets and variables → Actions → New repository secret`，添加三个 Secret：

| Secret | 说明 |
|---|---|
| `PAT` | 上面创建的 token（用于 checkout 和提交 token 缓存） |
| `AES_KEY` | 16 个字符的密钥，用于加密缓存登录 token。多账号或希望少登录就必填。请妥善保管 |
| `CONFIG` | 账号、步数、时间、Telegram 配置，JSON 格式（见下） |

**CONFIG 示例（多账号）：**

```json
{
  "USER": "a@qq.com#13800138000",
  "PWD": "pwd1#pwd2",
  "BRUSH_HOURS": "8,12,18,22",
  "MIN_STEP": "18000",
  "MAX_STEP": "25000",
  "SLEEP_GAP": "5",
  "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF...",
  "TELEGRAM_CHAT_ID": "123456789"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `USER` | 是 | 小米运动/ZeppLife 账号（手机号或邮箱），多账号用 `#` 分隔 |
| `PWD` | 是 | 对应密码，多账号用 `#` 分隔，数量必须与 USER 一致 |
| `BRUSH_HOURS` | 是 | 允许刷步的**北京时间小时**，逗号分隔，如 `8,12,18,22`。每天随机挑其中一个小时 + 随机分钟刷一次 |
| `MIN_STEP` / `MAX_STEP` | 否 | 随机步数范围，默认 18000~25000 |
| `SLEEP_GAP` | 否 | 多账号间执行间隔秒数，默认 5 |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot 的 token（与 `TELEGRAM_CHAT_ID` 同时配置才推送） |
| `TELEGRAM_CHAT_ID` | 否 | Telegram 的 chatId（与 `TELEGRAM_BOT_TOKEN` 同时配置才推送） |

> 手机号不带 `+86` 也能用，脚本会自动补 `+86`。账号/密码用 `#` 分隔时**数量必须一致**，否则跳过执行。

### 三、启用并手动测试

1. 进入 `Actions`，启用工作流 `刷步数`。
2. 点右上角 `Run workflow`，把 `force` 开关打开再 `Run`（强制模式会忽略随机时刻，立即刷全部账号，方便测试）。
3. 刷新查看执行记录，应收到 Telegram 推送。

日常无需手动干预，定时检查会自动刷步。

### 四、自定义时间范围

`BRUSH_HOURS` 里的小时是**北京时间**。工作流的检查 cron 覆盖北京 8:00~23:59。如果你的 `BRUSH_HOURS` 超出这个范围（比如凌晨 0~7 点），需要自行修改 `.github/workflows/run.yml` 里的 `schedule.cron`。

## 注意事项

1. 步数是写入云端的"假手环数据"，**小米运动 App 本身不会显示**，只有关联了支付宝/微信等的第三方才会同步。
2. 新版本接口有限制，同 IP 大量登录可能触发 429，多账号时建议 `SLEEP_GAP` 保持默认或调大。
3. 支付宝没更新步数时，到小米运动 → 设置 → 账号 → 注销账号 → 清空数据，重新登录并重新绑定第三方。
4. `AES_KEY` 变更后，`encrypted_tokens.data` 会解密失败，属正常现象，下次运行会用新密钥重新生成。

## 致谢

- 本仓库基于 [xunichanghuan/mimotion](https://github.com/xunichanghuan/mimotion)（已被 ban）和 [huangshihai/mimotion](https://github.com/huangshihai/mimotion) 修改。
- 新版本登录加密密钥参考 [hanximeng/Zepp_API](https://github.com/hanximeng/Zepp_API)。
