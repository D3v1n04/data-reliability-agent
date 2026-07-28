import json
import math
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.app.core.config import Settings, get_settings


class BedrockServiceError(RuntimeError):
    """Raised when Bedrock cannot produce a valid response."""


class BedrockService:
    """Small boundary around the Amazon Bedrock Runtime client."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()

        if client is None:
            session = boto3.Session(
                profile_name=self.settings.aws_profile,
                region_name=self.settings.aws_region,
            )
            client = session.client("bedrock-runtime")

        self.client = client

    def generate_text(
        self,
        prompt: str,
        system_prompt: str,
    ) -> str:
        """Generate text with the configured Amazon Nova model."""
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if not system_prompt.strip():
            raise ValueError("System prompt cannot be empty")

        try:
            response = self.client.converse(
                modelId=self.settings.bedrock_text_model_id,
                system=[
                    {
                        "text": system_prompt,
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt,
                            }
                        ],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 1024,
                    "temperature": 0.0,
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise BedrockServiceError(
                "Unable to invoke the Bedrock text model"
            ) from exc

        try:
            content_blocks = response["output"]["message"]["content"]

            generated_text = "".join(
                block["text"]
                for block in content_blocks
                if isinstance(block, dict)
                and isinstance(block.get("text"), str)
            ).strip()
        except (KeyError, TypeError) as exc:
            raise BedrockServiceError(
                "Bedrock returned an invalid text response"
            ) from exc

        if not generated_text:
            raise BedrockServiceError(
                "Bedrock returned an empty text response"
            )

        return generated_text

    def generate_structured_output(
        self,
        prompt: str,
        system_prompt: str,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate one structured tool-use response from Nova."""
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if not system_prompt.strip():
            raise ValueError("System prompt cannot be empty")

        if not tool_name.strip():
            raise ValueError("Tool name cannot be empty")

        try:
            response = self.client.converse(
                modelId=self.settings.bedrock_text_model_id,
                system=[
                    {
                        "text": system_prompt,
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt,
                            }
                        ],
                    }
                ],
                toolConfig=tool_config,
                inferenceConfig={
                    "maxTokens": 1024,
                    "temperature": 0.0,
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise BedrockServiceError(
                "Unable to invoke the Bedrock text model"
            ) from exc

        try:
            content_blocks = response["output"]["message"]["content"]
            matching_tool_uses = [
                block["toolUse"]
                for block in content_blocks
                if isinstance(block, dict)
                and isinstance(block.get("toolUse"), dict)
                and block["toolUse"].get("name") == tool_name
            ]
        except (KeyError, TypeError) as exc:
            raise BedrockServiceError(
                "Bedrock returned an invalid structured response"
            ) from exc

        if len(matching_tool_uses) != 1:
            raise BedrockServiceError(
                "Bedrock returned an invalid structured response"
            )

        tool_input = matching_tool_uses[0].get("input")

        if not isinstance(tool_input, dict):
            raise BedrockServiceError(
                "Bedrock returned an invalid structured response"
            )

        return tool_input

    def generate_embedding(
        self,
        input_text: str,
    ) -> list[float]:
        """Generate a normalized Titan V2 embedding."""
        if not input_text.strip():
            raise ValueError("Embedding input cannot be empty")

        request_body = json.dumps(
            {
                "inputText": input_text,
                "dimensions": (
                    self.settings.bedrock_embedding_dimensions
                ),
                "normalize": True,
            }
        )

        try:
            response = self.client.invoke_model(
                modelId=self.settings.bedrock_embedding_model_id,
                body=request_body,
                contentType="application/json",
                accept="application/json",
            )
        except (BotoCoreError, ClientError) as exc:
            raise BedrockServiceError(
                "Unable to invoke the Bedrock embedding model"
            ) from exc

        try:
            response_body = json.loads(
                response["body"].read()
            )
            embedding = response_body["embedding"]
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise BedrockServiceError(
                "Bedrock returned an invalid embedding response"
            ) from exc

        expected_dimensions = (
            self.settings.bedrock_embedding_dimensions
        )

        if (
            not isinstance(embedding, list)
            or len(embedding) != expected_dimensions
        ):
            raise BedrockServiceError(
                "Bedrock returned an embedding with invalid dimensions"
            )

        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in embedding
        ):
            raise BedrockServiceError(
                "Bedrock returned invalid embedding values"
            )

        return [float(value) for value in embedding]


@lru_cache
def get_bedrock_service() -> BedrockService:
    """Return the shared Bedrock service instance."""
    return BedrockService()
