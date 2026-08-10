# mimotion

[![ 刷步数](https://github.com/TonyJiangWJ/mimotion/actions/workflows/run.yml/badge.svg)](https://github.com/TonyJiangWJ/mimotion/actions/workflows/run.yml)
[![GitHub stars](https://img.shields.io/github/stars/TonyJiangWJ/mimotion?style=flat-square)](https://github.com/TonyJiangWJ/mimotion/stargazers)

## 小米运动 / Zepp Life 自动刷步数（优雅版）

精简重写版，只保留核心功能：

- **每天北京时间 12:30 自动刷一次随机步数**（固定时刻，由 GitHub Actions cron 触发）
- 仅 **Telegram** 推送刷步结果
- 多账号支持（`#` 分隔）
- token 加密缓存，减少重复登录

> 小米运动 APP 现已改名 **Zepp Life**。注册登录请搜索 `Zepp Life`，用的是**小米运动/ZeppLife 账号**，不是小米账号。

## 工作原理（一句话）

利用 Zepp Life 云端接受"未经验证的手环同步数据"这一特性：脚本复刻 App 的加密登录拿到 `app_token`，把一个预制的步数数据模板替换成今天的日期和你想要的步数，POST 到华米 `band_data.json` 接口，步数即写入云端，关联的支付宝/微信等第三方会自动同步。

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
| `CONFIG` | 账号、步数、Telegram 配置，JSON 格式（见下） |

**CONFIG 示例（多账号）：**

```json
{
  "USER": "a@qq.com#13800138000",
  "PWD": "pwd1#pwd2",
  "MIN_STEP": "12000",
  "MAX_STEP": "20000",
  "SLEEP_GAP": "5",
  "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF...",
  "TELEGRAM_CHAT_ID": "123456789"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `USER` | 是 | 小米运动/ZeppLife 账号（手机号或邮箱），多账号用 `#` 分隔 |
| `PWD` | 是 | 对应密码，多账号用 `#` 分隔，数量必须与 USER 一致 |
| `MIN_STEP` / `MAX_STEP` | 否 | 随机步数范围，默认 18000~25000 |
| `SLEEP_GAP` | 否 | 多账号间执行间隔秒数，默认 5 |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot 的 token（与 `TELEGRAM_CHAT_ID` 同时配置才推送） |
| `TELEGRAM_CHAT_ID` | 否 | Telegram 的 chatId（与 `TELEGRAM_BOT_TOKEN` 同时配置才推送） |

> 手机号不带 `+86` 也能用，脚本会自动补 `+86`。账号/密码用 `#` 分隔时**数量必须一致**，否则跳过执行。

### 三、启用并手动测试

1. 进入 `Actions`，启用工作流 `刷步数`。
2. 点右上角 `Run workflow` → `Run`，立即刷全部账号（等同于定时任务，方便测试）。
3. 想临时补刷/验证时，勾选 `force` 输入再 `Run`，会立即强制刷全部账号。

日常无需手动干预，每天北京时间 12:30 自动刷。

### 四、自定义刷步时间

工作流 cron 默认每天**北京时间 12:30**（UTC 04:30）。如需修改，编辑 `.github/workflows/run.yml` 里的：

```yaml
on:
  schedule:
    - cron: '30 4 * * *'   # 30 分 4 时(UTC) = 北京 12:30
```

GitHub Actions 的 cron 为 **UTC 时间**，是**北京时间 - 8**。

## 注意事项

1. 步数是写入云端的"假手环数据"，**小米运动 App 本身不会显示**，只有关联了支付宝/微信等的第三方才会同步。
2. 新版本接口有限制，同 IP 大量登录可能触发 429，多账号时建议 `SLEEP_GAP` 保持默认或调大。
3. 支付宝没更新步数时，到小米运动 → 设置 → 账号 → 注销账号 → 清空数据，重新登录并重新绑定第三方。
4. `AES_KEY` 变更后，`encrypted_tokens.data` 会解密失败，属正常现象，下次运行会用新密钥重新生成。

## 致谢

- 本仓库基于 [xunichanghuan/mimotion](https://github.com/xunichanghuan/mimotion)（已被 ban）和 [huangshihai/mimotion](https://github.com/huangshihai/mimotion) 修改。
- 新版本登录加密密钥参考 [hanximeng/Zepp_API](https://github.com/hanximeng/Zepp_API)。
