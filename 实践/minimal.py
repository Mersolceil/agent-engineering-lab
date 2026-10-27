"""第 1 关：确定性策略替身演示闭环，不宣称是语言模型。"""
import json


def model(messages):
    if messages[-1]['role'] == 'user':
        return {'tool': 'add', 'args': {'a': 2, 'b': 3}}
    return {'answer': str(messages[-1]['result'])}


def main():
    messages = [{'role': 'user', 'content': '计算 2+3'}]
    for _ in range(3):
        action = model(messages)
        messages.append({'role': 'assistant', 'action': action})
        if 'answer' in action:
            print(json.dumps(messages, ensure_ascii=False, indent=2))
            return
        # 此处故意简单，第 2 关会加入校验、白名单和验收。
        result = action['args']['a'] + action['args']['b']
        messages.append({'role': 'tool', 'result': result})
    raise RuntimeError('budget exhausted')


if __name__ == '__main__':
    main()
