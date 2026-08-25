from dataclasses import fields

from miniatured_world.activity import ActivitySource, KeyboardCategory, PointerCategory, PrivacyFilter


def test_keyboard_filter_keeps_only_category() -> None:
    event = PrivacyFilter().keyboard("super_secret_password", 100)

    assert event.category == KeyboardCategory.OTHER.value
    assert event.timestamp_ms == 100
    assert "super_secret_password" not in repr(event)

    field_names = {field.name for field in fields(event)}
    assert "key" not in field_names
    assert "raw" not in field_names
    assert "text" not in field_names


def test_pointer_filter_keeps_delta_magnitude_not_coordinates() -> None:
    event = PrivacyFilter().pointer_move(300, 400, 120)

    assert event.category == PointerCategory.MOVE.value
    assert 0.0 < event.magnitude <= 1.0

    field_names = {field.name for field in fields(event)}
    assert "x" not in field_names
    assert "y" not in field_names
    assert "position" not in field_names


def test_direct_interaction_is_marked_for_aggregator_exclusion() -> None:
    event = PrivacyFilter().keyboard("z", 100, source=ActivitySource.DIRECT)

    assert event.source == ActivitySource.DIRECT
