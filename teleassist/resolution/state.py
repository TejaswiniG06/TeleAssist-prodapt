"""Clarify common service-disabling changes until the current state is known.

These bounded rules supplement the classifier; they do not diagnose a cause.
The last explicit change wins, including answers from the clarification form.
"""
import re


SIM = r'(?:sim(?:\s+card)?|subscriber\s+identity\s+module)'
CABLE = r'(?:(?:power|ethernet|network|phone|wan)\s+)?(?:cable|cord|lead)'
DEVICE = r'(?:router|modem|ont|phone|set.top\s+box)'

# Each rule pairs an interrupted prerequisite with an explicit restored state.
RULES = [
    (rf'(?:removed|ejected|took\s+out)\s+(?:the\s+|my\s+)?{SIM}|{SIM}\s+(?:is\s+)?(?:still\s+)?(?:removed|out)',
     (rf'(?:reinserted|inserted|put)\s+(?:the\s+|my\s+)?{SIM}(?:\s+back)?'
      rf'|(?:reinserted|reseated)\s+it|put\s+(?:it|the\s+card)\s+back'
      rf'|{SIM}\s+is\s+(?:back\s+in|inserted)'),
     'Is the SIM currently inserted in the phone?'),
    (rf'(?:unplugged|disconnected|removed)\s+(?:the\s+|my\s+)?{CABLE}|{CABLE}\s+(?:is\s+)?(?:still\s+)?(?:unplugged|disconnected)',
     rf'(?:reconnected|plugged)\s+(?:the\s+|my\s+)?{CABLE}|{CABLE}\s+is\s+(?:connected|plugged\s+in)|plugged\s+it\s+back\s+in|reconnected\s+it',
     'Is the cable you disconnected currently connected again?'),
    ((rf'(?:turned|switched)\s+off\s+(?:the\s+|my\s+)?{DEVICE}'
      rf'|(?:turned|switched)\s+(?:the\s+|my\s+)?{DEVICE}\s+off'
      rf'|{DEVICE}\s+(?:is\s+)?(?:still\s+)?(?:off|powered\s+off)'),
     (rf'(?:turned|switched)\s+(?:the\s+|my\s+)?{DEVICE}\s+(?:back\s+)?on'
      rf'|(?:turned|switched)\s+(?:back\s+)?on\s+(?:the\s+|my\s+)?{DEVICE}'
      rf'|{DEVICE}\s+is\s+(?:back\s+)?on|turned\s+it\s+back\s+on'),
     'Is the device you switched off currently powered on?'),
    (r'(?:disabled|turned\s+off|switched\s+off)\s+(?:the\s+|my\s+)?wi[ -]?fi|wi[ -]?fi\s+is\s+(?:still\s+)?(?:off|disabled)',
     r'(?:enabled|turned\s+on|switched\s+on)\s+(?:the\s+|my\s+)?wi[ -]?fi|wi[ -]?fi\s+is\s+(?:back\s+)?(?:on|enabled)',
     'Is Wi-Fi currently enabled on the affected device?'),
    (r'(?:disabled|turned\s+off|switched\s+off)\s+(?:the\s+|my\s+)?mobile\s+data|mobile\s+data\s+is\s+(?:still\s+)?(?:off|disabled)',
     r'(?:enabled|turned\s+on|switched\s+on)\s+(?:the\s+|my\s+)?mobile\s+data|mobile\s+data\s+is\s+(?:back\s+)?(?:on|enabled)',
     'Is mobile data currently enabled?'),
    (r'(?:enabled|turned\s+on|switched\s+on)\s+(?:the\s+)?(?:airplane|flight)\s+mode|(?:airplane|flight)\s+mode\s+is\s+(?:still\s+)?on',
     r'(?:disabled|turned\s+off|switched\s+off)\s+(?:the\s+)?(?:airplane|flight)\s+mode|(?:airplane|flight)\s+mode\s+is\s+(?:now\s+)?off',
     'Is airplane mode currently switched off?'),
]


def positive_matches(pattern, text):
    """Yield event positions while ignoring nearby negation and hypothetical wording."""
    for match in re.finditer(r'\b(?:' + pattern + r')\b', text, re.I):
        prefix = text[max(0, match.start() - 35):match.start()]
        # Do not treat negation, a hypothetical or a quoted question as an event.
        if re.search(
            r"(?:not|never|haven't|hadn't|didn't|did not|have not"
            r'|if(?:\s+(?:i|we))?|should i|did you)\s+'
            r'(?:(?:yet|already|actually)\s+)?$',
            prefix, re.I,
        ):
            continue
        yield match.start()


def pending_state_questions(text):
    """Ask about interrupted prerequisites not clarified by a later state or answer."""
    questions = []
    for changed, restored, question in RULES:
        changes = list(positive_matches(changed, text))
        if not changes:
            continue
        # The UI appends the exact question followed by the customer's answer.
        confirmation = re.escape(question) + r'\s*Answer:\s*(?:yes|no)[.!]?\s*(?:\n|$)'
        restorations = list(positive_matches(restored, text))
        restorations.extend(m.start() for m in re.finditer(confirmation, text, re.I))
        # A complete off/on toggle in the same clause confirms restoration.
        if 'off' in changed and 'airplane' not in changed:
            for change in changes:
                clause = re.split(r'[.!?\n]', text[change:])[0]
                toggle = re.search(
                    r'\boff(?:\s+(?:the|my))?'
                    r'(?:\s+(?:wi[ -]?fi|mobile\s+data|router|modem|ont|phone|set.top\s+box))?'
                    r'\s+and\s+(?:back\s+)?on\b',
                    clause, re.I,
                )
                if toggle:
                    restorations.append(change + toggle.end())
        if 'airplane' in changed:
            for change in changes:
                clause = re.split(r'[.!?\n]', text[change:])[0]
                toggle = re.search(r'\bon\s+and\s+(?:back\s+)?off\b', clause, re.I)
                if toggle:
                    restorations.append(change + toggle.end())
        if not restorations or max(changes) > max(restorations):
            questions.append(question)
    return questions[:4]


def answered_state_questions(text):
    """A negative answer establishes state too; it does not establish recovery."""
    answered = set()
    for changed, _, question in RULES:
        pattern = re.escape(question) + r'\s*Answer:\s*(?:yes|no)[.!]?\s*(?:\n|$)'
        answers = [m.start() for m in re.finditer(pattern, text, re.I)]
        changes = list(positive_matches(changed, text))
        if answers and (not changes or max(answers) > max(changes)):
            answered.add(question)
    return answered


def repeats_answered_state(question, answered):
    """Catch common paraphrases of the six state questions, not unrelated questions."""
    signatures = [
        r'\bsim\b.*(?:insert|back|removed)|(?:insert|back|removed).*\bsim\b',
        r'\bcable\b.*(?:connect|plug)|(?:connect|plug).*\bcable\b',
        r'(?:device|router|phone|modem|ont|box).*(?:power|switched|turned).*(?:on|off)',
        r'wi[ -]?fi.*(?:enabled|disabled|on|off)',
        r'mobile\s+data.*(?:enabled|disabled|on|off)',
        r'(?:airplane|flight)\s+mode.*(?:enabled|disabled|on|off)',
    ]
    return any(stable in answered and (question == stable or re.search(pattern, question, re.I))
               for (_, _, stable), pattern in zip(RULES, signatures))
