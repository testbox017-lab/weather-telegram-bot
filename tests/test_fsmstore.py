import pytest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey

from fsmstore import MAX_AGE, JsonFileStorage


class Ask(StatesGroup):
    place = State()


KEY = StorageKey(bot_id=1, chat_id=42, user_id=42)


@pytest.mark.asyncio
async def test_state_survives_restart(tmp_path):
    f = tmp_path / "fsm.json"
    s = JsonFileStorage(f)
    await s.set_state(KEY, Ask.place)
    await s.update_data(KEY, {"prompt": 777, "name": "Бахмач"})
    again = JsonFileStorage(f)
    assert await again.get_state(KEY) == "Ask:place"
    assert await again.get_data(KEY) == {"prompt": 777, "name": "Бахмач"}
    await again.set_state(KEY, None)
    await again.set_data(KEY, {})
    assert await JsonFileStorage(f).get_state(KEY) is None and f.read_text() == "[]"


@pytest.mark.asyncio
async def test_old_questions_are_dropped(tmp_path):
    f = tmp_path / "fsm.json"
    s = JsonFileStorage(f)
    await s.set_state(KEY, Ask.place)
    import time

    assert await JsonFileStorage(f, now=time.time() + MAX_AGE + 60).get_state(KEY) is None


def test_broken_file_is_ignored(tmp_path):
    f = tmp_path / "fsm.json"
    f.write_text("не json", encoding="utf-8")
    assert JsonFileStorage(f).storage == {}
