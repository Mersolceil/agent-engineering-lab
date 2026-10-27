"""可回退图环境中的计划/反馈/重规划；纯代码搜索，不是模型规划性能测试。"""
from collections import deque
import json
from pathlib import Path

GRAPH={'S':['A','B'],'A':['G'],'B':['C'],'C':['G'],'G':[]}


def plan(start,known_blocked):
    queue=deque([(start,[])])
    seen={start}; expansions=0
    while queue:
        node,path=queue.popleft();expansions+=1
        if node=='G': return path,expansions
        for nxt in GRAPH[node]:
            if (node,nxt) not in known_blocked and nxt not in seen:
                seen.add(nxt);queue.append((nxt,path+[(node,nxt)]))
    return [],expansions


def episode(blocked,replanning,budget=4):
    state='S'; known=set(); trace=[]; total_expansions=0
    pending,n=plan(state,known);total_expansions+=n
    for step in range(budget):
        if not pending: break
        edge=pending.pop(0)
        ok=edge not in blocked
        trace.append({'step':step+1,'input_state':state,'action':list(edge),
                      'expected':edge[1],'observation':'moved' if ok else 'blocked'})
        if ok: state=edge[1]
        else:
            known.add(edge)
            if not replanning: break
            pending,n=plan(state,known);total_expansions+=n
        trace[-1]['output_state']=state
        trace[-1]['pending_plan']=[list(x) for x in pending]
        if state=='G': break
    return {'condition':'blocked_first_edge' if blocked else 'clean',
            'mode':'replan_on_feedback' if replanning else 'fixed_plan',
            'budget':budget,'action_calls':len(trace),'search_expansions':total_expansions,
            'final_state':state,'success':state=='G','trace':trace}


if __name__=='__main__':
    results=[episode(blocked,replan) for blocked in (set(),{('S','A')}) for replan in (False,True)]
    Path('results/planning.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False,indent=2))
