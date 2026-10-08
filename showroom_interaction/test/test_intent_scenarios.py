#!/usr/bin/env python3
"""
Data-driven intent regression suite for the showroom language layer.

Each case runs the same pipeline as `showroom_llm_bridge`: Mock model output,
then the multi-task and semantic normalizers, then contract validation. The
table intentionally mixes correct phrasing, synonyms, nicknames, ordinals,
homophones and typos so alias changes cannot silently regress.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_llm_contract import (  # noqa: E402
    command_from_result,
    extract_json_object,
    validate_model_result,
)
from showroom_llm_core import MockBackend  # noqa: E402
from showroom_llm_prompt import (  # noqa: E402
    build_messages,
    normalize_multi_task_result,
    normalize_semantic_result,
)


def infer(text):
    """Run the full text -> command pipeline used by the bridge."""
    backend = MockBackend()
    document = extract_json_object(backend.complete(build_messages(text)))
    document = normalize_multi_task_result(document, text)
    document = normalize_semantic_result(document, text)
    result = validate_model_result(document)
    return result['intent'], command_from_result(result)


def delivery(drink, target):
    return {'intent': 'deliver_drink', 'drink': drink, 'target': target}


def visit(target, dwell=0.0):
    return {
        'intent': 'temporary_visit', 'target': target,
        'dwell_sec': dwell, 'timeout_sec': 300.0,
    }


def meet(target, dwell=0.0):
    return {
        'intent': 'rendezvous', 'target': target,
        'dwell_sec': dwell, 'timeout_sec': 300.0,
    }


def robot(robot_id, action, duration=None):
    command = {
        'intent': 'robot_action', 'robot': robot_id, 'action': action}
    if duration is not None:
        command['duration_sec'] = float(duration)
    return command


# (text, expected_intent, expected_command)
CASES = [
    # --- delivery: correct phrasing, synonyms, ordinals ---
    ('送咖啡到第一个场馆', 'deliver_drink', delivery('coffee', 'technology_history')),
    ('去送几杯咖啡去第一场馆', 'deliver_drink', delivery('coffee', 'technology_history')),
    ('送杯水到计算机视觉展厅', 'deliver_drink', delivery('water', 'vision_hall')),
    ('送果汁去休息区', 'deliver_drink', delivery('juice', 'lounge')),
    ('把咖啡送到第三个展区', 'deliver_drink', delivery('coffee', 'robotics_hall')),
    ('麻烦给机器人馆送一杯咖啡', 'deliver_drink', delivery('coffee', 'robotics_hall')),
    ('送咖啡到最后一个场馆', 'deliver_drink', delivery('coffee', 'lounge')),
    # --- delivery: homophones and typos ---
    ('送杯咖非到第一场馆', 'deliver_drink', delivery('coffee', 'technology_history')),
    ('送杯咖妃到视觉管', 'deliver_drink', delivery('coffee', 'vision_hall')),
    ('送杯水到视觉关', 'deliver_drink', delivery('water', 'vision_hall')),
    ('送饮料到机器臂馆', 'deliver_drink', delivery('drink', 'robotics_hall')),
    ('送杯果汁到时空随道', 'deliver_drink', delivery('juice', 'time_tunnel')),
    ('送杯饮料到舞稻厅', 'deliver_drink', delivery('drink', 'dance_hall')),
    ('送咖啡到休息去', 'deliver_drink', delivery('coffee', 'lounge')),
    # --- delivery: no venue -> current exhibit; vague -> request_coffee ---
    ('带几杯咖啡来', 'deliver_drink', delivery('coffee', 'current_task')),
    ('送杯咖啡过来', 'deliver_drink', delivery('coffee', 'current_task')),
    ('给我一杯咖啡', 'request_coffee', {'intent': 'request_coffee'}),
    ('来杯咖啡', 'request_coffee', {'intent': 'request_coffee'}),
    # --- travel / temporary visit ---
    ('我想先去时空隧道', 'temporary_visit', visit('time_tunnel')),
    ('带我去时空隧道', 'temporary_visit', visit('time_tunnel')),
    ('我想先去视觉馆', 'temporary_visit', visit('vision_hall')),
    ('去机器人馆看看', 'temporary_visit', visit('robotics_hall')),
    ('前往休息区', 'temporary_visit', visit('lounge')),
    ('到第三个场馆待30秒', 'temporary_visit', visit('robotics_hall', 30.0)),
    ('在机器人展厅停留二十秒', 'temporary_visit',
     visit('robotics_hall', 20.0)),
    ('带我去隧道待三十秒', 'temporary_visit', visit('time_tunnel', 30.0)),
    # --- rendezvous (two robots meet) ---
    ('两个机器人在第二场馆会和', 'rendezvous', meet('vision_hall')),
    ('两台机器人去视觉馆集合', 'rendezvous', meet('vision_hall')),
    ('两个机器人在时空隧道碰头待30秒', 'rendezvous', meet('time_tunnel', 30.0)),
    ('两台机器人去机器人馆会合', 'rendezvous', meet('robotics_hall')),
    # --- robot control: nicknames + durations ---
    ('送餐机器人暂停10秒', 'robot_action', robot('coffee', 'pause', 10)),
    ('咖啡机器人继续', 'robot_action', robot('coffee', 'resume')),
    ('绿色机器人暂停', 'robot_action', robot('coffee', 'pause')),
    ('服务机器人暂停20秒', 'robot_action', robot('coffee', 'pause', 20)),
    ('蓝色机器人绕过障碍', 'robot_action', robot('guide', 'bypass_obstacle')),
    ('两台机器人暂停', 'robot_action', robot('all', 'pause')),
    ('导览机器人先停一下', 'pause_tour', {'intent': 'pause_tour'}),
    # --- tour control ---
    ('开始导览', 'start_tour', {'intent': 'start_tour', 'coffee': True}),
    ('开始导览，不需要咖啡', 'start_tour', {'intent': 'start_tour', 'coffee': False}),
    ('暂停一下', 'pause_tour', {'intent': 'pause_tour'}),
    ('继续参观', 'resume_tour', {'intent': 'resume_tour'}),
    ('返回原路线', 'resume_tour', {'intent': 'resume_tour'}),
    ('临时任务结束，回到原路线', 'resume_tour', {'intent': 'resume_tour'}),
    ('跳过这个展厅', 'skip_current', {'intent': 'skip_current'}),
    ('下个展区', 'next_task', {'intent': 'next_task'}),
    ('这里没兴趣，跳过', 'skip_current', {'intent': 'skip_current'}),
    ('这个展区再来一遍', 'repeat_current', {'intent': 'repeat_current'}),
    ('取消全部', 'cancel_all', {'intent': 'cancel_all'}),
    ('系统重置', 'reset', {'intent': 'reset'}),
    # --- multi-task plans ---
    ('多待30秒，再送杯水来', 'execute_plan', {
        'intent': 'execute_plan',
        'plan': [
            {'action': 'pause', 'robot': 'guide', 'duration_sec': 30.0},
            {'action': 'deliver_drink', 'drink': 'water',
             'target': 'current_task'},
        ]}),
    ('只看视觉馆和舞蹈馆', 'visit_only',
     {'intent': 'visit_only', 'tasks': ['vision_hall', 'dance_hall']}),
    ('跳过舞蹈馆', 'skip_task',
     {'intent': 'skip_task', 'tasks': ['dance_hall']}),
    ('我只看视觉馆，并送一杯咖啡到视觉馆', 'execute_plan', {
        'intent': 'execute_plan',
        'plan': [
            {'action': 'visit_only', 'tasks': ['vision_hall']},
            {'action': 'deliver_drink', 'drink': 'coffee',
             'target': 'vision_hall'},
        ]}),
    ('执行一个三步骤计划', 'execute_plan', {
        'intent': 'execute_plan',
        'plan': [
            {'action': 'temporary_visit', 'target': 'robotics_hall',
             'dwell_sec': 10.0, 'timeout_sec': 300.0},
            {'action': 'deliver_drink', 'drink': 'coffee',
             'target': 'lounge'},
            {'action': 'announce', 'text': '三步骤计划已完成。'},
        ]}),
    # --- status and chat (no command) ---
    ('机器人现在到哪了', 'ask_status', None),
    ('机器人在时空隧道了吗', 'ask_status', None),
    ('详细讲讲为什么它能避障', 'explain_more', {'intent': 'explain_more'}),
    ('你好呀', 'chat', None),
]


def main():
    failures = []
    for text, expected_intent, expected_command in CASES:
        intent, command = infer(text)
        if intent != expected_intent or command != expected_command:
            failures.append(
                f'{text!r}: got ({intent}, {command}), '
                f'expected ({expected_intent}, {expected_command})')
    if failures:
        for failure in failures:
            print('FAIL', failure)
        raise AssertionError(f'{len(failures)} intent case(s) failed')
    print(f'Showroom intent scenarios: OK ({len(CASES)} cases)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
