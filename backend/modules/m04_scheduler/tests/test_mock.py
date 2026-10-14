from modules.m04_scheduler import mock
from modules.m04_scheduler.contract import ScheduleResponse, CalendarResponse

def test_schedule_mock_matches_contract():
    out = ScheduleResponse.model_validate(mock.schedule({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_calendar_mock_matches_contract():
    out = CalendarResponse.model_validate(mock.calendar({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
