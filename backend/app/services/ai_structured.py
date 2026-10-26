"""Bounded non-streaming model calls shared by research tools."""
import asyncio
import json

import httpx

from backend.app.services import ai_assistant as ai


class StructuredError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


async def complete_text(provider_id: str, key: str, payload: dict) -> str:
    provider = ai.selected_provider(provider_id)
    try:
        async with asyncio.timeout(75):
            async with ai.create_client() as client:
                async with client.stream("POST", provider["base_url"] + "/chat/completions",
                                         headers={"Authorization": "Bearer " + key}, json=payload) as response:
                    if response.status_code != 200:
                        raise StructuredError(ai.provider_error(response.status_code), 502)
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 96000:
                            raise StructuredError("模型返回内容过长，请缩小需求范围。", 502)
                    choice = json.loads(content)["choices"][0]
                    if choice.get("finish_reason") != "stop":
                        raise StructuredError("模型回答不完整，请重试或更换模型。", 502)
                    raw = choice["message"]["content"]
                    if not isinstance(raw, str) or not raw or len(raw) > 24000:
                        raise StructuredError("模型没有返回有效内容。", 502)
                    return raw
    except (httpx.TimeoutException, TimeoutError):
        raise StructuredError("生成超时，请稍后重试或选择更快的模型。", 504) from None
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError, RecursionError):
        raise StructuredError("模型连接或响应异常，请检查个人设置后重试。", 502) from None
