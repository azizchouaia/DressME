from modules.m09_avatar_3d import mock
from modules.m09_avatar_3d.contract import RenderResponse

def test_render_mock_matches_contract():
    out = RenderResponse.model_validate(mock.render({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
