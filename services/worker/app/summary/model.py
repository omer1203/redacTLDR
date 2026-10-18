"""The Bedrock-backed summarizer. Tests pass their own `Summarizer` and never construct this."""

from __future__ import annotations

import logging

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel

from services.worker.app.config import AWS_REGION, BEDROCK_MODEL_ID
from services.worker.app.summary.engine import ModelResult
from services.worker.app.summary.errors import SummaryError
from services.worker.app.summary.schemas import MODELS

logger = logging.getLogger(__name__)

_RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException", "ModelNotReadyException"}


class BedrockSummarizer:
    def __init__(self, model_id: str = BEDROCK_MODEL_ID, region: str = AWS_REGION) -> None:
        self.model_id = model_id
        self.region = region

    def complete(self, mode: str, system: str, user: str) -> ModelResult:
        schema: type[BaseModel] = MODELS[mode]
        try:
            from langchain_aws import ChatBedrockConverse

            chat = ChatBedrockConverse(model=self.model_id, region_name=self.region, max_tokens=4096)
            structured = chat.with_structured_output(schema, include_raw=True)
            result = structured.invoke([("system", system), ("human", user)])
        except SummaryError:
            raise
        except (ClientError, BotoCoreError) as exc:
            code = ""
            if isinstance(exc, ClientError):
                code = exc.response.get("Error", {}).get("Code") or ""
            logger.warning("summary model call failed code=%s", code or exc.__class__.__name__)
            retryable = code in _RETRYABLE or isinstance(exc, BotoCoreError)
            raise SummaryError(
                "MODEL_UNAVAILABLE",
                "The summary service was unavailable. It will be retried." if retryable else "The summary service rejected the request.",
                retryable=retryable,
            ) from exc
        except Exception as exc:  # noqa: BLE001 — the SDK raises several families; the text stays generic
            logger.warning("summary model call failed error=%s", exc.__class__.__name__)
            raise SummaryError(
                "MODEL_UNAVAILABLE",
                "The summary service was unavailable. It will be retried.",
                retryable=True,
            ) from exc

        parsed = result.get("parsed") if isinstance(result, dict) else result
        raw = result.get("raw") if isinstance(result, dict) else None
        if parsed is None:
            raise SummaryError(
                "OUTPUT_INVALID",
                "The summary did not match the expected format, so it was not saved. You can try again.",
                retryable=False,
            )
        data = parsed.model_dump() if isinstance(parsed, BaseModel) else dict(parsed)
        usage = getattr(raw, "usage_metadata", None) or {}
        return ModelResult(
            data=data,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )
