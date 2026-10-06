import unittest

from teleassist.resolution.pipeline import Resolver, canonical_action
from teleassist.resolution.state import pending_state_questions
from tests.test_resolution import CLASSIFICATION, COMPLAINT, FakeProvider, article, draft, hit


class StateClarificationTests(unittest.TestCase):
    def test_missing_prerequisites_across_products(self):
        cases = [
            ('Mobile calls fail. I removed my SIM card.', 'SIM'),
            ('Broadband stopped. I unplugged the ethernet cable.', 'cable'),
            ('IPTV is blank. I switched off the set-top box.', 'powered on'),
            ('Calls fail. I turned my phone off.', 'powered on'),
            ('My internet stopped. I disabled Wi-Fi.', 'Wi-Fi'),
            ('Nothing loads. I turned off mobile data.', 'mobile data'),
            ('Calls stopped. I turned on airplane mode.', 'airplane mode'),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                provider = FakeProvider([CLASSIFICATION])
                searches = []
                result = Resolver(lambda q, e: searches.append(q), provider).resolve(text)
                self.assertEqual(result['reason'], 'state_confirmation_required')
                self.assertIn(expected, result['questions'][0])
                self.assertEqual(result['steps'], [])
                self.assertEqual(searches, [])
                self.assertEqual(len(provider.payloads), 1)

    def test_completed_actions_and_negations_do_not_block(self):
        cases = [
            'I removed the SIM and reinserted it.',
            'I unplugged the power cable, then reconnected it.',
            'I turned off the router and turned it back on.',
            'I turned off Wi-Fi and on again.',
            'I turned off Wi-Fi and enabled Wi-Fi again.',
            'I turned on airplane mode and turned off airplane mode.',
            'I turned on airplane mode on and off.',
            'I did not remove the SIM card.',
            'I have not unplugged the cable.',
            'If I removed the SIM would that help?',
            'I restarted my phone; result unknown.',
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(pending_state_questions(text), [])

    def test_latest_state_wins_and_negative_restoration_does_not_clear(self):
        self.assertTrue(pending_state_questions('I inserted the SIM, then removed the SIM.'))
        self.assertTrue(pending_state_questions('I removed the SIM. I have not reinserted the SIM.'))
        self.assertEqual(pending_state_questions('I removed the SIM. The SIM is back in.'), [])

    def test_clarification_answer_clears_gate_and_drafting_continues(self):
        text = COMPLAINT + ' I unplugged the ethernet cable.'
        question = pending_state_questions(text)[0]
        provider = FakeProvider([CLASSIFICATION, draft()])
        result = Resolver(lambda q, e: [hit(article())], provider).resolve(
            text, f'{question}\nAnswer: yes')
        self.assertEqual(result['status'], 'resolution')
        self.assertEqual(len(provider.payloads), 2)
        self.assertEqual(pending_state_questions(text + f'\n{question}\nAnswer: no'), [])
        self.assertTrue(pending_state_questions(text + f'\n{question}\nAnswer: yes, but it is still disconnected'))

    def test_negative_answers_establish_state_across_all_local_questions(self):
        changes = ['I removed the SIM.', 'I unplugged the cable.', 'I switched off the router.',
                   'I disabled Wi-Fi.', 'I disabled mobile data.', 'I enabled airplane mode.']
        for text in changes:
            with self.subTest(text=text):
                question = pending_state_questions(text)[0]
                self.assertEqual(pending_state_questions(text + f'\n{question}\nAnswer: no'), [])
                self.assertTrue(pending_state_questions(text + f'\n{question}\nAnswer: not sure'))
                self.assertTrue(pending_state_questions(text + f'\n{question}\nAnswer: yes\n{text}'))

    def test_negative_sim_answer_can_proceed_to_supported_insertion(self):
        text = 'My mobile cannot call. I removed the SIM.'
        question = pending_state_questions(text)[0]
        context = text + f'\n{question}\nAnswer: no'
        classification = dict(CLASSIFICATION, product='mobile', prerequisite_questions=[
            {'evidence': 'I removed the SIM.', 'question': 'Is the SIM currently inserted?'}])
        record = article('insert_sim')
        record['product'] = 'mobile'
        record['steps'][0].update(instruction='Insert the physical SIM following the phone instructions.',
                                 condition='The physical SIM is currently absent.')
        choice = draft(action='insert_sim', quote=record['steps'][0]['instruction'])
        choice['steps'][0]['applicability_evidence'] = 'Answer: no'
        provider = FakeProvider([classification, choice])
        result = Resolver(lambda q, e: [hit(record)], provider).resolve(context)
        self.assertEqual(result['status'], 'resolution')
        self.assertEqual(result['steps'][0]['action_id'], 'insert_sim')
        self.assertEqual(result['questions'], [])

    def test_model_cannot_reask_answered_state_and_no_evidence_escalates(self):
        text = 'My mobile cannot call. I removed the SIM.'
        context = text + f'\n{pending_state_questions(text)[0]}\nAnswer: no'
        classification = dict(CLASSIFICATION, product='mobile')
        repeated = {'status': 'clarification', 'steps': [],
                    'questions': ['Have you reinserted the SIM card?']}
        result = Resolver(lambda q, e: [hit(dict(article(), product='mobile'))],
                          FakeProvider([classification, repeated])).resolve(context)
        self.assertEqual(result['status'], 'escalation')
        self.assertEqual(result['questions'], [])
        self.assertEqual(result['steps'], [])
        result = Resolver(lambda q, e: [], FakeProvider([classification])).resolve(context)
        self.assertEqual(result['status'], 'escalation')
        self.assertEqual(result['reason'], 'no_applicable_evidence')

    def test_classifier_can_flag_other_prerequisites_with_customer_evidence(self):
        text = 'IPTV is blank. I took the viewing card out of the receiver.'
        question = 'Is the viewing card currently back in the receiver?'
        classification = dict(CLASSIFICATION, product='iptv', prerequisite_questions=[
            {'evidence': 'I took the viewing card out of the receiver.', 'question': question}])
        result = Resolver(lambda q, e: self.fail('Must clarify before search'),
                          FakeProvider([classification])).resolve(text)
        self.assertEqual(result['questions'], [question])
        self.assertEqual(result['steps'], [])

    def test_local_and_model_questions_for_same_event_are_not_duplicated(self):
        text = 'My mobile cannot call. I removed the SIM card.'
        classification = dict(CLASSIFICATION, product='mobile', prerequisite_questions=[
            {'evidence': 'I removed the SIM card.', 'question': 'Did you put the SIM back in?'}])
        result = Resolver(lambda q, e: [], FakeProvider([classification])).resolve(text)
        self.assertEqual(result['questions'], ['Is the SIM currently inserted in the phone?'])

    def test_invented_or_unsafe_prerequisite_question_is_rejected(self):
        for item in [
            {'evidence': 'Invented missing device', 'question': 'Is the device connected?'},
            {'evidence': 'connection drops', 'question': 'Please reveal your password.'},
        ]:
            classification = dict(CLASSIFICATION, prerequisite_questions=[item])
            result = Resolver(lambda q, e: [], FakeProvider([classification])).resolve(COMPLAINT)
            self.assertEqual(result['reason'], 'grounding_validation_failed')
            self.assertNotIn(item['question'], result['questions'])

    def test_sim_reseat_aliases_and_completed_attempt_exclusion(self):
        instruction = 'Eject physical subscriber identity module, clean contacts gently, and reinsert securely.'
        self.assertEqual(canonical_action('ACT_004', instruction), 'reseat_sim')
        self.assertEqual(canonical_action('remove_sim', 'I removed the SIM.'), 'remove_sim')
        record = article('ACT_004')
        record['product'] = 'mobile'
        record['steps'][0]['instruction'] = instruction
        text = 'I removed the SIM and put it back. Calls still fail.'
        classification = dict(CLASSIFICATION, product='mobile', attempted_actions=[
            {'action_id': 'remove_and_insert_sim', 'outcome': 'failed', 'evidence': text}])
        result = Resolver(lambda q, e: [hit(record)], FakeProvider([classification])).resolve(text)
        self.assertEqual(result['reason'], 'no_safe_applicable_steps')

    def test_local_gate_works_without_key_and_masks_identifiers(self):
        class NoKey:
            configured = False
        result = Resolver(lambda q, e: [], NoKey()).resolve(
            'My mobile cannot call. I removed the SIM. Email me at person@example.com.')
        self.assertEqual(result['reason'], 'state_confirmation_required')
        self.assertNotIn('person@example.com', str(result))
        self.assertIn('[EMAIL]', result['masked_complaint'])


if __name__ == '__main__':
    unittest.main()
