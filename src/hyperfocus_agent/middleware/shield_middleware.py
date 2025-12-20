from collections.abc import Callable

from langchain.agents.middleware import wrap_tool_call
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from ..shield import is_shield_enabled, shield_text
from ..shield.shield import stringify_for_shield

_SCANNED_TOOL_CALL_IDS: set[str] = set()


@wrap_tool_call
def shield_tool_output(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command]
) -> ToolMessage | Command:
    result = handler(request)

    if not is_shield_enabled():
        return result

    tool_call_id = _get_tool_call_id(request, result)
    if tool_call_id and tool_call_id in _SCANNED_TOOL_CALL_IDS:
        return result

    tool_name = request.tool.name if request.tool else "unknown_tool"

    should_scan, payloads = _collect_payloads(tool_name, result)
    if not should_scan:
        return result

    for source, content in payloads:
        shield_text(content, source=source)

    if tool_call_id:
        _SCANNED_TOOL_CALL_IDS.add(tool_call_id)

    return result


def _collect_payloads(
    tool_name: str,
    result: ToolMessage | Command
) -> tuple[bool, list[tuple[str, str]]]:
    payloads: list[tuple[str, str]] = []
    shield_requested = False

    if isinstance(result, ToolMessage):
        shield_requested = _message_requests_shield(result)
        if shield_requested:
            payloads.extend(_payloads_from_message(tool_name, result))
        return shield_requested, payloads

    if isinstance(result, Command):
        update = result.update or {}
        for message in update.get("messages", []) or []:
            if isinstance(message, ToolMessage):
                if _message_requests_shield(message):
                    shield_requested = True
                    payloads.extend(_payloads_from_message(tool_name, message))
            else:
                content = getattr(message, "content", None)
                if content and shield_requested:
                    payloads.append(
                        (f"{tool_name} message", stringify_for_shield(content))
                    )

        if shield_requested:
            stored_data = update.get("stored_data", {}) or {}
            for data_id, entry in stored_data.items():
                content = None
                data_type = "unknown"
                if isinstance(entry, dict):
                    content = entry.get("content")
                    data_type = entry.get("data_type", data_type)
                if content:
                    payloads.append(
                        (
                            f"{tool_name} stored_data:{data_id} ({data_type})",
                            stringify_for_shield(content),
                        )
                    )

    return shield_requested, payloads


def _payloads_from_message(tool_name: str, message: ToolMessage) -> list[tuple[str, str]]:
    if not message.content:
        return []
    return [(f"{tool_name} tool_message", stringify_for_shield(message.content))]


def _message_requests_shield(message: ToolMessage) -> bool:
    return bool(getattr(message, "additional_kwargs", {}).get("shield"))


def _get_tool_call_id(
    request: ToolCallRequest,
    result: ToolMessage | Command
) -> str | None:
    tool_call = getattr(request, "tool_call", {}) or {}
    tool_call_id = tool_call.get("id")
    if tool_call_id:
        return tool_call_id

    if isinstance(result, ToolMessage):
        return getattr(result, "tool_call_id", None)

    if isinstance(result, Command):
        update = result.update or {}
        for message in update.get("messages", []) or []:
            if isinstance(message, ToolMessage) and message.tool_call_id:
                return message.tool_call_id
    return None
