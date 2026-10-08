#!/usr/bin/env python3
"""Prompt and compact context configuration for the showroom intent model."""

import json
import re


# Fuzzy fallback catches substitution typos and ASR slips ("视觉关" ~ "视觉馆")
# while the alias list stays small. A window of the alias length slides over the
# text; only position-wise near-matches count, so a shift like "始导览" does not
# spuriously match "导览车".
FUZZY_RATIO = 0.66

MEET_WORDS = ('会和', '会合', '集合', '碰头', '碰面', '汇合', '会面')


PLACE_ALIASES = (
    (('计算机视觉馆', '计算机视觉展厅', '视觉馆', '视觉展厅', '视觉区',
      '图像馆', '视觉识别区'),
     'vision_hall'),
    (('智能机器人馆', '智能机器人展厅', '机器人馆', '机器人展厅', '机器人区',
      '机械臂馆', '机器臂馆', '机器臂场馆', '机械臂展厅', '机器人场馆'),
     'robotics_hall'),
    (('科技发展历史展区', '科技历史馆', '历史馆', '历史展区', '科技发展史',
      '发展历史馆', '科技史'),
     'technology_history'),
    (('时空科技隧道', '时空隧道', '科技隧道', '时光隧道', '隧道',
      '遂道', '随道'),
     'time_tunnel'),
    (('科技舞蹈展厅', '科技舞蹈馆', '舞蹈馆', '舞蹈展厅', '舞蹈厅',
      '数字艺术馆', '舞厅'),
     'dance_hall'),
    (('智能休息服务区', '咖啡休息区', '休息区', '休息室', '服务区', '休闲区'),
     'lounge'),
    (('入馆接待', '接待区', '入馆区', '入口', '门口', '前台'), 'reception'),
)

# Robot nicknames a visitor may use; all map to the contract robot targets.
ROBOT_ALIASES = (
    (('导览机器人', '蓝色机器人', '导游机器人', '讲解机器人', '导览车'),
     'guide'),
    (('服务机器人', '送餐机器人', '咖啡机器人', '配送机器人', '绿色机器人',
      '送咖啡机器人', '送饮料机器人'),
     'coffee'),
    (('两台机器人', '两个机器人', '所有机器人', '全部机器人', '机器人们'),
     'all'),
)

# Ordinals count the five exhibit halls, excluding reception and lounge.
EXHIBIT_ORDER = (
    'technology_history', 'vision_hall', 'robotics_hall',
    'time_tunnel', 'dance_hall',
)
ORDINAL_DIGITS = {
    '一': 1, '1': 1, '二': 2, '两': 2, '2': 2, '三': 3, '3': 3,
    '四': 4, '4': 4, '五': 5, '5': 5,
}


def _exact_present(text, aliases):
    return any(alias in text for alias in aliases)


def _fuzzy_present(text, aliases):
    """Return True when a position-wise near-match of any alias appears."""
    for alias in aliases:
        size = len(alias)
        if size < 2 or len(text) < size:
            continue
        for start in range(len(text) - size + 1):
            window = text[start:start + size]
            matches = sum(
                1 for a, b in zip(window, alias) if a == b)
            if matches / size >= FUZZY_RATIO:
                return True
    return False


DRINK_WORDS = (
    ('咖啡', 'coffee'), ('咖非', 'coffee'), ('咖妃', 'coffee'),
    ('加啡', 'coffee'), ('咖灰', 'coffee'),
    ('饮料', 'drink'), ('饮枓', 'drink'),
    ('果汁', 'juice'), ('果知', 'juice'),
    ('水', 'water'),
)


def detect_drink(text):
    """Return the canonical drink named in the sentence, or None."""
    for word, name in DRINK_WORDS:
        if word in text:
            return name
    for word, name in DRINK_WORDS:
        if len(word) >= 2 and _fuzzy_present(text, (word,)):
            return name
    return None


CHINESE_DIGITS = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9,
}


def parse_duration_sec(text):
    """Parse a duration like '30秒' or '三十秒' into seconds, or None."""
    match = re.search(r'(\d+(?:\.\d+)?)\s*秒', text)
    if match:
        return float(match.group(1))
    match = re.search(r'([零一二两三四五六七八九十]+)\s*秒', text)
    if not match:
        return None
    digits = match.group(1)
    if '十' in digits:
        head, _, tail = digits.partition('十')
        tens = CHINESE_DIGITS.get(head, 1) if head else 1
        ones = CHINESE_DIGITS.get(tail, 0) if tail else 0
        return float(tens * 10 + ones)
    total = 0
    for character in digits:
        total = total * 10 + CHINESE_DIGITS.get(character, 0)
    return float(total)


