"""帳號欄位與密碼規則(README §4.11)。"""

import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# 學生:8 碼數字(例:13173207);教職員的員工編號長度不一,放寬為 4–20 碼英數字
STUDENT_NUMBER_PATTERN = r"^\d{8}$"
STAFF_ID_PATTERN = r"^[A-Za-z0-9]{4,20}$"

validate_student_number = RegexValidator(STUDENT_NUMBER_PATTERN, "學號應為 8 碼數字,例如 13173207")
validate_staff_id = RegexValidator(STAFF_ID_PATTERN, "員工編號應為 4–20 碼英數字")

# 中文(含擴充區與注音符號以外的常用字)、英文字母,以及姓名常見的空白、間隔號與連字號
NAME_PATTERN = r"^[一-鿿㐀-䶿A-Za-z][一-鿿㐀-䶿A-Za-z ·．・'\-]*$"
validate_person_name = RegexValidator(NAME_PATTERN, "姓名只能使用中文或英文字母,不可含數字或符號")


def validate_account_id(value: str, role: str) -> None:
    """依身分套用不同的帳號格式。學生一律 8 碼數字。"""
    if role == "student":
        validate_student_number(value)
    else:
        validate_staff_id(value)


class PasswordComplexityValidator:
    """密碼至少 6 碼,且須同時包含大寫英文字母與數字(README §4.11)。"""

    def __init__(self, min_length: int = 6):
        self.min_length = min_length

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.min_length:
            errors.append(f"密碼至少需要 {self.min_length} 個字元")
        if not re.search(r"[A-Z]", password):
            errors.append("密碼需要至少一個英文大寫字母")
        if not re.search(r"\d", password):
            errors.append("密碼需要至少一個數字")
        if errors:
            raise ValidationError(errors, code="password_too_weak")

    def get_help_text(self):
        return f"密碼至少 {self.min_length} 個字元,並且要包含英文大寫字母與數字。"
