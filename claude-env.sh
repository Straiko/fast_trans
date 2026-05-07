#!/bin/bash

export ANTHROPIC_BASE_URL=http://localhost:20128/v1
export ANTHROPIC_AUTH_TOKEN=sk-f5d194e4f8f0a571-44a788-f6e7528f
export ANTHROPIC_API_KEY=sk-f5d194e4f8f0a571-44a788-f6e7528f

# Проверь, чтобы префикс (kr/ или kiro/) совпадал с тем, что в OmniRoute
export ANTHROPIC_MODEL=kr/claude-sonnet-4.5
export ANTHROPIC_SMALL_FAST_MODEL=kr/claude-haiku-4.5

export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

claude "$@"