def _exact_task_ids(text):
    return [
        task_id for aliases, task_id in PLACE_ALIASES
        if _exact_present(text, aliases)
    ]


def _exact_robot_ids(text):
    return [
        robot for aliases, robot in ROBOT_ALIASES
        if _exact_present(text, aliases)
    ]


def robot_ids_in_text(text):
    """Return canonical robot targets mentioned in the sentence."""
    ids = _exact_robot_ids(text)
    if not ids and not _exact_task_ids(text):
        # Only fall back to fuzzy matching when nothing was recognized at all,
        # so a shared token like 机器人 cannot misfire between families.
        ids = [
            robot for aliases, robot in ROBOT_ALIASES
            if _fuzzy_present(text, aliases)
        ]
    return ids


def ordinal_task_id(text):
    """Resolve '第一个场馆' style ordinals over the five exhibit halls."""
    if '最后' in text:
        return 'lounge'
    match = re.search(
        r'第\s*([一二两三四五12345])\s*(?:个|号)?\s*'
        r'(?:场馆|展馆|展区|展厅|区|任务|站)?', text)
    if not match:
        return None
    index = ORDINAL_DIGITS.get(match.group(1))
    if index and 1 <= index <= len(EXHIBIT_ORDER):
        return EXHIBIT_ORDER[index - 1]
    return None


def task_ids_in_text(text):
    """Extract semantic task ids in configured showroom order."""
    ids = _exact_task_ids(text)
    if not ids and not _exact_robot_ids(text):
        ids = [
            task_id for aliases, task_id in PLACE_ALIASES
            if _fuzzy_present(text, aliases)
        ]
    ordinal = ordinal_task_id(text)
    if ordinal and ordinal not in ids:
        ids.append(ordinal)
    return ids


def normalize_semantic_result(document, user_text):
    """Make explicit place selection and bypass phrases deterministic."""
    if not isinstance(document, dict):
        return document
    text = str(user_text)
    tasks = task_ids_in_text(text)
    robots = robot_ids_in_text(text)
    reply = document.get('reply', '')
    intent = document.get('intent')
    # Repair robot targeting from nicknames: "送餐机器人暂停" must pause the
    # coffee robot, not fall back to the guide robot.
    if robots:
        if intent in ('pause_tour', 'resume_tour') and robots[0] in (
                'coffee', 'all'):
            repaired = {
                'intent': 'robot_action',
                'robot': robots[0],
                'action': 'pause' if intent == 'pause_tour' else 'resume',
                'reply': reply,
            }
            if 'duration_sec' in document:
                repaired['duration_sec'] = document['duration_sec']
            return repaired
        if intent == 'robot_action':
            repaired = dict(document)
            repaired['robot'] = robots[0]
            return repaired
    selection_request = any(
        word in text for word in ('只看', '只参观', '只去', '只逛'))
    skip_request = any(word in text for word in (
        '不看', '不参观', '不去', '别去', '跳过', '略过', '取消参观'))
    drink_name = detect_drink(text)
    drink_request = drink_name is not None
    delivery_request = any(word in text for word in (
        '送', '拿', '给', '带', '端', '来杯', '来几杯', '来一'))
    drink = drink_name or 'coffee'
    if tasks and (selection_request or skip_request) \
            and drink_request and delivery_request:
        return {
            'intent': 'execute_plan',
            'plan': [
                {
                    'action': 'visit_only' if selection_request else 'skip_task',
                    'tasks': tasks,
                },
                {
                    'action': 'deliver_drink',
                    'drink': drink,
                    'target': tasks[0],
                },
            ],
            'reply': reply,
        }
    if tasks and selection_request:
        return {'intent': 'visit_only', 'tasks': tasks, 'reply': reply}
    if tasks and skip_request:
        return {'intent': 'skip_task', 'tasks': tasks, 'reply': reply}
    if any(word in text for word in ('绕过障碍', '绕开障碍', '绕过去', '避开障碍')):
        return {
            'intent': 'robot_action',
            'robot': robots[0] if robots else 'guide',
            'action': 'bypass_obstacle', 'reply': reply}
    if tasks and drink_request and delivery_request and not any(
            word in text for word in (
                '多待', '多呆', '停留', '待一会', '呆一会', '再看看')):
        return {
            'intent': 'deliver_drink', 'drink': drink,
            'target': tasks[0], 'reply': reply}
    if tasks and any(word in text for word in MEET_WORDS):
        rendezvous = {
            'intent': 'rendezvous',
            'target': tasks[0],
            'reply': reply,
        }
        seconds = parse_duration_sec(text)
        if seconds is not None:
            rendezvous['dwell_sec'] = seconds
        return rendezvous
    travel_request = any(word in text for word in (
        '去', '到', '前往', '带我去', '带我到', '过去', '导航到')) and not any(
            word in text for word in (
                '到了吗', '到哪', '怎么去', '如何去', '多远', '多久',
                '吗', '呢', '?', '？'))
    if tasks and travel_request:
        result = {
            'intent': 'temporary_visit',
            'target': tasks[0],
            'reply': reply,
        }
        seconds = parse_duration_sec(text)
        stay_request = any(word in text for word in (
            '多待', '多呆', '停留', '待一会', '呆一会', '多看一会', '待', '呆'))
        if seconds is not None:
            result['dwell_sec'] = seconds
        elif stay_request:
            result['dwell_sec'] = 20.0
        return result
    stay_only = any(word in text for word in (
        '多待', '多呆', '停留', '待一会', '呆一会', '多看一会')) \
        and not drink_request
    if tasks and stay_only:
        result = {
            'intent': 'temporary_visit',
            'target': tasks[0],
            'reply': reply,
        }
        seconds = parse_duration_sec(text)
        result['dwell_sec'] = seconds if seconds is not None else 20.0
        return result
    return document


