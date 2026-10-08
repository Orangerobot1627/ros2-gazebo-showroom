#!/usr/bin/env python3
"""Provider registry and compatibility exports for the showroom LLM layer."""

import json
import os
import re
import urllib.error
import urllib.request

from showroom_llm_contract import (
    ALLOWED_INTENTS,
    command_from_result,
    COMMAND_INTENTS,
    extract_json_object,
    LLMError,
    LLMOutputError,
    LLMTransportError,
    validate_model_result,
)
from showroom_llm_prompt import (
    build_messages,
    compact_context,
    ground_explanation_result,
    normalize_multi_task_result,
)
from showroom_ollama_client import OllamaClient


DRINK_KEYWORDS = (
    ('咖啡', 'coffee'), ('饮料', 'drink'), ('果汁', 'juice'), ('水', 'water'),
)
# Ordinals count the five exhibit halls, not the reception and lounge areas.
EXHIBIT_ORDER = (
    'technology_history', 'vision_hall', 'robotics_hall',
    'time_tunnel', 'dance_hall',
)
TASK_KEYWORDS = (
    ('科技发展历史', 'technology_history'),
    ('历史', 'technology_history'),
    ('视觉', 'vision_hall'),
    ('机器人', 'robotics_hall'),
    ('时空', 'time_tunnel'),
    ('隧道', 'time_tunnel'),
    ('舞蹈', 'dance_hall'),
    ('休息', 'lounge'),
    ('接待', 'reception'),
    ('入口', 'reception'),
    ('前台', 'reception'),
)
ORDINAL_DIGITS = {
    '一': 1, '1': 1, '二': 2, '两': 2, '2': 2, '三': 3, '3': 3,
    '四': 4, '4': 4, '五': 5, '5': 5,
}
DELIVERY_VERBS = ('送', '配送', '拿到', '端', '带', '递')


def resolve_drink(text):
    """Map a drink word in the sentence to the contract drink name."""
    for keyword, name in DRINK_KEYWORDS:
        if keyword in text:
            return name
    return 'coffee'


def resolve_delivery_target(text):
    """Resolve a delivery task id from explicit names or an exhibit ordinal."""
    for keyword, task in TASK_KEYWORDS:
        if keyword in text:
            return task
    if '最后' in text:
        return 'lounge'
    match = re.search(
        r'第\s*([一二两三四五12345])\s*(?:个|号)?\s*'
        r'(?:场馆|展馆|展区|展厅|区|任务|站)?', text)
    if match:
        index = ORDINAL_DIGITS.get(match.group(1))
        if index and 1 <= index <= len(EXHIBIT_ORDER):
            return EXHIBIT_ORDER[index - 1]
    return None


def has_delivery_verb(text):
    """Return True when the sentence asks to bring or send something."""
    return any(word in text for word in DELIVERY_VERBS)


