#!/usr/bin/env python3
"""Deterministic tests for the provider-independent LLM bridge logic."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_llm_contract import (  # noqa: E402
    command_from_result,
    extract_json_object,
    LLMOutputError,
    validate_model_result,
)
from showroom_llm_core import (  # noqa: E402
    MockBackend,
    OllamaBackend,
    OpenAICompatibleBackend,
)
from showroom_llm_prompt import (  # noqa: E402
    build_messages,
    compact_context,
    ground_explanation_result,
    normalize_multi_task_result,
    normalize_semantic_result,
)


def infer_with_mock(text):
    backend = MockBackend()
    messages = build_messages(text)
    return validate_model_result(
        extract_json_object(backend.complete(messages)))


def infer(text):
    """Mirror the bridge pipeline: mock, then normalizers, then validation."""
    backend = MockBackend()
    document = extract_json_object(backend.complete(build_messages(text)))
    document = normalize_multi_task_result(document, text)
    document = normalize_semantic_result(document, text)
    return validate_model_result(document)


def expect_invalid(document):
    try:
        validate_model_result(document)
    except LLMOutputError:
        return
    raise AssertionError(f'Expected invalid model document: {document!r}')


class StubOpenAIBackend(OpenAICompatibleBackend):
    """Return a fixed OpenAI-style response without opening a socket."""

    def post_json(self, payload):
        assert payload['model'] == 'qwen-test'
        assert payload['messages'][-1]['content'] == '你好'
        return {'choices': [{'message': {'content': '{"intent":"chat"}'}}]}


class StubOllamaBackend(OllamaBackend):
    """Return a fixed Ollama response without opening a socket."""

    def post_json(self, payload):
        assert payload['format'] == 'json'
        assert payload['stream'] is False
        assert payload['think'] is False
        return {'message': {
            'thinking': '{"intent":"cancel_all"}',
            'content': '{"intent":"pause_tour"}',
        }}


def main():
    fenced = '分析省略\n```json\n{"intent":"pause_tour","reply":"好"}\n```'
    assert extract_json_object(fenced)['intent'] == 'pause_tour'
    assert extract_json_object('<think>...</think>{"intent":"chat"}') == {
        'intent': 'chat'}

    normalized = validate_model_result({
        'intent': 'status',
        'reply': '正在读取状态。',
    })
    assert normalized['intent'] == 'ask_status'
    pause_only = validate_model_result({'intent': 'pause_tour'})
    assert pause_only == {
        'intent': 'pause_tour',
        'reply': '已提交暂停导览请求。',
    }
    expect_invalid({'intent': 'drive_to_xy', 'reply': '前往坐标。'})
    expect_invalid({'intent': 'start_tour', 'reply': '开始。', 'coffee': 'yes'})
    expect_invalid({
        'intent': 'robot_action', 'robot': 'guide', 'action': 'fly'})
    expect_invalid({'intent': 'explain_current'})
    grounded = ground_explanation_result(
        {'intent': 'explain_more'},
        {'current_task': {
            'summary': '机器人闭环。',
            'detail': '感知、决策、规划和执行。',
        }},
    )
    assert validate_model_result(grounded)['reply'] == (
        '感知、决策、规划和执行。')
    grounded_override = ground_explanation_result(
        {'intent': 'explain_current', 'reply': '模型编造的内容'},
        {'current_task': {'summary': '配置中的讲解。'}},
    )
    assert grounded_override['reply'] == '配置中的讲解。'
    repaired = normalize_multi_task_result({
        'intent': 'robot_action',
        'robot': 'coffee',
        'action': 'deliver_drink',
    }, '我想在视觉馆多待30秒，送杯水来')
    repaired = validate_model_result(repaired)
    assert repaired['intent'] == 'execute_plan'
    assert repaired['plan'] == [
        {'action': 'pause', 'robot': 'guide', 'duration_sec': 30.0},
        {
            'action': 'deliver_drink',
            'drink': 'water',
            'target': 'vision_hall',
        },
    ]
    semantic = normalize_semantic_result(
        {'intent': 'chat'}, '机器人馆不看了，跳过吧')
    assert command_from_result(validate_model_result(semantic)) == {
        'intent': 'skip_task', 'tasks': ['robotics_hall']}
    semantic = normalize_semantic_result(
        {'intent': 'chat'}, '我只看视觉馆和舞蹈馆')
    assert command_from_result(validate_model_result(semantic)) == {
        'intent': 'visit_only',
        'tasks': ['vision_hall', 'dance_hall'],
    }
    semantic = normalize_semantic_result(
        {'intent': 'request_coffee'}, '送一杯咖啡到机器人馆')
    assert command_from_result(validate_model_result(semantic)) == {
        'intent': 'deliver_drink',
        'drink': 'coffee',
        'target': 'robotics_hall',
    }
    semantic = normalize_semantic_result(
        {'intent': 'chat'}, '蓝色机器人绕过障碍')
    assert command_from_result(validate_model_result(semantic)) == {
        'intent': 'robot_action',
        'robot': 'guide',
        'action': 'bypass_obstacle',
    }
    semantic = normalize_semantic_result(
        {'intent': 'start_tour'}, '带我去时空隧道停留30秒')
    assert command_from_result(validate_model_result(semantic)) == {
        'intent': 'temporary_visit',
        'target': 'time_tunnel',
        'dwell_sec': 30.0,
        'timeout_sec': 300.0,
    }
    semantic = normalize_semantic_result(
        {'intent': 'ask_status'}, '机器人到时空隧道了吗')
    assert validate_model_result(semantic)['intent'] == 'ask_status'
    semantic = normalize_semantic_result(
        {'intent': 'chat'}, '时空隧道不去了')
    assert validate_model_result(semantic) == {
        'intent': 'skip_task',
        'reply': '好的，已从后续导览中移除指定场馆。',
        'tasks': ['time_tunnel'],
    }
    semantic = normalize_semantic_result(
        {'intent': 'chat'}, '我只看视觉馆，并送一杯咖啡到视觉馆')
    assert validate_model_result(semantic)['plan'] == [
        {'action': 'visit_only', 'tasks': ['vision_hall']},
        {
            'action': 'deliver_drink', 'drink': 'coffee',
            'target': 'vision_hall',
        },
    ]

    robot_action = validate_model_result({
        'intent': 'robot_action',
        'robot': 'coffee',
        'action': 'pause',
        'duration_sec': 20,
    })
    assert command_from_result(robot_action) == {
        'intent': 'robot_action',
        'robot': 'coffee',
        'action': 'pause',
        'duration_sec': 20.0,
    }
    explanation = validate_model_result({
        'intent': 'explain_current',
        'reply': '这里展示机器人如何形成感知与控制闭环。',
    })
    assert command_from_result(explanation) == {
        'intent': 'explain_current'}
    assert command_from_result(validate_model_result({
        'intent': 'skip_current'})) == {'intent': 'skip_current'}
    multi = validate_model_result({
        'intent': 'plan',
        'plan': [
            {'action': 'pause_tour', 'duration_sec': 25},
            {'action': 'request_drink', 'target': 'current_task'},
        ],
    })
    assert command_from_result(multi) == {
        'intent': 'execute_plan',
        'plan': [
            {'action': 'pause', 'robot': 'guide', 'duration_sec': 25.0},
            {
                'action': 'deliver_drink',
                'drink': 'coffee',
                'target': 'current_task',
            },
        ],
    }

    result = infer_with_mock('开始导览，不需要咖啡')
    assert result == {
        'intent': 'start_tour',
        'reply': '已提交导览任务请求。',
        'coffee': False,
    }
    assert command_from_result(result) == {
        'intent': 'start_tour', 'coffee': False}
    assert command_from_result(infer_with_mock('机器人现在是什么状态？')) is None
    assert infer_with_mock('暂停一下')['intent'] == 'pause_tour'
    assert infer_with_mock(
        '我想在这里多看一会儿，你先别往前走。')['intent'] == 'pause_tour'
    assert infer_with_mock('给我一杯咖啡')['intent'] == 'request_coffee'
    assert infer_with_mock('这个展厅没兴趣，跳过吧')['intent'] == (
        'skip_current')
    assert infer_with_mock('下个展区')['intent'] == 'next_task'
    assert infer_with_mock('详细讲讲为什么它能避障')['intent'] == (
        'explain_more')
    planned = infer_with_mock('我想在这个展馆多呆30秒，再送杯饮料来')
    assert planned['intent'] == 'execute_plan'
    assert planned['plan'][0]['duration_sec'] == 30.0
    assert planned['plan'][1]['action'] == 'deliver_drink'
    assert infer_with_mock('绿色机器人暂停10秒') == {
        'intent': 'robot_action',
        'reply': '绿色服务机器人将等待 10 秒，随后自动恢复原来的任务。',
        'robot': 'coffee',
        'action': 'pause',
        'duration_sec': 10.0,
    }

    delivered = infer_with_mock('送咖啡到第一个场馆')
    assert delivered['intent'] == 'deliver_drink'
    assert command_from_result(delivered) == {
        'intent': 'deliver_drink', 'drink': 'coffee',
        'target': 'technology_history'}
    assert command_from_result(infer_with_mock('送杯水到计算机视觉展厅')) == {
        'intent': 'deliver_drink', 'drink': 'water', 'target': 'vision_hall'}
    assert command_from_result(infer_with_mock('送果汁到第三个展区')) == {
        'intent': 'deliver_drink', 'drink': 'juice', 'target': 'robotics_hall'}
    assert command_from_result(infer_with_mock('送咖啡去休息区')) == {
        'intent': 'deliver_drink', 'drink': 'coffee', 'target': 'lounge'}
    # A delivery without any venue defaults to the current exhibit.
    assert command_from_result(infer_with_mock('送杯咖啡过来')) == {
        'intent': 'deliver_drink', 'drink': 'coffee', 'target': 'current_task'}

    # Nicknames and ordinals are normalized on the full bridge pipeline.
    assert command_from_result(infer('送餐机器人暂停20秒')) == {
        'intent': 'robot_action', 'robot': 'coffee', 'action': 'pause',
        'duration_sec': 20.0}
    assert command_from_result(infer('蓝色机器人绕过障碍')) == {
        'intent': 'robot_action', 'robot': 'guide',
        'action': 'bypass_obstacle'}
    assert command_from_result(infer('两台机器人暂停')) == {
        'intent': 'robot_action', 'robot': 'all', 'action': 'pause'}
    assert command_from_result(infer('送杯水到第一个场馆')) == {
        'intent': 'deliver_drink', 'drink': 'water',
        'target': 'technology_history'}
    assert command_from_result(infer('机器臂馆送杯咖啡')) == {
        'intent': 'deliver_drink', 'drink': 'coffee', 'target': 'robotics_hall'}
    assert command_from_result(infer('带我去隧道待30秒')) == {
        'intent': 'temporary_visit', 'target': 'time_tunnel',
        'dwell_sec': 30.0, 'timeout_sec': 300.0}
    # Fuzzy fallback catches substitution typos without cross-family hits.
    assert command_from_result(infer('机气人馆送杯水')) == {
        'intent': 'deliver_drink', 'drink': 'water',
        'target': 'robotics_hall'}
    assert command_from_result(infer('视觉关送咖啡')) == {
        'intent': 'deliver_drink', 'drink': 'coffee', 'target': 'vision_hall'}
    assert command_from_result(infer('时空遂道送杯咖啡')) == {
        'intent': 'deliver_drink', 'drink': 'coffee', 'target': 'time_tunnel'}
    assert command_from_result(infer('送杯咖非到第一场馆')) == {
        'intent': 'deliver_drink', 'drink': 'coffee',
        'target': 'technology_history'}
    assert command_from_result(infer('送杯饮料到舞稻厅')) == {
        'intent': 'deliver_drink', 'drink': 'drink', 'target': 'dance_hall'}
    assert command_from_result(infer('到第三个场馆待30秒')) == {
        'intent': 'temporary_visit', 'target': 'robotics_hall',
        'dwell_sec': 30.0, 'timeout_sec': 300.0}
    assert command_from_result(
        infer('带我去隧道待三十秒'))['dwell_sec'] == 30.0
    assert command_from_result(infer('导览机器人先停一下')) == {
        'intent': 'pause_tour'}
    assert command_from_result(infer('两个机器人在第二场馆会和')) == {
        'intent': 'rendezvous', 'target': 'vision_hall',
        'dwell_sec': 0.0, 'timeout_sec': 300.0}
    assert command_from_result(infer('两个机器人在时空隧道碰头待30秒')) == {
        'intent': 'rendezvous', 'target': 'time_tunnel',
        'dwell_sec': 30.0, 'timeout_sec': 300.0}
    # A plain "开始导览" must not be mistaken for a robot nickname.
    assert command_from_result(infer('开始导览')) == {
        'intent': 'start_tour', 'coffee': True}

    compact = compact_context(
        {'guide_state': 'TOURING', 'private': 'drop-me'},
        {'robots': {'robot_0': {
            'navigation_state': 'NAVIGATING',
            'current_waypoint': 'vision_display',
            'pose': {'x': 123},
            'nav2_feedback': {
                'distance_remaining_m': 2.75,
                'estimated_time_remaining_sec': 6.5,
                'number_of_recoveries': 1,
            },
        }}},
    )
    assert compact['business']['guide_state'] == 'TOURING'
    assert 'private' not in compact['business']
    assert 'pose' not in compact['robots']['robot_0']
    assert compact['robots']['robot_0']['distance_remaining_m'] == 2.75
    assert compact['robots']['robot_0'][
        'estimated_time_remaining_sec'] == 6.5
    assert compact['robots']['robot_0']['nav2_recovery_count'] == 1

    compact = compact_context({
        'current_task': {
            'task_id': 'robotics_hall',
            'summary': '机器人闭环。',
            'detail': '感知、决策、规划和执行。',
        }}, {})
    assert compact['business']['current_task']['task_id'] == 'robotics_hall'

    system_prompt = build_messages('你好')[0]['content']
    assert '绝不能生成速度、坐标或 cmd_vel 指令' in system_prompt
    assert 'skip_current' in system_prompt
    assert 'execute_plan' in system_prompt
    messages = [{'role': 'user', 'content': '你好'}]
    openai_backend = StubOpenAIBackend('http://unused', 'qwen-test')
    assert json.loads(openai_backend.complete(messages))['intent'] == 'chat'
    ollama_backend = StubOllamaBackend('http://unused', 'qwen-test')
    assert ollama_backend.endpoint == 'http://unused/api/chat'
    assert json.loads(
        ollama_backend.complete(messages))['intent'] == 'pause_tour'
    json.dumps(compact)
    print('LLM bridge parsing, validation, and mock scenarios: OK')


if __name__ == '__main__':
    main()
