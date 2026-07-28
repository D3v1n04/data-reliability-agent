import json
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from backend.app.core.config import Settings
from backend.app.services.bedrock import (
    BedrockService,
    BedrockServiceError,
)


class FakeResponseBody:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self.payload


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=(
            "postgresql://user:password@example.com/database"
        ),
        aws_profile="data-reliability-agent",
        aws_region="us-east-1",
        bedrock_text_model_id="amazon.nova-lite-v1:0",
        bedrock_embedding_model_id=(
            "amazon.titan-embed-text-v2:0"
        ),
        bedrock_embedding_dimensions=256,
    )


def test_generate_text_returns_nova_text(
    settings: Settings,
) -> None:
    client = Mock()
    client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '{"explanation":"Pipeline failed"}',
                    }
                ]
            }
        }
    }

    service = BedrockService(
        settings=settings,
        client=client,
    )

    result = service.generate_text(
        prompt="Diagnose this incident",
        system_prompt="Return structured JSON",
    )

    assert result == '{"explanation":"Pipeline failed"}'

    client.converse.assert_called_once_with(
        modelId="amazon.nova-lite-v1:0",
        system=[
            {
                "text": "Return structured JSON",
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": "Diagnose this incident",
                    }
                ],
            }
        ],
        inferenceConfig={
            "maxTokens": 1024,
            "temperature": 0.0,
        },
    )


def test_generate_structured_output_returns_tool_input(
    settings: Settings,
) -> None:
    client = Mock()
    client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "name": "submit_diagnosis",
                            "input": {"explanation": "failed"},
                        }
                    }
                ]
            }
        }
    }
    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": "submit_diagnosis",
                }
            }
        ]
    }

    service = BedrockService(
        settings=settings,
        client=client,
    )

    result = service.generate_structured_output(
        prompt="Diagnose this incident",
        system_prompt="Return structured JSON",
        tool_name="submit_diagnosis",
        tool_config=tool_config,
    )

    assert result == {"explanation": "failed"}
    assert client.converse.call_args.kwargs["toolConfig"] == (
        tool_config
    )


def test_generate_structured_output_rejects_free_form_text(
    settings: Settings,
) -> None:
    client = Mock()
    client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": "Here is the diagnosis.",
                    }
                ]
            }
        }
    }

    service = BedrockService(
        settings=settings,
        client=client,
    )

    with pytest.raises(
        BedrockServiceError,
        match="invalid structured response",
    ):
        service.generate_structured_output(
            prompt="Diagnose this incident",
            system_prompt="Return structured JSON",
            tool_name="submit_diagnosis",
            tool_config={"tools": []},
        )


def test_generate_embedding_returns_256_floats(
    settings: Settings,
) -> None:
    client = Mock()
    client.invoke_model.return_value = {
        "body": FakeResponseBody(
            {
                "embedding": [0.25] * 256,
                "inputTextTokenCount": 4,
            }
        )
    }

    service = BedrockService(
        settings=settings,
        client=client,
    )

    result = service.generate_embedding(
        "Pipeline failed validation"
    )

    assert len(result) == 256
    assert all(value == 0.25 for value in result)

    client.invoke_model.assert_called_once()

    request = client.invoke_model.call_args.kwargs

    assert request["modelId"] == (
        "amazon.titan-embed-text-v2:0"
    )
    assert request["contentType"] == "application/json"
    assert request["accept"] == "application/json"

    assert json.loads(request["body"]) == {
        "inputText": "Pipeline failed validation",
        "dimensions": 256,
        "normalize": True,
    }


def test_generate_embedding_rejects_wrong_dimensions(
    settings: Settings,
) -> None:
    client = Mock()
    client.invoke_model.return_value = {
        "body": FakeResponseBody(
            {
                "embedding": [0.25] * 255,
            }
        )
    }

    service = BedrockService(
        settings=settings,
        client=client,
    )

    with pytest.raises(
        BedrockServiceError,
        match="invalid dimensions",
    ):
        service.generate_embedding("Pipeline failed")


def test_generate_text_wraps_aws_client_error(
    settings: Settings,
) -> None:
    client = Mock()
    client.converse.side_effect = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "Access denied",
            }
        },
        "Converse",
    )

    service = BedrockService(
        settings=settings,
        client=client,
    )

    with pytest.raises(
        BedrockServiceError,
        match="Unable to invoke",
    ):
        service.generate_text(
            prompt="Diagnose this incident",
            system_prompt="Return structured JSON",
        )
