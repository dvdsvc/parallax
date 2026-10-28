# Environment configuration / 环境配置

The released analysis and evidence checks run without provider credentials. Live experiment routes use their documented provider configuration; the template includes the OpenAI-compatible, Qwen gateway and optional E2B settings.

已提供的分析与证据检查无需服务商密钥。重跑在线实验时，按相应入口配置模型服务、Qwen 网关或可选 E2B 环境。

## Local setup

```bash
cp .env.example .env
```

Fill in the supported variables in your local `.env`. The file is ignored by Git; keep the committed template's credential fields empty. For entrypoints that read process variables, add `--env-file .env` to the documented `uv run` command. See the repository's running guide for provider and data options.

在本地 `.env` 中填写所需变量，提交的示例文件保持空白。读取进程环境变量的入口可通过 `uv run --env-file .env ...` 载入配置，具体运行方式见对应说明。

## Repository check

With [Gitleaks](https://github.com/gitleaks/gitleaks) installed and on PATH:

```bash
uv run python scripts/check_secrets.py --history
```

This checks publication files and reachable Git history using the repository's detector configuration. Reports show locations without credential values.
