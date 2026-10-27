from __future__ import annotations

from app.models.enums import QuestionStatus


class TransitionError(ValueError):
    pass


QUESTION_TRANSITIONS: dict[QuestionStatus, set[QuestionStatus]] = {
    QuestionStatus.draft: {QuestionStatus.investigating},
    QuestionStatus.investigating: {
        QuestionStatus.supported,
        QuestionStatus.unsupported,
        QuestionStatus.open,
    },
    QuestionStatus.supported: {QuestionStatus.completed, QuestionStatus.investigating},
    QuestionStatus.unsupported: {QuestionStatus.completed, QuestionStatus.investigating},
    QuestionStatus.open: {QuestionStatus.completed, QuestionStatus.investigating},
    QuestionStatus.completed: {QuestionStatus.investigating},
}


def allowed_question_statuses(current: QuestionStatus) -> list[QuestionStatus]:
    return sorted(QUESTION_TRANSITIONS[current], key=lambda status: status.value)


def assert_question_transition(current: QuestionStatus, target: QuestionStatus) -> None:
    if current == target:
        return
    if target not in QUESTION_TRANSITIONS[current]:
        raise TransitionError("That status change is not available")
