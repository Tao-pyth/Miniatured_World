from miniatured_world.activity import ActivityAggregator, ActivitySource, PrivacyFilter


def test_aggregator_produces_normalized_frame() -> None:
    privacy = PrivacyFilter()
    aggregator = ActivityAggregator(frame_window_ms=1000)

    for index in range(12):
        aggregator.add(privacy.keyboard("a", index * 40))
    aggregator.add(privacy.pointer_move(250, 0, 500))
    aggregator.add(privacy.pointer_click(520))
    aggregator.add(privacy.pointer_scroll(600, 540))

    frame = aggregator.frame(1000)

    assert 0.0 <= frame.keyboard_activity <= 1.0
    assert 0.0 <= frame.pointer_activity <= 1.0
    assert 0.0 <= frame.click_activity <= 1.0
    assert 0.0 <= frame.scroll_activity <= 1.0
    assert 0.0 <= frame.burstiness <= 1.0
    assert 0.0 <= frame.continuity <= 1.0
    assert 0.0 <= frame.idle_ratio <= 1.0


def test_direct_interaction_is_not_counted_as_ambient_activity() -> None:
    privacy = PrivacyFilter()
    aggregator = ActivityAggregator(frame_window_ms=1000)
    aggregator.add(privacy.keyboard("a", 10, source=ActivitySource.DIRECT))

    frame = aggregator.frame(1000)

    assert frame.keyboard_activity == 0.0
    assert frame.idle_ratio == 1.0

