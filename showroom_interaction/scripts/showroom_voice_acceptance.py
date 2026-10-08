#!/usr/bin/env python3
"""
End-to-end voice/LLM acceptance for the showroom interaction layer.

It publishes the fixed visitor command set on the same topic the ASR node
feeds (``/showroom/user_text``) and records the whole pipeline for each line:

* the recognised intent and reply (from ``/showroom/assistant_text``),
* whether a whitelisted command was dispatched, and which one,
* whether the task manager acknowledged it (on ``/showroom/response``),
* the first-response latency.

Run it against the Mock backend for a fully offline pass, or against the local
Qwen (Ollama) backend for the external-model pass. A Qwen run with an
unreachable endpoint exercises the error-handling path. The harness prints a
table and writes one JSON report, so all four cases (Mock / Qwen / offline /
Ollama-unavailable) can be diffed.
"""

import argparse
import json
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


DEFAULT_CASES = [
    {'text': '开始导览', 'intent': 'start_tour'},
    {'text': '暂停一下', 'intent': 'pause_tour'},
    {'text': '继续参观', 'intent': 'resume_tour'},
    {'text': '跳过这个展厅', 'intent': 'skip_current'},
    {'text': '去机器人展厅', 'intent': 'temporary_visit'},
    {'text': '给机器人展厅送咖啡', 'intent': 'deliver_drink'},
    {'text': '在机器人展厅停留二十秒', 'intent': 'temporary_visit'},
    {'text': '返回原路线', 'intent': 'resume_tour'},
    {'text': '取消全部', 'intent': 'cancel_all'},
    {'text': '执行一个三步骤计划', 'intent': 'execute_plan'},
]


def transient_qos():
    """Return the durable QoS used by the assistant/status topics."""
    return QoSProfile(
        depth=50,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


class VoiceAcceptance(Node):
    """Drive one command set through the LLM bridge and record the pipeline."""

    def __init__(self, options):
        super().__init__('showroom_voice_acceptance')
        self.options = options
        self.assistant = []
        self.responses = []
        self.bridge_status = {}

        self.text_publisher = self.create_publisher(
            String, options.user_topic, 10)
        self.create_subscription(
            String, options.assistant_topic, self.on_assistant, transient_qos())
        self.create_subscription(
            String, options.response_topic, self.on_response, 10)
        self.create_subscription(
            String, options.status_topic, self.on_status, transient_qos())
        self.get_logger().info(
            f'Voice acceptance ready: user_topic={options.user_topic}, '
            f'backend_label={options.backend_label}')

    @staticmethod
    def parse(message):
        try:
            document = json.loads(message.data)
        except (json.JSONDecodeError, TypeError):
            return {}
        return document if isinstance(document, dict) else {}

    def on_assistant(self, message):
        document = self.parse(message)
        document['received_at'] = time.monotonic()
        self.assistant.append(document)

    def on_response(self, message):
        self.responses.append(self.parse(message))

    def on_status(self, message):
        self.bridge_status = self.parse(message)

    def ask(self, case):
        """Send one utterance and return the recorded pipeline result."""
        before_assistant = len(self.assistant)
        before_response = len(self.responses)
        sent_at = time.monotonic()
        message = String()
        message.data = case['text']
        self.text_publisher.publish(message)

        deadline = sent_at + self.options.timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if len(self.assistant) > before_assistant:
                break

        # Give the task manager a moment to acknowledge the dispatched command.
        settle = time.monotonic() + self.options.settle_sec
        while rclpy.ok() and time.monotonic() < settle:
            rclpy.spin_once(self, timeout_sec=0.05)

        result = {
            'text': case['text'],
            'expected_intent': case.get('intent'),
            'intent': None,
            'match': None,
            'reply': None,
            'command_dispatched': False,
            'command': None,
            'task_response': None,
            'latency_sec': None,
            'error': None,
        }
        if len(self.assistant) > before_assistant:
            response = self.assistant[before_assistant]
            result['intent'] = response.get('intent')
            result['reply'] = response.get('reply')
            result['command_dispatched'] = bool(
                response.get('command_dispatched'))
            result['command'] = response.get('command')
            result['latency_sec'] = round(
                response['received_at'] - sent_at, 3)
            if result['intent'] == 'error':
                result['error'] = response.get('reply')
        else:
            result['error'] = 'no assistant response before timeout'
            result['error'] = result['error'] or self.bridge_status.get(
                'last_error')
        if len(self.responses) > before_response:
            result['task_response'] = self.responses[-1]
        expected = result['expected_intent']
        if expected is not None:
            result['match'] = (result['intent'] == expected)
        return result

    def run(self):
        """Run every case in order and return the acceptance document."""
        results = [self.ask(case) for case in self.options.cases]
        matched = sum(1 for item in results if item['match'] is True)
        checked = sum(1 for item in results if item['match'] is not None)
        return {
            'backend': self.options.backend_label,
            'model': self.bridge_status.get('model'),
            'results': results,
            'matched': matched,
            'checked': checked,
            'total': len(results),
        }


def parse_args(argv=None):
    """Parse the command line for the voice acceptance harness."""
    parser = argparse.ArgumentParser(
        description='Run the fixed voice/LLM command set and record results.')
    parser.add_argument('--user-topic', default='/showroom/user_text')
    parser.add_argument('--assistant-topic', default='/showroom/assistant_text')
    parser.add_argument('--response-topic', default='/showroom/response')
    parser.add_argument('--status-topic', default='/showroom/llm_status')
    parser.add_argument('--backend-label', default='mock')
    parser.add_argument('--cases', default=None,
                        help='optional JSON file with [{"text","intent"}] cases')
    parser.add_argument('--timeout-sec', type=float, default=40.0)
    parser.add_argument('--settle-sec', type=float, default=0.5)
    parser.add_argument('--report', default='logs/acceptance/voice.json')
    options = parser.parse_args(argv)
    if options.cases:
        document = json.loads(Path(options.cases).read_text(encoding='utf-8'))
        options.cases = document
    else:
        options.cases = DEFAULT_CASES
    return options


def print_summary(document):
    """Print a compact pipeline table and a pass/fail line."""
    print('{:<22} {:<18} {:<16} {:<6} {:<9} {}'.format(
        'text', 'expected', 'intent', 'match', 'dispatch', 'latency'))
    for item in document['results']:
        print('{:<22} {:<18} {:<16} {:<6} {:<9} {}'.format(
            item['text'][:20],
            str(item['expected_intent']),
            str(item['intent']),
            str(item['match']),
            str(item['command_dispatched']),
            str(item['latency_sec']),
        ))
    print('matched {}/{} (checked {}/{})'.format(
        document['matched'], document['total'],
        document['checked'], document['total']))


def main(argv=None):
    """Entry point for the voice acceptance harness."""
    options = parse_args(argv)
    rclpy.init()
    node = VoiceAcceptance(options)
    # Let subscriptions latch before the first request.
    settle = time.monotonic() + 1.0
    while rclpy.ok() and time.monotonic() < settle:
        rclpy.spin_once(node, timeout_sec=0.1)
    document = node.run()
    path = Path(options.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    print_summary(document)
    print(f'report: {path}')
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0 if document['checked'] == 0 or document['matched'] == document[
        'checked'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