def normalize_multi_task_result(document, user_text):
    """Repair common small-model omissions for stay-and-drink requests."""
    if not isinstance(document, dict):
        return document
    text = str(user_text)
    stay_request = any(word in text for word in (
        '多待', '多呆', '停留', '待一会', '呆一会', '再看看', '多看一会'))
    drink_request = detect_drink(text) is not None
    if not (stay_request and drink_request):
        return document

    duration_match = parse_duration_sec(text)
    pause = {'action': 'pause', 'robot': 'guide'}
    if duration_match:
        pause['duration_sec'] = duration_match
    drink = detect_drink(text) or 'coffee'
    target = 'current_task'
    for aliases, task_id in PLACE_ALIASES:
        if any(alias in text for alias in aliases):
            target = task_id
            break
    return {
        'intent': 'execute_plan',
        'plan': [
            pause,
            {
                'action': 'deliver_drink',
                'drink': drink,
                'target': target,
            },
        ],
        'reply': document.get('reply', ''),
    }


def ground_explanation_result(document, business):
    """Replace explanation prose with configured current-task knowledge."""
    if not isinstance(document, dict):
        return document
    intent = document.get('intent')
    field = {
        'explain_current': 'summary',
        'explain_more': 'detail',
    }.get(intent)
    if field is None:
        return document
    business = business if isinstance(business, dict) else {}
    current_task = business.get('current_task') or {}
    grounded_reply = current_task.get(field)
    if not isinstance(grounded_reply, str) or not grounded_reply.strip():
        return document
    result = dict(document)
    result['reply'] = grounded_reply.strip()
    return result


def compact_context(business, monitor):
    """Keep only state useful to a small local model."""
    business = business if isinstance(business, dict) else {}
    monitor = monitor if isinstance(monitor, dict) else {}
    robots = monitor.get('robots') or {}
    compact_robots = {}
    for robot_id in ('robot_0', 'robot_1'):
        robot = robots.get(robot_id) or {}
        feedback = robot.get('nav2_feedback') or {}
        compact_robots[robot_id] = {
            'navigation_state': robot.get('navigation_state'),
            'current_waypoint': robot.get('current_waypoint'),
            'obstacle_detected': robot.get('obstacle_detected'),
            'front_clearance_m': robot.get('front_clearance_m'),
            'block_count': robot.get('block_count'),
            'distance_remaining_m': feedback.get('distance_remaining_m'),
            'estimated_time_remaining_sec': feedback.get(
                'estimated_time_remaining_sec'),
            'nav2_recovery_count': feedback.get('number_of_recoveries'),
        }
    return {
        'business': {
            'guide_state': business.get('guide_state'),
            'coffee_state': business.get('coffee_state'),
            'coffee_requested': business.get('coffee_requested'),
            'coffee_trigger_reached': business.get('coffee_trigger_reached'),
            'human_override_active': business.get(
                'human_override_active'),
            'human_overrides': business.get('human_overrides'),
            'current_task': business.get('current_task'),
        },
        'robots': compact_robots,
    }