class OpenAICompatibleBackend:
    """Adapter for OpenAI-compatible chat-completions endpoints."""

    def __init__(self, endpoint, model, timeout_sec=20.0, api_key=''):
        self.endpoint = endpoint
        self.model = model
        self.timeout_sec = float(timeout_sec)
        self.api_key = api_key

    def post_json(self, payload):
        """POST one OpenAI-compatible JSON request."""
        if not self.endpoint:
            raise LLMTransportError('没有配置模型服务 endpoint')
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(
                    request, timeout=self.timeout_sec) as response:
                body = response.read().decode('utf-8')
        except urllib.error.HTTPError as exception:
            detail = exception.read().decode('utf-8', errors='replace')[:500]
            raise LLMTransportError(
                f'模型服务 HTTP {exception.code}：{detail}') from exception
        except (urllib.error.URLError, TimeoutError, OSError) as exception:
            raise LLMTransportError(
                f'无法访问模型服务 {self.endpoint}：{exception}') from exception
        try:
            return json.loads(body)
        except json.JSONDecodeError as exception:
            raise LLMTransportError('模型服务返回的不是 JSON') from exception

    def complete(self, messages):
        """Return the OpenAI-compatible assistant content."""
        response = self.post_json({
            'model': self.model,
            'messages': messages,
            'temperature': 0.1,
            'max_tokens': 256,
            'stream': False,
        })
        try:
            return response['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as exception:
            raise LLMTransportError(
                'OpenAI 兼容接口响应缺少 choices[0].message.content') \
                from exception


class MockBackend:
    """Deterministic local backend for ROS integration tests and teaching."""

    def complete(self, messages):
        """Classify a few Chinese phrases without a model server."""
        user_text = messages[-1]['content'].strip()
        normalized = user_text.lower()
        duration_match = re.search(r'(\d+(?:\.\d+)?)\s*秒', user_text)
        duration = (
            float(duration_match.group(1)) if duration_match else None)
        coffee_robot = any(word in user_text for word in (
            '绿色', '服务机器人', '咖啡机器人'))
        all_robots = any(word in user_text for word in (
            '两个机器人', '两台机器人', '所有机器人'))
        stay_request = any(word in user_text for word in (
            '多待', '多呆', '停留', '待一会', '呆一会'))
        drink_request = any(word in user_text for word in (
            '饮料', '咖啡', '水', '果汁'))
        delivery_verb = has_delivery_verb(user_text)
        if stay_request and drink_request:
            pause = {'action': 'pause', 'robot': 'guide'}
            if duration is not None:
                pause['duration_sec'] = duration
            result = {
                'intent': 'execute_plan',
                'plan': [
                    pause,
                    {
                        'action': 'deliver_drink',
                        'drink': 'coffee',
                        'target': 'current_task',
                    },
                ],
            }
        elif any(word in user_text for word in ('状态', '到哪', '为什么停')):
            result = {'intent': 'ask_status'}
        elif any(word in user_text for word in (
                '详细讲', '深入讲', '展开讲', '为什么它')):
            result = {
                'intent': 'explain_more',
                'reply': '我会结合当前展区内容作进一步说明。',
            }
        elif any(word in user_text for word in (
                '讲解当前', '介绍当前', '讲讲这个', '解释一下')):
            result = {
                'intent': 'explain_current',
                'reply': '我来介绍当前展区的主要内容。',
            }
        elif any(word in user_text for word in (
                '跳过', '没兴趣', '不想看这个')):
            result = {'intent': 'skip_current'}
        elif any(word in user_text for word in (
                '重新参观', '这个展区再来一遍', '重复当前任务')):
            result = {'intent': 'repeat_current'}
        elif any(word in user_text for word in (
                '下一个任务', '下个展区', '继续下一个')):
            result = {'intent': 'next_task'}
        elif any(word in user_text for word in (
                '暂停', '等一下', '稍等', '多看一会', '别往前走')):
            if coffee_robot or all_robots:
                result = {
                    'intent': 'robot_action',
                    'robot': 'all' if all_robots else 'coffee',
                    'action': 'pause',
                }
            else:
                result = {'intent': 'pause_tour'}
            if duration is not None:
                result['duration_sec'] = duration
        elif any(word in user_text for word in ('继续', '恢复')):
            if coffee_robot or all_robots:
                result = {
                    'intent': 'robot_action',
                    'robot': 'all' if all_robots else 'coffee',
                    'action': 'resume',
                }
            else:
                result = {'intent': 'resume_tour'}
        elif any(word in user_text for word in ('取消', '停止全部')):
            result = {'intent': 'cancel_all'}
        elif any(word in user_text for word in ('重置', '重新初始化')):
            result = {'intent': 'reset'}
        elif coffee_robot and any(word in user_text for word in (
                '立即', '现在', '默认配送', '开始配送')):
            result = {
                'intent': 'robot_action',
                'robot': 'coffee',
                'action': 'start_default',
            }
        elif drink_request and delivery_verb:
            result = {
                'intent': 'deliver_drink',
                'drink': resolve_drink(user_text),
                'target': resolve_delivery_target(user_text) or 'lounge',
            }
        elif '咖啡' in user_text and not any(
                word in user_text for word in ('导览', '参观', '讲解')):
            result = {'intent': 'request_coffee'}
        elif any(word in user_text for word in ('导览', '参观', '讲解', '开始')):
            no_coffee = any(
                word in user_text for word in ('不要咖啡', '不需要咖啡'))
            result = {'intent': 'start_tour', 'coffee': not no_coffee}
        else:
            result = {
                'intent': 'chat',
                'reply': f'我收到了您的问题：{normalized or user_text}',
            }
        return json.dumps(result, ensure_ascii=False)


OllamaBackend = OllamaClient


def create_backend(kind, endpoint='', model='', timeout_sec=30.0,
                   api_key_env='SHOWROOM_LLM_API_KEY'):
    """Create one configured provider adapter."""
    normalized = kind.strip().lower()
    if normalized == 'mock':
        return MockBackend()
    if normalized == 'ollama':
        return OllamaClient(endpoint, model, timeout_sec=timeout_sec)
    api_key = os.environ.get(api_key_env, '') if api_key_env else ''
    if normalized in ('openai', 'openai_compatible'):
        return OpenAICompatibleBackend(
            endpoint, model, timeout_sec=timeout_sec, api_key=api_key)
    raise ValueError(f'不支持的 LLM backend：{kind!r}')


__all__ = [
    'ALLOWED_INTENTS',
    'COMMAND_INTENTS',
    'LLMError',
    'LLMOutputError',
    'LLMTransportError',
    'MockBackend',
    'OllamaBackend',
    'OpenAICompatibleBackend',
    'build_messages',
    'command_from_result',
    'compact_context',
    'create_backend',
    'extract_json_object',
    'ground_explanation_result',
    'normalize_multi_task_result',
    'validate_model_result',
]
