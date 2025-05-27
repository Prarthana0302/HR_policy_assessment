from django.contrib.auth.tokens import PasswordResetTokenGenerator
import re
import pdfplumber
import random

class CustomTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.password}"

custom_token_generator = CustomTokenGenerator()

def extract_questions_without_answers(filepath):
    questions = []
    with pdfplumber.open(filepath) as pdf:
        full_text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    raw_questions = re.split(r'\nQ\d+\.', full_text)
    for raw in raw_questions[1:]:
        q_match = re.search(r'(.*?)(A\..*?)(B\..*?)(C\..*?)(D\..*?)Answer:', raw, re.DOTALL)
        if q_match:
            question = {
                'text': q_match.group(1).strip(),
                'options': {
                    'A': q_match.group(2).strip(),
                    'B': q_match.group(3).strip(),
                    'C': q_match.group(4).strip(),
                    'D': q_match.group(5).strip(),
                }
            }
            questions.append(question)

    return questions


def extract_questions_with_answers(filepath):
    questions = []
    with pdfplumber.open(filepath) as pdf:
        full_text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    raw_questions = re.split(r'\nQ\d+\.', full_text)
    for raw in raw_questions[1:]:
        q_match = re.search(r'(.*?)(A\..*?)(B\..*?)(C\..*?)(D\..*?)(Answer:\s*([A-D]))', raw, re.DOTALL)
        if q_match:
            question = {
                'text': q_match.group(1).strip(),
                'options': {
                    'A': q_match.group(2).strip(),
                    'B': q_match.group(3).strip(),
                    'C': q_match.group(4).strip(),
                    'D': q_match.group(5).strip(),
                },
                'answer': q_match.group(6).strip()
            }
            questions.append(question)

    return questions