def build_messages(user_text, business=None, monitor=None, knowledge=None):
    """Build a short intent-classification prompt for Qwen3.5 4B."""
    context = compact_context(business, monitor)
    knowledge_text = knowledge or (
        '展馆包括入口、咖啡区、视觉展厅、机器人展厅、时空隧道、'
        '科技舞蹈展厅和休息区。')
    system = f"""你是科技展馆双机器人系统的中文意图分类器。
你只负责把游客原话转换成高层业务意图，绝不能生成速度、坐标或 cmd_vel 指令。

只允许以下 intent：
- start_tour：开始导览。可增加布尔字段 coffee，默认 true
- request_coffee：请求咖啡
- deliver_drink：把 drink 指定的饮料送到 target 指定场馆
- pause_tour：临时暂停蓝色导览机器人，可增加 duration_sec，默认 20 秒
- resume_tour：继续导览、返回原路线、回到原路线（临时任务结束后回到默认行程）
- cancel_all：取消全部任务
- reset：重置业务
- robot_action：控制指定机器人。robot 只能是 guide、coffee、all；action 只能是
  pause、resume、start_default、cancel、bypass_obstacle。pause 可增加 duration_sec，默认 20 秒
- skip_current：游客明确表示对当前展区没兴趣或要求跳过
- repeat_current：从当前任务单元起点重新执行一次
- next_task：正常结束当前内容并进入下一个任务单元
- skip_task：跳过一个或多个指定场馆，tasks 是稳定场馆 ID 数组
- visit_only：只参观指定场馆，tasks 是稳定场馆 ID 数组
- temporary_visit：临时前往 target 场馆，可带 dwell_sec 停留时间。到达或超时后恢复原导览
- rendezvous：两台机器人在 target 场馆会合，可带 dwell_sec 停留时间
- explain_current：讲解 current_task，必须用 summary 生成 reply
- explain_more：追问当前内容，必须用 detail 生成更详细的 reply
- execute_plan：一句话同时包含多个任务时使用。plan 是 2..8 个 action 的数组
  - pause：robot 为 guide、coffee 或 all，可带 duration_sec
  - resume：robot 为 guide、coffee 或 all
  - deliver_drink：drink 为 coffee、water、juice 或 drink；target 默认 current_task
  - skip_current、repeat_current、next_task
  - skip_task、visit_only：带 tasks 场馆 ID 数组
  - temporary_visit：带 target，可带 dwell_sec 和 timeout_sec
  - bypass_obstacle：robot 为 guide、coffee 或 all
  - announce：必须带 text
- ask_status：询问机器人位置、进度、障碍或任务状态
- chat：不属于上述业务命令

只输出一个 JSON 对象，不要输出 Markdown、思考过程或额外文字。
普通命令示例：{{"intent":"pause_tour"}}
开始导览示例：{{"intent":"start_tour","coffee":false}}
蓝色机器人等待示例：{{"intent":"pause_tour","duration_sec":20}}
绿色机器人等待示例：{{"intent":"robot_action","robot":"coffee","action":"pause","duration_sec":20}}
绿色机器人立即执行默认配送：{{"intent":"robot_action","robot":"coffee","action":"start_default"}}
跳过当前展区：{{"intent":"skip_current"}}
跳过指定展区：{{"intent":"skip_task","tasks":["robotics_hall"]}}
只看指定展区：{{"intent":"visit_only","tasks":["vision_hall","dance_hall"]}}
临时前往并停留：{{"intent":"temporary_visit","target":"time_tunnel","dwell_sec":20}}
两台机器人和：{{"intent":"rendezvous","target":"robotics_hall","dwell_sec":20}}
送到指定场馆：{{"intent":"deliver_drink","drink":"coffee","target":"robotics_hall"}}
绕过当前障碍：{{"intent":"robot_action","robot":"guide","action":"bypass_obstacle"}}
重新执行当前展区：{{"intent":"repeat_current"}}
讲解当前展区：{{"intent":"explain_current","reply":"根据 current_task.summary 生成的讲解"}}
深入讲解：{{"intent":"explain_more","reply":"根据 current_task.detail 生成的补充讲解"}}
多任务示例：{{"intent":"execute_plan","plan":[{{"action":"pause","robot":"guide","duration_sec":20}},{{"action":"deliver_drink","drink":"coffee","target":"current_task"}}]}}
三步骤计划示例：{{"intent":"execute_plan","plan":[{{"action":"temporary_visit","target":"robotics_hall","dwell_sec":10}},{{"action":"deliver_drink","drink":"coffee","target":"lounge"}},{{"action":"announce","text":"三步骤计划已完成。"}}]}}
除 explain_current 和 explain_more 外，reply 字段不是必需的。
讲解只能使用当前状态中的 current_task 内容，不得编造展品、数字或能力。
同一句话有两个及以上明确动作时，必须使用 execute_plan，不要只返回其中一个 intent。

展馆资料：{knowledge_text}
稳定场馆 ID：reception、technology_history、vision_hall、robotics_hall、time_tunnel、dance_hall、lounge。
当前系统状态：{json.dumps(context, ensure_ascii=False, separators=(',', ':'))}
"""
    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user_text.strip()},
    ]
