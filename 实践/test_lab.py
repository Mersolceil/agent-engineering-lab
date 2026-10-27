import copy
import json
from pathlib import Path
import tempfile
import unittest
from lab import ScriptedModel, new_state, run, load, search, strict_json
from metrics import cost, summarize


class RuntimeTests(unittest.TestCase):
    def test_resume_equivalence(self):
        baseline = run(new_state('alpha'), ScriptedModel())
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'s.json'
            paused = run(new_state('alpha'), ScriptedModel(), path, pause_after=1)
            self.assertEqual(paused['status'], 'running')
            resumed = run(load(path), ScriptedModel(), path)
            self.assertEqual(resumed['answer'], baseline['answer'])
            self.assertEqual(sum(m['role']=='tool' for m in resumed['messages']),1)
            # 终态重入不会重复行动
            self.assertEqual(run(resumed, ScriptedModel())['steps'], 2)

    def test_bad_input(self):
        for value in ['{"query":1}', '{"query":"alpha","extra":1}',
                      '{"query":"alpha","query":"beta"}', '{"query":NaN}']:
            with self.assertRaises(ValueError):
                search(strict_json(value), {})

    def test_unknown_tool(self):
        class Wrong(ScriptedModel):
            def query(self, state):
                return {'type':'call','name':'shell','arguments':'{}','call_id':'x'},None
        state = run(new_state('alpha',max_steps=1),Wrong())
        self.assertEqual(state['messages'][-1]['error']['code'],'PermissionError')
        self.assertEqual(state['status'],'budget_exhausted')

    def test_meter_does_not_double_count_reasoning(self):
        usage = {'input_tokens':1000,'output_tokens':200,
                 'input_tokens_details':{'cached_tokens':400},
                 'output_tokens_details':{'reasoning_tokens':100}}
        # 以下是合成费率，仅验证算式，不是市场价格
        self.assertAlmostEqual(cost(usage,{'input':2,'cached_input':1,'output':4}),.0024)
        self.assertIsNone(cost(None,{}))
        sample=new_state('alpha')
        sample.update(status='success',usage=[usage],elapsed_s=1.0,non_token_cost=.01)
        failed=copy.deepcopy(sample);failed['status']='model_error'
        result=summarize([sample,failed],{'input':2,'cached_input':1,'output':4})
        self.assertAlmostEqual(result['cost_per_success'],.0048)
        self.assertAlmostEqual(result['total_cost_per_success'],.0248)
        failed.pop('non_token_cost')
        self.assertIsNone(summarize([sample,failed],{'input':2,'cached_input':1,'output':4})['total_cost_all_categories'])

    def test_early_finish_and_loop(self):
        self.assertEqual(run(new_state('alpha'),ScriptedModel('early'))['status'],'rejected_final')
        self.assertEqual(run(new_state('alpha'),ScriptedModel('loop'))['status'],'repeat_limit')

    def test_paid_parse_failure_is_metered(self):
        class BadModel(ScriptedModel):
            def query(self,state):
                state['_last_usage']={'input_tokens':10,'output_tokens':4}
                raise ValueError('parse error after paid call')
        result=run(new_state('alpha'),BadModel())
        self.assertEqual(result['status'],'model_error')
        self.assertEqual(result['usage'][0]['output_tokens'],4)


# 可由 unittest discover 加载；下面验证真实适配器的本地 wire 映射，不发网络请求。
from unittest.mock import patch
from lab import OpenAIModel, verify
from live_benchmark import architecture


class ProtocolTests(unittest.TestCase):
    def test_invalid_final_field_rejected(self):
        self.assertFalse(verify({'owner':'林','status':'通过','citation':[], 'quote':'abcdefgh'},[], 'alpha'))

    def test_responses_wire_and_usage(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self):
                return json.dumps({'status':'completed','output':[
                    {'type':'reasoning','id':'r','summary':[]},
                    {'type':'function_call','name':'search','arguments':'{"query":"alpha"}',
                     'call_id':'call-1','id':'fc-1'}],
                    'usage':{'input_tokens':20,'output_tokens':10}}).encode()
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fixture-secret'}), \
             patch('urllib.request.urlopen',return_value=Response()) as fake:
            model=OpenAIModel('fixture-model')
            state=new_state('alpha')
            action,usage=model.query(state)
            self.assertEqual(action['call_id'],'call-1')
            self.assertEqual(action['wire'][0]['type'],'reasoning')
            self.assertEqual(usage['output_tokens'],10)
            payload=json.loads(fake.call_args[0][0].data)
            self.assertFalse(payload['store'])
            self.assertFalse(payload['parallel_tool_calls'])
            state['messages'] += [{'role':'assistant','wire':action['wire']},
                                  {'role':'tool','call_id':'call-1','ok':True,'data':[]}]
            model.query(state)
            payload=json.loads(fake.call_args[0][0].data)
            self.assertEqual(payload['input'][-1]['type'],'function_call_output')
            self.assertEqual(payload['input'][-1]['call_id'],'call-1')
            self.assertEqual(payload['input'][1]['type'],'reasoning')

    def test_three_architectures_offline(self):
        class FakeProvider:
            def query(self,state):
                topics=['alpha','beta'] if 'alpha' in state['topic'] and 'beta' in state['topic'] else [state['topic']]
                observed={d['id']:d for m in state['messages'] if m['role']=='tool' and m['ok'] for d in m['data']}
                gold={'alpha':('D1','林','通过'), 'beta':('D2','陈','待审')}
                for topic in topics:
                    if gold[topic][0] not in observed:
                        action={'type':'call','name':'search','arguments':json.dumps({'query':topic}),
                                'call_id':'fake-'+topic}
                        action['wire']=[{'type':'function_call','name':'search','arguments':action['arguments'],
                                         'call_id':action['call_id']}]
                        return action,{'input_tokens':10,'output_tokens':10}
                answer={t:{'owner':gold[t][1],'status':gold[t][2],'citation':gold[t][0],
                           'quote':observed[gold[t][0]]['text']} for t in topics}
                return {'type':'final','answer':answer if len(topics)>1 else answer[topics[0]],'wire':[]}, {'input_tokens':10,'output_tokens':10}
        outputs=[architecture(FakeProvider(),m,6) for m in ('workflow','single','multi')]
        self.assertTrue(all(r['status']=='success' for r in outputs))
        self.assertEqual([r['steps'] for r in outputs],[1,3,4])
        self.assertTrue(all(len(r['usage'])==r['steps'] for r in outputs))


if __name__=='__main__':
    unittest.main(verbosity=2)
